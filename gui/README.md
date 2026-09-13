# 🩺 Clinical Note Enhancer

A Streamlit application that transforms raw clinical notes into professionally articulated summaries and extracts SNOMED-CT codes via the `api/` service (LLM-based, OpenAI-compatible).

## ✨ Features

- **Clinical Note Processing**: Transform abbreviated clinical notes into structured, professional summaries
- **SNOMED-CT Code Extraction**: Automatically extract and map medical concepts to SNOMED-CT codes via the `api/` service (LLM-backed)
- **Term Mapping**: Convert SNOMED-CT codes to human-readable terms using official SNOMED-CT Snapshot files
- **Interactive UI**: Badge-style display of extracted codes with term-code pairing
- **Dark/Light Mode Support**: Responsive design that adapts to Streamlit themes
- **Medical Abbreviation Expansion**: Handles common medical abbreviations (DM, HPT, od, bd, etc.)

## 📋 Prerequisites

Before running the application, ensure you have the following:

### 1. Python Environment
- **Python 3.8+** (recommended: Python 3.10 or 3.11)
- **pip** package manager

### 2. External Services
- **`api/` service**: reachable from the GUI — `http://localhost:8082` when both run on the host, or `http://cne-api-container:8082` when both run as containers on the shared `backend` Docker network (see `api/README.md` for setup, including the OpenAI-compatible LLM and Snowstorm). The API itself needs `OPENAI_API_BASE`/`OPENAI_API_KEY`/`OPENAI_MODEL_ID` — the GUI has no LLM credentials of its own, it only calls the API over HTTP.

## 🛠️ Installation

### Step 1: Install Python Dependencies
Install all required Python packages from the root directory:

```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- `streamlit` - Web application framework
- `requests` - HTTP client for the `api/` service
- `streamlit-authenticator` - login/session handling
- `python-dotenv` - Environment variable management

### Step 2: Setup Environment Variables
The GUI reads these from `.env` (root `.env` when run via `./build.sh`, or
`gui/.env` when run standalone):

```bash
# .env file
API_BASE_URL=http://localhost:8082
API_BEARER_TOKEN=<matches the api/ service's API_BEARER_TOKEN>
```

### Step 3: Download SNOMED-CT Snapshot Files
Download the required SNOMED-CT files (requires valid license):

1. **Description File**: `sct2_Description_Snapshot_InternationalRF2_PRODUCTION_*.txt`
2. **Concept File**: `sct2_Concept_Snapshot_InternationalRF2_PRODUCTION_*.txt`

**Sources:**
- [SNOMED International](https://www.snomed.org/) (requires license)
- [UMLS](https://www.nlm.nih.gov/research/umls/) (via NLM license)

**Setup:**
1. Create a `data/` directory in the , or just place the file in the root.
2. Update file paths in `helpers.py`:
   ```python
   SNOMED_DESC_FILE = "data/snomed/sct2_Description_Snapshot_InternationalRF2_PRODUCTION_20250131T120000Z.txt"
   ```

### Step 4: Start the `api/` Service
1. **Verify Service**: Ensure the API is running and healthy: `curl http://localhost:8082/health` (see `api/README.md` for full setup, including Snowstorm).

## 🚀 Running the Application

### Containerized (recommended)
From the repository root: `./build.sh` builds and runs the GUI alongside
Snowstorm and the API, wired to reach the API over the `backend` Docker
network. Open `http://localhost:8081`.

### Standalone (local Streamlit)
From the `gui/` directory, with `API_BASE_URL` pointing at a running API:

```bash
streamlit run main.py
```

The application will open in your default browser at `http://localhost:8501`.

### Test with Sample Data
Use these test inputs to verify functionality:

**Diagnosis Text:**
```
J45 - Asthma^^^^^^E119 - Type 2 diabetes mellitus without complications^^^^^^I10 - Essential (primary) hypertension
```

**Symptoms Text:**
```
U/C asthma h/o allergic rhinitis since 2019 DM HPT currently: t salbutamol 100mcg inhaler prn t budesonide 200mcg inhaler bd t metformin 850mg bd t amlodipine 5mg od BP DXT stable no active complaints
```

**Prescription Text:**
```
101 | Salbutamol 100mcg Inhaler | UoM: INHALER | ^^^^^^102 | Budesonide 200mcg Inhaler | UoM: INHALER | ^^^^^^281 | Metformin 850mg Tablet | UoM: TABLET | ^^^^^^301 | Amlodipine 5mg Tablet | UoM: TABLET |
```

## 📁 Project Structure

```
clinical-note-enhancer/
├── main.py                 # Streamlit application entry point
├── helpers.py              # Core logic: calls into the `api/` service
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (API keys)
├── data/
│   └── snomed/             # SNOMED-CT Snapshot files
│       ├── sct2_Description_Snapshot_*.txt
│       └── sct2_Concept_Snapshot_*.txt
└── README.md
```

## 🔧 Configuration

### Customizing SNOMED-CT Paths
Edit `helpers.py` to point to your SNOMED-CT files:
```python
SNOMED_DESC_FILE = "path/to/your/sct2_Description_Snapshot_*.txt"
```

### `api/` Service Configuration
Set `API_BASE_URL` in `.env` if the API isn't reachable at `localhost:8082`
(e.g. `http://cne-api-container:8082` when containerized — `build.sh` sets
this automatically).

### LLM Model
The LLM is configured on the `api/` side, not here — see `OPENAI_API_BASE`/
`OPENAI_MODEL_ID` in `api/README.md`.

## 🐛 Troubleshooting

### Common Issues

1. **"Failed to generate enriched summary"**
   - Check `OPENAI_API_BASE`/`OPENAI_API_KEY`/`OPENAI_MODEL_ID` in the API's environment file (`api/README.md`)
   - Verify internet connectivity from the `api/` container to that endpoint
   - Check `cne-api-container` logs for the actual LLM error: `docker logs cne-api-container`

2. **"Failed to generate tags"**
   - Verify the `api/` service is running: `curl http://localhost:8082/health`
   - Check `cne-api-container` logs for errors: `docker logs cne-api-container`
   - Check `/generate/terms/health` to confirm the term discovery step is working

3. **"Unknown" terms for SNOMED-CT codes**
   - Verify SNOMED-CT file paths in `helpers.py`
   - Check file permissions and format (tab-separated)
   - Ensure files contain active English descriptions

4. **CSS/Styling Issues**
   - Clear browser cache and hard refresh (Ctrl+F5)
   - Check browser console for CSS errors
   - Verify `unsafe_allow_html=True` in `st.markdown()`

## 🔒 Licensing and Compliance

### SNOMED-CT License
- Requires valid SNOMED-CT license from SNOMED International or UMLS
- For research/educational use, contact [NLM UMLS](https://www.nlm.nih.gov/research/umls/)
- Commercial use requires SNOMED International licensing

### LLM Provider
- Subject to whichever OpenAI-compatible provider is configured via `OPENAI_API_BASE` in the API's environment — check that provider's terms and usage limits

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request


This README provides comprehensive setup instructions for your Clinical Note Enhancer application, covering all dependencies, external services, and troubleshooting steps needed to get the app running successfully.