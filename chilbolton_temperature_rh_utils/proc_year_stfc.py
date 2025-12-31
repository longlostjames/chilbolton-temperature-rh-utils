#!/usr/bin/env python3
"""Process a full year of HMP155 data from STFC variant."""

import subprocess
import sys
from pathlib import Path

def main():
    """Execute the proc_year_stfc.sh bash script."""
    # Get the directory where this Python file is located
    script_dir = Path(__file__).parent
    bash_script = script_dir / "proc_year_stfc.sh"
    
    if not bash_script.exists():
        print(f"Error: Script not found at {bash_script}", file=sys.stderr)
        sys.exit(1)
    
    # Execute the bash script, passing all command-line arguments
    try:
        result = subprocess.run(
            ["bash", str(bash_script)] + sys.argv[1:],
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
