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
raw_data_base="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/legacy/cao-analog-format5_chilbolton/data/long-term/format5"

# Date range for the given year
start_date="${year}0825"
end_date="${year}1231"

# Activate conda environment
source ~/anaconda3/etc/profile.d/conda.sh  # or wherever your conda is installed
conda activate cao_3_11

current_date=$start_date
while [ "$current_date" -le "$end_date" ]; do

    YMD=$(date -d "$current_date" +%y%m%d)
    outdir="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1_f5/$year"

    mkdir -p "$outdir"

    # Calculate the previous day's date
    previous_date=$(date -d "$current_date - 1 day" +%Y%m%d)
    previous_year=$(date -d "$current_date - 1 day" +%Y)

    # Construct paths to the current and previous day's files
    infile="$raw_data_base/chan${YMD}.000"

    # Find metadata file from package installation
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    mfile="${script_dir}/metadata_f5.json"
    corr_file_oat="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/met_cao/data/long-term/corrections/oatnew_ch.corr"
    corr_file_rh="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/met_cao/data/long-term/corrections/rhnew_ch.corr"

    # Run the Python script
    python -c "from chilbolton_temperature_rh_utils.process_hmp155_f5 import main; import sys; sys.argv = ['process-hmp155-f5', '$infile', '-m', '$mfile', '-o', '$outdir']; main()"

        # Path to the generated NetCDF file
    ncfile="$outdir/ncas-temperature-rh-1_cao_${current_date}_surface-met_v1.0.nc"

    # Add QC flags for purge times
    if [ -f "$ncfile" ]; then
        if [ -z "$previous_ncfile" ]; then
            # No previous file for the first day
            python -c "from chilbolton_temperature_rh_utils.flag_purge_times import main; import sys; sys.argv = ['flag-hmp155-purge-times', '$ncfile', '--corr-file-temperature', '$corr_file_oat', '--corr-file-rh', '$corr_file_rh']; main()"
        else
            # Use the previous day's file for consistency checks
            python -c "from chilbolton_temperature_rh_utils.flag_purge_times import main; import sys; sys.argv = ['flag-hmp155-purge-times', '$ncfile', '--previous-file', '$previous_ncfile', '--corr-file-temperature', '$corr_file_oat', '--corr-file-rh', '$corr_file_rh']; main()"
        fi
        # Update the previous file to the current file
        previous_ncfile="$ncfile"
    else
        echo "Warning: NetCDF file $ncfile not found. Skipping QC flagging."
    fi

    current_date=$(date -d "$current_date + 1 day" +%Y%m%d)
done
