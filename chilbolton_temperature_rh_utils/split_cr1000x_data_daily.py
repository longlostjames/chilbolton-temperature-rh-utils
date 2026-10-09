"""
# Split Campbell Scientific CR1000X data files into daily files
"""

import pandas as pd
from pathlib import Path
import argparse
import csv

try:
    from . import __version__
except ImportError:
    __version__ = "unknown"

def count_daily_data_rows(file_path):
    """Count data rows in a split daily file (excluding the 4-line TOA5 header)."""
    with open(file_path, 'r', encoding='utf-8') as f:
        line_count = sum(1 for _ in f)
    return max(line_count - 4, 0)


def split_file(input_file, output_dir, delimiter, timestamp_column, output_prefix, verbose=False):
    # === LOCATE TOA5 HEADER BLOCK ROBUSTLY ===
    with open(input_file, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()

    toa5_start = None
    for idx, line in enumerate(all_lines):
        first_token = line.split(delimiter, 1)[0].strip().strip('"').upper()
        if first_token == 'TOA5':
            toa5_start = idx
            break

    if toa5_start is None or len(all_lines) < toa5_start + 4:
        print(f"ERROR: Could not find a valid 4-line TOA5 header block in {input_file}")
        return

    header_lines = all_lines[toa5_start:toa5_start + 4]

    # Parse column names from the second TOA5 header line.
    column_names = [
        c.strip().strip('"')
        for c in next(csv.reader([header_lines[1]], delimiter=delimiter, quotechar='"'))
    ]

    # === LOAD DATAFRAME ===
    df = pd.read_csv(
        input_file,
        skiprows=toa5_start + 4,
        delimiter=delimiter,
        quotechar='"',
        low_memory=False,
        header=None,
        names=column_names
    )
    df.columns = df.columns.str.strip().str.replace('"', '')

    if timestamp_column not in df.columns:
        print(f"ERROR: Timestamp column '{timestamp_column}' not found in columns: {df.columns.tolist()}")
        return

    # Parse timestamps with explicit format (CR1000X typical format: YYYY-MM-DD HH:MM:SS)
    df[timestamp_column] = pd.to_datetime(df[timestamp_column], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    df = df.dropna(subset=[timestamp_column])

    # === SHIFT MIDNIGHT TO PREVIOUS DAY ===
    timestamps = df[timestamp_column]
    adjusted_dates = timestamps.dt.date.where(
        timestamps.dt.time != pd.to_datetime("00:00:00").time(),
        timestamps.dt.date - pd.Timedelta(days=1)
    )
    df['group_date'] = adjusted_dates

    # === WRITE DAILY FILES WITH HEADER IN YYYY/YYYYMM SUBDIRS ===
    for date, group in df.groupby('group_date'):
        date_obj = pd.to_datetime(date)
        year_str = date_obj.strftime('%Y')
        ym_str = date_obj.strftime('%Y%m')
        ymd_str = date_obj.strftime('%Y%m%d')
        out_subdir = Path(output_dir) / year_str / ym_str
        out_subdir.mkdir(parents=True, exist_ok=True)
        out_file = out_subdir / f"{output_prefix}_{ymd_str}.dat"

        candidate_rows = len(group)
        if out_file.exists():
            existing_rows = count_daily_data_rows(out_file)
            if candidate_rows <= existing_rows:
                if verbose:
                    print(
                        f"Skipping {out_file}: existing file has {existing_rows} rows; "
                        f"candidate from {Path(input_file).name} has {candidate_rows} rows."
                    )
                continue
            if verbose:
                print(
                    f"Replacing {out_file}: existing file has {existing_rows} rows; "
                    f"candidate from {Path(input_file).name} has {candidate_rows} rows."
                )

        # Convert timestamp column to string (no extra quotes)
        group = group.copy()
        group[timestamp_column] = group[timestamp_column].dt.strftime('%Y-%m-%d %H:%M:%S')

        # Write the 4-line TOA5 header
        with open(out_file, 'w', encoding='utf-8', newline='') as f:
            f.writelines(header_lines)
            group.drop(columns='group_date').to_csv(
                f,
                index=False,
                header=False,  # Don't write header - already in header_lines
                quoting=csv.QUOTE_MINIMAL,
                quotechar='"'
            )
        if verbose:
            print(f"Saved: {out_file}")

def main():
    """CLI entry point for split-cr1000x-data-daily command."""
    parser = argparse.ArgumentParser(description="Split CR1000X_Chilbolton_Rxcabinmet1*.dat files into daily files in YYYY/YYYYMM subdirectories, keeping the most complete daily file where overlaps exist.")
    parser.add_argument("-i", "--input_dir", required=True, help="Directory containing CR1000X_Chilbolton_Rxcabinmet1*.dat files")
    parser.add_argument("-o", "--output_dir", default="daily_files", help="Directory to write daily files (default: daily_files)")
    parser.add_argument("-d", "--delimiter", default=",", help="Delimiter for input file (default: ',')")
    parser.add_argument("-t", "--timestamp_column", default="TIMESTAMP", help="Name of timestamp column (default: TIMESTAMP)")
    parser.add_argument("-p", "--output_prefix", default="CR1000XSeries_Chilbolton_Rxcabinmet1", help="Output filename prefix for daily files (default: CR1000XSeries_Chilbolton_Rxcabinmet1)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = args.output_dir

    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")

    # Process both CR1000X naming variants with case-insensitive matching
    # so files like RXcabinmet1 and Rxcabinmet1 are both included.
    input_files = {
        path for path in input_dir.glob("*.dat")
        if path.name.lower().startswith("cr1000x_chilbolton_rxcabinmet1")
        or path.name.lower().startswith("cr1000xseries_chilbolton_rxcabinmet1")
    }

    if not input_files:
        print("No matching CR1000X cabin met files found in input directory.")
        return

    for input_file in sorted(input_files):
        print(f"Processing {input_file}")
        split_file(str(input_file), output_dir, args.delimiter, args.timestamp_column, args.output_prefix, args.verbose)


if __name__ == "__main__":
    main()