import requests
import json
from google import genai
from google.generativeai import types
from google.genai import types
from google.oauth2 import service_account
from dotenv import load_dotenv
import os
import pandas as pd

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

There are five categoris of terms that will be extracted from Apache CTAKES, and you should on keeping terms from these categories that has these certain keywords. Generally, you should keep terms that are do not have the terms regarding "qualifier value", "unit of presentation"
1. Anatomical Sites - keywords such as "Body Structure", "Body Part"
2. Procedures - keywords such as "Procedure", "Therapeutic Procedure", "Diagnostic Procedure", don't include any "qualifier value"
3. Symptoms - keywords such as "Finding", "Sign", "Symptom", "Clinical Finding", don't include any "qualifier value", "substance" for this category
4. Diagnosis - keywords such as "Disease", "Disorder", "Syndrome", "Infection", "Neoplasm", don't include any "qualifier value"
5. Medications - keywords such as "Pharmaceutical", "Drug", "Medication", "Therapeutic Substance", "Substance", don't include any "unit of presentation", "qualifier value" or specifically "Medicinal Product" for this category

Besides, after filtering out the terms that are not relevant to the clinical text summary, you should analysze the remaining terms filtered for the clinical text summary, and further suggest any additional SNOMED-CT Terms and ConceptID that are relevant to the clinical text summary based on the clininal text summary and the generated SNOMED-CT Terms and ConceptIDs from Apache CTAKES, and add them to the list of filtered terms.

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

    used_codes = set()

    for ctakes_key, output_key in category_map.items():
        if ctakes_key in json_output and isinstance(json_output[ctakes_key], list):
            codes = set()
            for mention in json_output[ctakes_key]:
                if isinstance(mention, dict) and "conceptAttributes" in mention:
                    if mention.get("polarity") == 0:
                        continue  # Skip negated mentions
                    for attr in mention.get("conceptAttributes", []):
                        if attr.get("codingScheme") == "SNOMEDCT_US":
                            code = attr.get("code")
                            if code and code not in used_codes:
                                term = code_to_term.get(str(code), "Unknown")
                                if term != "Unknown":
                                    codes.add((str(code), term))  # Store as tuple
                                used_codes.add(code)
            result[output_key] = sorted(list(codes), key=lambda x: x[0])  # Sort by code

    return json.dumps(result)

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
        thinking_config=types.ThinkingConfig(thinking_budget=500),
    )
    response = call_llm(contents, config)

    filtered_and_enriched_tags = response.parsed

    #final filtering to identify the terms are in the SNOMED CT description file

    final_output = {
        "anatomical_sites": [],
        "procedures": [],
        "symptoms": [],
        "diagnosis": [],
        "medications": []
    }

    for section in filtered_and_enriched_tags:
        seen_codes = set()  # Track codes already added to this section
        for item in filtered_and_enriched_tags[section]:
            code = item.get('code')
            # Skip if code is already in this section (duplicate)
            if code in seen_codes:
                continue
            # Add to seen_codes and append to output
            seen_codes.add(code)
            # Add the term to the item if the code is in the SNOMED CT description file
            if code in desc_df['conceptId'].values:
                item['term'] = code_to_term.get(str(code), "Unknown")
                final_output[section].append(item)
                
    return response.parsed