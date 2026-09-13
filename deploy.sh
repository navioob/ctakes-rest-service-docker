#!/usr/bin/env bash
set -e

#remeber to activate the vpn first
# Edit these before running.
REMOTE_USER="ubuntu"
REMOTE_HOST="13.212.153.112"
REMOTE_REPO_PATH="/home/ubuntu/ctakes-rest-service-docker"

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Repo-relative on both ends - matches api/start.sh's default
# (<repo>/medcat_models/model_pack), so no MEDCAT_MODEL_PACK_HOST_PATH
# override is needed on the server either.
LOCAL_MODEL_PACK_PATH="${ROOT_DIR}/medcat_models/model_pack"
REMOTE_MODEL_PACK_PATH="${REMOTE_REPO_PATH}/medcat_models/model_pack"

# Repo-relative SNOMED CT RF2 archive(s) - drop your licensed archive in
# scripts/snomed/data/ locally (gitignored), same path used by
# scripts/snomed/snomed_rf_refresh.py for onboarding.
LOCAL_SNOMED_DATA_PATH="${ROOT_DIR}/scripts/snomed/data"
REMOTE_SNOMED_DATA_PATH="${REMOTE_REPO_PATH}/scripts/snomed/data"

echo "Copying MedCAT model pack..."
ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p $(dirname "${REMOTE_MODEL_PACK_PATH}")"
scp -r "${LOCAL_MODEL_PACK_PATH}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_MODEL_PACK_PATH}"

if [ -d "${LOCAL_SNOMED_DATA_PATH}" ] && [ -n "$(ls -A "${LOCAL_SNOMED_DATA_PATH}" 2>/dev/null)" ]; then
    echo "Copying SNOMED CT RF2 archive(s)..."
    ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p $(dirname "${REMOTE_SNOMED_DATA_PATH}")"
    scp -r "${LOCAL_SNOMED_DATA_PATH}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_SNOMED_DATA_PATH}"
else
    echo "No local SNOMED CT archive found at ${LOCAL_SNOMED_DATA_PATH}, skipping."
fi

echo "Copying .env..."
scp "${ROOT_DIR}/.env" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_REPO_PATH}/.env"

echo "Done. On the server: cd ${REMOTE_REPO_PATH} && ./build.sh"
echo "Then onboard SNOMED into Snowstorm: python scripts/snomed/snomed_rf_refresh.py --archive-path <path-under-scripts/snomed/data> --base-url http://localhost:8083"
