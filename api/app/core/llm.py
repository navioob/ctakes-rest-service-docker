from google import genai
from google.generativeai import types
from google.genai import types
from google.oauth2 import service_account
from .config import llm_credentials

# Initialize the Google GenAI client
# This client is used for all LLM calls (Gemini 3 Flash Preview)
# It uses Vertex AI when vertexai=True is set
llm_client = genai.Client(
    project=llm_credentials['GOOGLE_APPLICATION_CREDENTIALS'].get("project_id"),
    credentials=service_account.Credentials.from_service_account_info(
        llm_credentials['GOOGLE_APPLICATION_CREDENTIALS'],
        scopes=llm_credentials['GOOGLE_APPLICATION_SCOPES']
    ),
    location="global",
    vertexai=True
)
