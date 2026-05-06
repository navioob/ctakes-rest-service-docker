## This script is used to refresh the SNOMED RF files
## Please make sure that the SNOMED Snowstorm is running on port 8080 and the SNOMED RF files are up to date
## Drop the Snomed RF archive in the snomed/data directory

import argparse
import os
import sys
import time

import requests


def _raise_for_json(response: requests.Response, context: str) -> dict:
    """Parse JSON or fail with status + body snippet."""
    response.raise_for_status()
    text = (response.text or "").strip()
    if not text:
        # Some endpoints might return 201/204 with no body
        return {}
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError as e:
        snippet = text[:800] + ("..." if len(text) > 800 else "")
        raise RuntimeError(
            f"{context}: expected JSON, got non-JSON (HTTP {response.status_code}). "
            f"Body starts with:\n{snippet}"
        ) from e


def create_import_job(base_url: str) -> str:
    """
    Create a new import job for the SNOMED RF files (Snowstorm POST /imports).
    Returns the job ID from the Location header.
    """
    url = f"{base_url.rstrip('/')}/imports"
    headers = {"Content-Type": "application/json"}
    body = {
        "branchPath": "MAIN",
        "createCodeSystemVersion": True,
        "type": "SNAPSHOT",
    }
    response = requests.post(url, headers=headers, json=body, timeout=120)
    response.raise_for_status()
    
    # Snowstorm returns the job URL in the Location header
    location = response.headers.get("location")
    if not location:
        raise RuntimeError("create_import_job: No 'location' header in response.")
    
    job_id = location.split("/")[-1]
    return job_id


def upload_archive(base_url: str, import_job_id: str, archive_path: str) -> None:
    """
    Upload the SNOMED RF archive to the import job.
    """
    url = f"{base_url.rstrip('/')}/imports/{import_job_id}/archive"
    with open(archive_path, "rb") as f:
        files = {"file": (os.path.basename(archive_path), f)}
        response = requests.post(url, files=files, timeout=600)
    response.raise_for_status()


def get_import_status(base_url: str, import_job_id: str) -> dict:
    """
    Get the status of an import job (Snowstorm GET /imports/{id}).
    """
    url = f"{base_url.rstrip('/')}/imports/{import_job_id}"
    headers = {"accept": "application/json"}
    response = requests.get(url, headers=headers, timeout=30)
    return _raise_for_json(response, "get_import_status")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snomed Snowstorm RF Refresh Script")
    parser.add_argument("--archive-path", type=str, required=True, help="Path to the SNOMED RF archive")
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8080",
        help="Snowstorm base URL (default: http://localhost:8080)",
    )
    args = parser.parse_args()

    print("Snomed Snowstorm RF Refresh Script initiated.")
    print(f"Snowstorm base URL: {args.base_url}")
    
    try:
        # 1. Create Job
        import_job_id = create_import_job(args.base_url)
        print(f"Import job created with ID: {import_job_id}")
        
        # 2. Upload
        print(f"Uploading archive: {args.archive_path}...")
        upload_archive(args.base_url, import_job_id, args.archive_path)
        print("Archive uploaded. Starting status polling (every 60s)...")

        # 3. Poll Status
        while True:
            job_info = get_import_status(args.base_url, import_job_id)
            status = job_info.get("status", "UNKNOWN")
            print(f"[{time.strftime('%H:%M:%S')}] Current Status: {status}")

            if status == "COMPLETED":
                print("SNOMED RF import completed successfully.")
                break
            elif status in ("FAILED", "ERROR"):
                print(f"Error: Import job {import_job_id} failed with status: {status}", file=sys.stderr)
                print(f"Full response: {job_info}", file=sys.stderr)
                sys.exit(1)
            
            # Wait 1 minute before checking again
            time.sleep(60)

    except (requests.exceptions.RequestException, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
