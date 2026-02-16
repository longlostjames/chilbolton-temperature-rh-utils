#!/usr/bin/env python3
"""
Apply bad data indices from a CSV file to netCDF files.
"""

import xarray as xr
import pandas as pd
import numpy as np
import argparse
import os
from pathlib import Path
import shutil
from netCDF4 import Dataset
from datetime import datetime


def set_time_units_to_seconds_since_epoch(nc_file):
    """
    Reopen the NetCDF file using netCDF4 and set the time units to 'seconds since 1970-01-01 00:00:00'.
    Also set required CF convention attributes.
    """
    with Dataset(nc_file, mode='r+') as ds:
        if 'time' in ds.variables:
            time_var = ds.variables['time']
            time_var.setncattr('units', 'seconds since 1970-01-01 00:00:00')
            time_var.setncattr('standard_name', 'time')
            time_var.setncattr('long_name', 'Time (seconds since 1970-01-01 00:00:00)')
            time_var.setncattr('axis', 'T')
            # Set valid_min and valid_max from actual data
            if len(time_var[:]) > 0:
                time_var.setncattr('valid_min', float(time_var[:].min()))
                time_var.setncattr('valid_max', float(time_var[:].max()))


def apply_bad_data_indices_to_file(nc_file, bad_data_indices_row):
    """
    Apply bad data flags to a netCDF file based on indices from CSV.
    
    Parameters:
        nc_file: Path to netCDF file
        bad_data_indices_row: Row from the CSV DataFrame with bad data indices
    """
    flag_good = 1
    flag_bad = 2
    
    with xr.open_dataset(nc_file, mode='r+') as ds:
        if 'qc_flag_air_temperature' not in ds or 'qc_flag_relative_humidity' not in ds:
            print(f"Warning: QC flags not found in {nc_file}, skipping")
            return
        
        # Get existing flags
        qc_temp = ds['qc_flag_air_temperature'].values.copy()
        qc_rh = ds['qc_flag_relative_humidity'].values.copy()
        
        # Reset all bad data flags to good (1), preserving purge/recovery flags
        qc_temp[qc_temp == flag_bad] = flag_good
        qc_rh[qc_rh == flag_bad] = flag_good
        
        # First, handle 'both_bad' columns that apply to both temp and RH
        both_bad_num = 1
        while True:
            both_bad_start_col = f'both_bad{both_bad_num}_start_idx'
            both_bad_end_col = f'both_bad{both_bad_num}_end_idx'
            
            # Check if this bad data period exists in the CSV columns
            has_both_bad = both_bad_start_col in bad_data_indices_row.index and both_bad_end_col in bad_data_indices_row.index
            
            if not has_both_bad:
                # No more 'both' bad data periods defined
                break
            
            # Apply bad data flag to both temp and RH using indices
            if pd.notna(bad_data_indices_row.get(both_bad_start_col)) and pd.notna(bad_data_indices_row.get(both_bad_end_col)):
                start_idx = int(bad_data_indices_row[both_bad_start_col])
                end_idx = int(bad_data_indices_row[both_bad_end_col])
                qc_temp[start_idx:end_idx+1] = flag_bad
                qc_rh[start_idx:end_idx+1] = flag_bad
            
            both_bad_num += 1
        
        # Handle variable number of temperature bad data periods dynamically
        temp_bad_num = 1
        while True:
            temp_bad_start_col = f'temp_bad{temp_bad_num}_start_idx'
            temp_bad_end_col = f'temp_bad{temp_bad_num}_end_idx'
            
            # Check if this bad data period exists in the CSV columns
            has_temp_bad = temp_bad_start_col in bad_data_indices_row.index and temp_bad_end_col in bad_data_indices_row.index
            
            if not has_temp_bad:
                # No more temperature bad data periods defined
                break
            
            # Apply bad data flag to temperature using indices
            if pd.notna(bad_data_indices_row.get(temp_bad_start_col)) and pd.notna(bad_data_indices_row.get(temp_bad_end_col)):
                start_idx = int(bad_data_indices_row[temp_bad_start_col])
                end_idx = int(bad_data_indices_row[temp_bad_end_col])
                qc_temp[start_idx:end_idx+1] = flag_bad
            
            temp_bad_num += 1
        
        # Handle variable number of RH bad data periods dynamically
        rh_bad_num = 1
        while True:
            rh_bad_start_col = f'rh_bad{rh_bad_num}_start_idx'
            rh_bad_end_col = f'rh_bad{rh_bad_num}_end_idx'
            
            # Check if this bad data period exists in the CSV columns
            has_rh_bad = rh_bad_start_col in bad_data_indices_row.index and rh_bad_end_col in bad_data_indices_row.index
            
            if not has_rh_bad:
                # No more RH bad data periods defined
                break
            
            # Apply bad data flag to RH using indices
            if pd.notna(bad_data_indices_row.get(rh_bad_start_col)) and pd.notna(bad_data_indices_row.get(rh_bad_end_col)):
                start_idx = int(bad_data_indices_row[rh_bad_start_col])
                end_idx = int(bad_data_indices_row[rh_bad_end_col])
                qc_rh[start_idx:end_idx+1] = flag_bad
            
            rh_bad_num += 1
        
        # Update the flags
        ds['qc_flag_air_temperature'].values[:] = qc_temp
        ds['qc_flag_relative_humidity'].values[:] = qc_rh
        
        # Update history and last_modified attributes
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        history_entry = f"{timestamp} - Applied bad data indices from CSV file using apply-hmp155-bad-data-indices"
        if 'history' in ds.attrs:
            ds.attrs['history'] = f"{history_entry}\n{ds.attrs['history']}"
        else:
            ds.attrs['history'] = history_entry
        
        ds.attrs['last_modified'] = timestamp
        
        # Save changes using netCDF4 for in-place modification
        temp_filename = str(nc_file) + '.tmp'
        ds.to_netcdf(temp_filename)
    
    # Move temp file to replace original
    shutil.move(temp_filename, nc_file)
    
    # Set time units
    set_time_units_to_seconds_since_epoch(nc_file)


def find_nc_file_for_date(input_dir, date, year=None):
    """Find the netCDF file corresponding to a given date."""
    date_str = date.strftime('%Y%m%d')
    
    # Try different patterns
    if year:
        search_dir = Path(input_dir) / str(year)
    else:
        search_dir = Path(input_dir)
    
    # Look for files with date string in name
    candidates = list(search_dir.glob(f"*{date_str}*.nc"))
    
    if candidates:
        return candidates[0]
    
    return None


def main():
    """CLI entry point for apply-hmp155-bad-data-indices command."""
    parser = argparse.ArgumentParser(
        description="Apply bad data indices from CSV to netCDF files."
    )
    parser.add_argument(
        "-c", "--csv_file",
        required=True,
        help="CSV file with bad data indices (created by extract-hmp155-bad-data-indices)"
    )
    parser.add_argument(
        "-i", "--input_dir",
        required=True,
        help="Directory containing netCDF files (or parent directory with year subdirectories)"
    )
    parser.add_argument(
        "-y", "--year",
        type=int,
        default=None,
        help="Specific year to process (optional, will look in input_dir/YYYY/)"
    )
    
    args = parser.parse_args()
    
    # Read CSV file and handle variable number of columns per row
    # First, read raw lines to find maximum number of columns
    max_cols = 0
    with open(args.csv_file, 'r') as f:
        for line in f:
            num_cols = len(line.strip().split(','))
            if num_cols > max_cols:
                max_cols = num_cols
    
    # Generate column names dynamically based on maximum columns found
    # Calculate max temp_bad and rh_bad periods
    # Columns are: date, temp_bad1_start, temp_bad1_end, ..., rh_bad1_start, rh_bad1_end, ...
    # We need to parse the header to understand the structure
    df = pd.read_csv(args.csv_file, parse_dates=['date'])
    print(f"Read {len(df)} rows from {args.csv_file}")
    
    # Count the number of different bad data period types
    temp_bad_cols = [col for col in df.columns if col.startswith('temp_bad')]
    rh_bad_cols = [col for col in df.columns if col.startswith('rh_bad')]
    
    if temp_bad_cols or rh_bad_cols:
        print(f"Found {len(temp_bad_cols)//2} temperature bad data period types and {len(rh_bad_cols)//2} RH bad data period types")
    
    # Process each row
    success_count = 0
    skip_count = 0
    
    for idx, row in df.iterrows():
        date = row['date']
        
        # Find corresponding netCDF file
        nc_file = find_nc_file_for_date(args.input_dir, date, args.year)
        
        if nc_file is None:
            print(f"Warning: No netCDF file found for {date.strftime('%Y-%m-%d')}")
            skip_count += 1
            continue
        
        # Apply bad data indices
        try:
            apply_bad_data_indices_to_file(nc_file, row)
            print(f"Applied bad data indices to {nc_file.name}")
            success_count += 1
        except Exception as e:
            print(f"Error processing {nc_file}: {e}")
            skip_count += 1
    
    print(f"\nComplete: {success_count} files updated, {skip_count} skipped")


if __name__ == "__main__":
    main()
