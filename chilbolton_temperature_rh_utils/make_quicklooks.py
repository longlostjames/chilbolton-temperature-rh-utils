#!/usr/bin/env python3
"""
# Generate quicklook plots for HMP155 data with QC flags
"""

import xarray as xr
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
import argparse

try:
    from . import __version__
except ImportError:
    __version__ = "unknown"

def get_purge_intervals(qc_flag, time_coord, flag_value=3):
    """Return list of (start_time, end_time) tuples where the specified QC flag value occurs."""
    purge_mask = (qc_flag == flag_value).values
    times = pd.to_datetime(time_coord.values)
    intervals = []

    start = None
    for i, val in enumerate(purge_mask):
        if val and start is None:
            start = times[i]
        elif not val and start is not None:
            end = times[i - 1]
            intervals.append((start, end))
            start = None
    if start is not None:
        intervals.append((start, times[-1]))
    return intervals

def plot_day(ds, nc_filename, outdir):
    """Plot air_temperature and RH with purge flags, shaded regions for bad data, and RH dip recovery."""
    if ds.time.size == 0:
        print(f"Skipping {nc_filename}: no data")
        return
    
    try:
        date_str = [s for s in nc_filename.split('_') if s.isdigit() and len(s) == 8][0]
        date_label = pd.to_datetime(date_str, format="%Y%m%d").strftime('%Y-%m-%d')
    except IndexError:
        date_label = "unknown_date"

    day_start = pd.to_datetime(date_label)
    day_end = day_start + pd.Timedelta(days=1)

    time = ds['time'].values

    # Get purge intervals
    intervals = get_purge_intervals(ds['qc_flag_air_temperature'], ds['time'])
    n_purges = len(intervals)

    # Create subplots with better proportions
    # Give more height to full-day plots, less to zoomed plots
    if n_purges > 0:
        fig = plt.figure(figsize=(14, 10 + (2 * n_purges)))
        gs = fig.add_gridspec(2 + 2, n_purges if n_purges > 0 else 1, 
                             height_ratios=[2, 2, 1.5, 1.5],  # Full-day plots get more space
                             hspace=0.8, wspace=0.3)
    else:
        fig = plt.figure(figsize=(14, 8))
        gs = fig.add_gridspec(2, 1, height_ratios=[1, 1], hspace=0.3)

    # Convert air_temperature from K to °C for plotting
    air_temp_C = ds['air_temperature'] - 273.15

    # --- Full-day Air temperature ---
    ax_full_temp = fig.add_subplot(gs[0, :])
    ax_full_temp.plot(time, air_temp_C, label='Air temperature')
    purge_temp = ds['qc_flag_air_temperature'] == 3
    ax_full_temp.plot(time[purge_temp], air_temp_C.values[purge_temp], 'r.', label='Purge flagged (3)')
    # Shade regions where QC flag is 2 (bad data)
    bad_intervals = get_purge_intervals(ds['qc_flag_air_temperature'], ds['time'], flag_value=2)
    for i, (start, end) in enumerate(bad_intervals):
        label = "Bad data (2)" if i == 0 else None
        ax_full_temp.axvspan(start, end, color='grey', alpha=0.3, label=label)
    # Shade regions where QC flag is 3 (purge regions)
    for start, end in intervals:
        ax_full_temp.axvspan(start, end, color='red', alpha=0.2)
    ax_full_temp.set_ylabel('Air temperature (°C)')
    ax_full_temp.set_title(f'Air temperature with QC Flags - {date_label}')
    ax_full_temp.legend()
    ax_full_temp.grid(True)
    ax_full_temp.set_xlim(day_start, day_end)

    # --- Full-day Relative humidity ---
    ax_full_rh = fig.add_subplot(gs[1, :])
    ax_full_rh.plot(time, ds['relative_humidity'], label='Relative humidity')

    # Plot purge flags (value 3)
    purge_rh = ds['qc_flag_relative_humidity'] == 3
    ax_full_rh.plot(time[purge_rh], ds['relative_humidity'].values[purge_rh], 'r.', label='Purge flagged (3)')

    # Plot RH dip flags (value 4) as "Purge recovery"
    rh_dip = ds['qc_flag_relative_humidity'] == 4
    ax_full_rh.plot(time[rh_dip], ds['relative_humidity'].values[rh_dip], 'b.', label='Purge recovery (4)')

    # Shade regions where QC flag is 2 (bad data)
    bad_intervals_rh = get_purge_intervals(ds['qc_flag_relative_humidity'], ds['time'], flag_value=2)
    for i, (start, end) in enumerate(bad_intervals_rh):
        label = "Bad data (2)" if i == 0 else None  # Add label only for the first interval
        ax_full_rh.axvspan(start, end, color='grey', alpha=0.3, label=label)

    # Shade regions where QC flag is 3 (purge regions)
    for start, end in intervals:
        ax_full_rh.axvspan(start, end, color='red', alpha=0.2, label=None)

    # Shade regions where QC flag is 4 (RH dip regions)
    for start, end in intervals:
        rh_start = end  # RH dip starts immediately after the purge region
        rh_end = rh_start + pd.Timedelta(minutes=6)  # RH dip lasts for 6 minutes
        ax_full_rh.axvspan(rh_start, rh_end, color='peachpuff', alpha=0.5, label=None)

    ax_full_rh.set_ylabel('Relative humidity (%)')
    ax_full_rh.set_xlabel('Time (UTC)')
    ax_full_rh.set_title(f'Relative humidity with QC Flags — {date_label}')
    ax_full_rh.legend()
    ax_full_rh.grid(True)
    ax_full_rh.set_xlim(day_start, day_end)

    # --- Zoomed plots for each purge interval ---
    if n_purges > 0:
        for i, (start, end) in enumerate(intervals):
            buffer = pd.Timedelta(minutes=10)
            zoom_start = start - buffer
            zoom_end = end + buffer

            subset = ds.sel(time=slice(zoom_start, zoom_end))
            if subset.time.size == 0:
                continue

            time = subset['time'].values

            # Zoomed Air temperature
            ax_zoom_temp = fig.add_subplot(gs[2, i])
            air_temp_C_zoom = subset['air_temperature'] - 273.15
            ax_zoom_temp.plot(time, air_temp_C_zoom, label='Air temperature')
            purge_temp = subset['qc_flag_air_temperature'] == 3
            ax_zoom_temp.plot(time[purge_temp], air_temp_C_zoom.values[purge_temp], 'r.', label='Purge flagged (3)')
            bad_intervals_zoom = get_purge_intervals(subset['qc_flag_air_temperature'], subset['time'], flag_value=2)
            for j, (start_zoom, end_zoom) in enumerate(bad_intervals_zoom):
                label = "Bad data (2)" if j == 0 else None
                ax_zoom_temp.axvspan(start_zoom, end_zoom, color='grey', alpha=0.3, label=label)
            ax_zoom_temp.axvspan(start, end, color='red', alpha=0.2)
            ax_zoom_temp.set_ylabel('Air temperature (°C)')
            ax_zoom_temp.set_title(f'Purge {i + 1}', pad=20)
            ax_zoom_temp.grid(True)
            ax_zoom_temp.tick_params(axis='x', labelbottom=False)  # Hide x labels on top plot

            # Zoomed Relative humidity
            ax_zoom_rh = fig.add_subplot(gs[3, i])
            ax_zoom_rh.plot(time, subset['relative_humidity'], label='Relative humidity')

            # Plot purge flags (value 3)
            purge_rh = subset['qc_flag_relative_humidity'] == 3
            ax_zoom_rh.plot(time[purge_rh], subset['relative_humidity'].values[purge_rh], 'r.', label='Purge flagged (3)')

            # Plot RH dip flags (value 4) as "Purge recovery"
            rh_dip = subset['qc_flag_relative_humidity'] == 4
            ax_zoom_rh.plot(time[rh_dip], subset['relative_humidity'].values[rh_dip], 'b.', label='Purge recovery (4)')

            # Shade regions where QC flag is 2 (bad data)
            bad_intervals_zoom_rh = get_purge_intervals(subset['qc_flag_relative_humidity'], subset['time'], flag_value=2)
            for j, (start_zoom, end_zoom) in enumerate(bad_intervals_zoom_rh):
                label = "Bad data (2)" if j == 0 else None  # Add label only for the first interval
                ax_zoom_rh.axvspan(start_zoom, end_zoom, color='grey', alpha=0.3, label=label)

            # Shade regions where QC flag is 3 (purge regions)
            ax_zoom_rh.axvspan(start, end, color='red', alpha=0.2, label=None)

            # Shade regions where QC flag is 4 (RH dip regions)
            rh_start = end
            rh_end = rh_start + pd.Timedelta(minutes=6)
            ax_zoom_rh.axvspan(rh_start, rh_end, color='peachpuff', alpha=0.5, label=None)

            ax_zoom_rh.set_ylabel('Relative humidity (%)')
            ax_zoom_rh.set_xlabel('Time (UTC)')
            ax_zoom_rh.grid(True)

    # Save to PNG
    outfile = os.path.join(outdir, f"{nc_filename.replace('.nc', '.png')}")
    plt.savefig(outfile, dpi=200)
    plt.close()
    print(f"Saved {outfile}")

def main():
    """CLI entry point for make-hmp155-quicklooks command."""
    parser = argparse.ArgumentParser(description="Generate daily QC flag plots for all NetCDF files in a directory.")
    parser.add_argument(
        "-i", "--input_dir",
        default="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1a/",
        help="Base directory containing yearly subdirectories of NetCDF files (default: ./netcdf_input)"
    )
    parser.add_argument(
        "-o", "--output_dir",
        default="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1a/quicklooks/",
        help="Base directory to save yearly subdirectories of PNG plots (default: ./plots_output)"
    )
    parser.add_argument(
        "-y", "--year",
        required=True,
        help="Year to process (e.g., 2017)"
    )
    parser.add_argument(
        "-d", "--day",
        help="Specific day to process (format: YYYYMMDD). If not provided, all days in the year will be processed."
    )
    args = parser.parse_args()

    # Construct year-specific input and output directories
    input_dir = os.path.join(args.input_dir, args.year)
    output_dir = os.path.join(args.output_dir, args.year)

    os.makedirs(output_dir, exist_ok=True)

    # Get list of NetCDF files in the input directory (search recursively in subdirectories)
    from pathlib import Path
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"Input directory does not exist: {input_dir}")
        return
    
    # Search for .nc files in year directory and subdirectories (e.g., YYYYMM/)
    nc_files = sorted([f for f in input_path.rglob("*.nc")])
    
    if not nc_files:
        print(f"No .nc files found in input directory: {input_dir}")
        return

    # Filter files for a specific day if --day is provided
    if args.day:
        nc_files = [f for f in nc_files if args.day in f.name]
        if not nc_files:
            print(f"No .nc files found for the specified day: {args.day}")
            return

    for nc_file in nc_files:
        try:
            ds = xr.open_dataset(nc_file)
            ds = ds.sortby('time')
            if 'time' in ds:
                date_str = pd.to_datetime(ds.time.values[0]).strftime('%Y-%m-%d')
                plot_day(ds, nc_file.name, output_dir)
            else:
                print(f"{nc_file.name}: no 'time' variable")
        except Exception as e:
            print(f"Failed to process {nc_file.name}: {e}")

if __name__ == "__main__":
    main()