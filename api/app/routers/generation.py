from fastapi import APIRouter, HTTPException, Depends
import json
from app.models import GenerateNoteRequest, GenerateNoteResponse, GenerateTermsRequest, GenerateTermsResponse, SNOMEDTerm, SNOMEDTermsResponse
from app.core.functions import (
    generate_summary,
    generate_tags,
    parse_ctakes_to_json,
    filter_tags
)
from app.core.auth import verify_token

router = APIRouter(prefix="/generate", tags=["Generation"])

# Endpoints
@router.post("/note", response_model=GenerateNoteResponse)
async def generate_note(
    request: GenerateNoteRequest,
    token: str = Depends(verify_token)
):
    """
    Generate clinical note summary from raw doctor's text.
    
    Args:
        request: Request containing raw doctor's clinical notes
    
    Returns:
        Generated clinical summary
    """
    try:
        summary = await generate_summary(request.text)
        return GenerateNoteResponse(text=summary)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/terms", response_model=GenerateTermsResponse)
async def generate_terms(
    request: GenerateTermsRequest,
    token: str = Depends(verify_token)
):
    """
    Generate SNOMED-CT terms from clinical text.
    
    This endpoint:
    1. Calls cTAKES to extract SNOMED-CT terms based on the input enriched clinical text
    2. Filters and enriches terms using LLM
    3. Validates terms against SNOMED CT description file
    
    Args:
        request: Request containing clinical text
    
    Returns:
        Filtered and enriched SNOMED-CT terms grouped by category
    """
    try:
        # Generate tags from cTAKES (async - can use pre-generated summary)
        ctakes_response = await generate_tags(request.text)
        
        # Parse cTAKES response (synchronous - fast operation)
        parsed_terms = parse_ctakes_to_json(ctakes_response)
        
        # Filter and enrich terms (async)
        filtered_terms = await filter_tags(request.text, parsed_terms)
        
        # Convert to response format
        terms_response = SNOMEDTermsResponse(
            anatomical_sites=[SNOMEDTerm(**item) for item in filtered_terms.get("anatomical_sites", [])],
            procedures=[SNOMEDTerm(**item) for item in filtered_terms.get("procedures", [])],
            symptoms=[SNOMEDTerm(**item) for item in filtered_terms.get("symptoms", [])],
            diagnosis={"communicable_disease": [SNOMEDTerm(**item) for item in filtered_terms.get("diagnosis", {}).get("communicable_disease", [])], "non_communicable_disease": [SNOMEDTerm(**item) for item in filtered_terms.get("diagnosis", {}).get("non_communicable_disease", [])]},
            medications=[SNOMEDTerm(**item) for item in filtered_terms.get("medications", [])]
        )
        
        return GenerateTermsResponse(terms=terms_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ctakes/health")
async def ctakes_health(
    token: str = Depends(verify_token)
):
    """
    Health check endpoint for cTAKES service.
    
    Uses a static test text to verify if cTAKES is alive and responding.
    - If cTAKES returns any terms: service is alive
    - If cTAKES returns empty: service is not responding/alive
    
    Returns:
        Health status and extracted terms from cTAKES
    """
    # Static test text
    test_text = """Swollen LL, limited mobility, pain and redness over R LL. Possible PE post THR and TKR. 

        IV Streptokinase stat

        IV NS 500ml run fast

        SC Clean 200U stat



        Refer to IR for possible embolectomy"""
    
    try:
        # Generate summary (async)
        clinical_summary = await generate_summary(test_text)
        
        # Generate tags from cTAKES (async)
        ctakes_response = await generate_tags(clinical_summary)
        
        # Parse cTAKES response (returns JSON string)
        parsed_terms_json = parse_ctakes_to_json(ctakes_response)
        
        # Parse JSON string to dict
        parsed_terms = json.loads(parsed_terms_json)
        
        # Count total terms
        total_terms = (
            len(parsed_terms.get("anatomical_sites", [])) +
            len(parsed_terms.get("procedures", [])) +
            len(parsed_terms.get("symptoms", [])) +
            len(parsed_terms.get("diagnosis", [])) +
            len(parsed_terms.get("medications", []))
        )
        
        # Determine health status
        is_alive = total_terms > 0
        status = "alive" if is_alive else "not_responding"
        
        # Convert to response format (parsed_terms contains lists like [code, term] after JSON deserialization)
        def convert_to_dict(item):
            if isinstance(item, (list, tuple)) and len(item) == 2:
                return {'code': str(item[0]), 'term': str(item[1])}
            elif isinstance(item, dict):
                return item
            return item
        
        terms_response = SNOMEDTermsResponse(
            anatomical_sites=[SNOMEDTerm(**convert_to_dict(item)) for item in parsed_terms.get("anatomical_sites", [])],
            procedures=[SNOMEDTerm(**convert_to_dict(item)) for item in parsed_terms.get("procedures", [])],
            symptoms=[SNOMEDTerm(**convert_to_dict(item)) for item in parsed_terms.get("symptoms", [])],
            diagnosis=[SNOMEDTerm(**convert_to_dict(item)) for item in parsed_terms.get("diagnosis", [])],
            medications=[SNOMEDTerm(**convert_to_dict(item)) for item in parsed_terms.get("medications", [])]
        )
        
        return {
            "status": status,
            "alive": is_alive,
            "total_terms": total_terms,
            "terms": terms_response
        }
    except Exception as e:
        # If there's an error, cTAKES is not alive
        return {
            "status": "error",
            "alive": False,
            "total_terms": 0,
            "error": str(e),
            "terms": SNOMEDTermsResponse()
        }
