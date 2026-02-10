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

# Load SNOMED CT descriptions into a DataFrame
# This file contains the mapping between Concept IDs and their human-readable terms
desc_df = pd.read_csv(SNOMED_DESC_FILE, sep='\t', usecols=['conceptId', 'term', 'typeId', 'active', 'languageCode'])
desc_df['conceptId'] = desc_df['conceptId'].astype(str)
desc_df['typeID'] = desc_df['typeId'].astype(str)

# Filter for active English terms, prioritizing Fully Specified Names (FSN)
desc_df = desc_df[(desc_df['typeID'] == '900000000000003001')&(desc_df['active'] == 1) & (desc_df['languageCode'] == 'en')]

# Create lookup dictionaries for fast access
code_to_term = dict(zip(desc_df['conceptId'], desc_df['term']))
valid_concept_ids = set(desc_df['conceptId'].values)
term_list = list(desc_df['term'].values)
term_to_code = dict(zip(desc_df['term'], desc_df['conceptId']))

async def call_llm(contents, config):
    """
    Generic asynchronous wrapper for LLM calls using the Google GenAI API.
    
    Args:
        contents: The prompt content/parts
        config: Generation configuration (schema, temperature, etc.)
    
    Returns:
        tuple: (response, token_usage_dict)
    """
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

async def generate_summary(doctors_text):
    """
    Step 1: Refine raw clinical notes into a professional narrative summary.
    Uses LLM with clinical_text_refinement_prompt.
    """
    contents = [
        types.Part.from_text(text=f"Raw text from the doctor's clinical notes written during triage or consultation: {doctors_text}"),
    ]
    
    config = types.GenerateContentConfig(
        system_instruction=types.Part.from_text(text=clinical_text_refinement_prompt),
        temperature=0.0,
        response_mime_type='application/json',
        response_json_schema=clinical_text_refinement_schema_output,
        thinking_config=types.ThinkingLevel.MINIMAL,
    )
    response, token_usage = await call_llm(contents, config)
    return response.parsed['text'], token_usage


async def generate_tags(doctors_text):
    """
    Step 2: Send clinical text to the cTAKES REST service for initial term extraction.
    cTAKES identifies medical entities like symptoms, procedures, and medications.
    """
    # API follows the container name deployed for cTAKES REST service
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
    Parses raw cTAKES JSON output into a simplified structure.
    Filters for SNOMEDCT_US codes and performs initial term lookup.
    
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
                                
                            # Look up the preferred term from our SNOMED snapshot
                            term = code_to_term.get(code_str, "Unknown")
                            if term != "Unknown":
                                codes.add((code_str, term))
                                used_codes.add(code_str)
            
            result[output_key] = sorted(list(codes), key=lambda x: x[0])
    
    print("Result from Ctakes:", result, "\n")
    return json.dumps(result)

def fuzzy_search_term(search_term, threshold=80):
    """
    Performs fuzzy matching on the SNOMED CT term list.
    Used when cTAKES fails to find a direct code or when LLM suggests new terms.
    """
    if not search_term or not isinstance(search_term, str):
        return None, None, 0
    
    # Use rapidfuzz WRatio for robust string matching
    result = process.extractOne(
        search_term.strip(),
        term_list,
        scorer=fuzz.WRatio,
        score_cutoff=threshold
    )
    
    if result:
        matched_term, score, _ = result
        matched_code = term_to_code.get(matched_term)
        if matched_code:
            return matched_term, matched_code, score
    
    return None, None, 0

async def filter_tags(clinical_text, generated_terms):
    """
    Step 3 & 4: Filter and enrich SNOMED-CT terms using LLM and fuzzy matching.
    
    1. LLM filters out irrelevant terms and suggests missing ones.
    2. Fuzzy search validates LLM-suggested terms against the SNOMED snapshot.
    3. Final LLM validation ensures clinical consistency.
    """
    tokens_used = {}
    
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
        thinking_config=types.ThinkingLevel.MINIMAL,
    )
    response, token_usage = await call_llm(contents, config)
    filtered_and_enriched_tags = response.parsed
    tokens_used['filter_tags'] = token_usage

    print("Result from LLM:", filtered_and_enriched_tags, "\n")

    # Step 3b: Validate all terms (especially LLM-suggested ones) against local SNOMED snapshot
    final_output = {
        "anatomical_sites": [],
        "procedures": [],
        "symptoms": [],
        "diagnosis": [],
        "medications": []
    }

    FUZZY_SEARCH_THRESHOLD = 90
    
    for section in filtered_and_enriched_tags:
        seen_codes = set()
        for item in filtered_and_enriched_tags[section]:
            code = item.get('code')
            term = item.get('term', '')
            code_str = str(code) if code else None
            
            if code_str and code_str in seen_codes:
                continue
            
            # Direct lookup if code is provided
            if code_str and code_str in valid_concept_ids:
                matched_term = code_to_term.get(code_str, "Unknown")
                if matched_term != "Unknown":
                    seen_codes.add(code_str)
                    final_output[section].append({'code': code_str, 'term': matched_term})
                    continue
            
            # Fuzzy search if code is missing or invalid
            if term:
                matched_term, matched_code, similarity_score = fuzzy_search_term(term, threshold=FUZZY_SEARCH_THRESHOLD)
                if matched_code and matched_code not in seen_codes:
                    seen_codes.add(matched_code)
                    final_output[section].append({'code': matched_code, 'term': matched_term})

    print("Final Output after mapping/fuzzy search:", final_output, "\n")

    # Step 4: Final LLM validation to ensure context relevance and split diagnosis
    validated_output, validation_token_usage = await validate_final_output(clinical_text, final_output)
    tokens_used['validate_final_output'] = validation_token_usage
    
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
        thinking_config=types.ThinkingLevel.MINIMAL,
    )
    
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
