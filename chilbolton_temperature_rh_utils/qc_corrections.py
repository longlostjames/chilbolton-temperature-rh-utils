"""Shared helpers for the .corr QC correction files.

Monthly, index-based, comma-separated files with '#' comments::

    <base>/<variable>/YYYY/YYYYMM.corr    YYYYMMDD,start_idx,end_idx,flag

Temperature and relative humidity have separate variable folders; intervals
that apply to both (e.g. purge periods) are duplicated into each folder so a
file always states exactly what happens to its own variable.

Legacy daily YYYYMMDD.corr files, and lines without a flag column, are read
but never written.
"""

import os
from datetime import datetime

import numpy as np

FLAG_NOT_USED = 0
FLAG_GOOD = 1
FLAG_BAD = 2
FLAG_PURGE = 3
FLAG_RECOVERY = 4

# App-level variable key -> folder name
CORR_VARIABLES = {
    "temperature": "temperature",
    "rh": "relative_humidity",
}

# Variable key -> QC flag variable in the NetCDF files
QC_FLAG_VARIABLES = {
    "temperature": "qc_flag_air_temperature",
    "rh": "qc_flag_relative_humidity",
}


def _as_date(date):
    if isinstance(date, str):
        return datetime.strptime(date[:10].replace("-", ""), "%Y%m%d").date()
    return date.date() if isinstance(date, datetime) else date


def monthly_corr_path(base, variable, date):
    date = _as_date(date)
    return os.path.join(base, CORR_VARIABLES[variable],
                        f"{date.year:04d}", f"{date.strftime('%Y%m')}.corr")


def daily_corr_path(base, variable, date):
    date = _as_date(date)
    return os.path.join(base, CORR_VARIABLES[variable],
                        f"{date.year:04d}", f"{date.strftime('%Y%m%d')}.corr")


def find_corr_file(base, variable, date):
    """Return the existing monthly or legacy daily .corr path for a date."""
    monthly = monthly_corr_path(base, variable, date)
    if os.path.exists(monthly):
        return monthly
    daily = daily_corr_path(base, variable, date)
    if os.path.exists(daily):
        return daily
    return None


def parse_corr_line(line):
    """Parse one .corr line into (date_str or None, start_idx, end_idx, flag), or None."""
    line = line.split("#", 1)[0].strip()
    if not line:
        return None
    parts = [p.strip() for p in line.split(",") if p.strip()]
    if len(parts) not in (2, 3, 4):
        return None
    date_str = None
    offset = 0
    if len(parts) in (3, 4) and len(parts[0]) == 8 and parts[0].isdigit():
        date_str, offset = parts[0], 1
    try:
        start_idx = int(parts[offset])
        end_idx = int(parts[offset + 1])
        flag = int(parts[offset + 2]) if len(parts) == offset + 3 else FLAG_BAD
    except (ValueError, IndexError):
        return None
    return date_str, start_idx, end_idx, flag


def read_corr_file(path):
    """Return all (date_str or None, start_idx, end_idx, flag) records in a file."""
    records = []
    if not path or not os.path.exists(path):
        return records
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            parsed = parse_corr_line(raw)
            if parsed is not None:
                records.append(parsed)
    return records


def load_corr_intervals(base, variable, date):
    """Return list of (start_idx, end_idx, flag) for a date, or [] if no file."""
    date_str = _as_date(date).strftime("%Y%m%d")
    return [
        (start_idx, end_idx, flag)
        for line_date, start_idx, end_idx, flag in read_corr_file(find_corr_file(base, variable, date))
        if line_date is None or line_date == date_str
    ]


def save_corr_intervals(base, variable, date, intervals):
    """Replace a date's entries in its monthly .corr file, leaving other dates intact."""
    path = monthly_corr_path(base, variable, date)
    date_str = _as_date(date).strftime("%Y%m%d")

    records = [r for r in read_corr_file(path) if r[0] != date_str]
    records += [(date_str, s, e, flag) for s, e, flag in intervals]
    records.sort(key=lambda r: (r[0] or date_str, r[1], r[2]))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# YYYYMMDD,start_idx,end_idx,flag\n")
        for line_date, start_idx, end_idx, flag in records:
            f.write(f"{line_date or date_str},{start_idx},{end_idx},{flag}\n")
    return path


def qc_from_intervals(num_points, intervals, default_flag=FLAG_NOT_USED,
                      good_flag=FLAG_GOOD, source=""):
    """Build a QC flag array from .corr intervals.

    Samples not covered by any interval are set to good_flag, since the
    presence of a .corr file means the day has been reviewed.
    """
    qc = np.full(num_points, default_flag, dtype=np.int8)
    for start_idx, end_idx, flag in intervals:
        if start_idx > end_idx:
            raise ValueError(f"{source}: start_idx ({start_idx}) must be <= end_idx ({end_idx})")
        if start_idx < 0 or end_idx >= num_points:
            raise ValueError(
                f"{source}: interval {start_idx}:{end_idx} is outside 0:{num_points - 1}"
            )
        qc[start_idx:end_idx + 1] = np.int8(flag)
    qc[qc == np.int8(default_flag)] = np.int8(good_flag)
    return qc
