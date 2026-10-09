#!/usr/bin/env bash

#set -euo pipefail

# Cron-friendly wrapper to process STFC CR1000X HMP155 data for yesterday and today (UTC).
# Optional overrides via environment variables:
#   CONDA_SH, CONDA_ENV, GWS_ROOT, RSYNC_SOURCE, RSYNC_DEST, SPLIT_INPUT_BASE,
#   RAW_DATA_BASE, OUTPUT_BASE, LOG_DIR, METADATA_FILE

CONDA_SH=${CONDA_SH:-/home/users/cjwalden/miniforge3/etc/profile.d/conda.sh}
CONDA_ENV=${CONDA_ENV:-cao_3_11}
GWS_ROOT=${GWS_ROOT:-/gws/ssde/j25a/chil_atmos}
RSYNC_SOURCE=${RSYNC_SOURCE:-betty:/data/range/mirror_grape_loggernet/CR1000X*.dat}
RSYNC_DEST=${RSYNC_DEST:-${GWS_ROOT}/raw_data/cao-surface-met/long-term/loggernet/}
# Directory containing unsplit CR1000X source files from rsync.
SPLIT_INPUT_BASE=${SPLIT_INPUT_BASE:-${RSYNC_DEST}}
# Directory containing split daily files in YYYY/YYYYMM subdirectories.
RAW_DATA_BASE=${RAW_DATA_BASE:-${GWS_ROOT}/raw_data/met_cao/data/long-term/new_daily_split}
OUTPUT_BASE=${OUTPUT_BASE:-${GWS_ROOT}/processing/stfc-temperature-rh-1/20240401_longterm}
OUTPUT_SUBDIR=${OUTPUT_SUBDIR:-latest-no-qc}
LOG_DIR=${LOG_DIR:-${GWS_ROOT}/processing/stfc-temperature-rh-1/20240401_longterm/logs}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
METADATA_FILE=${METADATA_FILE:-${SCRIPT_DIR}/chilbolton_temperature_rh_utils/metadata_stfc.json}

mkdir -p "${LOG_DIR}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="${LOG_DIR}/hmp155_stfc_today_yesterday_${STAMP}.log"

if [[ ! -f "${CONDA_SH}" ]]; then
    echo "ERROR: conda init script not found at ${CONDA_SH}" >&2
    exit 1
fi

if command -v flock >/dev/null 2>&1; then
    LOCK_FILE="/tmp/hmp155_stfc_today_yesterday.lock"
    exec 9>"${LOCK_FILE}"
    if ! flock -n 9; then
        echo "Another run is already in progress; exiting." | tee -a "${LOG_FILE}"
        exit 0
    fi
fi

{
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting STFC daily gap-catchup processing"
    echo "GWS_ROOT=${GWS_ROOT}"
    echo "RSYNC_SOURCE=${RSYNC_SOURCE}"
    echo "RSYNC_DEST=${RSYNC_DEST}"
    echo "SPLIT_INPUT_BASE=${SPLIT_INPUT_BASE}"
    echo "RAW_DATA_BASE=${RAW_DATA_BASE}"
    echo "OUTPUT_BASE=${OUTPUT_BASE}"
    echo "OUTPUT_SUBDIR=${OUTPUT_SUBDIR}"
    echo "METADATA_FILE=${METADATA_FILE}"

    # shellcheck source=/dev/null
    source "${CONDA_SH}"
    conda activate "${CONDA_ENV}"

    if ! command -v rsync >/dev/null 2>&1; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: rsync command not found"
        exit 1
    fi

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Running rsync from logger host"
    mkdir -p "${RSYNC_DEST}"
    rsync -avz "${RSYNC_SOURCE}" "${RSYNC_DEST}"

    if ! command -v split-cr1000x-data-daily >/dev/null 2>&1; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: split-cr1000x-data-daily command not found"
        exit 1
    fi

    if ! command -v process-hmp155-stfc >/dev/null 2>&1; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: process-hmp155-stfc command not found"
        exit 1
    fi

    if [[ ! -d "${SPLIT_INPUT_BASE}" ]]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: Split source directory missing ${SPLIT_INPUT_BASE}"
        exit 1
    fi

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Running split for ${SPLIT_INPUT_BASE}"
    split-cr1000x-data-daily -i "${SPLIT_INPUT_BASE}" -o "${RAW_DATA_BASE}"

    for DAYS_AGO in 1 0; do
        DATE_UTC=$(date -u -d "${DAYS_AGO} day ago" +%Y%m%d)
        YEAR=$(date -u -d "${DAYS_AGO} day ago" +%Y)
        YEAR_MONTH=$(date -u -d "${DAYS_AGO} day ago" +%Y%m)

        INFILE="${RAW_DATA_BASE}/${YEAR}/${YEAR_MONTH}/CR1000XSeries_Chilbolton_Rxcabinmet1_${DATE_UTC}.dat"
        OUTDIR="${OUTPUT_BASE}/${OUTPUT_SUBDIR}/${YEAR}"

        mkdir -p "${OUTDIR}"

        if [[ ! -f "${INFILE}" ]]; then
            echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] WARNING: Missing input file ${INFILE}; skipping"
            continue
        fi

        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Processing ${DATE_UTC}"
        process-hmp155-stfc "${INFILE}" -o "${OUTDIR}" -m "${METADATA_FILE}"
    done

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Completed successfully"
} >>"${LOG_FILE}" 2>&1

echo "Run complete. Log: ${LOG_FILE}"
