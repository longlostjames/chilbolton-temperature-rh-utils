#!/usr/bin/env python3
"""
Extract purge and recovery indices from netCDF files and save to CSV.
"""

import xarray as xr
import pandas as pd
import argparse
import os
from pathlib import Path


def get_purge_intervals(qc_flag, flag_value=3):
    """Return list of (start_idx, end_idx) tuples where the specified QC flag value occurs."""
    purge_mask = (qc_flag == flag_value).values
    intervals = []

    start_idx = None
    for i, val in enumerate(purge_mask):
        if val and start_idx is None:
            start_idx = i
        elif not val and start_idx is not None:
            end_idx = i - 1
            intervals.append((start_idx, end_idx))
            start_idx = None
    if start_idx is not None:
        intervals.append((start_idx, len(purge_mask) - 1))
    return intervals


def extract_purge_indices_from_file(nc_file):
    """Extract purge and recovery indices from a single netCDF file."""
    try:
        ds = xr.open_dataset(nc_file)
        
        # Get date from filename
        filename = os.path.basename(nc_file)
        try:
            date_str = [s for s in filename.split('_') if s.isdigit() and len(s) == 8][0]
            date = pd.to_datetime(date_str, format="%Y%m%d")
        except (IndexError, ValueError):
            date = pd.to_datetime(ds['time'].values[0]).normalize()
        
        # Get purge intervals (flag=3)
        if 'qc_flag_relative_humidity' in ds:
            purge_intervals = get_purge_intervals(ds['qc_flag_relative_humidity'], flag_value=3)
            recovery_intervals = get_purge_intervals(ds['qc_flag_relative_humidity'], flag_value=4)
        else:
            purge_intervals = []
            recovery_intervals = []
        
        ds.close()
        
        # Build result dictionary
        result = {'date': date}
        
        # Add purge 1
        if len(purge_intervals) >= 1:
            result['purge1_start_idx'] = purge_intervals[0][0]
            result['purge1_end_idx'] = purge_intervals[0][1]
        else:
            result['purge1_start_idx'] = pd.NA
            result['purge1_end_idx'] = pd.NA
        
        # Add recovery 1
        if len(recovery_intervals) >= 1:
            result['recovery1_start_idx'] = recovery_intervals[0][0]
            result['recovery1_end_idx'] = recovery_intervals[0][1]
        else:
            result['recovery1_start_idx'] = pd.NA
            result['recovery1_end_idx'] = pd.NA
        
        # Add purge 2
        if len(purge_intervals) >= 2:
            result['purge2_start_idx'] = purge_intervals[1][0]
            result['purge2_end_idx'] = purge_intervals[1][1]
        else:
            result['purge2_start_idx'] = pd.NA
            result['purge2_end_idx'] = pd.NA
        
        # Add recovery 2
        if len(recovery_intervals) >= 2:
            result['recovery2_start_idx'] = recovery_intervals[1][0]
            result['recovery2_end_idx'] = recovery_intervals[1][1]
        else:
            result['recovery2_start_idx'] = pd.NA
            result['recovery2_end_idx'] = pd.NA
        
        return result
        
    except Exception as e:
        print(f"Error processing {nc_file}: {e}")
        return None


def main():
    """CLI entry point for extract-purge-indices command."""
    parser = argparse.ArgumentParser(description="Extract purge and recovery indices from netCDF files to CSV.")
    parser.add_argument(
        "-i", "--input_dir",
        required=True,
        help="Directory containing netCDF files (or parent directory with year subdirectories)"
    )
    parser.add_argument(
        "-o", "--output_file",
        required=True,
        help="Output CSV file path"
    )
    parser.add_argument(
        "-y", "--year",
        type=int,
        default=None,
        help="Specific year to process (optional, will look in input_dir/YYYY/)"
    )
    
    args = parser.parse_args()
    
    # Determine input directory
    if args.year:
        input_path = Path(args.input_dir) / str(args.year)
    else:
        input_path = Path(args.input_dir)
    
    if not input_path.exists():
        print(f"Error: Input directory {input_path} does not exist")
        return
    
    # Find all netCDF files
    nc_files = sorted(input_path.glob("*.nc"))
    
    if not nc_files:
        print(f"No netCDF files found in {input_path}")
        return
    
    print(f"Processing {len(nc_files)} files from {input_path}")
    
    # Extract indices from all files
    results = []
    for nc_file in nc_files:
        result = extract_purge_indices_from_file(nc_file)
        if result:
            results.append(result)
    
    # Create DataFrame and save to CSV
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values('date')
        
        # Ensure output directory exists
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        df.to_csv(args.output_file, index=False)
        print(f"Saved purge indices to {args.output_file}")
        print(f"Processed {len(results)} days")
    else:
        print("No results to save")


if __name__ == "__main__":
    main()
