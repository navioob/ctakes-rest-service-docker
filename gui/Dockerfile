# Use a Python base image suitable for Streamlit
# We use a slim-buster image for a smaller footprint
FROM python:3.11-slim-buster

# 1. Set the working directory inside the container
WORKDIR /app

# 2. Copy the required files and directories
# Copy main application files and configuration
COPY . .

# 3. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 4. Set Streamlit to run on the specified port (8081)
# Streamlit runs on port 8501 by default, but we'll tell it to use 8081
# Note: This is the internal container port.
ENV STREAMLIT_SERVER_PORT=8081
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# 5. Expose the port where Streamlit will listen
# This is the internal container port (8081)
EXPOSE 8081

# 6. Run the Streamlit application
# We use 'CMD' to run the app. The '--server.port' flag ensures it runs on 8081.
CMD ["streamlit", "run", "main.py", "--server.port", "8081"]