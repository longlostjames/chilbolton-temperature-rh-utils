#!/usr/bin/env python3
"""Process a full year of HMP155 data from Format5."""

import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta

from .process_hmp155_f5 import process_file
from .flag_purge_times import main as flag_purge_main


def main():
    """Process a full year of HMP155 data from Format5."""
    parser = argparse.ArgumentParser(
        description="Process a full year of HMP155 data from legacy Format5.",
        epilog="""This command processes an entire year of Vaisala HMP155 temperature and 
relative humidity data from legacy Format5 binary files to CF-compliant NetCDF 
files with automated QC flagging."""
    )
    parser.add_argument("-y", "--year", required=True, type=int,
                        help="Year to process (e.g., 2018)")
    parser.add_argument("--raw-data-base", type=str,
                        default="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/legacy/cao-analog-format5_chilbolton/data/long-term/format5",
                        help="Base directory for raw Format5 data")
    parser.add_argument("--output-base", type=str,
                        default="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1_f5",
                        help="Base directory for output NetCDF files")
    parser.add_argument("--corr-file-temperature", type=str,
                        default="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/met_cao/data/long-term/corrections/oatnew_ch.corr",
                        help="Correction file for air temperature")
    parser.add_argument("--corr-file-rh", type=str,
                        default="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/met_cao/data/long-term/corrections/rhnew_ch.corr",
                        help="Correction file for relative humidity")
    
    args = parser.parse_args()
    
    # Get metadata file from package installation
    script_dir = Path(__file__).parent
    metadata_file = script_dir / "metadata_f5.json"
    
    if not metadata_file.exists():
        print(f"Error: Metadata file not found at {metadata_file}", file=sys.stderr)
        sys.exit(1)
    
    # Date range for the given year
    start_date = datetime(args.year, 1, 1)
    end_date = datetime(args.year, 12, 31)
    
    current_date = start_date
    previous_ncfile = None
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        date_str_short = current_date.strftime("%y%m%d")
        
        # Create output directory
        outdir = Path(args.output_base) / str(args.year)
        outdir.mkdir(parents=True, exist_ok=True)
        
        # Construct input file path (Format5 uses YYMMDD format)
        infile = Path(args.raw_data_base) / f"chan{date_str_short}.000"
        
        if not infile.exists():
            print(f"Warning: Input file not found: {infile}")
            current_date += timedelta(days=1)
            continue
        
        # Generate NetCDF file
        try:
            process_file(str(infile), str(outdir), str(metadata_file))
        except Exception as e:
            print(f"Error processing {infile}: {e}", file=sys.stderr)
            current_date += timedelta(days=1)
            continue
        
        # Path to the generated NetCDF file
        ncfile = outdir / f"ncas-temperature-rh-1_cao_{date_str}_surface-met_v1.1.nc"
        
        # Add QC flags for purge times
        if ncfile.exists():
            try:
                # Build arguments for flag_purge_main
                flag_args = [
                    str(ncfile),
                    "--corr-file-temperature", args.corr_file_temperature,
                    "--corr-file-rh", args.corr_file_rh
                ]
                
                if previous_ncfile:
                    flag_args.extend(["--previous-file", str(previous_ncfile)])
                
                # Save original sys.argv and replace it
                original_argv = sys.argv
                sys.argv = ["flag-hmp155-purge-times"] + flag_args
                
                try:
                    flag_purge_main()
                finally:
                    sys.argv = original_argv
                
                previous_ncfile = ncfile
            except Exception as e:
                print(f"Error flagging {ncfile}: {e}", file=sys.stderr)
        else:
            print(f"Warning: NetCDF file {ncfile} not found. Skipping QC flagging.")
        
        # Move to the next day
        current_date += timedelta(days=1)
    
    print(f"\nProcessing complete for year {args.year}")


if __name__ == "__main__":
    main()
