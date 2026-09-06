#!/usr/bin/env bash

set -e

# Ensure docker network 'backend' exists
if ! docker network inspect backend >/dev/null 2>&1; then
    echo "Creating docker network: backend"
    docker network create backend
fi

# Function to stop and remove existing container if present
stop_and_remove() {
    local name="$1"
    if docker ps -a --format '{{.Names}}' | grep -Eq "^${name}$"; then
        echo "Stopping and removing existing container: ${name}..."
        docker rm -f "${name}" >/dev/null
    fi
}

echo "Cleaning up existing containers if running..."
stop_and_remove "ctakes-rest-service"
stop_and_remove "clinical-notes-enhancer"
stop_and_remove "snowstorm-lite"

echo "Starting services..."

echo "Starting ctakes-rest-service..."
docker run -d -p 8080:8080 --memory=5g --name ctakes-rest-service --network backend ctakes-rest-service:latest

echo "Starting clinical-notes-enhancer..."
docker run -d --name clinical-notes-enhancer -p 8081:8081 --network backend clinical-notes-enhancer:latest

echo "Starting snowstorm-lite..."
docker run -d -p 8083:8080 --name snowstorm-lite --network backend -v snowstorm-lite-volume:/app/lucene-index snomedinternational/snowstorm-lite --index.path=lucene-index/data --admin.password=admin

echo "All services started successfully!"
