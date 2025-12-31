#!/usr/bin/env python3

import os
import xarray as xr
import numpy as np
import argparse

# --- Parse command-line argument for directory ---
parser = argparse.ArgumentParser(description="Count qc_flag_air_temperature == 3 in NetCDF files")
parser.add_argument('-d', '--directory', required=True, help="Directory containing NetCDF files")
args = parser.parse_args()

# --- Scan and process files ---
total_flagged = 0
file_count = 0

for root, _, files in os.walk(args.directory):
    for file in files:
        if file.endswith('.nc'):
            path = os.path.join(root, file)
            try:
                ds = xr.open_dataset(path)
                if 'qc_flag_air_temperature' in ds:
                    count = int((ds['qc_flag_air_temperature'] == 3).sum())
                    print(f"{file}: {count} flagged samples")
                    total_flagged += count
                    file_count += 1
                else:
                    print(f"{file}: variable 'qc_flag_air_temperature' not found")
            except Exception as e:
                print(f"Failed to process {file}: {e}")

print(f"\nProcessed {file_count} files")
print(f"Total qc_flag_air_temperature == 3: {total_flagged}")