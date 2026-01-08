#!/bin/bash

#SBATCH --partition=standard
#SBATCH --job-name=hmp155_main_2020-2024
#SBATCH --time=24:00:00
#SBATCH --mem=16G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/hmp155_main_2020-2024_%j.out
#SBATCH --error=logs/hmp155_main_2020-2024_%j.err
#SBATCH --array=2020-2024
#SBATCH --account=ncas_radar
#SBATCH --qos=standard

# Process HMP155 data from 2020-2024 using main version

# Load conda environment
source /home/users/cjwalden/miniforge3/etc/profile.d/conda.sh
conda activate cao_3_11

# Debug: show Python and package version
echo "Python: $(which python)"
echo "Command: $(which process-hmp155-year)"
echo "Package version: $(python -c 'import chilbolton_temperature_rh_utils; print(chilbolton_temperature_rh_utils.__version__)' 2>&1)"
echo "Working directory: $(pwd)"
echo "Processing year: ${SLURM_ARRAY_TASK_ID}"

# Create log directory if it doesn't exist
mkdir -p logs

# Set paths
RAW_DATA_BASE="/gws/pw/j07/ncas_obs_vol2/cao/raw_data/met_cao/data/long-term"
OUTPUT_BASE="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1d"
METADATA_FILE="/home/users/cjwalden/git/chilbolton-temperature-rh-utils/chilbolton_temperature_rh_utils/metadata.json"

# Process each year
echo "Starting processing for year ${SLURM_ARRAY_TASK_ID}..."
process-hmp155-year \
    -y ${SLURM_ARRAY_TASK_ID} \
    --raw-data-base $RAW_DATA_BASE \
    --output-base $OUTPUT_BASE
    #--corr-file-temperature /home/users/cjwalden/git/chilbolton-temperature-rh-utils/correction_air_temperature.dat \
    #--corr-file-rh /home/users/cjwalden/git/chilbolton-temperature-rh-utils/correction_relative_humidity.dat

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "Successfully completed year ${SLURM_ARRAY_TASK_ID}"
else
    echo "ERROR: Process exited with code $EXIT_CODE for year ${SLURM_ARRAY_TASK_ID}"
    exit $EXIT_CODE
fi
