#!/usr/bin/env python3
"""
Update the time:units attribute in STFC NetCDF files.

Sets time:units to "seconds since 1970-01-01 00:00:00" (the form required by
CF conventions) and updates the history and last_revised_date global attributes.
The time values themselves are not changed.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from netCDF4 import Dataset


CORRECT_UNITS = "seconds since 1970-01-01 00:00:00"

STFC_FILE_PATTERN = "stfc-temperature-rh-1_cao_*_surface-met_*.nc"


def update_time_units(filename, dry_run=False, verbose=False):
    """
    Update time:units in a single NetCDF file to the full CF-compliant form.

    Parameters
    ----------
    filename : str or Path
        Path to the NetCDF file.
    dry_run : bool
        If True, report what would change without modifying the file.
    verbose : bool
        If True, print details for every file including those skipped.

    Returns
    -------
    bool
        True if the file was (or would be) updated, False if no change needed.
    """
    filename = Path(filename)

    with Dataset(filename, mode='r') as ds:
        if 'time' not in ds.variables:
            if verbose:
                print("  Skipping (no time variable)")
            return False
        current_units = ds.variables['time'].units if hasattr(ds.variables['time'], 'units') else ''

    if current_units == CORRECT_UNITS:
        if verbose:
            print(f"  Skipping (units already '{CORRECT_UNITS}')")
        return False

    if dry_run:
        print(f"  Would update time:units from '{current_units}' to '{CORRECT_UNITS}' (dry run)")
        return True

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    history_entry = (
        f"{now} - Corrected time:units from '{current_units}' "
        f"to '{CORRECT_UNITS}' using update-stfc-time-units"
    )

    with Dataset(filename, mode='r+') as ds:
        time_var = ds.variables['time']

        time_var.setncattr('units', CORRECT_UNITS)
        time_var.setncattr('standard_name', 'time')
        time_var.setncattr('long_name', 'Time (seconds since 1970-01-01 00:00:00)')
        time_var.setncattr('axis', 'T')

        # Refresh valid_min / valid_max from the stored data values
        data = time_var[:]
        if len(data) > 0:
            time_var.setncattr('valid_min', float(data.min()))
            time_var.setncattr('valid_max', float(data.max()))

        # Update global attributes
        existing_history = ds.getncattr('history') if 'history' in ds.ncattrs() else ''
        if existing_history:
            ds.setncattr('history', f"{history_entry}\n{existing_history}")
        else:
            ds.setncattr('history', history_entry)

        ds.setncattr('last_revised_date', now)

    print(f"  Updated time:units, history, and last_revised_date")
    return True


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Correct time:units in STFC temperature/RH NetCDF files to "
            f"'{CORRECT_UNITS}'. The time values are not modified."
        ),
        epilog=(
            "Specify one or more directories to search recursively, "
            "or provide explicit NetCDF file paths."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="PATH",
        help="One or more NetCDF files or directories to process.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be changed without modifying any files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print details for every file, including those already correct.",
    )

    args = parser.parse_args()

    nc_files = []
    for path_str in args.paths:
        p = Path(path_str)
        if p.is_dir():
            nc_files.extend(sorted(p.rglob(STFC_FILE_PATTERN)))
        elif p.is_file() and p.suffix == ".nc":
            nc_files.append(p)
        else:
            print(f"Warning: '{p}' is not a file or directory, skipping.", file=sys.stderr)

    if not nc_files:
        print("No STFC NetCDF files found.", file=sys.stderr)
        sys.exit(1)

    updated = 0
    skipped = 0

    for nc_file in nc_files:
        print(f"Processing: {nc_file}")
        try:
            changed = update_time_units(nc_file, dry_run=args.dry_run, verbose=args.verbose)
            if changed:
                updated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Error processing {nc_file}: {e}", file=sys.stderr)
            skipped += 1

    action = "Would update" if args.dry_run else "Updated"
    print(f"\n{action} {updated} file(s); skipped {skipped} file(s).")


if __name__ == "__main__":
    main()
