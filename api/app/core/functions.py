import asyncio
import json

import os
import httpx

from .prompt import clinical_text_refinement_prompt, tags_filtering_and_enrichment_prompt, final_validation_prompt, term_discovery_prompt
from .schema import clinical_text_refinement_schema_output, tags_filtering_and_enrichment_schema_output, final_validation_schema_output, term_discovery_schema_output
from .llm import llm_client

from .config import SNOWSTORM_URL, SNOWSTORM_BRANCH, OPENAI_MODEL_ID

async def call_llm(system_prompt, user_text, schema, reasoning=False):
    """
    Generic asynchronous wrapper for LLM calls using an OpenAI-compatible
    chat completions API, forcing JSON output matching the given schema.

    Args:
        system_prompt: System instruction text
        user_text: User message text
        schema: JSON Schema dict describing the expected response shape
        reasoning: Whether to let the model think before answering. Off by
            default - most calls here are fast structured-output tasks that
            don't benefit from it and pay heavily in latency/tokens if left on.

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
            # Qwen3 hybrid models default to thinking mode, burning heavy
            # reasoning tokens even for a short structured-JSON task - not a
            # standard OpenAI param, so it goes through extra_body.
            extra_body={"enable_thinking": reasoning},
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


async def discover_terms(clinical_text):
    """
    Step 2: Use the LLM (reasoning enabled) to discover clinical entities
    directly from the refined note - replaces MedCAT NER+L, which needed a
    multi-GB model pack in RAM per worker.
    """
    try:
        parsed, token_usage = await call_llm(
            term_discovery_prompt,
            clinical_text,
            term_discovery_schema_output,
            reasoning=True,
        )
        return json.dumps(parsed), token_usage
    except Exception as e:
        print(f"Error in discover_terms: {e}")
        empty = {"anatomical_sites": [], "procedures": [], "symptoms": [], "diagnosis": [], "medications": []}
        return json.dumps(empty), {'input_token': 0, 'output_token': 0}

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
