#!/usr/bin/env python

import xarray as xr
import numpy as np
import argparse
import pandas as pd
from netCDF4 import Dataset

# Define QC flag values
FLAG_GOOD = 1
FLAG_PURGE = 3
FLAG_RH_RECOVERY = 4

def set_time_units_to_seconds_since_epoch(nc_file):
    """
    Reopen the NetCDF file using netCDF4 and set the time units to 'seconds since 1970-01-01 00:00:00'.
    """
    with Dataset(nc_file, mode='r+') as ds:
        if 'time' in ds.variables:
            time_var = ds.variables['time']
            time_var.setncattr('units', 'seconds since 1970-01-01 00:00:00')
            print(f"Updated time units to 'seconds since 1970-01-01 00:00:00' in {nc_file}")

def get_previous_day_purge_times(prev_file, shift_seconds=0):
    """
    Extract purge times from the previous day's file and apply an optional time shift.
    """
    with xr.open_dataset(prev_file, mode="r") as ds:
        # Ensure the dataset is sorted by time
        ds = ds.sortby("time")

        # Get purge intervals from QC flags
        purge_mask = ds["qc_flag_air_temperature"] == FLAG_PURGE
        times = pd.to_datetime(ds["time"].values)

        intervals = []
        start = None
        for i, val in enumerate(purge_mask.values):
            if val and start is None:
                start = times[i]
            elif not val and start is not None:
                end = times[i - 1]
                intervals.append((start, end))
                start = None
        if start is not None:
            intervals.append((start, times[-1]))

        # Apply the time shift
        shifted_intervals = [(start + pd.Timedelta(seconds=shift_seconds), end + pd.Timedelta(seconds=shift_seconds)) for start, end in intervals]
        return shifted_intervals

def flag_based_on_time_of_day(ds, purge_intervals, recovery_duration=6 * 60):
    """
    Flag data based on the time of day for multiple purge and recovery periods.
    """
    # Convert time to pandas datetime for easier indexing
    time = pd.to_datetime(ds["time"].values)

    # Extract time of day (seconds since midnight) for each timestamp
    time_of_day = time.hour * 3600 + time.minute * 60 + time.second

    for start, end in purge_intervals:
        # Convert purge start and end times to seconds since midnight
        purge_start_seconds = start.hour * 3600 + start.minute * 60 + start.second
        purge_end_seconds = end.hour * 3600 + end.minute * 60 + end.second

        # Flag purge period
        purge_mask = (time_of_day >= purge_start_seconds) & (time_of_day < purge_end_seconds)
        ds["qc_flag_air_temperature"].values[purge_mask] = FLAG_PURGE
        ds["qc_flag_relative_humidity"].values[purge_mask] = FLAG_PURGE

        # Flag recovery period
        recovery_start_seconds = purge_end_seconds
        recovery_end_seconds = recovery_start_seconds + recovery_duration
        recovery_mask = (time_of_day >= recovery_start_seconds) & (time_of_day < recovery_end_seconds)
        ds["qc_flag_relative_humidity"].values[recovery_mask] = FLAG_RH_RECOVERY

def clear_purge_flags(ds):
    """Set all purge and recovery flags back to FLAG_GOOD."""
    if "qc_flag_air_temperature" in ds.variables:
        arr = ds["qc_flag_air_temperature"].values
        arr[(arr == FLAG_PURGE)] = FLAG_GOOD
        ds["qc_flag_air_temperature"].values[:] = arr
    if "qc_flag_relative_humidity" in ds.variables:
        arr = ds["qc_flag_relative_humidity"].values
        arr[(arr == FLAG_PURGE) | (arr == FLAG_RH_RECOVERY)] = FLAG_GOOD
        ds["qc_flag_relative_humidity"].values[:] = arr

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Manually flag purge periods in a NetCDF file based on time of day.")
    parser.add_argument("-f", "--file", required=True, help="Path to the NetCDF file")
    parser.add_argument("--prev-file", help="Path to the previous day's NetCDF file to read purge times")
    parser.add_argument("--shift-seconds", type=float, default=0.0, help="Shift purge times by this many seconds (default: 0.0)")
    parser.add_argument("-s", "--start", help="Start time of the purge period (format: HH:MM:SS)")
    parser.add_argument("-e", "--end", help="End time of the purge period (format: HH:MM:SS)")
    parser.add_argument("--clear-purge-flags", action="store_true", help="Clear existing purge and recovery flags before applying new ones")
    args = parser.parse_args()

    # Determine purge intervals
    if args.prev_file:
        # Use purge times from the previous day's file
        intervals = get_previous_day_purge_times(args.prev_file, shift_seconds=args.shift_seconds)
        if not intervals:
            print(f"No purge intervals found in {args.prev_file}")
            return
        # Convert intervals to time of day
        purge_intervals = [(start.time(), end.time()) for start, end in intervals]
    else:
        # Use manually specified start and end times
        if not args.start or not args.end:
            print("Error: You must provide both --start and --end times if --prev-file is not used.")
            return
        purge_start_time = pd.to_datetime(args.start, format="%H:%M:%S").time()
        purge_end_time = pd.to_datetime(args.end, format="%H:%M:%S").time()
        purge_intervals = [(purge_start_time, purge_end_time)]

    # Open the NetCDF file
    with xr.open_dataset(args.file, mode="r+") as ds:
        # Ensure the dataset is sorted by time
        ds = ds.sortby("time")

        # Initialize QC flags if they don't exist
        if "qc_flag_air_temperature" not in ds.variables:
            ds["qc_flag_air_temperature"] = xr.full_like(ds["air_temperature"], fill_value=FLAG_GOOD, dtype=np.int8)
            ds["qc_flag_air_temperature"].attrs = {
                "units": "1",
                "long_name": "Data Quality flag: Air Temperature",
                "standard_name": "quality_flag",
                "flag_values": np.array([0, 1, 2, 3], dtype=np.int8),
                "flag_meanings": "not_used good_data bad_data_measurement_suspect bad_data_purge_cycle_value_fixed_as_start_of_purge"
            }

        if "qc_flag_relative_humidity" not in ds.variables:
            ds["qc_flag_relative_humidity"] = xr.full_like(ds["relative_humidity"], fill_value=FLAG_GOOD, dtype=np.int8)
            ds["qc_flag_relative_humidity"].attrs = {
                "units": "1",
                "long_name": "Data Quality flag: Relative Humidity",
                "standard_name": "quality_flag",
                "flag_values": np.array([0, 1, 2, 3, 4], dtype=np.int8),
                "flag_meanings": "not_used good_data bad_data_measurement_suspect bad_data_purge_cycle_value_fixed_as_start_of_purge recovery_in_rh_after_purge"
            }

        # Clear existing purge/recovery flags if requested
        if args.clear_purge_flags:
            clear_purge_flags(ds)

        # Flag data based on time of day
        flag_based_on_time_of_day(ds, purge_intervals)

        # Save changes to the file
        ds.to_netcdf(args.file, mode="a")  # Append mode ensures updates are written
        print(f"QC flags successfully added to {args.file}.")

    # Update time units to 'seconds since 1970-01-01 00:00:00'
    set_time_units_to_seconds_since_epoch(args.file)

if __name__ == "__main__":
    main()