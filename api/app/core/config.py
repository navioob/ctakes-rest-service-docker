from dotenv import load_dotenv
import json
import os
import ast

# Load environment variables from .env file at the start of the application
load_dotenv(override=True)

# Configuration for Google LLM (Gemini/Vertex AI)
# GOOGLE_APPLICATION_CREDENTIALS should contain the JSON string of the service account key
# GOOGLE_APPLICATION_SCOPES should contain the required OAuth scopes
llm_credentials = {
    "GOOGLE_APPLICATION_CREDENTIALS": ast.literal_eval(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
    "GOOGLE_APPLICATION_SCOPES": [(os.getenv("GOOGLE_APPLICATION_SCOPES"))]
}

# Snowstorm Configuration
SNOWSTORM_URL = os.getenv("SNOWSTORM_URL")
SNOWSTORM_BRANCH = os.getenv("SNOWSTORM_BRANCH")