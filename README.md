# Clinical Notes Enhancer

This repository turns raw clinical notes into categorized, validated SNOMED-CT
terms. A FastAPI middleware service (`api/`) refines the note with an LLM,
discovers clinical entities with a second (reasoning-enabled) LLM call, and
validates each term against a local Snowstorm Lite SNOMED-CT server.

Two NLP engines previously filled the entity-discovery role here: Apache
cTAKES (Java/Tomcat/MySQL), then MedCAT (an in-process Python model requiring
a multi-gigabyte model pack in RAM). Both have been retired in favor of an
LLM call — see [`docs/medcat-to-llm-term-discovery.md`](docs/medcat-to-llm-term-discovery.md)
for why.

## Services

- **`api/`** — FastAPI middleware: LLM note refinement, LLM term discovery,
  Snowstorm validation. See [`api/README.md`](api/README.md) for
  architecture, env vars, endpoints, and full deployment steps.
- **Snowstorm Lite** — SNOMED-CT terminology server (`snomedinternational/snowstorm-lite`).
  Onboard a SNOMED-CT RF2 release via `scripts/snomed/snomed_rf_refresh.py`
  (documented in `api/README.md`).
- **`gui/`** — Streamlit client for the API.

## Quick start

```bash
./build.sh
```

Brings up `snowstorm-lite`, auto-onboards SNOMED CT from
`scripts/snomed/data/` if the Snowstorm volume is empty, then builds+starts
`cne-api-container` and `cne-gui-container` — all on a shared `backend`
Docker network. See `docs/deployment-prerequisites.md` for what needs to be
in place first (SNOMED archive, `.env`) and `deploy.sh` for copying those to
a remote server.
