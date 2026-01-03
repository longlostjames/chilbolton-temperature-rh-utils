#!/usr/bin/env python

import xarray as xr
import numpy as np
import argparse
from netCDF4 import Dataset
import pandas as pd
from datetime import datetime


def detect_flat(data, window, threshold):
    """
    Detect flat regions without smoothing the data.

    Parameters:
        data (xarray.DataArray): The data to analyze.
        window (int): The rolling window size (in samples) for detecting flat regions.
        threshold (float): The standard deviation threshold for detecting flat regions.

    Returns:
        xarray.DataArray: A boolean mask indicating flat regions.
    """
    # Apply a rolling standard deviation directly to the raw data
    rolling_std = data.rolling(time=window, center=True).std()
    flat_points = (rolling_std < threshold)

    return flat_points


def detect_rh_dips(rh_data, time_data, drop_thresh=3.0, recovery_time=360, flat_window=5, flat_threshold=0.1):
    """
    Detect sharp RH dips followed by recovery, only if there is a preceding flat region.

    Parameters:
        rh_data (xarray.DataArray): Relative humidity data.
        time_data (xarray.DataArray): Time data corresponding to RH.
        drop_thresh (float): Minimum RH drop to identify a dip.
        recovery_time (int): Maximum time (in seconds) for recovery after a dip.
        flat_window (int): Rolling window size (in samples) for detecting flat regions.
        flat_threshold (float): Standard deviation threshold for detecting flat regions.

    Returns:
        list of tuples: List of (start, end) indices for detected RH dips.
    """
    rh = rh_data.values
    time = pd.to_datetime(time_data.values)
    dips = []

    # Detect flat regions with a less strict criterion
    flat_mask = detect_flat(rh_data, flat_window, flat_threshold).values

    for i in range(3, len(rh) - 10):
        # Check if there is a preceding flat region
        if not np.any(flat_mask[max(0, i - flat_window):i]):
            continue

        # Detect RH dip
        max_before = max(rh[i - 3:i])
        delta_down = max_before - rh[i]
        if delta_down >= drop_thresh:
            for j in range(i + 1, min(i + 20, len(rh))):
                delta_up = rh[j] - rh[i]
                t_elapsed = (time[j] - time[i]).total_seconds()
                if delta_up >= delta_down and t_elapsed <= recovery_time:
                    dips.append((i, j))  # Dip starts at i, not earlier
                    break

    return dips


def check_purge_consistency(previous_purge_times, current_purge_times):
    """Check if the time of day for purge times is consistent across days."""
    # Extract the time of day (in seconds since midnight) for both sets of purge times
    previous_times_of_day = (previous_purge_times.astype('datetime64[s]') - previous_purge_times.astype('datetime64[D]')).astype(int)
    current_times_of_day = (current_purge_times.astype('datetime64[s]') - current_purge_times.astype('datetime64[D]')).astype(int)

    # Check if the times of day are consistent within a threshold (e.g., 60 minutes)
    threshold_seconds = 60 * 60  # 60 minutes in seconds
    if len(previous_times_of_day) != len(current_times_of_day):
        return False
    for prev, curr in zip(previous_times_of_day, current_times_of_day):
        if abs(prev - curr) > threshold_seconds:
            return False
    return True

def exclude_high_rh(rh_data, purge_mask, max_rh=99.5):
    """Exclude flagged points where RH is at or near saturation."""
    return purge_mask & (rh_data < max_rh)

def filter_short_events(mask, min_samples):
    """
    Expand flagged regions to ensure they last at least min_samples.

    Parameters:
        mask (xarray.DataArray): Boolean mask indicating flagged regions.
        min_samples (int): Minimum number of samples for a flagged region.

    Returns:
        xarray.DataArray: A boolean mask with expanded regions.
    """
    mask_np = mask.values
    filtered = np.zeros_like(mask_np, dtype=bool)

    start = None
    for i, val in enumerate(mask_np):
        if val:
            if start is None:
                start = i
        elif start is not None:
            if i - start >= min_samples:
                # Expand the region to ensure it lasts at least min_samples
                filtered[max(0, start - min_samples):min(len(mask_np), i + min_samples)] = True
            start = None
    if start is not None and len(mask_np) - start >= min_samples:
        filtered[max(0, start - min_samples):] = True

    return xr.DataArray(filtered, coords=mask.coords, dims=mask.dims)

def set_time_units_to_seconds_since_epoch(nc_file):
    """
    Reopen the NetCDF file using netCDF4 and set the time units to 'seconds since 1970-01-01 00:00:00'.
    """
    with Dataset(nc_file, mode='r+') as ds:
        if 'time' in ds.variables:
            time_var = ds.variables['time']
            time_var.setncattr('units', 'seconds since 1970-01-01 00:00:00')
            print(f"Updated time units to 'seconds since 1970-01-01 00:00:00' in {nc_file}")

def read_bad_intervals(corr_file):
    bad_intervals = []
    with open(corr_file, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4 and parts[-1] == "BADDATA":
                date = parts[0]
                start = parts[1]
                end = parts[2]
                start_dt = datetime.strptime(date + start, "%Y%m%d%H%M%S")
                end_dt = datetime.strptime(date + end, "%Y%m%d%H%M%S")
                bad_intervals.append((start_dt, end_dt))
    return bad_intervals

def flag_bad_data_xr(ds, bad_intervals, flag_var):
    # Convert NetCDF time to pandas datetime
    time = pd.to_datetime(ds['time'].values)
    qc = ds[flag_var].values.copy()
    for start, end in bad_intervals:
        mask = (time >= start) & (time <= end)
        qc[mask] = 2
    ds[flag_var].values[:] = qc

# Open the dataset in read/write mode

def main():
    """Main entry point for the command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Detect and flag purge cycles and RH dips in HMP155 data.")
    parser.add_argument('filename', type=str, help='Path to the NetCDF file')
    parser.add_argument('--previous-file', type=str, default=None,
                        help='Path to the previous day NetCDF file for RH dip flagging context')
    parser.add_argument('--corr-file-temperature', type=str, default=None,
                        help='Path to the correction file for bad air temperature intervals')
    parser.add_argument('--corr-file-rh', type=str, default=None,
                        help='Path to the correction file for bad relative humidity intervals')
    parser.add_argument('--window-minutes', type=int, default=8,
                        help='Rolling window size in minutes (default: 8)')
    parser.add_argument('--std-threshold-temp', type=float, default=0.03,
                        help='Standard deviation threshold for temperature (default: 0.03)')
    parser.add_argument('--std-threshold-rh', type=float, default=0.02,
                        help='Standard deviation threshold for RH (default: 0.02)')
    parser.add_argument('--exclude-times', action='store_true',
                        help='Exclude purges at certain times of day (midnight 23:00-02:00, evening 17:00-20:00)')

    args = parser.parse_args()
    
    filename = args.filename
    previous_filename = args.previous_file
    corr_file_temperature = args.corr_file_temperature
    corr_file_rh = args.corr_file_rh
    window_minutes = args.window_minutes
    std_threshold_temp = args.std_threshold_temp
    std_threshold_rh = args.std_threshold_rh
    exclude_times = args.exclude_times

    # Define QC flags
    flag_good = 1
    flag_bad = 2
    flag_purge = 3
    flag_rh_dip = 4

    with xr.open_dataset(filename, mode='r+') as ds:
        # Check if required variables exist
        if 'time' not in ds.dims and 'time' not in ds.coords:
            print(f"Error: No 'time' variable found in {filename}")
            print(f"Available dimensions: {list(ds.dims)}")
            print(f"Available coordinates: {list(ds.coords)}")
            print(f"Available variables: {list(ds.data_vars)}")
            return
        
        # Sort by time to ensure proper processing
        ds = ds.sortby('time')
    
        # Estimate sampling interval and rolling window size
        time_diff = np.median(np.diff(ds['time'].values).astype('timedelta64[s]').astype(int))
        window_size = int((window_minutes * 60) / time_diff)
        min_duration_samples = int((8 * 60) / time_diff)  # 8 minutes in samples
    
        # Check if QC flags already exist (from low temperature flagging)
        # If they do, mask out bad data (flag=2) before purge detection
        existing_bad_data_mask = None
        if 'qc_flag_air_temperature' in ds:
            existing_bad_data_mask = (ds['qc_flag_air_temperature'] == 2).values
            print(f"Found {np.sum(existing_bad_data_mask)} points already flagged as bad data (flag=2)")
    
        # Detect low-variance periods in each variable
        purge_temp = detect_flat(ds['air_temperature'], window_size, std_threshold_temp)
        purge_rh = detect_flat(ds['relative_humidity'], window_size, std_threshold_rh)
        purge_rh = exclude_high_rh(ds['relative_humidity'], purge_rh, max_rh=99.5)
        
        # Exclude regions already flagged as bad data (flag=2) from purge detection
        if existing_bad_data_mask is not None:
            purge_temp = purge_temp & ~xr.DataArray(existing_bad_data_mask, dims=purge_temp.dims, coords=purge_temp.coords)
            purge_rh = purge_rh & ~xr.DataArray(existing_bad_data_mask, dims=purge_rh.dims, coords=purge_rh.coords)
    
        # Use RH flatness as primary indicator (RH is the sensor being purged)
        # Temperature may also be flat during purge but RH is the key indicator
        combined_purge = purge_rh
    
        # Identify distinct purge periods
        purge_periods = []
        purge_mask = combined_purge.values
        start = None
        for i, val in enumerate(purge_mask):
            if val and start is None:
                start = i
            elif not val and start is not None:
                # Expand the purge region to ensure it lasts at least 8 minutes
                expanded_start = max(0, start - min_duration_samples // 2)
                expanded_end = min(len(purge_mask), i + min_duration_samples // 2)
                purge_periods.append((expanded_start, expanded_end))
                start = None
        if start is not None:
            expanded_start = max(0, start - min_duration_samples // 2)
            expanded_end = min(len(purge_mask), len(purge_mask))
            purge_periods.append((expanded_start, expanded_end))
    
        # Calculate the standard deviation of RH for each purge period
        purge_periods_with_std = []
        for start, end in purge_periods:
            rh_std = ds['relative_humidity'][start:end].std().item()
            temp_std = ds['air_temperature'][start:end].std().item()
            # Get the time of day for this period
            period_time = pd.to_datetime(ds['time'].values[start])
            purge_periods_with_std.append((start, end, rh_std, temp_std, period_time))
    
        # Filter out periods around midnight (23:00-02:00) and evening (17:00-20:00) as these are likely not purge cycles
        # This filtering is optional and controlled by exclude_times parameter
        filtered_periods = []
        for start, end, rh_std, temp_std, period_time in purge_periods_with_std:
            hour = period_time.hour
            # Optionally exclude periods around midnight (23:00-02:00) and evening (17:00-20:00)
            if exclude_times and ((hour >= 23 or hour <= 2) or (17 <= hour < 20)):
                continue  # Skip this period
            # Score primarily by RH flatness (it's the sensor being purged)
            combined_score = rh_std * 100 + temp_std  # Weight RH much more heavily
            filtered_periods.append((start, end, rh_std, temp_std, period_time, combined_score))
        
        # If no valid periods after filtering, fall back to all periods
        if not filtered_periods:
            filtered_periods = [(start, end, rh_std, temp_std, period_time, rh_std + temp_std * 10) 
                               for start, end, rh_std, temp_std, period_time in purge_periods_with_std]
        
        # Sort by combined score (flattest in both variables)
        filtered_periods.sort(key=lambda x: x[5])  # Sort by combined score
    
        # For dates from 2018-03-13 onwards, only keep the single flattest purge period
        dataset_date = pd.to_datetime(ds['time'].values[0]).date()
        if dataset_date >= pd.to_datetime("2018-03-13").date():
            purge_periods = [(start, end) for start, end, _, _, _, _ in filtered_periods[:1]]  # Keep only the flattest period
        else:
            # For earlier dates, keep the two flattest purge periods
            purge_periods = [(start, end) for start, end, _, _, _, _ in filtered_periods[:2]]
    
        # If only one purge period is found and the date is before 2018-03-13, flag an equivalent period 12 hours earlier or later
        if len(purge_periods) == 1 and dataset_date < pd.to_datetime("2018-03-13").date():
            start, end = purge_periods[0]
            duration = end - start  # Duration of the purge period in samples
    
            # Determine the start time of the initial purge period
            purge_start_time = pd.to_datetime(ds['time'].values[start])
            midday = purge_start_time.replace(hour=12, minute=0, second=0)
    
            if purge_start_time < midday:
                # Flag a period 12 hours later
                later_start = start + int((12 * 60 * 60) / time_diff)  # 12 hours after the start
                later_end = later_start + duration
                if later_end <= len(purge_mask):  # Ensure the indices are within bounds
                    purge_periods.append((later_start, later_end))
            else:
                # Flag a period 12 hours earlier
                earlier_start = start - int((12 * 60 * 60) / time_diff)  # 12 hours before the start
                earlier_end = earlier_start + duration
                if earlier_start >= 0:  # Ensure the indices are within bounds
                    purge_periods.append((earlier_start, earlier_end))
    
        # If no purge periods were detected and we have a previous file, use previous day's timing
        if len(purge_periods) == 0 and previous_filename:
            try:
                with xr.open_dataset(previous_filename, mode='r') as prev_ds:
                    prev_ds = prev_ds.sortby('time')
                    prev_time = pd.to_datetime(prev_ds['time'].values)
                    
                    # Find purge periods in previous day based on QC flags
                    if 'qc_flag_relative_humidity' in prev_ds:
                        prev_purge_mask = (prev_ds['qc_flag_relative_humidity'] == 3).values
                        prev_start = None
                        prev_purge_times = []
                        
                        for i, val in enumerate(prev_purge_mask):
                            if val and prev_start is None:
                                prev_start = prev_time[i]
                            elif not val and prev_start is not None:
                                prev_end = prev_time[i - 1]
                                prev_purge_times.append((prev_start, prev_end))
                                prev_start = None
                        if prev_start is not None:
                            prev_purge_times.append((prev_start, prev_time[-1]))
                        
                        # Apply same time-of-day to current day
                        current_time = pd.to_datetime(ds['time'].values)
                        current_date = current_time[0].date()
                        
                        for prev_start, prev_end in prev_purge_times:
                            # Get time of day from previous purge
                            start_time_of_day = prev_start.time()
                            end_time_of_day = prev_end.time()
                            
                            # Apply to current day
                            current_start = pd.Timestamp.combine(current_date, start_time_of_day)
                            current_end = pd.Timestamp.combine(current_date, end_time_of_day)
                            
                            # Find indices in current day's data
                            start_idx = np.argmin(np.abs((current_time - current_start).total_seconds()))
                            end_idx = np.argmin(np.abs((current_time - current_end).total_seconds()))
                            
                            if start_idx < len(current_time) and end_idx < len(current_time):
                                purge_periods.append((start_idx, end_idx))
                                print(f"Applied previous day's purge timing: {current_start.strftime('%H:%M')} - {current_end.strftime('%H:%M')}")
            except Exception as e:
                print(f"Warning: Could not use previous day's purge timing: {e}")
    
        # Initialize QC flags as 1 (good_data), but preserve existing flag=2 (bad data) if present
        if existing_bad_data_mask is not None:
            qc_temp = xr.where(xr.DataArray(existing_bad_data_mask, dims=ds['air_temperature'].dims, coords=ds['air_temperature'].coords),
                              2, flag_good).astype(np.int8)
            qc_rh = xr.where(xr.DataArray(existing_bad_data_mask, dims=ds['relative_humidity'].dims, coords=ds['relative_humidity'].coords),
                            2, flag_good).astype(np.int8)
        else:
            qc_temp = xr.full_like(ds['air_temperature'], fill_value=flag_good, dtype=np.int8)
            qc_rh = xr.full_like(ds['relative_humidity'], fill_value=flag_good, dtype=np.int8)
    
        # Apply purge flag (3) for each purge period
        for start, end in purge_periods:
            # Ensure indices are within valid range
            if start >= len(qc_temp) or end > len(qc_temp):
                print(f"Warning: Purge period [{start}:{end}] extends beyond data range ({len(qc_temp)}). Skipping.")
                continue
                
            qc_temp[start:end] = flag_purge
            qc_rh[start:end] = flag_purge
    
            # Flag 6 minutes after each purge period as 4 (only if recovery period is within data range)
            # But do NOT overwrite bad data (flag=2)
            recovery_start = end
            recovery_end = min(len(qc_rh), end + int((6 * 60) / time_diff))  # 6 minutes in samples
            
            # Only flag recovery if it's within the actual data range and not already bad data
            if recovery_start < len(qc_rh) and recovery_end > recovery_start:
                for i in range(recovery_start, recovery_end):
                    if qc_rh[i] != 2:  # Don't overwrite bad data flags
                        qc_rh[i] = flag_rh_dip  # Use flag 4 for RH recovery
    
        # Detect RH dips with a preceding flat region
        # Exclude dips that occur when RH is at or near saturation
        # Use a tightened flat_threshold to reduce spurious detections
        dip_intervals = detect_rh_dips(
            ds['relative_humidity'], 
            ds['time'], 
            drop_thresh=3.0, 
            recovery_time=360, 
            flat_window=5, 
            flat_threshold=0.2  # Tightened to reduce false positives
        )
        
        # Filter out dips where the RH before/during the dip is at or near saturation
        # Check both the start point and the preceding 10 samples
        filtered_dip_intervals = []
        for start, end in dip_intervals:
            lookback = max(0, start - 10)
            max_rh_before = ds['relative_humidity'][lookback:start+1].max().values
            if max_rh_before < 97.0:  # Only flag dips well below saturation
                filtered_dip_intervals.append((start, end))
        dip_intervals = filtered_dip_intervals
    
       # --- Flag RH dips only during expected purge windows (from previous day) ---
        buffer_samples = int((8 * 60) / time_diff)  # 8 minutes in samples
        dip_time = pd.to_datetime(ds['time'].values)
    
        expected_purge_windows = []
        if previous_filename:
            with xr.open_dataset(previous_filename, mode='r') as prev_ds:
                prev_ds = prev_ds.sortby('time')
                purge_mask_prev = (detect_flat(prev_ds['air_temperature'], window_size, std_threshold_temp) &
                                   exclude_high_rh(prev_ds['relative_humidity'],
                                                   detect_flat(prev_ds['relative_humidity'], window_size, std_threshold_rh),
                                                   max_rh=99.9))
                times = pd.to_datetime(prev_ds['time'].values)
                mask_vals = purge_mask_prev.values
                start = None
                for i, val in enumerate(mask_vals):
                    if val and start is None:
                        start = times[i]
                    elif not val and start is not None:
                        end = times[i - 1]
                        t0 = pd.Timestamp(start).replace(hour=0, minute=0, second=0)
                        expected_purge_windows.append((start - t0, end - t0))
                        start = None
                if start is not None:
                    end = times[-1]
                    t0 = pd.Timestamp(start).replace(hour=0, minute=0, second=0)
                    expected_purge_windows.append((start - t0, end - t0))
    
        # Option to enable or disable purge flagging based on 8 minutes preceding an RH dip
        enable_purge_flagging_before_rh_dip = False  # Set to True to enable this behavior
    
        # Apply RH dip flags ONLY if there's a purge detected nearby
        # Recovery should only be flagged after an actual purge
        for start, end in dip_intervals:
            dip_start_time = dip_time[start]
            seconds_since_midnight = (dip_start_time - dip_start_time.replace(hour=0, minute=0, second=0)).total_seconds()
    
            # Check if there's a purge period within 20 minutes before this dip
            has_nearby_purge = False
            for purge_start, purge_end in purge_periods:
                if purge_end <= start and (start - purge_end) <= int((20 * 60) / time_diff):
                    has_nearby_purge = True
                    break
            
            # Only flag recovery if there's a detected purge nearby OR if within expected windows
            allow = has_nearby_purge
            if not allow and expected_purge_windows:
                for expected_start, expected_end in expected_purge_windows:
                    if expected_start.total_seconds() - 900 <= seconds_since_midnight <= expected_end.total_seconds() + 900:
                        allow = True
                        break
    
            if allow:
                if enable_purge_flagging_before_rh_dip:
                    # Optionally flag the 8 minutes preceding the RH dip as purge
                    # But do NOT overwrite bad data (flag=2)
                    purge_start = max(0, start - buffer_samples)
                    purge_end = max(purge_start, start)
                    for i in range(purge_start, purge_end):
                        if qc_temp[i] != 2:
                            qc_temp[i] = flag_purge
                        if qc_rh[i] != 2:
                            qc_rh[i] = flag_purge
    
                # Flag the RH dip itself (recovery), but do NOT overwrite bad data (flag=2)
                for i in range(start + 1, end):
                    if qc_rh[i] != 2:  # Skip dip initiation point and preserve bad data
                        qc_rh[i] = flag_rh_dip
    
        # Assign QC variables
        ds['qc_flag_air_temperature'] = qc_temp
        ds['qc_flag_air_temperature'].attrs = {
            'units': '1',
            'long_name': 'Data Quality flag: Air Temperature',
            'standard_name': 'quality_flag',
            'flag_values': np.array([0, 1, 2, 3], dtype=np.int8),
            'flag_meanings': 'not_used good_data bad_data_measurement_suspect bad_data_purge_cycle_value_fixed_as_start_of_purge'
        }
    
        ds['qc_flag_relative_humidity'] = qc_rh
        ds['qc_flag_relative_humidity'].attrs = {
            'units': '1',
            'long_name': 'Data Quality flag: Relative Humidity',
            'standard_name': 'quality_flag',
            'flag_values': np.array([0, 1, 2, 3, 4], dtype=np.int8),
            'flag_meanings': 'not_used good_data bad_data_measurement_suspect bad_data_purge_cycle_value_fixed_as_start_of_purge recovery_in_rh_after_purge'
        }
    
        # --- Flag bad data intervals from correction files ---
        if corr_file_temperature:
            bad_intervals_temp = read_bad_intervals(corr_file_temperature)
            print(f"Flagging bad data intervals for air temperature from {corr_file_temperature}")
            flag_bad_data_xr(ds, bad_intervals_temp, "qc_flag_air_temperature")
    
        if corr_file_rh:
            bad_intervals_rh = read_bad_intervals(corr_file_rh)
            print(f"Flagging bad data intervals for relative humidity from {corr_file_rh}")
            flag_bad_data_xr(ds, bad_intervals_rh, "qc_flag_relative_humidity")
    
        # Save changes to the file
        ds.to_netcdf(filename, mode='a')  # Append mode ensures updates are written
        print(f"QC flags successfully added to {filename}.")
    
    # Reopen the file with netCDF4 and set the time units
    set_time_units_to_seconds_since_epoch(filename)
if __name__ == "__main__":
    main()
