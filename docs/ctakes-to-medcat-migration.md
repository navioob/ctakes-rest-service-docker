# Why we replaced Apache cTAKES with MedCAT

## Summary

This project used [Apache cTAKES](https://ctakes.apache.org/) for clinical
named entity recognition and linking (NER+L) — turning raw clinical text
into coded medical concepts (symptoms, procedures, diagnoses, medications,
anatomical sites). As of this migration, cTAKES has been fully removed and
replaced with [MedCAT](https://github.com/CogStack/cogstack-nlp/)
(Medical Concept Annotation Toolkit), run in-process inside the existing
FastAPI middleware service.

## The problem with cTAKES here

1. **Outdated, unmaintained build chain.** The root `Dockerfile` built cTAKES
   from scratch on every image build: `svn export` from
   `svn.apache.org/repos/asf/ctakes/trunk`, a full Maven build of ~25
   `ctakes-*` modules against Java 8 / UIMA 2.4 / Spring 4.3 (released 2017),
   on Ubuntu 18.04 (EOL April 2023). The build routinely took "several
   hours" per the project's own README, and depended on Apache SVN and
   snapshot repositories staying reachable indefinitely.
2. **Heavy, bespoke infrastructure just for a dictionary lookup.** cTAKES's
   NER relied on a MySQL-backed UMLS/RxNorm/SNOMED dictionary
   (`sno_rx_21_aa_db/`, `sno_rx_16ab_db/` — tens of SQL dump files, loaded
   into an in-container MySQL instance at build time). That's a full
   database server, a Java servlet container (Tomcat 8.5), and a Spring MVC
   app, all to answer "what SNOMED concepts are in this text" — a task a
   single Python library call now does in-process.
3. **Not actively developed.** cTAKES's public activity has slowed
   significantly; the version pinned here (4.0.1-SNAPSHOT) was never a
   tagged release. MedCAT, by contrast, had a major architecture release
   (v2.0.0) in August 2025 and continues to ship new public SNOMED model
   packs (most recently October 2025).
4. **No natural fit for the rest of the stack.** Everything else in this
   pipeline (the FastAPI middleware, the Gemini LLM calls, Snowstorm
   queries) is already Python-native and talks over HTTP or in-process
   calls. cTAKES was the only piece requiring a separate Java runtime, a
   second Docker network hop, and its own multi-gigabyte, hours-long build.

## Why MedCAT

- **Python-native, in-process.** MedCAT installs via `pip install
  medcat[spacy]` and runs as a library call
  (`CAT.load_model_pack(...)`, `cat.get_entities(text)`) directly inside the
  FastAPI service. No second container, no network hop, no Java/Maven/SVN
  build step, no MySQL instance.
- **Actively maintained.** Developed by [CogStack](https://cogstack.org/)
  (King's College London / South London and Maudsley NHS Foundation Trust),
  with continuous releases, a public roadmap, and a research paper
  specifically covering the v2 architecture (see References).
- **Same UMLS/SNOMED CT foundation.** MedCAT model packs are built from the
  same underlying ontologies (UMLS, SNOMED CT) this project already used
  for cTAKES's dictionary, via a UTS/UMLS-licensed download — so the
  licensing story didn't change, only the toolchain.
- **Measured, not assumed, improvement.** Before committing to this
  migration we ran the same clinical note (a pneumonia case, previously
  used to validate the cTAKES integration) through both systems and
  compared output side by side:

  | | cTAKES (historical) | MedCAT |
  |---|---|---|
  | Diagnosis specificity | generic "pneumonia" | "Community acquired pneumonia" (more specific) |
  | Diabetes handling | duplicated (2 separate codes for the same fact) | single, correct entry |
  | Symptom list | 25 codes, many overlapping sub-span duplicates and non-symptom noise ("history", "general", "rest") | 13 codes, clean, one per real symptom |
  | Medication list | 9 codes (each drug duplicated across coding schemes) | 4 codes, one per drug |
  | Anatomical detail | generic "chest" (duplicated) | "Structure of lower lobe of right lung" (more specific) |
  | Negation handling | broken (checked `polarity == 0`, but negation is encoded as `-1` — the check never fired) | none in this model pack (no bundled MetaCAT negation model) — same net result, different cause |

  Net result: MedCAT's output was cleaner and more clinically specific on
  every axis we compared except negation, where both systems currently fail
  in the same way for different reasons. This is documented here as the
  evidence basis for the decision, not just an architectural preference.

## What changed operationally

- Root `Dockerfile` (cTAKES/Tomcat/MySQL/Maven/SVN build), `ctakes-web-rest/`,
  the UMLS SQL dumps (`sno_rx_21_aa_db/`, `sno_rx_16ab_db/`), and their
  onboarding scripts were deleted outright.
- `api/app/core/functions.py` now loads a MedCAT model pack once per worker
  process (lazily, on first request) and calls `get_entities()` directly —
  no HTTP round trip.
- The API's public contract (`/generate/terms` request/response shape) is
  unchanged; only the internal NER engine and the now-retired
  `/generate/ctakes/health` → `/generate/medcat/health` endpoint name
  changed.
- The MedCAT model pack itself (a licensed UMLS/SNOMED CT-derived artifact,
  multi-gigabyte) is downloaded once to the host and mounted read-only into
  the API container — not baked into the Docker image — since it's too
  large and license-gated to build automatically.

## References

- CogStack. **cogstack-nlp / MedCAT** (source, current v2 releases, model
  pack downloads). <https://github.com/CogStack/cogstack-nlp/>
- CogStack. **MedCAT documentation.** <https://cogstack-nlp.readthedocs.io/>
- Kraljević, Ž., Searle, T., Shek, A., Roguski, Ł., Noor, K., Bean, D.,
  Mascio, A., Zhu, L., Folarin, A. A., Roberts, A., Bendayan, R.,
  Richardson, M. P., Stewart, R., Shah, A. D., Wong, W. K., Ibrahim, Z.,
  Teo, J. T., & Dobson, R. J. B. (2021). **Multi-domain clinical natural
  language processing with MedCAT: The Medical Concept Annotation
  Toolkit.** *Artificial Intelligence in Medicine*, 117, 102083.
  <https://doi.org/10.1016/j.artmed.2021.102083> · preprint:
  <https://arxiv.org/abs/2010.01165>
- Ratas, M., Searle, T., Sutton, A., & Dobson, R. (2026). **MedCAT v2: a
  modular, extensible architecture for clinical named entity recognition
  and linking under real-world privacy and compute constraints.**
  *Proceedings of BioNLP 2026*, 191–198. Association for Computational
  Linguistics. <https://doi.org/10.18653/v1/2026.bionlp-1.17>
- CogStack Discourse forum (community support, model pack questions).
  <https://discourse.cogstack.org/>
- Apache Software Foundation. **Apache cTAKES.** (the system being
  replaced, for reference). <https://ctakes.apache.org/>

## See also

- [`../README.md`](../README.md) — current architecture overview
- [`../api/README.md`](../api/README.md) — API setup, environment variables,
  and how to obtain a MedCAT model pack
