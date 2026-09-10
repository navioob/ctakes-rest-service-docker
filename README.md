# Clinical Notes Enhancer

This repository turns raw clinical notes into categorized, validated SNOMED-CT
terms. A FastAPI middleware service (`api/`) refines the note with an LLM,
extracts medical entities in-process with [MedCAT](https://github.com/CogStack/cogstack-nlp/)
(no separate NLP container), and validates each term against a local
Snowstorm Lite SNOMED-CT server.

Apache cTAKES (Java/Tomcat/MySQL) previously filled the NER role here and has
been fully retired in favor of MedCAT.

## Services

- **`api/`** — FastAPI middleware: LLM refinement, MedCAT NER+L, Snowstorm
  validation. See [`api/README.md`](api/README.md) for architecture, env
  vars, endpoints, and full deployment steps (including how to obtain and
  mount a MedCAT model pack).
- **Snowstorm Lite** — SNOMED-CT terminology server (`snomedinternational/snowstorm-lite`).
  Onboard a SNOMED-CT RF2 release via `scripts/snomed/snomed_rf_refresh.py`
  (documented in `api/README.md`).
- **`gui/`** — optional Streamlit client for the API.

## Quick start

```bash
./start.sh
```

Brings up `snowstorm-lite` and the `cne-api` container on a shared `backend`
Docker network. See `api/README.md` for the model pack and Snowstorm
onboarding steps you need to run first.
