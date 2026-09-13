# Why we replaced MedCAT with an LLM-based term discovery step

## Summary

MedCAT (see [`ctakes-to-medcat-migration.md`](ctakes-to-medcat-migration.md)
for why it replaced Apache cTAKES) has itself now been replaced. Its role —
discovering clinical entities (symptoms, procedures, diagnoses, medications,
anatomical sites) from a refined clinical note — is now done by a dedicated
LLM call with reasoning enabled, using the same OpenAI-compatible endpoint
already used elsewhere in the pipeline. MedCAT's model pack, Python
dependency, and Docker/deployment machinery have all been removed.

## The problem: MedCAT needed more RAM than the server had

The deployed MedCAT model pack (SNOMED CT UK 40.2 + Drug Extension, 820,134
concepts / 3,272,745 names) needed **~14.4GB of resident RAM** to load, on a
production box with **15.3GB total RAM**. `htop` on the server showed a
single gunicorn worker sitting at 94.4% MEM just from the loaded model —
nothing left for Snowstorm's JVM, the GUI, or a second request. Every real
request that touched MedCAT triggered `SIGKILL! Perhaps out of memory?` in
an infinite crashloop (the worker respawns, immediately retries loading,
gets OOM-killed again, repeat).

## The attempted fix: filtering the CDB

MedCAT's `CDB.filter_by_cui(cuis_to_keep)` genuinely prunes the concept
database's core dictionaries (`cui2info`, `name2info`) rather than just
adding a runtime allow-list. The plan: keep only the semantic tags this
pipeline actually needs (`finding` → symptoms, `disorder` → diagnosis,
`substance`/`clinical drug`/`medicinal product`/`medicinal product form` →
medications), discarding everything else (anatomical structures,
procedures, and dozens of other SNOMED semantic tags never surfaced by this
API).

Measured locally (same machine, same method, so directly comparable):

| | CUIs | Names | Peak RSS on load |
|---|---|---|---|
| Full pack | 820,134 | 3,272,745 | 5,474 MB |
| Filtered pack | 195,489 | 1,115,050 | 4,483 MB |

Cutting 76% of CUIs only cut memory by **18%** — nowhere near enough. Why:
the CDB's own stats show only 64,015 of 820,134 concepts ever received
training (i.e. carry a real context vector — the actual heavy per-entry
payload; everything else is a lightweight, untrained shell). Symptoms,
diagnoses, and medications are exactly the concepts that show up constantly
in real clinical text, so the trained/heavy concepts concentrate almost
entirely in the categories this pipeline wanted to keep. The filter kept
nearly all the expensive entries and discarded mostly cheap ones — an
inversion of what was needed. 18% off ~14.4GB in production is still
~11.8GB, still too tight against a 15.3GB box once Snowstorm/GUI/OS need
their share.

Filtering by training status instead of semantic category might have
worked better, but trades away recall (untrained concepts can still be
exact-name-matched even without a context vector) for an uncertain memory
win, and doesn't change the fundamental shape of the problem: a component
that needs several GB of RAM just to answer "what entities are in this
text" is a poor fit for this deployment target.

## The fix: replace MedCAT with an LLM call

`api/app/core/functions.py`'s `discover_terms()` now does what
`generate_tags()` + `parse_medcat_to_json()` used to do, via one LLM call:

```python
async def discover_terms(clinical_text):
    parsed, token_usage = await call_llm(
        term_discovery_prompt,
        clinical_text,
        term_discovery_schema_output,
        reasoning=True,
    )
    return json.dumps(parsed), token_usage
```

`call_llm()` gained a `reasoning` parameter (default `False`), wired to
`extra_body={"enable_thinking": reasoning}` — the other three LLM calls in
the pipeline (note refinement, filter/enrich, final validation) keep
reasoning off since they're fast structured-output tasks that don't
benefit from it (~2s/25 tokens measured with thinking disabled, versus
tens of seconds and thousands of reasoning tokens with it left on by
default). Term discovery is different: it has to do the actual clinical
entity recognition MedCAT used to do, so it's given the model's full
reasoning budget.

This also let us fix a real, longstanding gap: neither cTAKES (a code bug —
it checked `polarity == 0`, but negation is encoded as `-1`, so the check
never fired) nor MedCAT (no bundled MetaCAT negation model in the deployed
pack) ever correctly excluded negated/denied findings (e.g. "denies chest
pain", "no active complaints"). `term_discovery_prompt` explicitly
instructs the LLM to exclude these, which a general-purpose reasoning model
can just do correctly.

## What this removed entirely

- `medcat[spacy]` from `api/requirements.txt`, and the `en_core_web_md`
  spaCy download from `api/Dockerfile`.
- The MedCAT model pack requirement — no more UTS/UMLS-licensed multi-GB
  download, no more `medcat_models/` directory, no more volume mount in
  `api/start.sh`, no more fail-fast check in `build.sh`, no more copy step
  in `deploy.sh`.
- `gunicorn -w 1` → back to `-w 4` — the single-worker constraint existed
  solely because each prefork worker would otherwise load its own multi-GB
  MedCAT copy. With no in-process model, real multi-process concurrency is
  free again.
- `_get_cat`, `SEMANTIC_TAG_CATEGORY_MAP`, `NEGATED_STATUSES`,
  `classify_tui`, `_get_type_id_category_map`, `parse_medcat_to_json`,
  `generate_tags` from `api/app/core/functions.py`.

Snowstorm's role (validating/resolving the LLM-discovered terms against
real SNOMED CT codes by text) is completely unchanged — it was always
independent of how the initial term list was produced.

## What to expect operationally

`discover_terms` is now a genuine LLM call with real latency and token
cost (previously `generate_tags` was a free local call). With reasoning
enabled, expect it to be the slowest of the four LLM calls in the
`/generate/terms` pipeline — watch actual latency once deployed and revisit
nginx's `proxy_read_timeout` if it's tight, the same way it needed raising
when `qwen3.x-flash`'s reasoning mode was still on for every call.
