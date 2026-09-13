import asyncio
import json

import os
import httpx
from functools import lru_cache

from .prompt import clinical_text_refinement_prompt, tags_filtering_and_enrichment_prompt, final_validation_prompt
from .schema import clinical_text_refinement_schema_output, tags_filtering_and_enrichment_schema_output, final_validation_schema_output
from .llm import llm_client

from .config import SNOWSTORM_URL, SNOWSTORM_BRANCH, MEDCAT_MODEL_PACK_PATH, OPENAI_MODEL_ID

async def call_llm(system_prompt, user_text, schema):
    """
    Generic asynchronous wrapper for LLM calls using an OpenAI-compatible
    chat completions API, forcing JSON output matching the given schema.

    Args:
        system_prompt: System instruction text
        user_text: User message text
        schema: JSON Schema dict describing the expected response shape

    Returns:
        tuple: (parsed_response_dict, token_usage_dict)
    """
    messages = [
        {"role": "system", "content": f"{system_prompt}\n\nRespond with ONLY a JSON object matching this JSON Schema, no markdown fences, no extra text:\n{json.dumps(schema)}"},
        {"role": "user", "content": user_text},
    ]
    try:
        response = await llm_client.chat.completions.create(
            model=OPENAI_MODEL_ID,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
        parsed = json.loads(content)

        usage = response.usage
        token_usage = {
            'input_token': getattr(usage, 'prompt_tokens', 0) or 0,
            'output_token': getattr(usage, 'completion_tokens', 0) or 0,
        }

        return parsed, token_usage
    except Exception as e:
        print(f"LLM Call Error: {e}")
        raise e

async def generate_summary(doctors_text):
    """
    Step 1: Refine raw clinical notes into a professional narrative summary.
    Uses LLM with clinical_text_refinement_prompt.
    """
    try:
        parsed, token_usage = await call_llm(
            clinical_text_refinement_prompt,
            f"Raw text from the doctor's clinical notes written during triage or consultation: {doctors_text}",
            clinical_text_refinement_schema_output,
        )
        return parsed['text'], token_usage
    except Exception as e:
        print(f"Error in generate_summary: {e}")
        # Return original text as fallback and zero tokens
        return doctors_text, {'input_token': 0, 'output_token': 0}


@lru_cache(maxsize=1)
def _get_cat():
    """
    Loads the MedCAT model pack once per worker process, on first use.
    Lazy (not module-level/eager) so importing this module - e.g. from the
    offline TUI-mapping self-check - never pays for a multi-GB model load.
    """
    from medcat.cat import CAT
    print(f"Loading MedCAT model pack from {MEDCAT_MODEL_PACK_PATH} ...")
    return CAT.load_model_pack(MEDCAT_MODEL_PACK_PATH)


async def generate_tags(doctors_text):
    """
    Step 2: Run MedCAT NER+L in-process over the refined clinical text.
    get_entities() is synchronous/CPU-bound, so it runs in a thread to
    avoid blocking the event loop.
    """
    print("\nGenerated Summary:\n", doctors_text, "\n")
    cat = _get_cat()
    return await asyncio.to_thread(cat.get_entities, doctors_text)

async def snowstorm_search(term, section=None, limit=1, client=None):
    """
    Searches for a SNOMED CT concept using the Snowstorm Lite FHIR API ($expand).
    Returns the preferred term and concept ID for the best match.
    
    Args:
        term: The search string.
        section: The clinical category (anatomical_sites, procedures, symptoms, diagnosis, medications).
        limit: Number of results to return.
        client: Optional httpx.AsyncClient for connection pooling.
    """
    if not term or not isinstance(term, str):
        return None, None

    # Map our internal sections to SNOMED CT hierarchy roots for ECL filtering
    hierarchy_root_map = {
        "anatomical_sites": "<<442083009", # Body structure
        "procedures": "<<71388002",       # Procedure
        "symptoms": "<<404684003",         # Clinical finding
        "diagnosis": "<<64572001",         # Disease/Disorder
        "medications": "<<105590001 OR <<373873005" # Substance OR Pharmaceutical/biologic product
    }
    
    root_ecl = hierarchy_root_map.get(section)
    
    # Base FHIR expand URL
    url = f"{SNOWSTORM_URL}/fhir/ValueSet/$expand"
    
    # Construct the ValueSet URL with ECL filter if a hierarchy root is known
    vs_url = "http://snomed.info/sct?fhir_vs"
    if root_ecl:
        vs_url = f"http://snomed.info/sct?fhir_vs=ecl/{root_ecl}"

    params = {
        "url": vs_url,
        "filter": term.strip(),
        "count": limit,
        "includeDesignations": "true"
    }

    try:
        if client:
            response = await client.get(url, params=params)
        else:
            async with httpx.AsyncClient(timeout=10.0) as local_client:
                response = await local_client.get(url, params=params)
                
        response.raise_for_status()
        data = response.json()
        
        # Parse the FHIR ValueSet expansion results
        expansion = data.get("expansion", {})
        contains = expansion.get("contains", [])
        
        if contains:
            best_match = contains[0]
            matched_code = best_match.get("code")
            matched_term = best_match.get("display")
            print(f"Matched term (FHIR): {matched_term}, Matched code: {matched_code}")
            return matched_term, matched_code
    except Exception as e:
        print(f"Snowstorm FHIR search error for '{term}' in section '{section}': {e}")
    
    return None, None

# SNOMED CT semantic tag -> internal category. The current public MedCAT
# model packs are built from SNOMED CT RF2, so each entity's type_ids are
# opaque per-build numeric ids pointing into the loaded pack's own
# cdb.type_id2info - NOT UMLS TUIs. The *names* stored there are the
# standard SNOMED semantic tags, which are stable across different SNOMED
# model pack builds even though the numeric ids are not, so the
# type_id -> category map is built dynamically per loaded pack (see
# _get_type_id_category_map) rather than hardcoded by numeric id.
# This mirrors the semantic tags this repo's own tags_filtering_and_enrichment_prompt
# (prompt.py) already expects per category: body structure, procedure,
# finding, disorder, substance/product.
SEMANTIC_TAG_CATEGORY_MAP = {
    "body structure": "anatomical_sites",
    "procedure": "procedures",
    "finding": "symptoms",
    "disorder": "diagnosis",
    "substance": "medications",
    "product": "medications",
}

# Meta-annotation values treated as "not actually present" (mirrors cTAKES's
# polarity == 0 skip). Only takes effect if the loaded model pack ships a
# MetaCAT status/presence model - if it doesn't, meta_anns is empty and every
# entity is treated as affirmed (no negation filtering available).
NEGATED_STATUSES = {"negated", "hypothetical", "family", "other"}


def classify_tui(type_ids, type_id_category_map):
    """Returns the first internal category matched by any of the given type_ids, or None."""
    for tid in type_ids or []:
        category = type_id_category_map.get(tid)
        if category:
            return category
    return None


@lru_cache(maxsize=1)
def _get_type_id_category_map():
    """
    Builds {type_id: category} from the loaded model pack's own
    cdb.type_id2info, by matching each type_id's SNOMED semantic tag name
    against SEMANTIC_TAG_CATEGORY_MAP. Built once per worker, right after
    the model itself loads (triggers _get_cat(), same lazy-load semantics).
    """
    cat = _get_cat()
    mapping = {}
    for type_id, info in cat.cdb.type_id2info.items():
        category = SEMANTIC_TAG_CATEGORY_MAP.get(info.name.lower())
        if category:
            mapping[type_id] = category
    return mapping


async def parse_medcat_to_json(medcat_output):
    """
    Parses MedCAT's get_entities() output into the same simplified structure
    parse_ctakes_to_json used to produce. The "code" in each (code, term) pair
    is a UMLS CUI rather than a SNOMED code - that's fine, filter_tags/
    snowstorm_search re-resolves every term to a real SNOMED code by TEXT
    later; this tuple is only used for dedup and as LLM filtering context.

    Args:
        medcat_output: dict from CAT.get_entities(), shaped like
            {"entities": {"0": {"cui": ..., "pretty_name": ..., "type_ids": [...],
                                 "meta_anns": {...}}, ...}, "tokens": [...]}
    """
    entities = medcat_output.get("entities", {}) if isinstance(medcat_output, dict) else {}

    result = {
        "anatomical_sites": [],
        "procedures": [],
        "symptoms": [],
        "diagnosis": [],
        "medications": []
    }

    used_cuis = set()  # Prevent duplicate CUIs across categories
    type_id_category_map = _get_type_id_category_map()

    print(f"MedCAT entity count: {len(entities)}")

    for ent in entities.values():
        cui = ent.get("cui")
        term = ent.get("pretty_name") or ent.get("source_value", "")
        if not cui or not term or cui in used_cuis:
            continue

        meta = ent.get("meta_anns") or {}
        status = (meta.get("Status") or meta.get("Presence") or {}).get("value", "")
        if status.lower() in NEGATED_STATUSES:
            continue

        category = classify_tui(ent.get("type_ids"), type_id_category_map)
        if category is None:
            continue

        result[category].append((cui, term))
        used_cuis.add(cui)

    for key in result:
        result[key] = sorted(result[key], key=lambda x: x[0])

    print("Result from MedCAT:", result, "\n")
    return json.dumps(result)

async def filter_tags(clinical_text, generated_terms):
    """
    Step 3 & 4: Filter and enrich SNOMED-CT terms using LLM and Snowstorm.
    
    1. LLM filters out irrelevant terms and suggests missing ones.
    2. Snowstorm validates LLM-suggested terms against the SNOMED CT.
    3. Final LLM validation ensures clinical consistency.
    """
    tokens_used = {}

    print("Filtering and enriching SNOMED-CT terms using LLM and SNOMED snapshot")
    try:
        # Step 3a: LLM filtering and enrichment
        user_text = f"Clinical Text: {clinical_text}\nGenerated Terms: {generated_terms}"
        filtered_and_enriched_tags, token_usage = await call_llm(
            tags_filtering_and_enrichment_prompt,
            user_text,
            tags_filtering_and_enrichment_schema_output,
        )
        tokens_used['filter_tags'] = token_usage

        print("Result from LLM:", filtered_and_enriched_tags, "\n")
    except Exception as e:
        print(f"Error in filter_tags (LLM step): {e}")
        # Fallback to using generated_terms directly if LLM fails
        try:
            filtered_and_enriched_tags = json.loads(generated_terms)
        except Exception:
            filtered_and_enriched_tags = {}
        tokens_used['filter_tags'] = {'input_token': 0, 'output_token': 0}

    # Step 3b: Validate all terms (especially LLM-suggested ones) against Snowstorm in parallel
    print("Validating all terms (especially LLM-suggested ones) against Snowstorm in parallel")
    final_output = {
        "anatomical_sites": [],
        "procedures": [],
        "symptoms": [],
        "diagnosis": [],
        "medications": []
    }

    async def resolve_term(section, item, client):
        # The LLM is asked for [{"term": ...}, ...] per section, but
        # response_format=json_object only guarantees valid JSON - not this
        # exact nested shape. Some models flatten to a plain list of strings
        # instead. Accept either so a schema-format slip doesn't wipe out
        # the whole section.
        term = item.get('term', '') if isinstance(item, dict) else (item if isinstance(item, str) else '')
        if not term:
            return None

        # Always resolve using Snowstorm FHIR search by term.
        normalized_term = term.strip()
        if normalized_term.endswith(")") and " (" in normalized_term:
            normalized_term = normalized_term.rsplit(" (", 1)[0].strip()

        matched_term, matched_code = await snowstorm_search(normalized_term, section=section, client=client)
        if matched_code:
            return {"section": section, "code": matched_code, "term": matched_term}
        return None

    try:
        tasks = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            for section in filtered_and_enriched_tags:
                if section in final_output:
                    for item in filtered_and_enriched_tags[section]:
                        tasks.append(resolve_term(section, item, client))

            if tasks:
                results = await asyncio.gather(*tasks)
                for res in results:
                    if res:
                        sec = res["section"]
                        # Prevent duplicate codes within the same section
                        if not any(existing['code'] == res['code'] for existing in final_output[sec]):
                            final_output[sec].append({'code': res['code'], 'term': res['term']})
    except Exception as e:
        print(f"Error in filter_tags (Snowstorm parallel step): {e}")

    print("Final Output after mapping/Snowstorm search:", final_output, "\n")

    try:
        # Step 4: Final LLM validation to ensure context relevance and split diagnosis
        validated_output, validation_token_usage = await validate_final_output(clinical_text, final_output)
        tokens_used['validate_final_output'] = validation_token_usage
    except Exception as e:
        print(f"Error in filter_tags (Final validation step): {e}")
        # Fallback to final_output without categorization
        validated_output = final_output
        if isinstance(validated_output.get("diagnosis"), list):
            validated_output["diagnosis"] = {
                "communicable_disease": [],
                "non_communicable_disease": validated_output["diagnosis"]
            }
        tokens_used['validate_final_output'] = {'input_token': 0, 'output_token': 0}
    
    print("Final Validated Output:", validated_output, "\n")
    return validated_output, tokens_used

async def validate_final_output(clinical_text, final_output):
    """
    Final validation layer using LLM.
    - Ensures terms are actually supported by the clinical text.
    - Categorizes diagnoses into communicable vs non-communicable.
    """
    compact_json = json.dumps(final_output, separators=(',', ':'))
    user_text = f"Clinical: {clinical_text}\nTerms: {compact_json}"

    try:
        validated_output, token_usage = await call_llm(
            final_validation_prompt,
            user_text,
            final_validation_schema_output,
        )

        # Ensure all required keys exist in the response
        for section in ["anatomical_sites", "procedures", "symptoms", "medications"]:
            if section not in validated_output:
                validated_output[section] = []
        
        if "diagnosis" not in validated_output:
            validated_output["diagnosis"] = {"communicable_disease": [], "non_communicable_disease": []}
        
        return validated_output, token_usage
    except Exception as e:
        print(f"Error in final validation: {e}")
        # Fallback logic if LLM validation fails
        if isinstance(final_output.get("diagnosis"), list):
            final_output["diagnosis"] = {
                "communicable_disease": [],
                "non_communicable_disease": final_output["diagnosis"]
            }
        return final_output, {'input_token': 0, 'output_token': 0}
