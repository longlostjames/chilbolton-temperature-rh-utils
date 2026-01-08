#!/usr/bin/env python3
"""
Fix isolated recovery flags (flag=4) that are not adjacent to purge flags (flag=3).
These should be changed to good data (flag=1).
"""

import xarray as xr
import numpy as np
import argparse
from datetime import datetime
import os
import shutil


def fix_isolated_recovery_flags(filename, dry_run=False):
    """
    Find and fix isolated recovery flags in NetCDF file.
    
    Parameters:
    -----------
    filename : str
        Path to NetCDF file
    dry_run : bool
        If True, report what would be changed without modifying the file
    """
    print(f"Processing: {filename}")
    
    # Open dataset and load into memory
    ds = xr.open_dataset(filename)
    
    # Check if QC flags exist
    if 'qc_flag_relative_humidity' not in ds:
        print("  No qc_flag_relative_humidity found")
        ds.close()
        return
    
    qc_rh = ds['qc_flag_relative_humidity'].values
    if 'qc_flag_air_temperature' in ds:
        qc_temp = ds['qc_flag_air_temperature'].values
    else:
        qc_temp = None
    
    # Find recovery flags (flag=4)
    recovery_mask = (qc_rh == 4)
    recovery_indices = np.where(recovery_mask)[0]
    
    if len(recovery_indices) == 0:
        print("  No recovery flags found")
        ds.close()
        return
    
    print(f"  Found {len(recovery_indices)} recovery flags")
    
    # Check each recovery flag to see if it's adjacent to a purge flag
    isolated_count = 0
    for idx in recovery_indices:
        # Look in a window before the recovery flag for purge flags (flag=3)
        lookback_start = max(0, idx - 50)  # Look back up to 50 samples (~8 minutes at 10s sampling)
        has_adjacent_purge = False
        
        # Check if there's any purge flag in the lookback window
        if idx > lookback_start:
            purge_in_window = np.any(qc_rh[lookback_start:idx] == 3)
            has_adjacent_purge = purge_in_window
        
        if not has_adjacent_purge:
            time_str = str(ds['time'].values[idx])
            print(f"    Isolated recovery at index {idx} ({time_str}) - no purge in previous 50 samples")
            
            # Show context
            if idx >= 5:
                context_start = max(0, idx - 5)
                context_flags = qc_rh[context_start:idx+1]
                print(f"      Context flags: {context_flags}")
            
            isolated_count += 1
            
            if not dry_run:
                qc_rh[idx] = 1  # Change to good data
                if qc_temp is not None:
                    qc_temp[idx] = 1
    
    if isolated_count > 0:
        print(f"  Found {isolated_count} isolated recovery flags")
        
        if not dry_run:
            # Write back the corrected flags
            ds['qc_flag_relative_humidity'][:] = qc_rh
            if qc_temp is not None:
                ds['qc_flag_air_temperature'][:] = qc_temp
            
            # Update metadata
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            history_entry = f"{now} - Fixed {isolated_count} isolated recovery flags (changed flag=4 to flag=1 where no adjacent purge)"
            
            if 'history' in ds.attrs:
                ds.attrs['history'] = history_entry + "\n" + ds.attrs['history']
            else:
                ds.attrs['history'] = history_entry
            
            ds.attrs['last_revised_date'] = now
            
            # Save to temporary file then replace original
            temp_filename = filename + '.tmp'
            print(f"  Writing changes to {filename}")
            ds.to_netcdf(temp_filename)
            ds.close()
            
            # Replace original with corrected file
            shutil.move(temp_filename, filename)
            
            print(f"  Fixed {isolated_count} isolated recovery flags")
            print(f"  Updated history and last_revised_date metadata")
        else:
            print(f"  Would fix {isolated_count} isolated recovery flags (dry run)")
    else:
        print("  No isolated recovery flags found")
    
    ds.close()


def main():
    parser = argparse.ArgumentParser(
        description="Fix isolated recovery flags in NetCDF files"
    )
    parser.add_argument('files', nargs='+', help='NetCDF file(s) to process')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be changed without modifying files')
    
    args = parser.parse_args()
    
    for filename in args.files:
        try:
            fix_isolated_recovery_flags(filename, dry_run=args.dry_run)
        except Exception as e:
            print(f"Error processing {filename}: {e}")


if __name__ == '__main__':
    main()
