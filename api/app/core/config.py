from dotenv import load_dotenv
import os

# Load environment variables from .env file at the start of the application
load_dotenv(override=True)

# Configuration for the OpenAI-compatible LLM endpoint
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID")

# Snowstorm Configuration
SNOWSTORM_URL = os.getenv("SNOWSTORM_URL")
SNOWSTORM_BRANCH = os.getenv("SNOWSTORM_BRANCH")