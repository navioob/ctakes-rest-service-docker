# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# spaCy tokenizer model required by the MedCAT SNOMED CT model pack
RUN python -m spacy download en_core_web_md

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 8082

# Define environment variable
ENV PYTHONUNBUFFERED=1

# Command to run the application using Gunicorn with Uvicorn workers.
# ponytail: single worker trades away concurrency for a fixed multi-GB-per-worker
# RAM cost (each prefork worker loads its own copy of the MedCAT model pack).
# Revisit with gunicorn --preload + more workers if throughput becomes the bottleneck.
CMD ["gunicorn", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8082", "app.main:app"]
