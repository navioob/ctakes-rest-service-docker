# cTAKES REST Service through Docker

This repository provides an easy Dockerized setup extension for the Apache cTAKES REST service by [Go Team Epsilon](https://github.com/GoTeamEpsilon/ctakes-rest-service), enabling natural language processing (NLP) of clinical text. The service runs on Apache Tomcat and uses MySQL for data storage, with all dependencies bundled in a Docker image.

## Prerequisites

To use this service, you need Docker installed on your system. The service requires at least 5GB of RAM and sufficient disk space (approximately 10-15GB) for the image and build process.

### Install Docker

1. **Install Docker**:
   - **macOS**:
     - Download and install Docker Desktop from [Docker Hub](https://www.docker.com/products/docker-desktop/).
     - Follow the installation instructions and ensure Docker Desktop is running.
   - **Linux**:
     - Install Docker using your package manager. For Ubuntu:
       ```bash
       sudo apt-get update
       sudo apt-get install -y docker.io
       sudo systemctl start docker
       sudo systemctl enable docker
       ```
     - Add your user to the `docker` group to run Docker without `sudo`:
       ```bash
       sudo usermod -aG docker $USER
       ```
       Log out and back in for the group change to take effect.
   - **Windows**:
     - Install Docker Desktop with WSL 2 backend from [Docker Hub](https://www.docker.com/products/docker-desktop/).
     - Ensure WSL 2 is enabled and follow the setup instructions.

2. **Verify Docker Installation**:
   Run the following command to confirm Docker is installed and running:
   ```bash
   docker --version
   ```
   You should see output like `Docker version 20.x.x, build xxxxxxx`.

3. **Ensure Sufficient Disk Space**:
   Check available disk space:
   ```bash
   df -h
   ```
   Ensure at least 15GB is free. On macOS, verify Docker Desktop’s disk allocation:
   - Open Docker Desktop > **Preferences** > **Resources** > **Advanced**.
   - Set the disk image size to at least 128GB **if needed**.

## Building the Docker Image

1. **Navigate to the Repository Directory**:
   Ensure you are in the root directory of the repository containing the `Dockerfile`:
   ```bash
   cd /path/to/ctakes-rest-service-docker
   ```

2. **Build the Docker Image**:
   Run the following command to build the Docker image:
   ```bash
   docker build -t ctakes-rest-service .
   ```
   **Note**: The build process may take several hours due to the loading of large SQL data files and Maven dependencies. Ensure your system has internet access and sufficient resources (5GB RAM, 15GB disk).

3. **Verify the Image**:
   Check that the image was created successfully:
   ```bash
   docker images
   ```
   You should see `ctakes-rest-service` listed with the `latest` tag.

## Running the Service

1. **Run the Docker Container**:
   Start the container with the following command:
   ```bash
   docker run -d --name ctakes-rest -p 8080:8080 --memory=5g ctakes-rest-service
   ```
   - `-d`: Runs the container in detached mode.
   - `--name ctakes-rest`: Names the container.
   - `-p 8080:8080`: Maps port 8080 on your host to port 8080 in the container.
   - `--memory=5g`: Allocates 5GB of RAM to the container.

2. **Verify the Container is Running**:
   Check the container status:
   ```bash
   docker ps
   ```
   You should see `ctakes-rest` listed. If it’s not running, check logs for errors:
   ```bash
   docker logs ctakes-rest
   ```

3. **Access the Service**:
   - **Web Interface**: Open a browser and navigate to:
     ```
     http://localhost:8080/ctakes-web-rest/index.jsp
     ```
   - **API**: Test the service with a cURL command:
     ```bash
     curl -X POST 'http://localhost:8080/ctakes-web-rest/service/analyze?pipeline=Default' -d 'Patient has hypertension'
     ```
   - **Tomcat Logs**: View real-time logs for debugging:
     ```bash
     docker exec -it ctakes-rest tail -f /opt/tomcat/latest/logs/catalina.out
     ```

## Troubleshooting

- **Build Fails**:
  - Ensure you have internet access to download dependencies from `https://svn.apache.org` and `http://repository.apache.org/snapshots`.
  - Check disk space and RAM availability.
  - Review build logs for specific errors:
    ```bash
    docker logs <build-container-id>
    ```
  - If Maven dependency errors occur, try cleaning the build environment and rebuilding:
    ```bash
    docker system prune -a
    docker build -t ctakes-rest-service .
    ```

- **Container Fails to Start**:
  - Check container logs:
    ```bash
    docker logs ctakes-rest
    ```
  - Ensure port 8080 is not in use by another process:
    ```bash
    lsof -i :8080
    ```
  - Verify sufficient memory allocation (5GB).

- **Platform Compatibility**:
  - The image is built for ARM64 (e.g., Apple M1/M2). For AMD64 systems, you may need to rebuild the image or use a multi-architecture image. Contact the repository maintainer for assistance.

## Sharing the Image

To share the built image with teammates without requiring them to rebuild:

1. **Export the Image**:
   ```bash
   docker save -o ctakes-rest-service.tar ctakes-rest-service:latest
   ```
   Compress the file to reduce size:
   ```bash
   gzip ctakes-rest-service.tar
   ```

2. **Share the File**:
   Transfer `ctakes-rest-service.tar.gz` via cloud storage (e.g., Google Drive, Dropbox), SFTP, or a USB drive:
   ```bash
   scp ctakes-rest-service.tar.gz user@remote-server:/path/to/destination
   ```

3. **Teammates Import the Image**:
   Instruct teammates to:
   - Decompress the file:
     ```bash
     gunzip ctakes-rest-service.tar.gz
     ```
   - Import the image:
     ```bash
     docker load -i ctakes-rest-service.tar
     ```
   - Run the container as described above.

Alternatively, push the image to a container registry (e.g., Docker Hub):
```bash
docker tag ctakes-rest-service:latest yourusername/ctakes-rest-service:latest
docker login
docker push yourusername/ctakes-rest-service:latest
```
Teammates can pull it:
```bash
docker pull yourusername/ctakes-rest-service:latest
```

## Notes

- The service requires significant resources due to cTAKES’s processing demands. Ensure your system meets the requirements.
- For production use, consider configuring additional security settings for MySQL and Tomcat.
- If you encounter issues, check the [Apache cTAKES documentation](https://cwiki.apache.org/confluence/display/CTAKES) or open an issue in this repository.