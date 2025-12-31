"""
# Process Vaisala HMP155A temperature and humidity sensor data to netCDF
"""

import polars as pl
import numpy as np
import ncas_amof_netcdf_template as nant
import datetime as dt
from datetime import datetime
import cftime
import re
import os
from datetime import datetime, timezone

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

def preprocess_data(infile):
    print(infile)

    # Step 1: Read the current day's file
    with open(infile, "r") as f:
        data = f.readlines()

    # Step 2: Parse the header to get column names
    header_line = data[1].strip()  # Assume the second line contains column names
    column_names = [col.strip('"') for col in header_line.split(",")]  # Clean column names
    print(f"Parsed column names: {column_names}")  # Debugging output

    # Step 3: Skip metadata lines (assume first 4 lines are metadata)
    data_lines = data[4:]  # Data starts after the first 4 lines

    # Step 4: Process the current day's data
    processed_data = []
    for line in data_lines:
        if line.strip():  # Skip empty lines
            fields = line.strip().split(",")
            processed_data.append(fields)

    # Step 5: Create a Polars DataFrame with the parsed column names
    df = pl.DataFrame(processed_data, schema=column_names, orient="row")

    # Step 6: Ensure required columns exist
    required_columns = ["TIMESTAMP", "Air_T_Avg", "RH_Avg"]
    for column in required_columns:
        if column not in df.columns:
            print(f"Column '{column}' is missing. Filling with null values.")
            df = df.with_columns(pl.lit(None).alias(column))

    # Step 7: Strip quotes from all string columns
    for column in df.columns:
        if df.schema[column] == pl.Utf8:
            df = df.with_columns(
                pl.col(column).str.strip_chars('"').alias(column)
            )

    # Step 8: Replace invalid values (e.g., "NAN") with null
    for column in ["Air_T_Avg", "RH_Avg"]:  # Only process relevant columns
        if column in df.columns:
            df = df.with_columns(
                pl.when(pl.col(column) == "NAN")
                .then(None)
                .otherwise(pl.col(column))
                .alias(column)
            )

    # Step 9: Convert specific columns to appropriate data types
    type_conversions = {
        "TIMESTAMP": pl.Datetime,
        "Air_T_Avg": pl.Float64,
        "RH_Avg": pl.Float64,
    }

    for column, dtype in type_conversions.items():
        if column in df.columns:
            if column == "TIMESTAMP":
                # Parse TIMESTAMP column to proper datetime format
                df = df.with_columns(
                    pl.col("TIMESTAMP").str.strptime(
                        pl.Datetime, format="%Y-%m-%d %H:%M:%S", strict=False
                    )
                )
            else:
                df = df.with_columns(pl.col(column).cast(dtype))

    # Step 10: Keep only the TIMESTAMP, WS_Avg, and WD_Avg columns
    df = df.select(["TIMESTAMP", "Air_T_Avg", "RH_Avg"])

    df = df.with_columns([
        (pl.col("Air_T_Avg") * 0.02 + 233.15).alias("Air_T_Avg"),
        (pl.col("RH_Avg")*0.02 + 0.00).alias("RH_Avg"),
    ])


    return df


def main(infile, outdir="./", metadata_file="metadata_stfc.json", aws_7_file=None):
    # Read data
    df = preprocess_data(infile)

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

    # Create NetCDF file
    #nc = nant.create_netcdf.main("ncas-temperature-rh-1", date=file_date, 
    #                             dimension_lengths={"time": len(unix_times)}, 
    #                             products="surface-met", file_location=outdir, 
    #                             product_version="1.0")
    
    nc = nant.create_netcdf.make_product_netcdf("surface-met","stfc-temperature-rh-1", date=file_date, 
                                 dimension_lengths={"time": len(unix_times)}, 
                                 file_location=outdir, platform="cao")
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
    nc.setncattr("processing_software_version", __version__)

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
    """CLI entry point for process-hmp155-stfc command."""
    import argparse
    parser = argparse.ArgumentParser(description="Process Vaisala HMP155 Temperature and Humidity Probe data (STFC variant) to netCDF")
    parser.add_argument("infile", type=str, help="Input file")
    parser.add_argument("-o", "--outdir", type=str, default="./", help="Output directory")
    parser.add_argument("-m", "--metadata_file", type=str, default="metadata.json", help="Metadata file")

    args = parser.parse_args()
    process_file(args.infile, outdir=args.outdir, metadata_file=args.metadata_file)

