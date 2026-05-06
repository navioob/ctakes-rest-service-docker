import json

import os
import httpx

from .prompt import clinical_text_refinement_prompt, tags_filtering_and_enrichment_prompt, final_validation_prompt
from .schema import clinical_text_refinement_schema_output, tags_filtering_and_enrichment_schema_output, final_validation_schema_output
from .llm import llm_client, types

from .config import SNOWSTORM_URL, SNOWSTORM_BRANCH

async def call_llm(contents, config):
    """
    Generic asynchronous wrapper for LLM calls using the Google GenAI API.
    
    Args:
        contents: The prompt content/parts
        config: Generation configuration (schema, temperature, etc.)
    
    Returns:
        tuple: (response, token_usage_dict)
    """
    try:
        response = await llm_client.aio.models.generate_content(
            model='gemini-3-flash-preview',
            contents=contents,
            config=config
        )
        
        # Extract token usage metadata from the response
        input_tokens = 0
        output_tokens = 0
        
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
            output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
        
        token_usage = {
            'input_token': input_tokens,
            'output_token': output_tokens
        }
        
        return response, token_usage
    except Exception as e:
        print(f"LLM Call Error: {e}")
        raise e

async def generate_summary(doctors_text):
    """
    Step 1: Refine raw clinical notes into a professional narrative summary.
    Uses LLM with clinical_text_refinement_prompt.
    """
    try:
        contents = [
            types.Part.from_text(text=f"Raw text from the doctor's clinical notes written during triage or consultation: {doctors_text}"),
        ]
        
        config = types.GenerateContentConfig(
            system_instruction=types.Part.from_text(text=clinical_text_refinement_prompt),
            temperature=0.0,
            response_mime_type='application/json',
            response_json_schema=clinical_text_refinement_schema_output,
            thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            )
        )
        response, token_usage = await call_llm(contents, config)
        return response.parsed['text'], token_usage
    except Exception as e:
        print(f"Error in generate_summary: {e}")
        # Return original text as fallback and zero tokens
        return doctors_text, {'input_token': 0, 'output_token': 0}


async def generate_tags(doctors_text):
    """
    Step 2: Send clinical text to the cTAKES REST service for initial term extraction.
    cTAKES identifies medical entities like symptoms, procedures, and medications.
    """
    # API follows the container name deployed for cTAKES REST service
    # url = 'http://localhost:8083/ctakes-web-rest/service/analyze' #dev
    url = 'http://ctakes-rest-service:8080/ctakes-web-rest/service/analyze' #prod

    params = {'pipeline': 'Default'}
    headers = {'cache-control': 'no-cache'}
    data = doctors_text

    print("\nGenerated Summary:\n", data, '\n')
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, params=params, headers=headers, content=data)
            response.raise_for_status()
            print("Status Code:", response.status_code)
            return response.text
    except httpx.RequestError as e:
        print(f"An error occurred: {e}")
        raise

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
        "anatomical_sites": "442083009", # Body structure
        "procedures": "71388002",       # Procedure
        "symptoms": "404684003",         # Clinical finding
        "diagnosis": "64572001",         # Disease/Disorder
        "medications": "105590001"       # Substance
    }
    
    root_id = hierarchy_root_map.get(section)
    
    # Base FHIR expand URL
    url = f"{SNOWSTORM_URL}/fhir/ValueSet/$expand"
    
    # Construct the ValueSet URL with ECL filter if a hierarchy root is known
    vs_url = "http://snomed.info/sct?fhir_vs"
    if root_id:
        vs_url = f"http://snomed.info/sct?fhir_vs=ecl/<<{root_id}"

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

async def parse_ctakes_to_json(json_output):
    """
    Parses raw cTAKES JSON output into a simplified structure.
    Filters for SNOMEDCT_US codes and performs initial term lookup via Snowstorm.
    
    Args:
        json_output: Raw JSON string or dict from cTAKES
    """
    if isinstance(json_output, str):
        try:
            json_output = json.loads(json_output)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string provided as input")

    if not isinstance(json_output, dict):
        raise ValueError("Input must be a dictionary or valid JSON string")

    # Map cTAKES mention types to our internal categories
    category_map = {
        "AnatomicalSiteMention": "anatomical_sites",
        "ProcedureMention": "procedures",
        "SignSymptomMention": "symptoms",
        "DiseaseDisorderMention": "diagnosis",
        "MedicationMention": "medications"
    }

    result = {
        "anatomical_sites": [],
        "procedures": [],
        "symptoms": [],
        "diagnosis": [],
        "medications": []
    }

    used_codes = set()  # Prevent duplicate codes across categories

    print(f"cTAKES JSON keys: {list(json_output.keys()) if isinstance(json_output, dict) else 'Not a dict'}")
    
    for ctakes_key, output_key in category_map.items():
        if ctakes_key in json_output and isinstance(json_output[ctakes_key], list):
            print(f"Processing {ctakes_key} -> {output_key}, found {len(json_output[ctakes_key])} mentions")
            
            codes = set()
            
            for mention in json_output[ctakes_key]:
                if isinstance(mention, dict) and "conceptAttributes" in mention:
                    
                    ## term of the concept
                    term = mention.get("text", "")
                    # Skip negated mentions (e.g., "no cough")
                    if mention.get("polarity") == 0:
                        continue 
                    
                    for attr in mention.get("conceptAttributes", []):
                        # Only interested in SNOMED CT codes
                        if attr.get("codingScheme") == "SNOMEDCT_US":
                            code = attr.get("code")
                            if not code:
                                continue
                            
                            code_str = str(code)
                            if code_str in used_codes:
                                continue
                                
                            # Use the term and code directly from cTAKES without Snowstorm search
                            # This speeds up the initial parsing; validation happens in filter_tags
                            if term and code_str:
                                codes.add((code_str, term))
                                used_codes.add(code_str)
            
            result[output_key] = sorted(list(codes), key=lambda x: x[0])
    
    print("Result from Ctakes:", result, "\n")
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
        contents = [
            types.Part.from_text(text=f"Clinical Text: {clinical_text}"),
            types.Part.from_text(text=f"Generated Terms: {generated_terms}"),
        ]
        
        config = types.GenerateContentConfig(
            system_instruction=types.Part.from_text(text=tags_filtering_and_enrichment_prompt),
            temperature=0.0,
            response_mime_type='application/json',
            response_json_schema=tags_filtering_and_enrichment_schema_output,
            thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.MINIMAL
        )
        )
        response, token_usage = await call_llm(contents, config)
        filtered_and_enriched_tags = response.parsed
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

    import asyncio

    async def resolve_term(section, item, client):
        term = item.get('term', '')
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
    
    contents = [
        types.Part.from_text(text=f"Clinical: {clinical_text}"),
        types.Part.from_text(text=f"Terms: {compact_json}"),
    ]
    
    config = types.GenerateContentConfig(
        system_instruction=types.Part.from_text(text=final_validation_prompt),
        temperature=0.0,
        response_mime_type='application/json',
        response_json_schema=final_validation_schema_output,
        thinking_config=types.ThinkingConfig(
                thinking_level=types.ThinkingLevel.MINIMAL
            ))
    
    try:
        response, token_usage = await call_llm(contents, config)
        validated_output = response.parsed
        
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
