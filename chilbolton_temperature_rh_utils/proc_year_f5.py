#!/usr/bin/env python3
"""Process a full year of HMP155 data from Format5."""

import argparse
import subprocess
import sys
from pathlib import Path

def main():
    """Execute the proc_year_f5.sh bash script."""
    parser = argparse.ArgumentParser(
        description="Process a full year of HMP155 data from legacy Format5.",
        epilog="""This command processes an entire year of Vaisala HMP155 temperature and 
relative humidity data from legacy Format5 binary files to CF-compliant NetCDF 
files with automated QC flagging."""
    )
    parser.add_argument("-y", "--year", required=True, type=int,
                        help="Year to process (e.g., 2018)")
    
    args = parser.parse_args()
    
    # Get the directory where this Python file is located
    script_dir = Path(__file__).parent
    bash_script = script_dir / "proc_year_f5.sh"
    
    if not bash_script.exists():
        print(f"Error: Script not found at {bash_script}", file=sys.stderr)
        sys.exit(1)
    
    # Execute the bash script with the year argument
    try:
        result = subprocess.run(
            ["bash", str(bash_script), "-y", str(args.year)],
            check=False
        )
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error executing script: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
