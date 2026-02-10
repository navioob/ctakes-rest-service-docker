from fastapi import APIRouter, HTTPException, Depends
import json
from app.models import (
    GenerateNoteRequest, 
    GenerateNoteResponse, 
    GenerateTermsRequest, 
    GenerateTermsResponse, 
    SNOMEDTerm, 
    SNOMEDTermsResponse, 
    DiagnosisResponse, 
    TokenUsage
)
from app.core.functions import (
    generate_summary,
    generate_tags,
    parse_ctakes_to_json,
    filter_tags
)
from app.core.auth import verify_token

# Initialize the router for generation-related endpoints
router = APIRouter(prefix="/generate", tags=["Generation"])

@router.post("/note", response_model=GenerateNoteResponse)
async def generate_note(
    request: GenerateNoteRequest,
    token: str = Depends(verify_token)
):
    """
    Refines raw doctor's clinical notes into a professional narrative summary.
    
    This is typically the first step in the pipeline, providing a cleaner 
    input for subsequent SNOMED-CT term extraction.
    """
    try:
        summary, token_usage = await generate_summary(request.text)
        tokens_used = {
            'generate_summary': TokenUsage(**token_usage)
        }
        return GenerateNoteResponse(text=summary, tokens_used=tokens_used)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/terms", response_model=GenerateTermsResponse)
async def generate_terms(
    request: GenerateTermsRequest,
    token: str = Depends(verify_token)
):
    """
    Extracts, filters, and enriches SNOMED-CT terms from clinical text.
    
    Pipeline:
    1. Send text to cTAKES for initial entity recognition.
    2. Parse cTAKES output into a structured format.
    3. Use LLM to filter irrelevant terms and suggest missing ones.
    4. Validate all terms against a local SNOMED-CT snapshot using fuzzy matching.
    5. Final LLM validation and diagnosis categorization.
    """
    try:
        tokens_used = {}
        
        # 1. Generate raw tags from cTAKES
        ctakes_response = await generate_tags(request.text)
        
        # 2. Parse cTAKES response into simplified JSON
        parsed_terms_json = parse_ctakes_to_json(ctakes_response)
        
        # 3, 4, 5. Filter, enrich, and validate terms using LLM and SNOMED snapshot
        filtered_terms, filter_tokens_used = await filter_tags(request.text, parsed_terms_json)
        
        # Format token usage for the response
        for key, value in filter_tokens_used.items():
            tokens_used[key] = TokenUsage(**value)
        
        # Map filtered terms to the Pydantic response models
        diagnosis_data = filtered_terms.get("diagnosis", {})
        diagnosis_response = DiagnosisResponse(
            communicable_disease=[SNOMEDTerm(**item) for item in diagnosis_data.get("communicable_disease", [])],
            non_communicable_disease=[SNOMEDTerm(**item) for item in diagnosis_data.get("non_communicable_disease", [])]
        )
        
        terms_response = SNOMEDTermsResponse(
            anatomical_sites=[SNOMEDTerm(**item) for item in filtered_terms.get("anatomical_sites", [])],
            procedures=[SNOMEDTerm(**item) for item in filtered_terms.get("procedures", [])],
            symptoms=[SNOMEDTerm(**item) for item in filtered_terms.get("symptoms", [])],
            diagnosis=diagnosis_response,
            medications=[SNOMEDTerm(**item) for item in filtered_terms.get("medications", [])]
        )
        
        return GenerateTermsResponse(terms=terms_response, tokens_used=tokens_used)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ctakes/health")
async def ctakes_health(
    token: str = Depends(verify_token)
):
    """
    Verifies the health of the underlying cTAKES service.
    
    Runs a sample clinical text through the pipeline to ensure that 
    the cTAKES container is up and correctly extracting terms.
    """
    test_text = """Swollen LL, limited mobility, pain and redness over R LL. Possible PE post THR and TKR. 
        IV Streptokinase stat. IV NS 500ml run fast. SC Clean 200U stat. Refer to IR for possible embolectomy"""
    
    try:
        tokens_used = {}
        
        # Generate summary for the test text
        clinical_summary, summary_token_usage = await generate_summary(test_text)
        tokens_used['generate_summary'] = TokenUsage(**summary_token_usage)
        
        # Call cTAKES
        ctakes_response = await generate_tags(clinical_summary)
        
        # Parse results
        parsed_terms_json = parse_ctakes_to_json(ctakes_response)
        parsed_terms = json.loads(parsed_terms_json)
        
        # Calculate total terms found to determine "aliveness"
        diagnosis_list = parsed_terms.get("diagnosis", [])
        diagnosis_count = len(diagnosis_list) if isinstance(diagnosis_list, list) else 0
        total_terms = (
            len(parsed_terms.get("anatomical_sites", [])) +
            len(parsed_terms.get("procedures", [])) +
            len(parsed_terms.get("symptoms", [])) +
            diagnosis_count +
            len(parsed_terms.get("medications", []))
        )
        
        is_alive = total_terms > 0
        status = "alive" if is_alive else "not_responding"
        
        # Helper to convert raw list/tuple terms to dict for Pydantic
        def convert_to_dict(item):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                return {'code': str(item[0]), 'term': str(item[1])}
            return item
        
        # Format the health check response
        diagnosis_response = DiagnosisResponse(
            communicable_disease=[],
            non_communicable_disease=[SNOMEDTerm(**convert_to_dict(item)) for item in diagnosis_list]
        )
        
        terms_response = SNOMEDTermsResponse(
            anatomical_sites=[SNOMEDTerm(**convert_to_dict(item)) for item in parsed_terms.get("anatomical_sites", [])],
            procedures=[SNOMEDTerm(**convert_to_dict(item)) for item in parsed_terms.get("procedures", [])],
            symptoms=[SNOMEDTerm(**convert_to_dict(item)) for item in parsed_terms.get("symptoms", [])],
            diagnosis=diagnosis_response,
            medications=[SNOMEDTerm(**convert_to_dict(item)) for item in parsed_terms.get("medications", [])]
        )
        
        return {
            "status": status,
            "alive": is_alive,
            "total_terms": total_terms,
            "terms": terms_response,
            "tokens_used": {k: v.dict() for k, v in tokens_used.items()}
        }
    except Exception as e:
        return {
            "status": "error",
            "alive": False,
            "total_terms": 0,
            "error": str(e),
            "terms": SNOMEDTermsResponse(),
            "tokens_used": {k: v.dict() for k, v in tokens_used.items()} if tokens_used else {}
        }
