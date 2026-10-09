#!/usr/bin/env python3
"""Apply monthly .corr QC files to HMP155 NetCDF files."""

import argparse
import datetime
import shutil
from pathlib import Path

import numpy as np
import xarray as xr
from netCDF4 import Dataset

from .qc_corrections import (
    QC_FLAG_VARIABLES,
    find_corr_file,
    load_corr_intervals,
    qc_from_intervals,
)

FLAG_MEANINGS_BASE = ("not_used good_data bad_data_measurement_suspect "
                      "bad_data_purge_cycle_value_fixed_as_start_of_purge")

# Temperature is never given the recovery flag, so its flag list stops at 3
QC_ATTRS = {
    "temperature": {
        "units": "1",
        "long_name": "Data Quality flag: Air Temperature",
        "standard_name": "quality_flag",
        "flag_values": np.array([0, 1, 2, 3], dtype=np.int8),
        "flag_meanings": FLAG_MEANINGS_BASE,
    },
    "rh": {
        "units": "1",
        "long_name": "Data Quality flag: Relative Humidity",
        "standard_name": "quality_flag",
        "flag_values": np.array([0, 1, 2, 3, 4], dtype=np.int8),
        "flag_meanings": f"{FLAG_MEANINGS_BASE} recovery_in_rh_after_purge",
    },
}


def find_nc_file_for_date(input_dir, date, year=None):
    """Find the NetCDF file corresponding to a given date."""
    search_dir = Path(input_dir) / str(year) if year is not None else Path(input_dir)
    if not search_dir.is_dir():
        return None
    candidates = sorted(search_dir.glob(f"*{date.strftime('%Y%m%d')}*.nc"))
    return candidates[0] if candidates else None


def apply_corr_to_file(nc_file, corr_dir, date):
    """Apply both variables' .corr intervals to one NetCDF file."""
    now = datetime.datetime.now(datetime.timezone.utc)
    history_entry = (f"{now.strftime('%Y-%m-%dT%H:%M:%S')} - Applied .corr QC flags "
                     f"using apply-hmp155-corr-files")

    with xr.open_dataset(nc_file) as ds:
        if "time" not in ds.sizes:
            raise ValueError(f"No 'time' dimension found in {nc_file}")
        num_points = int(ds.sizes["time"])

        for variable, qc_name in QC_FLAG_VARIABLES.items():
            intervals = load_corr_intervals(corr_dir, variable, date)
            qc_values = qc_from_intervals(num_points, intervals,
                                          source=str(find_corr_file(corr_dir, variable, date)))
            ds[qc_name] = (("time",), qc_values)
            ds[qc_name].attrs = dict(QC_ATTRS[variable])
            ds[qc_name].encoding["_FillValue"] = None

        ds.attrs["history"] = (f"{history_entry}\n{ds.attrs['history']}"
                               if "history" in ds.attrs else history_entry)
        ds.attrs.pop("last_modified", None)
        ds.attrs["last_revised_date"] = now.strftime("%Y-%m-%dT%H:%M:%S.%f")

        tmp_file = f"{nc_file}.tmp"
        ds.to_netcdf(tmp_file)

    shutil.move(tmp_file, nc_file)

    with Dataset(nc_file, mode="r+") as ds_nc:
        if "time" in ds_nc.variables:
            ds_nc.variables["time"].setncattr("units", "seconds since 1970-01-01 00:00:00")


def iter_dates(start, end):
    d = start
    while d <= end:
        yield d
        d += datetime.timedelta(days=1)


def main():
    """CLI entry point for apply-hmp155-corr-files."""
    parser = argparse.ArgumentParser(
        description="Apply purge, recovery and bad-data flags from .corr files to netCDF files."
    )
    parser.add_argument("-c", "--corr-dir", required=True,
                        help="Base of the .corr corrections tree")
    parser.add_argument("-i", "--input_dir", required=True,
                        help="Directory containing netCDF files (or parent with year subdirectories)")
    parser.add_argument("-y", "--year", type=int, default=None,
                        help="Year to process (files looked up in input_dir/YYYY/)")
    parser.add_argument("-s", "--start-date", default=None,
                        help="First date to process (YYYY-MM-DD)")
    parser.add_argument("-e", "--end-date", default=None,
                        help="Last date to process (YYYY-MM-DD)")

    args = parser.parse_args()

    if args.start_date and args.end_date:
        start = datetime.date.fromisoformat(args.start_date)
        end = datetime.date.fromisoformat(args.end_date)
    elif args.year:
        start = datetime.date(args.year, 1, 1)
        end = datetime.date(args.year, 12, 31)
    else:
        parser.error("Specify either --year or both --start-date and --end-date")

    success = skipped = 0
    for date in iter_dates(start, end):
        if not any(find_corr_file(args.corr_dir, v, date) for v in QC_FLAG_VARIABLES):
            continue

        nc_file = find_nc_file_for_date(args.input_dir, date, args.year or date.year)
        if nc_file is None:
            print(f"Warning: no netCDF file found for {date.isoformat()}")
            skipped += 1
            continue

        try:
            apply_corr_to_file(nc_file, args.corr_dir, date)
            print(f"Applied .corr flags to {nc_file.name}")
            success += 1
        except Exception as e:
            print(f"Error processing {nc_file}: {e}")
            skipped += 1

    print(f"\nComplete: {success} files updated, {skipped} skipped")


if __name__ == "__main__":
    main()
