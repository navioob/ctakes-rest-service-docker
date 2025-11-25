import requests
import json
from google import genai
from google.generativeai import types
from google.genai import types
from google.oauth2 import service_account
from dotenv import load_dotenv
import os
import pandas as pd
from rapidfuzz import fuzz, process

# Load environment variables from .env file
load_dotenv()

llm_credentials = {
    "GOOGLE_APPLICATION_CREDENTIALS": json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
    "GOOGLE_APPLICATION_SCOPES": [os.getenv("GOOGLE_APPLICATION_SCOPES")]
}

# Configure the LLM client (replace with your actual API key)
llm_client = genai.Client(
    project=llm_credentials['GOOGLE_APPLICATION_CREDENTIALS'].get("project_id"),
    credentials=service_account.Credentials.from_service_account_info(
        llm_credentials['GOOGLE_APPLICATION_CREDENTIALS'],
        scopes=llm_credentials['GOOGLE_APPLICATION_SCOPES']
    ),
    location="global",
    vertexai=True
)

# Load SNOMED CT description file (adjust path to your Snapshot file)
SNOMED_DESC_FILE = "./sct2_Description_Snapshot-en_INT_20250901.txt"
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

# Define the prompt and schema_output
clinical_text_refinement_prompt = """
You are an expert medical scribe AI tasked with transforming raw, abbreviated clinical notes from a doctor into a clear, structured, and professionally articulated narrative summary for medical professionals, patients, or reviewers. 

Your goal is to create a single, flowing paragraph that integrates the provided raw doctor's clinical input that includes the compilation of symptoms, diagnoses, and medications into a cohesive, readable narrative, strictly using only the input data without adding unprovided details (e.g., age, gender, vital signs, or symptoms not explicitly mentioned), with the steps below:

1. Expand medical abbreviations accurately based on standard medical terminology (e.g., 'DM' as Diabetes Mellitus, 'HPT' as Hypertension, 'U/L' as Uncontrolled, 'h/o' as history of, 'od' as once daily, 'bd' as twice daily, 'BP' as Blood Pressure, 'DXT' as blood glucose testing or control, 't' as tablet, 'on' as once nightly). If an abbreviation is ambiguous, infer the most likely meaning from context without introducing errors. Parse delimiter-separated inputs (e.g., '^^^^^^') to treat each segment as a distinct diagnosis or prescription.
2. Use the compilation of symptoms, diagnoses, and medications for current medication dosages if discrepancies exist with the prescription in the raw doctor's clinical input.
3. Structure the narrative as follows: (1) Start with the patient’s current presentation, summarizing diagnoses with full descriptions; (2) Include relevant medical history (e.g., past conditions like hepatitis A); (3) Describe current symptoms or status (e.g., 'no active complaints' or control status like 'BP well controlled'); (4) Conclude with the ongoing treatment plan, detailing medications with expanded dosage terms and monitoring instructions.
4. Ensure the tone is formal, objective, and medically accurate, mimicking the professional style of a clinical summary.
5. Do not include ICD-10 codes in the output.
6. Do not invent new conditions, treatments, or clinical findings not present in the input.
7. The output of the text should first describe the patient's current presentation, then include relevant medical history, describe current symptoms or status, then describe the current diagnosis and treatment plan, and conclude with the ongoing treatment plan, detailing medications with expanded dosage terms and monitoring instructions.
8. You should always include the generic name of the medication if the brand name is provided in the input in the output.

**Input**:
- Raw text from the doctor's clinical notes written during triage or consultation.

**Example Input**:
Raw text from the doctor's clinical notes written during triage or consultation: I10 - Essential (primary) hypertension^^^^^^E119 - Type 2 diabetes mellitus without complications^^^^^^E785 - Hyperlipidemia, unspecified, U/L DM HPT dyslipidemia h/o hepatitis A in 2022 currently: t losartan 100mg od t atorvastatin 40mg on t aspirin 100mg od t gliclazide 80mg od t metformin 1g bd no active complaints BP DXT well controlled, 273 | Losartan 50mg Tablet | UoM: TABLET | ^^^^^^281 | Metformin 500mg Tablet | UoM: TABLET | ^^^^^^258 | Gliclazide 80mg Tablet | UoM: TABLET | ^^^^^^206 | Atorvastatin 20mg Tablet | UoM: TABLET | ^^^^^^191 | Acetylsalicylic Acid 100mg Tablet (Aspirin) | UoM: TABLET |

**Example Output**:
The patient presents with essential (primary) hypertension, type 2 diabetes mellitus without complications, and hyperlipidemia. The patient has a history of hepatitis A diagnosed in 2022. Currently, the patient reports no active complaints, with blood pressure and blood glucose levels well controlled. The patient is managed with Losartan 100 mg once daily for hypertension, Metformin 1000 mg twice daily and Gliclazide 80 mg once daily for type 2 diabetes, Atorvastatin 40 mg at night for hyperlipidemia, and Aspirin 100 mg once daily for cardiovascular protection. The treatment plan includes continuing these medications as prescribed, with regular monitoring of blood pressure and blood glucose to maintain control.

Generate the narrative that is suitable for SNOMED-CT mapping using Apache CTAKES for the provided input.
"""

clinical_text_refinement_schema_output = {
    "type": "object",
    "properties": {
        "text": {
            "type": "string",
            "description": "The comprehensive medical summary paragraph that is suitable for SNOMED-CT mapping using Apache CTAKES."
        },
    },
    "required": ["text"]
}

tags_filtering_and_enrichment_prompt = """
You are an expert in medical text processing with a great understanding of SNOMED-CT concepts and the context of a clinical text that doctors writes during triage or consultation. Your task is to filter and retain and enrich the meaningful extracted SNOMED-CT terms that was extracted from the clinical text using Apache CTAKES.

Apache CTakes extract terms in a very traditional way, and often includes many terms that are not relevant to the clinical context, but with the downside of being rigid to its dictionary mapping that is provided and it is not always updated to the latest version of SNOMED-CT. Your goal is to analyze, counter check with the provided clinical text summary and the list of generated terms from Apache CTAKES, and filter out any terms that do not directly relate to the patient's current medical conditions, symptoms, diagnoses, or treatments as described in the input texts. 

There are five categories of terms that will be extracted from Apache CTAKES, and you should on keeping terms from these categories that has these certain keywords. Generally, you should keep terms that are do not have the terms regarding "qualifier value", "unit of presentation"
1. Anatomical Sites - keywords such as "Body Structure", "Body Part"
2. Procedures - keywords such as "Procedure", "Therapeutic Procedure", "Diagnostic Procedure", don't include any "qualifier value"
3. Symptoms - keywords such as "Finding", "Sign", "Symptom", "Clinical Finding", don't include any "qualifier value", "substance" for this category
4. Diagnosis - keywords such as "Disease", "Disorder", "Syndrome", "Infection", "Neoplasm", don't include any "qualifier value"
5. Medications - keywords such as "Pharmaceutical", "Drug", "Medication", "Therapeutic Substance", "Substance", don't include any "unit of presentation", "qualifier value" or specifically "Medicinal Product" for this category

TERM FORMATTING REQUIREMENT: When providing SNOMED-CT terms in your output, you must include the semantic type in parentheses after each term name. The format should be:
- Anatomical Sites: "Term Name (body structure)" - Example: "Heart (body structure)"
- Procedures: "Term Name (procedure)" - Example: "Blood test (procedure)"
- Symptoms: "Term Name (finding)" - Example: "Pain (finding)"
- Diagnosis: "Term Name (disorder)" - Example: "Diabetes (disorder)"
- Medications: "Term Name (substance)" - Example: "Enoxaparin (substance)"

Besides, after filtering out the terms that are not relevant to the clinical text summary, while abiding to the rules above, you should analysze the remaining terms filtered for the clinical text summary, and further suggest any additional SNOMED-CT Terms and ConceptID that are relevant to the clinical text summary based on the clininal text summary and the generated SNOMED-CT Terms and ConceptIDs from Apache CTAKES, and add them to the list of filtered terms:
1. You should suggest any possible anatomical sites, procedures, symptoms and diagnoses that are relevant to the clinical text summary, and add them to the list of filtered terms, if the relevant anatomical sites are already included in the list of filtered terms, you should not suggest them again.
2. For medications, you should suggest the generic name of the medication based on the medication brand name, and add them to the list of filtered terms, if the relevant medications are already included in the list of filtered terms, you should not suggest them again.
- Example: if found "Clexane", you should suggest "Enoxaparin (substance)" as the generic name, and add it to the list of filtered terms.

IMPORTANT: All SNOMED-CT terms and codes (ConceptIDs) that you provide must be based on the latest SNOMED CT description snapshot. Only use terms and codes that exist in the current SNOMED CT description snapshot file. Do not generate or suggest codes that are not present in the latest SNOMED CT description snapshot. Ensure that all ConceptIDs you provide correspond to valid, active SNOMED CT concepts from the most recent description snapshot.

You should keep only those terms that are explanatory and directly relevant clinical text summary.

**Input**:
- **Clinical Text Summary**: {{clinical_text_summary}}
- **Generated SNOMED-CT Terms and ConceptIDs**: {{generated_snomed_ct_terms_and_concept_ids}}

**Output**:
A JSON object with the following structure, containing only the filtered SNOMED-CT Terms and ConceptID for each category following the schema output provided.

"""

tags_filtering_and_enrichment_schema_output = {
    "type": "object",
    "properties": {
        "anatomical_sites": {
        "type": "array",
        "description": "List of SNOMED-CT Terms and ConceptID for catergory anatomical_sites. Can be an empty list [].",
        "items": {
            "type": "object",
            "properties": {
            "term": {"type": "string", "description": "Description of SNOMED-CT Term for the ConceptID."},
            "code": {"type": "string", "description": "ConceptID for SNOMED-CT."}
            },
            "required": ["term", "code"]
        }
        },
        "procedures": {
        "type": "array",
        "description": "List of SNOMED-CT Terms and ConceptID for catergory procedures. Can be an empty list [].",
        "items": {
            "type": "object",
            "properties": {
            "term": {"type": "string", "description": "Description of SNOMED-CT Term for the ConceptID."},
            "code": {"type": "string", "description": "ConceptID for SNOMED-CT."}
            },
            "required": ["term", "code"]
        }
        },
        "symptoms": {
        "type": "array",
        "description": "List of SNOMED-CT Terms and ConceptID for catergory symptoms. Can be an empty list [].",
        "items": {
            "type": "object",
            "properties": {
            "term": {"type": "string", "description": "Description of SNOMED-CT Term for the ConceptID."},
            "code": {"type": "string", "description": "ConceptID for SNOMED-CT."}
            },
            "required": ["term", "code"]
        }
        },
        "diagnosis": {
        "type": "array",
        "description": "List of SNOMED-CT Terms and ConceptID for catergory diagnosis. Can be an empty list [].",
        "items": {
            "type": "object",
            "properties": {
            "term": {"type": "string", "description": "Description of SNOMED-CT Term for the ConceptID."},
            "code": {"type": "string", "description": "ConceptID for SNOMED-CT."}
            },
            "required": ["term", "code"]
        }
        },
        "medications": {
        "type": "array",
        "description": "List of SNOMED-CT Terms and ConceptID for catergory Medications. Can be an empty list [].",
        "items": {
            "type": "object",
            "properties": {
            "term": {"type": "string", "description": "Description of SNOMED-CT Term for the ConceptID."},
            "code": {"type": "string", "description": "ConceptID for SNOMED-CT."}
            },
            "required": ["term", "code"]
        }
        }
    },
    "required": ["anatomical_sites", "procedures", "symptoms", "diagnosis", "medications"]
}

final_validation_prompt = """
Validate SNOMED-CT terms against clinical text. Keep only terms that:
- Are mentioned/implied in the clinical text
- Are clinically relevant to the patient's condition
- Are not generic/vague or incorrectly mapped

Remove terms that don't match the clinical context. Be conservative - remove if unsure.
Return JSON with same structure: anatomical_sites, procedures, symptoms, diagnosis, medications.
"""

final_validation_schema_output = {
    "type": "object",
    "properties": {
        "anatomical_sites": {"type": "array", "items": {"type": "object", "properties": {"term": {"type": "string"}, "code": {"type": "string"}}, "required": ["term", "code"]}},
        "procedures": {"type": "array", "items": {"type": "object", "properties": {"term": {"type": "string"}, "code": {"type": "string"}}, "required": ["term", "code"]}},
        "symptoms": {"type": "array", "items": {"type": "object", "properties": {"term": {"type": "string"}, "code": {"type": "string"}}, "required": ["term", "code"]}},
        "diagnosis": {"type": "array", "items": {"type": "object", "properties": {"term": {"type": "string"}, "code": {"type": "string"}}, "required": ["term", "code"]}},
        "medications": {"type": "array", "items": {"type": "object", "properties": {"term": {"type": "string"}, "code": {"type": "string"}}, "required": ["term", "code"]}}
    },
    "required": ["anatomical_sites", "procedures", "symptoms", "diagnosis", "medications"]
}

def call_llm(contents, config):
    return llm_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents,
        config=config
    )

def generate_summary(doctors_text):
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
    response = call_llm(contents, config)
    return response.parsed['text']

def generate_tags(doctors_text):
    # API follows the container name deployed for cTAKES REST service in the server environment
    # url = 'http://localhost:8080/ctakes-web-rest/service/analyze' #dev
    url = 'http://ctakes-rest-service:8080/ctakes-web-rest/service/analyze' #prod

    params = {'pipeline': 'Default'}
    headers = {'cache-control': 'no-cache'}
    data = generate_summary(
        doctors_text
    )

    print("\nGenerated Summary:\n", data, '\n')
    
    try:
        response = requests.post(url, params=params, headers=headers, data=data)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        print("Status Code:", response.status_code)

        return response.text  # or response.json() if the response is in JSON format

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")

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

def filter_tags(clinical_text, generated_terms):
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
    response = call_llm(contents, config)

    filtered_and_enriched_tags = response.parsed

    print("Result from LLM:", filtered_and_enriched_tags, "\n")

    #final filtering to identify the terms are in the SNOMED CT description file

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

    # Final validation layer: LLM counter-check if outputs make sense with clinical text
    validated_output = validate_final_output(clinical_text, final_output)
    
    print("Final Validated Output:", validated_output, "\n")

    return validated_output

def validate_final_output(clinical_text, final_output):
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
        response = call_llm(contents, config)
        validated_output = response.parsed
        
        # Ensure all sections exist even if empty
        for section in ["anatomical_sites", "procedures", "symptoms", "diagnosis", "medications"]:
            if section not in validated_output:
                validated_output[section] = []
        
        return validated_output
    except Exception as e:
        print(f"Error in final validation: {e}")
        # Return original output if validation fails
        return final_output