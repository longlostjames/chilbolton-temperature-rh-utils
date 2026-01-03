"""
# Process Vaisala HMP155A temperature and humidity sensor data to netCDF
"""

import polars as pl
import numpy as np
import ncas_amof_netcdf_template as nant
import datetime as dt
from datetime import datetime
import cftime
from datetime import timezone


import re
import os
from datetime import datetime, timezone
from .read_format5_content import read_format5_content
from .read_format5_header import read_format5_header
from .read_format5_chdb import read_format5_chdb

try:
    from . import __version__
except ImportError:
    __version__ = "unknown"

DATE_REGEX = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}" 
d = re.compile(DATE_REGEX)


def proc_line(line, extra_info=None):
    pattern = re.compile(
        r'(?P<date>\d{8}) (?P<time>\d{2}:\d{2}:\d{2}\.\d{3}) '
        r'x=\s*(?P<x>[-\d\.]+) y=\s*(?P<y>[-\d\.]+) z=\s*(?P<z>[-\d\.]+) '
        r'T=\s*(?P<T>[-\d\.]+) e1=\s*(?P<e1>[-\d\.]+) e2=\s*(?P<e2>[-\d\.]+) '
        r'e3=\s*(?P<e3>[-\d\.]+) e4=\s*(?P<e4>[-\d\.]+)'
    )
    match = pattern.match(line)
    if match:
        gd = match.groupdict()
        datetime_str = f"{gd['date']} {gd['time']}"
        return [f"{datetime_str},{gd['x']},{gd['y']},{gd['z']},{gd['T']},{gd['e1']},{gd['e2']},{gd['e3']},{gd['e4']}"]
    else:
        return []

def preprocess_data_f5(infile):
    """
    Preprocesses the data file to extract a Polars DataFrame with TIMESTAMP, Air_T_Avg, and RH_Avg columns.
    Applies preprocessing to oatnew_ch and rhnew_ch using rawrange and realrange from chdb.
    """
    print(f"Processing file: {infile}")

    # Step 1: Use read_format5_header to extract the header
    header = read_format5_header(infile)

    # Step 2: Use read_format5_content to read and process the file
    df = read_format5_content(infile, header)

    print(df)

    # Load the channel database from package installation directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    chdb_file = os.path.join(script_dir, "f5channelDB.chdb")
    chdb = read_format5_chdb(chdb_file)

    print(chdb['oatnew_ch'])
    print(chdb['rhnew_ch'])


    # Extract rawrange and realrange for oatnew_ch and rhnew_ch
    oatnew_rawrange = chdb["oatnew_ch"]["rawrange"]
    oatnew_realrange = chdb["oatnew_ch"]["realrange"]
    rhnew_rawrange = chdb["rhnew_ch"]["rawrange"]
    rhnew_realrange = chdb["rhnew_ch"]["realrange"]

    # Define a function to map raw values to real values
    def map_to_real_range(raw_col, raw_range, real_range):
        raw_min, raw_max = raw_range["lower"], raw_range["upper"]
        real_min, real_max = real_range["lower"], real_range["upper"]
        return (pl.col(raw_col) - raw_min) / (raw_max - raw_min) * (real_max - real_min) + real_min

    # Ensure the columns are numeric
    df = df.with_columns([
        pl.col("oatnew_ch").cast(pl.Float64),
        pl.col("rhnew_ch").cast(pl.Float64)
    ])

    # Apply the mapping to oatnew_ch and rhnew_ch
    df = df.with_columns([
        map_to_real_range("oatnew_ch", oatnew_rawrange, oatnew_realrange).alias("Air_T_Avg"),
        map_to_real_range("rhnew_ch", rhnew_rawrange, rhnew_realrange).alias("RH_Avg")
    ])

    # Keep only TIMESTAMP, WS_Avg, and WD_Avg columns
    df = df.select(["TIMESTAMP", "Air_T_Avg", "RH_Avg"])

    df = df.with_columns([
        (pl.col("Air_T_Avg") + 273.15).alias("Air_T_Avg")
    ])

    # Round WS_Avg and WD_Avg to 3 decimal places
    #df = df.with_columns(
    #    pl.col("WS_Avg").round(3).alias("WS_Avg"),
    #    pl.col("WD_Avg").round(3).alias("WD_Avg")
    #)

    return df


def process_file(infile, outdir="./", metadata_file="metadata.json", aws_7_file=None):
    # Read data
    df = preprocess_data_f5(infile)

    print(df)

    # Check if the year of the last timestamp is one greater than the previous timestamp
    if df["TIMESTAMP"][-1].year > df["TIMESTAMP"][-2].year:
        print("[INFO] Adjusting the last timestamp to be one year earlier temporarily.")
        # Temporarily adjust the last timestamp
        original_last_timestamp = df["TIMESTAMP"][-1]
        adjusted_last_timestamp = original_last_timestamp.replace(year=original_last_timestamp.year - 1)
        df = df.with_columns(
            pl.when(pl.col("TIMESTAMP") == original_last_timestamp)
            .then(adjusted_last_timestamp)
            .otherwise(pl.col("TIMESTAMP"))
            .alias("TIMESTAMP")
        )

    # Get all the time formats
    unix_times, day_of_year, years, months, days, hours, minutes, seconds, time_coverage_start_unix, time_coverage_end_unix, file_date = nant.util.get_times(df["TIMESTAMP"])

    # Restore the original last timestamp for correction later
    if "adjusted_last_timestamp" in locals():
        print("[INFO] Restoring the original last timestamp for correction.")
        unix_times[-1] = int(original_last_timestamp.replace(tzinfo=timezone.utc).timestamp())
        day_of_year[-1] = original_last_timestamp.timetuple().tm_yday
        years[-1] = original_last_timestamp.year
        months[-1] = original_last_timestamp.month
        days[-1] = original_last_timestamp.day
        hours[-1] = original_last_timestamp.hour
        minutes[-1] = original_last_timestamp.minute
        seconds[-1] = original_last_timestamp.second
        time_coverage_end_unix = unix_times[-1]

    file_date = f"{str(years[0])}{str(months[0]).zfill(2)}{str(days[0]).zfill(2)}"

    # Read product_version from metadata file
    import json
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    product_version = metadata.get('product_version', 'v1.0')

    # Create NetCDF file
    nc = nant.create_netcdf.make_product_netcdf("surface-met", "ncas-temperature-rh-1", date=file_date, 
                                 dimension_lengths={"time": len(unix_times)}, 
                                 file_location=outdir, platform="cao",
                                 product_version=product_version)
    if isinstance(nc, list):
        print("[WARNING] Unexpectedly got multiple netCDFs returned from nant.create_netcdf.main, just using first file...")
        nc = nc[0]

    # Update source and instrument_manufacturer attributes
    #nc.setncattr("source", "NCAS Temperature RH unit 1")
    #nc.setncattr("instrument_manufacturer", "Vaisala")
    #nc.setncattr("instrument_model", "HMP155A")

    # Add time variable data to NetCDF file
    nant.util.update_variable(nc, "time", unix_times)
    nant.util.update_variable(nc, "day_of_year", day_of_year)
    nant.util.update_variable(nc, "year", years)
    nant.util.update_variable(nc, "month", months)
    nant.util.update_variable(nc, "day", days)
    nant.util.update_variable(nc, "hour", hours)
    nant.util.update_variable(nc, "minute", minutes)
    nant.util.update_variable(nc, "second", seconds)

    # Correct the last timestamp and year in the NetCDF file
    if "adjusted_last_timestamp" in locals():
        print("[INFO] Correcting the last timestamp and year in the NetCDF file.")
        corrected_last_unix_time = int(original_last_timestamp.replace(tzinfo=timezone.utc).timestamp())
        nc.variables["time"][-1] = corrected_last_unix_time

        # Update the valid_max attribute for the "time" variable
        if "valid_max" in nc.variables["time"].ncattrs():
            nc.variables["time"].setncattr("valid_max", max(corrected_last_unix_time, nc.variables["time"].getncattr("valid_max")))

        # Correct the "year" variable
        nc.variables["year"][-1] = original_last_timestamp.year

        # Update the valid_max attribute for the "year" variable
        if "valid_max" in nc.variables["year"].ncattrs():
            nc.variables["year"].setncattr("valid_max", max(original_last_timestamp.year, nc.variables["year"].getncattr("valid_max")))

    # Add wind data from sonic to NetCDF file
    nant.util.update_variable(nc, "air_temperature", df["Air_T_Avg"])
    nant.util.update_variable(nc, "relative_humidity", df["RH_Avg"])

    # Add time_coverage_start and time_coverage_end metadata using data from get_times
    nc.setncattr(
        "time_coverage_start",
        dt.datetime.fromtimestamp(time_coverage_start_unix, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    )
    nc.setncattr(
        "time_coverage_end",
        dt.datetime.fromtimestamp(time_coverage_end_unix, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    )

    # Add metadata from file
    nant.util.add_metadata_to_netcdf(nc, metadata_file)
    
    # Set processing software version from package
    version_str = __version__ if __version__.startswith('v') else f"v{__version__}"
    nc.setncattr("processing_software_version", version_str)

        # Ensure the 'time' variable has the correct units and values
    if "time" in nc.variables:
        print("[INFO] Correcting the 'time' variable in the NetCDF file.")
        # Set the correct units for the 'time' variable
        nc.variables["time"].setncattr("units", "seconds since 1970-01-01 00:00:00")
        print(nc['time'])        
        # Convert the time values to cftime objects and ensure they are consistent
        time_values = nc.variables["time"][:]
        corrected_time_values = [
            cftime.date2num(
                cftime.num2date(t, "seconds since 1970-01-01 00:00:00"),
                "seconds since 1970-01-01 00:00:00"
            )
            for t in time_values
        ]
        nc.variables["time"][:] = corrected_time_values

    # Close file, remove empty
    file_name = nc.filepath()
    nc.close()
    nant.remove_empty_variables.main(file_name)


def none_or_str(value):
    if value == 'None':
        return None
    return value


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Process Vaisala HMP155 Temperature and Humidity Probe data to netCDF")
    parser.add_argument("infile", type=str, help="Input file")
    parser.add_argument("-o", "--outdir", type=str, default="./", help="Output directory")
    parser.add_argument("-m", "--metadata_file", type=str, default="metadata.json", help="Metadata file")

    args = parser.parse_args()
    process_file(args.infile, outdir=args.outdir, metadata_file=args.metadata_file)


def main():
    """CLI entry point for process-hmp155-f5 command."""
    import argparse
    parser = argparse.ArgumentParser(description="Process Vaisala HMP155 Temperature and Humidity Probe data from Format5 to netCDF")
    parser.add_argument("infile", type=str, help="Input Format5 file")
    parser.add_argument("-o", "--outdir", type=str, default="./", help="Output directory")
    parser.add_argument("-m", "--metadata_file", type=str, default="metadata.json", help="Metadata file")

    args = parser.parse_args()
    process_file(args.infile, outdir=args.outdir, metadata_file=args.metadata_file)

