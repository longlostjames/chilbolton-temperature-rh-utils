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
    """
    with Dataset(nc_file, mode='r+') as ds:
        if 'time' in ds.variables:
            time_var = ds.variables['time']
            time_var.setncattr('units', 'seconds since 1970-01-01 00:00:00')


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
        
        # Apply purge 1 using indices
        if pd.notna(purge_indices_row.get('purge1_start_idx')) and pd.notna(purge_indices_row.get('purge1_end_idx')):
            start_idx = int(purge_indices_row['purge1_start_idx'])
            end_idx = int(purge_indices_row['purge1_end_idx'])
            qc_temp[start_idx:end_idx+1] = flag_purge
            qc_rh[start_idx:end_idx+1] = flag_purge
        
        # Apply recovery 1 using indices
        if pd.notna(purge_indices_row.get('recovery1_start_idx')) and pd.notna(purge_indices_row.get('recovery1_end_idx')):
            start_idx = int(purge_indices_row['recovery1_start_idx'])
            end_idx = int(purge_indices_row['recovery1_end_idx'])
            qc_rh[start_idx:end_idx+1] = flag_recovery
        
        # Apply purge 2 using indices
        if pd.notna(purge_indices_row.get('purge2_start_idx')) and pd.notna(purge_indices_row.get('purge2_end_idx')):
            start_idx = int(purge_indices_row['purge2_start_idx'])
            end_idx = int(purge_indices_row['purge2_end_idx'])
            qc_temp[start_idx:end_idx+1] = flag_purge
            qc_rh[start_idx:end_idx+1] = flag_purge
        
        # Apply recovery 2 using indices
        if pd.notna(purge_indices_row.get('recovery2_start_idx')) and pd.notna(purge_indices_row.get('recovery2_end_idx')):
            start_idx = int(purge_indices_row['recovery2_start_idx'])
            end_idx = int(purge_indices_row['recovery2_end_idx'])
            qc_rh[start_idx:end_idx+1] = flag_recovery
        
        # Update the flags
        ds['qc_flag_air_temperature'].values[:] = qc_temp
        ds['qc_flag_relative_humidity'].values[:] = qc_rh
        
        # Update history and last_modified attributes
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
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
    
    # Read CSV file
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
