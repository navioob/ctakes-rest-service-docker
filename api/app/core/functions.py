import requests
import json

import os
import pandas as pd
from rapidfuzz import fuzz, process
import httpx

from .prompt import clinical_text_refinement_prompt, tags_filtering_and_enrichment_prompt, final_validation_prompt
from .schema import clinical_text_refinement_schema_output, tags_filtering_and_enrichment_schema_output, final_validation_schema_output
from .llm import llm_client, types


# Load SNOMED CT description file (adjust path to your Snapshot file)
# Use absolute path based on this file's location
_current_dir = os.path.dirname(os.path.abspath(__file__))
SNOMED_DESC_FILE = os.path.join(_current_dir, "data", "sct2_Description_Snapshot-en_INT_20250901.txt")
desc_df = pd.read_csv(SNOMED_DESC_FILE, sep='\t', usecols=['conceptId', 'term', 'typeId', 'active', 'languageCode'])
desc_df['conceptId'] = desc_df['conceptId'].astype(str)
desc_df['typeID'] = desc_df['typeId'].astype(str)
desc_df = desc_df[(desc_df['typeID'] == '900000000000003001')&(desc_df['active'] == 1) & (desc_df['languageCode'] == 'en')]# Prioritize Fully Specified Name (FSN) or preferred term
code_to_term = dict(zip(desc_df['conceptId'], desc_df['term']))
# Create a set of valid concept IDs for fast lookup
valid_concept_ids = set(desc_df['conceptId'].values)
# Create a list of terms for fuzzy search (pre-processed for performance)
term_list = list(desc_df['term'].values)
# Create a mapping from term to code for fast lookup after fuzzy match
term_to_code = dict(zip(desc_df['term'], desc_df['conceptId']))

async def call_llm(contents, config):
    """Async LLM call using native async API."""
    return await llm_client.aio.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents,
        config=config
    )

async def generate_summary(doctors_text):
    contents = [
        types.Part.from_text(text=f"Raw text from the doctor's clinical notes written during triage or consultation: {doctors_text}"),
    ]
    
    config = types.GenerateContentConfig(
        system_instruction=types.Part.from_text(text=clinical_text_refinement_prompt),
        temperature=0.0,
        response_mime_type='application/json',
        response_json_schema=clinical_text_refinement_schema_output,
        thinking_config=types.ThinkingConfig(thinking_budget=500),
    )
    response = await call_llm(contents, config)
    return response.parsed['text']


async def generate_tags(doctors_text):
    """Async version of generate_tags using httpx."""
    # API follows the container name deployed for cTAKES REST service in the server environment
    url = 'http://localhost:8080/ctakes-web-rest/service/analyze' #dev
    # url = 'http://ctakes-rest-service:8080/ctakes-web-rest/service/analyze' #prod

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

def parse_ctakes_to_json(json_output):
    """
    Parses cTAKES JSON output into a simplified JSON structure containing unique SNOMEDCT_US codes
    and their corresponding terms from the SNOMED CT Snapshot description file.

    Args:
        json_output (dict or str): The cTAKES JSON data, either as a dictionary or JSON string.

    Returns:
        str: A JSON string with keys 'anatomical_sites', 'procedures', 'symptoms', 'diagnosis', 'medications',
             each mapping to a list of [code, term] lists, with no duplicates across categories.

    Raises:
        ValueError: If json_output is not a valid dictionary or JSON string.
    """
    if isinstance(json_output, str):
        try:
            json_output = json.loads(json_output)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON string provided as input")

    if not isinstance(json_output, dict):
        raise ValueError("Input must be a dictionary or valid JSON string")

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

    used_codes = set()  # Track codes as strings for consistent comparison

    # Debug: Check what keys are in the JSON output
    print(f"cTAKES JSON keys: {list(json_output.keys()) if isinstance(json_output, dict) else 'Not a dict'}")
    
    for ctakes_key, output_key in category_map.items():
        if ctakes_key in json_output and isinstance(json_output[ctakes_key], list):
            print(f"Processing {ctakes_key} -> {output_key}, found {len(json_output[ctakes_key])} mentions")
            codes = set()
            mentions_processed = 0
            codes_found = 0
            codes_not_in_desc = 0
            
            for mention in json_output[ctakes_key]:
                if isinstance(mention, dict) and "conceptAttributes" in mention:
                    if mention.get("polarity") == 0:
                        continue  # Skip negated mentions
                    mentions_processed += 1
                    for attr in mention.get("conceptAttributes", []):
                        if attr.get("codingScheme") == "SNOMEDCT_US":
                            code = attr.get("code")
                            if not code:
                                continue
                            codes_found += 1
                            # Convert to string for consistent comparison
                            code_str = str(code)
                            # Skip if code is already used (to prevent duplicates across categories)
                            if code_str in used_codes:
                                continue
                            # Look up term in description file
                            term = code_to_term.get(code_str, "Unknown")
                            # Only add if term exists in description file
                            if term != "Unknown":
                                codes.add((code_str, term))  # Store as tuple
                                used_codes.add(code_str)  # Mark as used
                            else:
                                codes_not_in_desc += 1
                                print(f"  Code {code_str} not found in description file")
            
            print(f"  {output_key}: {mentions_processed} mentions processed, {codes_found} codes found, {codes_not_in_desc} not in desc, {len(codes)} added to result")
            result[output_key] = sorted(list(codes), key=lambda x: x[0])  # Sort by code
        else:
            print(f"  {ctakes_key} not found in JSON or not a list")
    
    print("Result from Ctakes:", result, "\n")
    return json.dumps(result)

def fuzzy_search_term(search_term, threshold=80):
    """
    Perform fuzzy search on the SNOMED CT description file to find the best matching term.
    
    Args:
        search_term (str): The term to search for (may include semantic type like "(substance)")
        threshold (int): Minimum similarity score (0-100) to consider a match. Default 80.
    
    Returns:
        tuple: (matched_term, code, score) if match found above threshold, else (None, None, 0)
    """
    if not search_term or not isinstance(search_term, str):
        return None, None, 0
    
    # Use rapidfuzz to find the best match
    # scorer=fuzz.WRatio uses weighted ratio which is good for partial matches
    result = process.extractOne(
        search_term.strip(),
        term_list,
        scorer=fuzz.WRatio,
        score_cutoff=threshold
    )
    
    if result:
        matched_term, score, _ = result
        # Get the corresponding code from the mapping
        matched_code = term_to_code.get(matched_term)
        if matched_code:
            return matched_term, matched_code, score
    
    return None, None, 0

async def filter_tags(clinical_text, generated_terms):
    """
    Filter and enrich SNOMED-CT terms using LLM, then apply fuzzy matching logic.
    
    Process flow:
    1. LLM generates filtered and enriched terms
    2. Apply fuzzy search logic to validate terms against SNOMED CT description file
    3. Final LLM validation to ensure terms are clinically relevant
    
    Args:
        clinical_text: Clinical text summary
        generated_terms: Generated terms from cTAKES (JSON string)
    
    Returns:
        Validated output with filtered and enriched SNOMED-CT terms
    """
    # Step 1: LLM generates filtered and enriched terms
    contents = [
        types.Part.from_text(text=f"Clinical Text: {clinical_text}"),
        types.Part.from_text(text=f"Generated Terms: {generated_terms}"),
    ]
    
    config = types.GenerateContentConfig(
        system_instruction=types.Part.from_text(text=tags_filtering_and_enrichment_prompt),
        temperature=0.0,
        response_mime_type='application/json',
        response_json_schema=tags_filtering_and_enrichment_schema_output,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    response = await call_llm(contents, config)
    filtered_and_enriched_tags = response.parsed

    print("Result from LLM:", filtered_and_enriched_tags, "\n")

    # Step 2: Apply fuzzy search logic to validate terms against SNOMED CT description file
    final_output = {
        "anatomical_sites": [],
        "procedures": [],
        "symptoms": [],
        "diagnosis": [],
        "medications": []
    }

    # Fuzzy search threshold (0-100, higher = more strict)
    FUZZY_SEARCH_THRESHOLD = 90
    
    for section in filtered_and_enriched_tags:
        seen_codes = set()  # Track codes already added to this section
        for item in filtered_and_enriched_tags[section]:
            code = item.get('code')
            term = item.get('term', '')
            
            # Convert code to string for consistent comparison
            code_str = str(code) if code else None
            
            # Skip if code is already in this section (duplicate)
            if code_str and code_str in seen_codes:
                continue
            
            matched_code = None
            matched_term = None
            similarity_score = 0
            
            # Case 1: Code exists and is valid
            if code_str and code_str in valid_concept_ids:
                matched_code = code_str
                matched_term = code_to_term.get(code_str, "Unknown")
                if matched_term != "Unknown":
                    seen_codes.add(code_str)
                    final_output[section].append({
                        'code': matched_code,
                        'term': matched_term
                    })
                    continue
            
            # Case 2: Code doesn't exist or is invalid, try fuzzy search on term
            if term:
                matched_term, matched_code, similarity_score = fuzzy_search_term(
                    term, 
                    threshold=FUZZY_SEARCH_THRESHOLD
                )
                
                if matched_code and matched_code not in seen_codes:
                    seen_codes.add(matched_code)
                    final_output[section].append({
                        'code': matched_code,
                        'term': matched_term
                    })
                    print(f"  Fuzzy matched: '{term}' -> '{matched_term}' (code: {matched_code}, score: {similarity_score:.1f})")
                elif matched_code:
                    print(f"  Fuzzy match found but code already used: '{term}' -> '{matched_term}' (code: {matched_code}, score: {similarity_score:.1f})")
                else:
                    print(f"  No fuzzy match found for: '{term}' (best score below threshold {FUZZY_SEARCH_THRESHOLD})")

    print("Final Output after mapping/fuzzy search:", final_output, "\n")

    # Step 3: Final validation layer - LLM counter-check if outputs make sense with clinical text
    validated_output = await validate_final_output(clinical_text, final_output)
    
    print("Final Validated Output:", validated_output, "\n")

    return validated_output

async def validate_final_output(clinical_text, final_output):
    """
    Final validation layer using LLM to counter-check if the mapped and fuzzy-searched
    outputs make sense in the context of the clinical text.
    
    Args:
        clinical_text (str): The original clinical text summary
        final_output (dict): The final output after mapping and fuzzy search
    
    Returns:
        dict: Validated output with only clinically relevant terms
    """
    # Compact JSON format to minimize tokens
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
        thinking_config=types.ThinkingConfig(thinking_budget=0),  # Reduced from 500
    )
    
    try:
        response = await call_llm(contents, config)
        validated_output = response.parsed
        
        # Ensure all sections exist even if empty
        for section in ["anatomical_sites", "procedures", "symptoms", "medications"]:
            if section not in validated_output:
                validated_output[section] = []
        
        # Handle diagnosis - schema should enforce it's an object, but verify
        if "diagnosis" not in validated_output:
            validated_output["diagnosis"] = {
                "communicable_disease": [],
                "non_communicable_disease": []
            }
        elif not isinstance(validated_output["diagnosis"], dict):
            # This shouldn't happen if schema is enforced, but handle it just in case
            # Convert array to split structure as fallback
            if isinstance(validated_output["diagnosis"], list):
                validated_output["diagnosis"] = {
                    "communicable_disease": [],
                    "non_communicable_disease": validated_output["diagnosis"]
                }
            else:
                validated_output["diagnosis"] = {
                    "communicable_disease": [],
                    "non_communicable_disease": []
                }
        
        # Ensure both sub-arrays exist
        if "communicable_disease" not in validated_output["diagnosis"]:
            validated_output["diagnosis"]["communicable_disease"] = []
        if "non_communicable_disease" not in validated_output["diagnosis"]:
            validated_output["diagnosis"]["non_communicable_disease"] = []
        
        return validated_output
    except Exception as e:
        print(f"Error in final validation: {e}")
        # If validation fails, convert diagnosis from array to split structure before returning
        if isinstance(final_output.get("diagnosis"), list):
            final_output["diagnosis"] = {
                "communicable_disease": [],
                "non_communicable_disease": final_output["diagnosis"]
            }
        return final_output
