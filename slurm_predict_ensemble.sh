#!/bin/bash

#SBATCH --partition=standard
#SBATCH --job-name=hmp155_predict_ensemble
#SBATCH --time=01:00:00
#SBATCH --mem=4G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --array=2015-2026
#SBATCH --output=logs/hmp155_predict_%A_%a.out
#SBATCH --error=logs/hmp155_predict_%A_%a.err
#SBATCH --account=chil_atmos
#SBATCH --qos=standard

# Run 5-model 1D U-Net ensemble inference in parallel per year on SLURM (LOTUS)

set -euo pipefail

source /home/users/cjwalden/miniforge3/etc/profile.d/conda.sh
conda activate cao_3_11

mkdir -p logs

REPO_ROOT=/home/users/cjwalden/git/chilbolton-temperature-rh-utils
CORR_DIR=${CORR_DIR:-${REPO_ROOT}/corrections}
export PROJ_LIB=/home/users/cjwalden/miniforge3/envs/cao_3_11/share/proj
export PYTHONUNBUFFERED=1

YEAR=${SLURM_ARRAY_TASK_ID}

echo "Running 5-model ensemble inference for Year ${YEAR}..."

python -m chilbolton_temperature_rh_utils.ml.predict \
    --checkpoint checkpoints/unet1d_ensemble_fold0.pt \
                 checkpoints/unet1d_ensemble_fold1.pt \
                 checkpoints/unet1d_ensemble_fold2.pt \
                 checkpoints/unet1d_ensemble_fold3.pt \
                 checkpoints/unet1d_ensemble_fold4.pt \
    --input /badc/ncas-cao/data/ncas-temperature-rh-1/20150415_longterm/v1.1/${YEAR} \
            /gws/ssde/j25a/chil_atmos/processing/stfc-temperature-rh-1/20240401_longterm/${YEAR} \
            /gws/ssde/j25a/chil_atmos/processing/stfc-temperature-rh-1/20240401_longterm/latest-no-qc/${YEAR} \
    --corr-dir "${CORR_DIR}"
