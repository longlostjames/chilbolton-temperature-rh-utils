#!/bin/bash

#SBATCH --partition=standard
#SBATCH --job-name=hmp155_stfc_2024-2025
#SBATCH --time=24:00:00
#SBATCH --mem=16G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/hmp155_stfc_2024-2025_%j.out
#SBATCH --error=logs/hmp155_stfc_2024-2025_%j.err
#SBATCH --array=2024-2025
#SBATCH --account=chil_atmos
#SBATCH --qos=standard

# Process HMP155 data from 2024-2025 using STFC version

# Load conda environment
source /home/users/cjwalden/miniforge3/etc/profile.d/conda.sh
conda activate cao_3_11

# Create log directory if it doesn't exist
mkdir -p logs

# Set paths
GWS_ROOT=${GWS_ROOT:-/gws/ssde/j25a/chil_atmos}
RAW_DATA_BASE=${GWS_ROOT}/raw_data/met_cao/data/long-term/new_daily_split
OUTPUT_BASE=${GWS_ROOT}/processing/stfc-temperature-rh-1/20240401_longterm
METADATA_FILE="/home/users/cjwalden/git/chilbolton-temperature-rh-utils/chilbolton_temperature_rh_utils/metadata_stfc.json"


# Process each year
process-hmp155-year-stfc \
    -y ${SLURM_ARRAY_TASK_ID} \
    --raw-data-base $RAW_DATA_BASE \
    --output-base $OUTPUT_BASE
    #--corr-file-temperature /home/users/cjwalden/git/chilbolton-temperature-rh-utils/correction_air_temperature.dat \
    #--corr-file-rh /home/users/cjwalden/git/chilbolton-temperature-rh-utils/correction_relative_humidity.dat
    
