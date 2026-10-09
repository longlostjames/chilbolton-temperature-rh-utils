#!/bin/bash

#SBATCH --partition=standard
#SBATCH --job-name=hmp155_train_ensemble
#SBATCH --time=06:00:00
#SBATCH --mem=8G
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --array=0-4
#SBATCH --output=logs/hmp155_train_ensemble_%A_%a.out
#SBATCH --error=logs/hmp155_train_ensemble_%A_%a.err
#SBATCH --account=chil_atmos
#SBATCH --qos=standard

# Train an ensemble of 5 1D U-Net models in parallel on SLURM (LOTUS)

set -euo pipefail

source /home/users/cjwalden/miniforge3/etc/profile.d/conda.sh
conda activate cao_3_11

mkdir -p logs checkpoints

REPO_ROOT=/home/users/cjwalden/git/chilbolton-temperature-rh-utils
CORR_DIR=${CORR_DIR:-${REPO_ROOT}/corrections}
export PROJ_LIB=/home/users/cjwalden/miniforge3/envs/cao_3_11/share/proj
export PYTHONUNBUFFERED=1

TASK_ID=${SLURM_ARRAY_TASK_ID}
SEED=$((42 + TASK_ID))
MODEL_NAME="unet1d_ensemble_fold${TASK_ID}.pt"

echo "Task ${TASK_ID}: Training ensemble model with Seed ${SEED} -> ${MODEL_NAME}"

python -m chilbolton_temperature_rh_utils.ml.train \
    --nc-roots /badc/ncas-cao/data/ncas-temperature-rh-1/20150415_longterm/v1.1 \
               /gws/ssde/j25a/chil_atmos/processing/stfc-temperature-rh-1/20240401_longterm \
    --corr-dir "${CORR_DIR}" \
    --train-years 2018 2019 2020 2021 2022 2023 \
    --val-years 2024 \
    --epochs 20 \
    --batch-size 32 \
    --seed "${SEED}" \
    --model-name "${MODEL_NAME}" \
    --output-dir checkpoints
