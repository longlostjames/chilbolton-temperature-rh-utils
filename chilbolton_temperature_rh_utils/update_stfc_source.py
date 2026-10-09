#!/usr/bin/env python3
"""
Update the source attribute in STFC NetCDF files.

Changes source from "Chilbolton Temperature and Humidity Sensor unit 1"
to "STFC Temperature and Humidity Sensor unit 1", and updates the
history and last_revised_date global attributes accordingly.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from netCDF4 import Dataset


OLD_SOURCE = "Chilbolton Temperature and Humidity Sensor unit 1"
NEW_SOURCE = "STFC Temperature and Humidity Sensor unit 1"

STFC_FILE_PATTERN = "stfc-temperature-rh-1_cao_*_surface-met_*.nc"


def update_source(filename, dry_run=False, verbose=False):
    """
    Update the source attribute in a single STFC NetCDF file.

    Parameters
    ----------
    filename : str or Path
        Path to the NetCDF file to update.
    dry_run : bool
        If True, report what would be changed without modifying the file.
    verbose : bool
        If True, print details even when no change is needed.

    Returns
    -------
    bool
        True if the file was (or would be) updated, False if no change needed.
    """
    filename = Path(filename)

    with Dataset(filename, mode='r') as ds:
        current_source = ds.getncattr('source') if 'source' in ds.ncattrs() else ''

    if current_source != OLD_SOURCE:
        if verbose:
            print(f"  Skipping (source is already '{current_source}')")
        return False

    if dry_run:
        print(f"  Would update source attribute (dry run)")
        return True

    # Update attributes in-place using netCDF4 (avoids any time re-encoding)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    history_entry = (
        f"{now} - Updated source attribute from '{OLD_SOURCE}' "
        f"to '{NEW_SOURCE}' using update-stfc-source"
    )

    with Dataset(filename, mode='r+') as ds:
        ds.setncattr('source', NEW_SOURCE)
        existing_history = ds.getncattr('history') if 'history' in ds.ncattrs() else ''
        if existing_history:
            ds.setncattr('history', f"{history_entry}\n{existing_history}")
        else:
            ds.setncattr('history', history_entry)
        ds.setncattr('last_revised_date', now)

    print(f"  Updated source, history, and last_revised_date")
    return True


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Update the source attribute in STFC temperature/RH NetCDF files. "
            "Changes '{}' to '{}'.".format(OLD_SOURCE, NEW_SOURCE)
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
        help="Print details for every file, including those skipped.",
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
            changed = update_source(nc_file, dry_run=args.dry_run, verbose=args.verbose)
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
