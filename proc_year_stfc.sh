#!/bin/bash

# Default values
year=""

# Parse command line options
while getopts "y:" opt; do
    case $opt in
        y) year="$OPTARG" ;;
        *)  
            echo "Usage: $0 -y <year>"
            exit 1
            ;;
    esac
done

# Check if year is provided
if [ -z "$year" ]; then
    echo "Error: Year (-y) is required."
    echo "Usage: $0 -y <year>"
    exit 1
fi

# Base directory for raw data
raw_data_base="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/met_cao/data/long-term"

# Date range for the given year
start_date="${year}0101"
end_date="${year}1231"

# Activate conda environment
source ~/anaconda3/etc/profile.d/conda.sh  # or wherever your conda is installed
conda activate cao_3_11

current_date=$start_date
previous_ncfile=""  # Initialize variable to store the previous day's NetCDF file

while [ "$current_date" -le "$end_date" ]; do

    YM=$(date -d "$current_date" +%Y%m)
    outdir="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1/$year"

    mkdir -p "$outdir"

    # Construct paths to the current day's files
    infile="$raw_data_base/$year/$YM/CR1000XSeries_Chilbolton_Rxcabinmet1_${current_date}.dat"
    # Find metadata file from package installation
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    mfile="${script_dir}/metadata_stfc.json"

    # Generate NetCDF file
    process-hmp155-stfc "$infile" -m "$mfile" -o "$outdir"

    # Path to the generated NetCDF file
    ncfile="$outdir/stfc-temperature-rh-1_cao_${current_date}_surface-met_v1.0.nc"

    # Add QC flags for purge times
    if [ -f "$ncfile" ]; then
        if [ -z "$previous_ncfile" ]; then
            # No previous file for the first day
            flag-hmp155-purge-times "$ncfile"
        else
            # Use the previous day's file for consistency checks
            flag-hmp155-purge-times "$ncfile" --previous-file "$previous_ncfile"
        fi
        # Update the previous file to the current file
        previous_ncfile="$ncfile"
    else
        echo "Warning: NetCDF file $ncfile not found. Skipping QC flagging."
    fi

    # Move to the next day
    current_date=$(date -d "$current_date + 1 day" +%Y%m%d)
done
