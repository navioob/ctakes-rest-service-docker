#!/bin/bash

# Start FastAPI application in a Docker container

# Get the directory where the script is located (api directory)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( cd "${SCRIPT_DIR}/.." && pwd )"
cd "${SCRIPT_DIR}"

# Image and container names
IMAGE_NAME="cne-api"
CONTAINER_NAME="cne-api-container"
NETWORK_NAME="backend"
PORT=8082

# Host path to the downloaded MedCAT model pack (a directory, or a .zip -
# CAT.load_model_pack() handles either), mounted read-only into the
# container. Requires a UTS/UMLS-licensed download - see api/README.md.
# Defaults to <repo>/medcat_models/model_pack (gitignored - each clone drops
# its own copy there; deploy.sh copies it to the same repo-relative path on
# a remote server).
MEDCAT_MODEL_PACK_HOST_PATH="${MEDCAT_MODEL_PACK_HOST_PATH:-${ROOT_DIR}/medcat_models/model_pack}"

echo "Starting deployment of ${IMAGE_NAME}..."

# 1. Create network if it doesn't exist
if ! docker network ls | grep -q "${NETWORK_NAME}"; then
    echo "Creating network ${NETWORK_NAME}..."
    docker network create "${NETWORK_NAME}"
fi

# 2. Build the Docker image
echo "Building Docker image..."
docker build -t "${IMAGE_NAME}" .

# 3. Stop and remove existing container if it exists
if [ "$(docker ps -aq -f name=${CONTAINER_NAME})" ]; then
    echo "Stopping and removing existing container..."
    docker stop "${CONTAINER_NAME}" >/dev/null 2>&1
    docker rm "${CONTAINER_NAME}" >/dev/null 2>&1
fi

# 4. Run the Docker container
echo "Running Docker container on port ${PORT}..."
# We use the .env file from the root directory
# We also attach it to the specified network
docker run -d \
    --name "${CONTAINER_NAME}" \
    --network "${NETWORK_NAME}" \
    -p "${PORT}:8082" \
    --env-file "${ROOT_DIR}/.env" \
    -v "${MEDCAT_MODEL_PACK_HOST_PATH}:/models/model_pack:ro" \
    --restart unless-stopped \
    "${IMAGE_NAME}"

echo "--------------------------------------------------"
echo "Clinical Notes Enhancer API started successfully!"
echo "Container: ${CONTAINER_NAME}"
echo "Port: ${PORT}"
echo "Network: ${NETWORK_NAME}"
echo "--------------------------------------------------"
echo "To view logs: docker logs -f ${CONTAINER_NAME}"
echo "To stop: docker stop ${CONTAINER_NAME}"
