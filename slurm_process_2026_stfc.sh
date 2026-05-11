#!/bin/bash

#SBATCH --partition=standard
#SBATCH --job-name=hmp155_stfc_2026
#SBATCH --time=24:00:00
#SBATCH --mem=16G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/hmp155_stfc_2026_%j.out
#SBATCH --error=logs/hmp155_stfc_2026_%j.err
#SBATCH --array=2026
#SBATCH --account=ncas_radar
#SBATCH --qos=standard

# Process HMP155 data from 2026 using STFC version

# Load conda environment
source /home/users/cjwalden/miniforge3/etc/profile.d/conda.sh
conda activate cao_3_11

# Create log directory if it doesn't exist
mkdir -p logs

# Set paths
RAW_DATA_BASE="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/met_cao/data/long-term/new_daily_split"
OUTPUT_BASE="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/20150415_long-term"
METADATA_FILE="/home/users/cjwalden/git/chilbolton-temperature-rh-utils/chilbolton_temperature_rh_utils/metadata_stfc.json"

# Process each year
process-hmp155-year-stfc \
    -y ${SLURM_ARRAY_TASK_ID} \
    --raw-data-base $RAW_DATA_BASE \
    --output-base $OUTPUT_BASE
    #--corr-file-temperature /home/users/cjwalden/git/chilbolton-temperature-rh-utils/correction_air_temperature.dat \
    #--corr-file-rh /home/users/cjwalden/git/chilbolton-temperature-rh-utils/correction_relative_humidity.dat
    

