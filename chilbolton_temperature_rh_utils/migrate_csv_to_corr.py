#!/usr/bin/env python3
"""Convert legacy purge/bad-data index CSV files into monthly .corr files."""

import argparse
import glob
import os
import re
from collections import defaultdict

import pandas as pd

from .qc_corrections import (
    FLAG_BAD,
    FLAG_PURGE,
    FLAG_RECOVERY,
    save_corr_intervals,
)


def _pairs(row, prefix):
    """Yield (start_idx, end_idx) for prefix1_*, prefix2_* … columns present in a row."""
    n = 1
    while True:
        start_col, end_col = f"{prefix}{n}_start_idx", f"{prefix}{n}_end_idx"
        if start_col not in row.index or end_col not in row.index:
            return
        start, end = row.get(start_col), row.get(end_col)
        if pd.notna(start) and pd.notna(end):
            yield int(start), int(end)
        n += 1


def intervals_from_purge_row(row):
    """Return (temperature_intervals, rh_intervals) for one purge CSV row."""
    purge = [(s, e, FLAG_PURGE) for s, e in _pairs(row, "purge")]
    recovery = [(s, e, FLAG_RECOVERY) for s, e in _pairs(row, "recovery")]
    return purge, purge + recovery


def intervals_from_bad_data_row(row):
    """Return (temperature_intervals, rh_intervals) for one bad-data CSV row."""
    both = [(s, e, FLAG_BAD) for s, e in _pairs(row, "both_bad")]
    temp = [(s, e, FLAG_BAD) for s, e in _pairs(row, "temp_bad")]
    rh = [(s, e, FLAG_BAD) for s, e in _pairs(row, "rh_bad")]
    return both + temp, both + rh


def read_index_csv(path):
    """Read an index CSV, tolerating rows with more columns than the header."""
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        max_cols = max((len(line.strip().split(",")) for line in f if line.strip()),
                       default=len(header))

    if max_cols <= len(header):
        return pd.read_csv(path, parse_dates=["date"])

    # Extra periods beyond the header: continue the header's repeating block
    patterns = []
    for col in header[1:]:
        pattern = re.sub(r"\d+", "{}", col, count=1)
        if pattern not in patterns:
            patterns.append(pattern)
    if not patterns:
        raise ValueError(f"{path}: cannot infer column layout")

    names = list(header)
    period = (len(header) - 1) // len(patterns) + 1
    while len(names) < max_cols:
        names += [pattern.format(period) for pattern in patterns]
        period += 1
    return pd.read_csv(path, names=names[:max_cols], skiprows=1, parse_dates=["date"])


def collect_intervals(csv_files, row_converter, collected):
    """Accumulate intervals per (date, variable) from a set of CSV files."""
    for path in csv_files:
        df = read_index_csv(path)
        for _, row in df.iterrows():
            date = row["date"].date()
            temp, rh = row_converter(row)
            collected[(date, "temperature")].extend(temp)
            collected[(date, "rh")].extend(rh)
        print(f"Read {len(df)} rows from {path}")


def main():
    """CLI entry point for migrate-hmp155-csv-to-corr."""
    parser = argparse.ArgumentParser(
        description="Convert purge_indices_*.csv and bad_data_indices_*.csv into monthly .corr files."
    )
    parser.add_argument("-p", "--purge-csv", nargs="*", default=None,
                        help="Purge index CSV files (default: purge_indices_????.csv in --csv-dir)")
    parser.add_argument("-b", "--bad-data-csv", nargs="*", default=None,
                        help="Bad data index CSV files (default: bad_data_indices_????.csv in --csv-dir)")
    parser.add_argument("-d", "--csv-dir", default=".",
                        help="Directory to search for CSV files (default: current directory)")
    parser.add_argument("-o", "--corr-dir", required=True,
                        help="Base of the .corr corrections tree to write into")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be written without writing files")

    args = parser.parse_args()

    purge_files = args.purge_csv
    if purge_files is None:
        purge_files = sorted(glob.glob(os.path.join(args.csv_dir, "purge_indices_????.csv")))
    bad_files = args.bad_data_csv
    if bad_files is None:
        bad_files = sorted(glob.glob(os.path.join(args.csv_dir, "bad_data_indices_????.csv")))

    if not purge_files and not bad_files:
        parser.error("No input CSV files found")

    collected = defaultdict(list)
    collect_intervals(purge_files, intervals_from_purge_row, collected)
    collect_intervals(bad_files, intervals_from_bad_data_row, collected)

    dates = sorted({date for date, _ in collected})
    print(f"\n{len(dates)} date(s) to migrate into {args.corr_dir}")
    if args.dry_run:
        for date in dates:
            temp = len(collected[(date, "temperature")])
            rh = len(collected[(date, "rh")])
            print(f"  {date}: {temp} temperature, {rh} RH interval(s)")
        return

    written = set()
    for date in dates:
        for variable in ("temperature", "rh"):
            intervals = sorted(set(collected[(date, variable)]))
            written.add(save_corr_intervals(args.corr_dir, variable, date, intervals))

    print(f"Wrote {len(written)} .corr file(s)")


if __name__ == "__main__":
    main()
