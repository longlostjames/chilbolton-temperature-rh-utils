#!/bin/bash

#SBATCH --partition=standard
#SBATCH --job-name=hmp155_corr_2024-2025
#SBATCH --time=02:00:00
#SBATCH --mem=4G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/hmp155_corr_2024-2025_%A_%a.out
#SBATCH --error=logs/hmp155_corr_2024-2025_%A_%a.err
#SBATCH --array=2024-2025
#SBATCH --account=chil_atmos
#SBATCH --qos=standard

# Apply HMP155 .corr QC flags to STFC NetCDF files for 2024 and 2025.

set -euo pipefail

source /home/users/cjwalden/miniforge3/etc/profile.d/conda.sh
conda activate cao_3_11

mkdir -p logs

REPO_ROOT=/home/users/cjwalden/git/chilbolton-temperature-rh-utils
GWS_ROOT=${GWS_ROOT:-/gws/ssde/j25a/chil_atmos}
CORR_DIR=${CORR_DIR:-${REPO_ROOT}/corrections}
OUTPUT_BASE=${GWS_ROOT}/processing/stfc-temperature-rh-1/20240401_longterm
YEAR=${SLURM_ARRAY_TASK_ID}

apply-hmp155-corr-files \
    --corr-dir "${CORR_DIR}" \
    --input_dir "${OUTPUT_BASE}" \
    --year "${YEAR}" \
    --start-date "${YEAR}-01-01" \
    --end-date "${YEAR}-12-31"
