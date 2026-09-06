#!/usr/bin/env python3
"""
Test script for CTakes REST Service API endpoints.
Tests all endpoints sequentially.
"""

import requests
import json
import sys
import os
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path to import app modules if needed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8082")
BEARER_TOKEN = os.getenv("API_BEARER_TOKEN", "")

# Test data
TEST_CLINICAL_TEXT = """Swollen LL, limited mobility, pain and redness over R LL. Possible PE post THR and TKR. 

IV Streptokinase stat

IV NS 500ml run fast

SC Clean 200U stat

Refer to IR for possible embolectomy"""


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")


def print_success(message: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print an error message."""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_info(message: str):
    """Print an info message."""
    print(f"{Colors.YELLOW}ℹ {message}{Colors.RESET}")


def get_headers() -> Dict[str, str]:
    """Get request headers with authentication."""
    headers = {"Content-Type": "application/json"}
    if BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {BEARER_TOKEN}"
    else:
        print_info("No bearer token provided - requests may fail if auth is required")
    return headers


def test_root_endpoint() -> bool:
    """Test the root endpoint."""
    print_header("Testing Root Endpoint (GET /)")
    try:
        response = requests.get(f"{BASE_URL}/", headers=get_headers(), timeout=10)
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Root endpoint working: {data.get('message', 'N/A')}")
            print(f"Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print_error(f"Root endpoint failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Error testing root endpoint: {str(e)}")
        return False


def test_health_endpoint() -> bool:
    """Test the health endpoint."""
    print_header("Testing Health Endpoint (GET /health)")
    try:
        response = requests.get(f"{BASE_URL}/health", headers=get_headers(), timeout=10)
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Health endpoint working: {data.get('status', 'N/A')}")
            print(f"Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print_error(f"Health endpoint failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Error testing health endpoint: {str(e)}")
        return False


def test_generate_note_endpoint() -> Tuple[bool, Optional[str]]:
    """Test the generate note endpoint."""
    print_header("Testing Generate Note Endpoint (POST /generate/note)")
    try:
        payload = {"text": TEST_CLINICAL_TEXT}
        response = requests.post(
            f"{BASE_URL}/generate/note",
            headers=get_headers(),
            json=payload,
            timeout=240  # Longer timeout for LLM processing
        )
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print_success("Generate note endpoint working")
            generated_text = data.get('text', '')
            print(f"Generated Summary (first 200 chars): {generated_text[:200]}...")
            return True, generated_text
        else:
            print_error(f"Generate note endpoint failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False, None
    except Exception as e:
        print_error(f"Error testing generate note endpoint: {str(e)}")
        return False, None


def test_generate_terms_endpoint(text) -> bool:
    """Test the generate terms endpoint."""
    print_header("Testing Generate Terms Endpoint (POST /generate/terms)")
    try:
        payload = {"text": text}
        response = requests.post(
            f"{BASE_URL}/generate/terms",
            headers=get_headers(),
            json=payload,
            timeout=300  # Pipeline now includes LLM summary + cTAKES + Snowstorm
        )
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            terms = data.get("terms", {})
            print_success("Generate terms endpoint working")
            
            # Count terms by category
            total = 0
            for category in ["anatomical_sites", "procedures", "symptoms", "medications"]:
                count = len(terms.get(category, []))
                total += count
                if count > 0:
                    print(f"  {category}: {count} terms")
            
            # diagnosis is a nested object, not a flat list
            diagnosis = terms.get("diagnosis", {})
            comm = len(diagnosis.get("communicable_disease", []))
            non_comm = len(diagnosis.get("non_communicable_disease", []))
            if comm > 0:
                print(f"  diagnosis (communicable): {comm} terms")
            if non_comm > 0:
                print(f"  diagnosis (non-communicable): {non_comm} terms")
            total += comm + non_comm
            
            print(f"Total terms extracted: {total}")
            print(f"Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print_error(f"Generate terms endpoint failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Error testing generate terms endpoint: {str(e)}")
        return False


def test_ctakes_health_endpoint() -> bool:
    """Test the cTAKES health endpoint."""
    print_header("Testing cTAKES Health Endpoint (GET /generate/ctakes/health)")
    try:
        response = requests.get(
            f"{BASE_URL}/generate/ctakes/health",
            headers=get_headers(),
            timeout=60  # Longer timeout for cTAKES processing
        )
        print_info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            alive = data.get("alive", False)
            total_terms = data.get("total_terms", 0)
            
            if alive:
                print_success(f"cTAKES is ALIVE - Status: {status}, Terms: {total_terms}")
            else:
                print_error(f"cTAKES is NOT RESPONDING - Status: {status}, Terms: {total_terms}")
            
            print(f"Response: {json.dumps(data, indent=2)}")
            return alive
        else:
            print_error(f"cTAKES health endpoint failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Error testing cTAKES health endpoint: {str(e)}")
        return False


def main():
    """Run all tests sequentially."""
    print_header("CTakes REST Service API Test Suite")
    print_info(f"Base URL: {BASE_URL}")
    print_info(f"Bearer Token: {f'{BEARER_TOKEN[0:10]}***' if BEARER_TOKEN else 'Not provided'}")
    
    # Test root and health endpoints first
    root_result = test_root_endpoint()
    health_result = test_health_endpoint()
    
    # Test generate note endpoint and capture the generated text
    note_success, generated_note = test_generate_note_endpoint()
    
    # Use generated note for terms generation, fallback to original text if note generation failed
    if note_success and generated_note:
        print_info("Using generated note as input for term generation")
        terms_text = generated_note
    else:
        print_info("Note generation failed, using original clinical text for term generation")
        terms_text = TEST_CLINICAL_TEXT
    
    # Test generate terms endpoint with the selected text
    terms_result = test_generate_terms_endpoint(terms_text)
    
    # Test cTAKES health endpoint
    ctakes_health_result = test_ctakes_health_endpoint()
    
    results = {
        "root": root_result,
        "health": health_result,
        "generate_note": note_success,
        "generate_terms": terms_result,
        "ctakes_health": ctakes_health_result,
    }
    
    # Summary
    print_header("Test Summary")
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    failed_tests = total_tests - passed_tests
    
    for test_name, result in results.items():
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"{test_name:20} {status}")
    
    print(f"\n{Colors.BOLD}Total: {total_tests} | Passed: {Colors.GREEN}{passed_tests}{Colors.RESET} | Failed: {Colors.RED}{failed_tests}{Colors.RESET}{Colors.RESET}")
    
    # Exit with appropriate code
    sys.exit(0 if failed_tests == 0 else 1)


if __name__ == "__main__":
    main()

