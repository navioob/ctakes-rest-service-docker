from dotenv import load_dotenv
import json
import os
# Load environment variables from .env file
load_dotenv()

llm_credentials = {
    "GOOGLE_APPLICATION_CREDENTIALS": json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
    "GOOGLE_APPLICATION_SCOPES": [os.getenv("GOOGLE_APPLICATION_SCOPES")]
}