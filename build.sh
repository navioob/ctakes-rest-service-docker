#!/usr/bin/env bash
set -e

ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

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

echo "Starting snowstorm-lite..."
docker run -d -p 8083:8080 --name snowstorm-lite --network backend \
    -v snowstorm-lite-volume:/app/lucene-index \
    snomedinternational/snowstorm-lite --index.path=lucene-index/data --admin.password=admin

echo "Starting the API (builds+runs cne-api; MedCAT loads in-process on first request)..."
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
