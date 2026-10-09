#!/usr/bin/env bash

set -euo pipefail

# Wrapper to process one specific STFC CR1000X HMP155 date (UTC), e.g. 20260607.
# Usage:
#   ./cron_process_single_date_stfc.sh 20260607
#   DATE_UTC=20260607 ./cron_process_single_date_stfc.sh
# Optional overrides via environment variables:
#   CONDA_SH, CONDA_ENV, GWS_ROOT, RSYNC_SOURCE, RSYNC_DEST, SPLIT_INPUT_BASE,
#   RAW_DATA_BASE, OUTPUT_BASE, LOG_DIR, METADATA_FILE

CONDA_SH=${CONDA_SH:-/home/users/cjwalden/miniforge3/etc/profile.d/conda.sh}
CONDA_ENV=${CONDA_ENV:-cao_3_11}
GWS_ROOT=${GWS_ROOT:-/gws/ssde/j25a/chil_atmos}
RSYNC_SOURCE=${RSYNC_SOURCE:-chobs_data:/data/range/mirror_grape_loggernet/CR1000X*.dat}
RSYNC_DEST=${RSYNC_DEST:-${GWS_ROOT}/raw_data/cao-surface-met/long-term/loggernet/}
SPLIT_INPUT_BASE=${SPLIT_INPUT_BASE:-${RSYNC_DEST}}
RAW_DATA_BASE=${RAW_DATA_BASE:-${GWS_ROOT}/raw_data/met_cao/data/long-term/new_daily_split}
OUTPUT_BASE=${OUTPUT_BASE:-${GWS_ROOT}/processing/stfc-temperature-rh-1/20240401_longterm}
OUTPUT_SUBDIR=${OUTPUT_SUBDIR:-latest-no-qc}
LOG_DIR=${LOG_DIR:-${GWS_ROOT}/processing/stfc-temperature-rh-1/20240401_longterm/logs}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
METADATA_FILE=${METADATA_FILE:-${SCRIPT_DIR}/chilbolton_temperature_rh_utils/metadata_stfc.json}

TARGET_DATE=${1:-${DATE_UTC:-}}

if [[ -z "${TARGET_DATE}" ]]; then
    echo "Usage: $0 YYYYMMDD" >&2
    echo "Example: $0 20260607" >&2
    exit 1
fi

if [[ ! "${TARGET_DATE}" =~ ^[0-9]{8}$ ]]; then
    echo "ERROR: Date must be in YYYYMMDD format, got '${TARGET_DATE}'" >&2
    exit 1
fi

if ! date -u -d "${TARGET_DATE}" +%Y%m%d >/dev/null 2>&1; then
    echo "ERROR: Invalid date '${TARGET_DATE}'" >&2
    exit 1
fi

YEAR=$(date -u -d "${TARGET_DATE}" +%Y)
YEAR_MONTH=$(date -u -d "${TARGET_DATE}" +%Y%m)

mkdir -p "${LOG_DIR}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG_FILE="${LOG_DIR}/hmp155_stfc_single_date_${TARGET_DATE}_${STAMP}.log"

if [[ ! -f "${CONDA_SH}" ]]; then
    echo "ERROR: conda init script not found at ${CONDA_SH}" >&2
    exit 1
fi

if command -v flock >/dev/null 2>&1; then
    LOCK_FILE="/tmp/hmp155_stfc_single_date.lock"
    exec 9>"${LOCK_FILE}"
    if ! flock -n 9; then
        echo "Another single-date run is already in progress; exiting." | tee -a "${LOG_FILE}"
        exit 0
    fi
fi

{
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting STFC single-date processing"
    echo "TARGET_DATE=${TARGET_DATE}"
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

    INFILE="${RAW_DATA_BASE}/${YEAR}/${YEAR_MONTH}/CR1000XSeries_Chilbolton_Rxcabinmet1_${TARGET_DATE}.dat"
    OUTDIR="${OUTPUT_BASE}/${OUTPUT_SUBDIR}/${YEAR}"

    mkdir -p "${OUTDIR}"

    if [[ ! -f "${INFILE}" ]]; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: Missing input file ${INFILE}"
        exit 1
    fi

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Processing ${TARGET_DATE}"
    process-hmp155-stfc "${INFILE}" -o "${OUTDIR}" -m "${METADATA_FILE}"

    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Completed successfully"
} >>"${LOG_FILE}" 2>&1

echo "Run complete. Log: ${LOG_FILE}"
