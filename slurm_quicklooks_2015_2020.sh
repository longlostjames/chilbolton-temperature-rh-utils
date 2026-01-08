#!/bin/bash

#SBATCH --partition=standard
#SBATCH --job-name=hmp155_quicklooks_2015-2020
#SBATCH --time=04:00:00
#SBATCH --mem=8G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/hmp155_quicklooks_%A_%a.out
#SBATCH --error=logs/hmp155_quicklooks_%A_%a.err
#SBATCH --array=2016
#SBATCH --account=ncas_radar
#SBATCH --qos=standard

# Generate quicklook plots for HMP155 data from 2015-2020

# Load conda environment
source /home/users/cjwalden/miniforge3/etc/profile.d/conda.sh
conda activate cao_3_11

# Create log directory if it doesn't exist
mkdir -p logs

# Set paths
INPUT_DIR="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1c/"
OUTPUT_DIR="/gws/pw/j07/ncas_obs_vol2/cao/processing/ncas-temperature-rh-1/data/long-term/level1c/quicklooks/"

# Create output directory if it doesn't exist
mkdir -p $OUTPUT_DIR

# Process year from array task ID
YEAR=${SLURM_ARRAY_TASK_ID}

echo "Generating quicklooks for year $YEAR..."
make-hmp155-quicklooks -y $YEAR -i $INPUT_DIR -o $OUTPUT_DIR

if [ $? -eq 0 ]; then
    echo "Successfully generated quicklooks for year $YEAR"
else
    echo "Error generating quicklooks for year $YEAR"
fi
