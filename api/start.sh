#!/bin/bash

# Start FastAPI application with Gunicorn
# Using 8 workers with Uvicorn worker class

# Get the directory where the script is located (api directory)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}"

# Gunicorn configuration
WORKERS=8
HOST="0.0.0.0"
PORT=8082
WORKER_CLASS="uvicorn.workers.UvicornWorker"
APP_MODULE="app.main:app"
LOG_FILE="${SCRIPT_DIR}/app/nohup.out"
PID_FILE="${SCRIPT_DIR}/app/gunicorn.pid"

# Start with nohup
nohup gunicorn \
    -w ${WORKERS} \
    -k ${WORKER_CLASS} \
    --bind ${HOST}:${PORT} \
    --pid ${PID_FILE} \
    --access-logfile - \
    --error-logfile - \
    ${APP_MODULE} > ${LOG_FILE} 2>&1 &

# Save the PID
echo $! > ${PID_FILE}

echo "CTakes REST Service API application started with Gunicorn"
echo "Workers: ${WORKERS}"
echo "Host: ${HOST}"
echo "Port: ${PORT}"
echo "PID: $(cat ${PID_FILE})"
echo "Log file: ${LOG_FILE}"
echo "To stop: kill $(cat ${PID_FILE})"

