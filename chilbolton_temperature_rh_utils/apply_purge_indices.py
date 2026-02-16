#!/usr/bin/env python3
"""
Apply purge and recovery indices from a CSV file to netCDF files.
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


def apply_purge_indices_to_file(nc_file, purge_indices_row):
    """
    Apply purge and recovery flags to a netCDF file based on indices from CSV.
    
    Parameters:
        nc_file: Path to netCDF file
        purge_indices_row: Row from the CSV DataFrame with purge/recovery indices
    """
    flag_good = 1
    flag_bad = 2
    flag_purge = 3
    flag_recovery = 4
    
    with xr.open_dataset(nc_file, mode='r+') as ds:
        if 'qc_flag_air_temperature' not in ds or 'qc_flag_relative_humidity' not in ds:
            print(f"Warning: QC flags not found in {nc_file}, skipping")
            return
        
        # Get existing flags to preserve bad data flags (flag=2)
        qc_temp = ds['qc_flag_air_temperature'].values.copy()
        qc_rh = ds['qc_flag_relative_humidity'].values.copy()
        
        # Reset purge and recovery flags to good (1), but keep bad data (2)
        qc_temp[(qc_temp == flag_purge) | (qc_temp == flag_recovery)] = flag_good
        qc_rh[(qc_rh == flag_purge) | (qc_rh == flag_recovery)] = flag_good
        
        # Handle variable number of purge periods dynamically
        # Parse all columns as a list to handle days with more than 2 purge periods
        purge_num = 1
        while True:
            purge_start_col = f'purge{purge_num}_start_idx'
            purge_end_col = f'purge{purge_num}_end_idx'
            recovery_start_col = f'recovery{purge_num}_start_idx'
            recovery_end_col = f'recovery{purge_num}_end_idx'
            
            # Check if this purge period exists in the CSV columns
            has_purge = purge_start_col in purge_indices_row.index and purge_end_col in purge_indices_row.index
            has_recovery = recovery_start_col in purge_indices_row.index and recovery_end_col in purge_indices_row.index
            
            if not (has_purge or has_recovery):
                # No more purge periods defined
                break
            
            # Apply purge using indices
            if has_purge and pd.notna(purge_indices_row.get(purge_start_col)) and pd.notna(purge_indices_row.get(purge_end_col)):
                start_idx = int(purge_indices_row[purge_start_col])
                end_idx = int(purge_indices_row[purge_end_col])
                qc_temp[start_idx:end_idx+1] = flag_purge
                qc_rh[start_idx:end_idx+1] = flag_purge
            
            # Apply recovery using indices
            if has_recovery and pd.notna(purge_indices_row.get(recovery_start_col)) and pd.notna(purge_indices_row.get(recovery_end_col)):
                start_idx = int(purge_indices_row[recovery_start_col])
                end_idx = int(purge_indices_row[recovery_end_col])
                qc_rh[start_idx:end_idx+1] = flag_recovery
            
            purge_num += 1
        
        # Update the flags
        ds['qc_flag_air_temperature'].values[:] = qc_temp
        ds['qc_flag_relative_humidity'].values[:] = qc_rh
        
        # Update history and last_modified attributes
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        history_entry = f"{timestamp} - Applied purge/recovery indices from CSV file using apply-hmp155-purge-indices"
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
    """CLI entry point for apply-hmp155-purge-indices command."""
    parser = argparse.ArgumentParser(
        description="Apply purge and recovery indices from CSV to netCDF files."
    )
    parser.add_argument(
        "-c", "--csv_file",
        required=True,
        help="CSV file with purge indices (created by extract-hmp155-purge-indices)"
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
    if max_cols > 9:
        # We have more than 2 purge periods in some rows
        # Calculate number of purge periods: (max_cols - 1) / 4
        num_periods = (max_cols - 1) // 4
        col_names = ['date']
        for i in range(1, num_periods + 1):
            col_names.extend([
                f'purge{i}_start_idx',
                f'purge{i}_end_idx',
                f'recovery{i}_start_idx',
                f'recovery{i}_end_idx'
            ])
        df = pd.read_csv(args.csv_file, names=col_names, skiprows=1, parse_dates=['date'])
        print(f"Read {len(df)} rows from {args.csv_file} (detected up to {num_periods} purge periods per day)")
    else:
        # Standard case with 2 purge periods
        df = pd.read_csv(args.csv_file, parse_dates=['date'])
        print(f"Read {len(df)} rows from {args.csv_file}")
    
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
        
        # Apply purge indices
        try:
            apply_purge_indices_to_file(nc_file, row)
            print(f"Applied purge indices to {nc_file.name}")
            success_count += 1
        except Exception as e:
            print(f"Error processing {nc_file}: {e}")
            skip_count += 1
    
    print(f"\nComplete: {success_count} files updated, {skip_count} skipped")


if __name__ == "__main__":
    main()
