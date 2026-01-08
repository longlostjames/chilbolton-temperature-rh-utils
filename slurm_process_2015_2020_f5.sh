#!/bin/bash

#SBATCH --partition=standard
#SBATCH --job-name=hmp155_f5_2015-2020
#SBATCH --time=24:00:00
#SBATCH --mem=16G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/hmp155_f5_2015-2020_%j.out
#SBATCH --error=logs/hmp155_f5_2015-2020_%j.err
#SBATCH --array=2015-2020
#SBATCH --account=ncas_radar
#SBATCH --qos=standard

# Process HMP155 data from 2015-2020 using Format5 version

# Load conda environment
source /home/users/cjwalden/miniforge3/etc/profile.d/conda.sh
conda activate cao_3_11

# Create log directory if it doesn't exist
mkdir -p logs

# Set paths
RAW_DATA_BASE="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/legacy/cao-analog-format5_chilbolton/data/long-term/format5/"
OUTPUT_BASE="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1c"
METADATA_FILE="/home/users/cjwalden/git/chilbolton-temperature-rh-utils/chilbolton_temperature_rh_utils/metadata_f5.json"

# Process each year
process-hmp155-year-f5 \
    -y ${SLURM_ARRAY_TASK_ID} \
    --raw-data-base $RAW_DATA_BASE \
    --output-base $OUTPUT_BASE
    #--corr-file-temperature /home/users/cjwalden/git/chilbolton-temperature-rh-utils/correction_air_temperature.dat \
    #--corr-file-rh /home/users/cjwalden/git/chilbolton-temperature-rh-utils/correction_relative_humidity.dat
    