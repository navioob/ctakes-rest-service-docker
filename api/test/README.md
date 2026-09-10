# API Test Script

This directory contains test scripts for the Clinical Notes Enhancer API.

## Usage

### Basic Usage

```bash
cd api/test
python test_api.py
```

### With Environment Variables

```bash
# Set base URL (default: http://localhost:8082)
export API_BASE_URL=http://localhost:8082

# Set bearer token for authentication
export API_BEARER_TOKEN=your-token-here

# Run tests
python test_api.py
```

### One-liner

```bash
API_BASE_URL=http://localhost:8082 API_BEARER_TOKEN=your-token python api/app/test/test_api.py
```

## Tested Endpoints

The script tests the following endpoints sequentially:

1. **GET /** - Root endpoint
2. **GET /health** - Health check endpoint
3. **POST /generate/note** - Generate clinical note summary
4. **POST /generate/terms** - Generate SNOMED-CT terms (full pipeline)
5. **GET /generate/medcat/health** - MedCAT health check

Also see `test_medcat_mapping.py` - an offline, no-server-required self-check
for the MedCAT type_id -> category mapping logic (`python test_medcat_mapping.py`).

## Output

The script provides:
- Color-coded output (green for success, red for errors)
- Detailed response information
- Summary of all test results
- Exit code 0 if all tests pass, 1 if any fail

## Requirements

- `requests` library
- Python 3.6+

Install dependencies:
```bash
pip install requests
```

