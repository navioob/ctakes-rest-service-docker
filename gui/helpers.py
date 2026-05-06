import requests
import json
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# FastAPI Service Configuration
# This assumes the FastAPI service is running on port 8082
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8082")
# If authentication is required, add the token to .env or use a default
API_TOKEN = os.getenv("API_BEARER_TOKEN", "")

def get_headers():
    headers = {
        "Content-Type": "application/json"
    }
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    return headers

def generate_summary(doctors_text):
    """
    Calls the FastAPI /generate/note endpoint to refine clinical notes.
    """
    url = f"{API_BASE_URL}/generate/note"
    payload = {"text": doctors_text}
    
    try:
        response = requests.post(url, headers=get_headers(), json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("text")
    except Exception as e:
        print(f"Error calling generate_summary API: {e}")
        return None

def generate_terms_full_pipeline(clinical_text):
    """
    Calls the FastAPI /generate/terms endpoint to get the full SNOMED-CT extraction 
    and validation pipeline results.
    """
    url = f"{API_BASE_URL}/generate/terms"
    payload = {"text": clinical_text}
    
    try:
        response = requests.post(url, headers=get_headers(), json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("terms")
    except Exception as e:
        print(f"Error calling generate_terms API: {e}")
        return None

# These functions are kept for compatibility with main.py but simplified
# to use the new centralized API logic.

def generate_tags(doctors_text):
    """
    In the latest process, this is part of the generate_terms_full_pipeline.
    We return the summary as a bridge for the GUI flow.
    """
    return generate_summary(doctors_text)

def parse_ctakes_to_json(summary_text):
    """
    No longer needed for parsing raw cTAKES, as the API handles it.
    Returns the summary text to be used in the next step.
    """
    return summary_text

def filter_tags(clinical_text, unused_tags=None):
    """
    Calls the new centralized API to get the validated and enriched tags.
    """
    return generate_terms_full_pipeline(clinical_text)