"""
# Process Vaisala HMP155A temperature and humidity sensor data to netCDF
"""

import polars as pl
import numpy as np
from datetime import datetime
import ncas_amof_netcdf_template as nant
import datetime as dt
import re
import os
import argparse
import cftime
from datetime import timezone

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
    # Only read relevant columns, skip first 4 lines
    try:
        df = pl.read_csv(
            infile,
            skip_rows=4,
            columns=["TIMESTAMP", "Air_T_Avg", "RH_Avg"],
            try_parse_dates=True,
            ignore_errors=True
        )
    except Exception as e:
        print(f"Error reading file: {e}")
        return pl.DataFrame({"TIMESTAMP": [], "Air_T_Avg": [], "RH_Avg": []})

    # Only keep relevant columns
    keep = ["TIMESTAMP", "Air_T_Avg", "RH_Avg"]
    for col in keep:
        if col not in df.columns:
            print(f"Column '{col}' missing, filling with null.")
            df = df.with_columns(pl.lit(None).alias(col))
    df = df.select(keep)
    # Convert types
    scale_factor_Air_T = 0.02
    offset_Air_T = 233.15  # Offset for temperature in Kelvin
    scale_factor_RH = 0.02  # Scale factor for relative humidity, typically 0.02
    offset_RH = 0.0  # Offset for relative humidity, typically 0

    df = df.with_columns([
        pl.col("Air_T_Avg").cast(pl.Float64) * scale_factor_Air_T + offset_Air_T,
        pl.col("RH_Avg").cast(pl.Float64) * scale_factor_RH + offset_RH
    ])
    return df


def main(infile, outdir="./", metadata_file="metadata.json", aws_7_file=None):
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
    nc = nant.create_netcdf.main("ncas-temperature-rh-1", date=file_date, 
                                 dimension_lengths={"time": len(unix_times)}, 
                                 products="surface-met", file_location=outdir, 
                                 product_version="1.0")
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


def read_bad_intervals(corr_file):
    bad_intervals = []
    with open(corr_file, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 4 and parts[-1] == "BADDATA":
                date = parts[0]
                start = parts[1]
                end = parts[2]
                # Build datetime objects for start and end
                start_dt = datetime.strptime(date + start, "%Y%m%d%H%M%S")
                end_dt = datetime.strptime(date + end, "%Y%m%d%H%M%S")
                bad_intervals.append((start_dt, end_dt))
    return bad_intervals

def flag_bad_data(df, bad_intervals, flag_column):
    timestamps = df["TIMESTAMP"].to_numpy()
    mask = np.zeros(len(timestamps), dtype=bool)
    for start, end in bad_intervals:
        mask |= (timestamps >= start) & (timestamps <= end)
    # Add the mask as a Boolean column
    df = df.with_columns(pl.Series("bad_mask", mask))
    # Now update the flag column in Polars
    if flag_column in df.columns:
        df = df.with_columns(
            pl.when(pl.col("bad_mask")).then(2).otherwise(pl.col(flag_column)).alias(flag_column)
        )
    else:
        df = df.with_columns(
            pl.when(pl.col("bad_mask")).then(2).otherwise(0).alias(flag_column)
        )
    # Remove the temporary mask column
    df = df.drop("bad_mask")
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Vaisala HMP155 Temperature and Humidity Probe data to netCDF")
    parser.add_argument("infile", type=str, help="Input file")
    parser.add_argument("-o", "--outdir", type=str, default="./", help="Output directory")
    parser.add_argument("-m", "--metadata_file", type=str, default="metadata.json", help="Metadata file")
    #parser.add_argument("--corr_file_rh", type=str, default=None, help="Correction file with BADDATA intervals for RH")
    #parser.add_argument("--corr_file_temperature", type=str, default=None, help="Correction file with BADDATA intervals for air temperature")

    args = parser.parse_args()

    main(
        args.infile,
        outdir=args.outdir,
        metadata_file=args.metadata_file,
        aws_7_file=args.aws_7_file if hasattr(args, "aws_7_file") else None #,
        #corr_file_temperature=args.corr_file_temperature,
        #corr_file_rh=args.corr_file_rh
    )

