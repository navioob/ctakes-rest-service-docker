#!/usr/bin/env bash
set -e

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SNOMED_DATA_DIR="${ROOT_DIR}/scripts/snomed/data"
SNOWSTORM_HOST_URL="http://localhost:8083"

# Ensure docker network 'backend' exists
if ! docker network inspect backend >/dev/null 2>&1; then
    echo "Creating docker network: backend"
    docker network create backend
fi

for name in snowstorm-lite cne-gui-container; do
    if docker ps -a --format '{{.Names}}' | grep -Eq "^${name}\$"; then
        echo "Stopping and removing existing container: ${name}..."
        docker rm -f "${name}" >/dev/null
    fi
done

# Also catch any leftover container holding one of our ports under a
# different name (e.g. a pre-rename "clinical-notes-enhancer") - a stale
# container by name is one thing, but a port bind failure kills the whole
# script partway through, so check by port too.
for port in 8081 8082 8083; do
    for name in $(docker ps -a --filter "publish=${port}" --format '{{.Names}}'); do
        echo "Stopping and removing container holding port ${port}: ${name}..."
        docker rm -f "${name}" >/dev/null
    done
done

echo "Starting snowstorm-lite..."
docker run -d -p 8083:8080 --name snowstorm-lite --network backend \
    -v snowstorm-lite-volume:/app/lucene-index \
    snomedinternational/snowstorm-lite --index.path=lucene-index/data --admin.password=admin

echo "Waiting for snowstorm-lite to come up..."
for i in $(seq 1 60); do
    if curl -sf -o /dev/null "${SNOWSTORM_HOST_URL}/fhir/CodeSystem"; then
        break
    fi
    sleep 3
    if [ "$i" -eq 60 ]; then
        echo "ERROR: snowstorm-lite didn't respond after 3 minutes." >&2
        exit 1
    fi
done

# Data survives across container recreation (named volume), so only onboard
# if this is genuinely a fresh volume with nothing loaded yet.
echo "Checking whether SNOMED CT is already loaded into Snowstorm..."
EXPAND_RESPONSE="$(curl -s "${SNOWSTORM_HOST_URL}/fhir/ValueSet/\$expand?url=http://snomed.info/sct?fhir_vs&count=1")"
if echo "${EXPAND_RESPONSE}" | grep -q '"contains"'; then
    echo "SNOMED CT already loaded, skipping onboarding."
else
    ARCHIVE_PATH="$(find "${SNOMED_DATA_DIR}" -maxdepth 1 -name '*.zip' 2>/dev/null | head -n1)"
    if [ -n "${ARCHIVE_PATH}" ]; then
        echo "Nothing loaded yet - onboarding ${ARCHIVE_PATH}..."
        python3 "${ROOT_DIR}/scripts/snomed/snomed_rf_refresh.py" \
            --archive-path "${ARCHIVE_PATH}" \
            --base-url "${SNOWSTORM_HOST_URL}"
    else
        echo "WARNING: no SNOMED CT loaded and no archive found in ${SNOMED_DATA_DIR} - Snowstorm will stay empty until you onboard one manually." >&2
    fi
fi

echo "Starting the API (builds+runs cne-api)..."
"${ROOT_DIR}/api/start.sh"

echo "Building and starting the GUI..."
(
    cd "${ROOT_DIR}/gui"
    docker build -t cne-gui .
    docker run -d \
        --name cne-gui-container \
        --network backend \
        -p 8081:8081 \
        --env-file "${ROOT_DIR}/.env" \
        -e API_BASE_URL="http://cne-api-container:8082" \
        --restart unless-stopped \
        cne-gui
)

echo "--------------------------------------------------"
echo "Stack up:"
echo "  snowstorm-lite      -> http://localhost:8083"
echo "  cne-api-container   -> http://localhost:8082"
echo "  cne-gui-container   -> http://localhost:8081"
echo "--------------------------------------------------"
