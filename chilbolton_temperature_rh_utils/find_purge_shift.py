#!/usr/bin/env python

import xarray as xr
import pandas as pd
import argparse
import numpy as np

# Define QC flag for purge periods
FLAG_PURGE = 3

def get_purge_intervals(nc_file):
    """
    Extract purge intervals from a NetCDF file based on QC flags.
    """
    with xr.open_dataset(nc_file, mode="r") as ds:
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

        return intervals

def calculate_time_of_day_shift(intervals1, intervals2):
    """
    Calculate the time of day shift (in seconds, including fractions) between two sets of purge intervals.
    """
    if len(intervals1) != len(intervals2):
        print("Warning: The number of purge intervals does not match between the two files.")
    
    shifts = []
    for (start1, _), (start2, _) in zip(intervals1, intervals2):
        # Extract the time of day (hours, minutes, seconds, microseconds) for each start time
        time_of_day1 = start1.time()
        time_of_day2 = start2.time()

        # Convert time of day to total seconds since midnight, including fractions
        seconds1 = (time_of_day1.hour * 3600 +
                    time_of_day1.minute * 60 +
                    time_of_day1.second +
                    time_of_day1.microsecond / 1e6)
        seconds2 = (time_of_day2.hour * 3600 +
                    time_of_day2.minute * 60 +
                    time_of_day2.second +
                    time_of_day2.microsecond / 1e6)

        # Calculate the shift in seconds (including fractions)
        shift = seconds2 - seconds1
        shifts.append(shift)
    
    return shifts

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Find the time of day shift in seconds (including fractions) between purge periods in two NetCDF files.")
    parser.add_argument("-f1", "--file1", required=True, help="Path to the first NetCDF file")
    parser.add_argument("-f2", "--file2", required=True, help="Path to the second NetCDF file")
    args = parser.parse_args()

    # Extract purge intervals from both files
    intervals1 = get_purge_intervals(args.file1)
    intervals2 = get_purge_intervals(args.file2)

    # Calculate the time of day shifts
    shifts = calculate_time_of_day_shift(intervals1, intervals2)

    # Print the results
    for i, shift in enumerate(shifts):
        print(f"Purge period {i + 1}: Time of day shift = {shift:.6f} seconds")

if __name__ == "__main__":
    main()