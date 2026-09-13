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
    discover_terms,
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
    1. Use the LLM (reasoning enabled) to discover clinical entities.
    2. Use LLM to filter irrelevant terms and suggest missing ones.
    3. Validate all terms against Snowstorm.
    4. Final LLM validation and diagnosis categorization.
    """
    try:
        tokens_used = {}

        # 1. Discover raw terms via the LLM (reasoning enabled)
        print("Discovering terms via LLM")
        discovered_terms_json, discover_tokens_used = await discover_terms(request.text)
        tokens_used['discover_terms'] = TokenUsage(**discover_tokens_used)

        # 2, 3, 4. Filter, enrich, and validate terms using LLM and Snowstorm
        print("Filtering, enriching, and validating terms using LLM and SNOMED snapshot")
        filtered_terms, filter_tokens_used = await filter_tags(request.text, discovered_terms_json)

        print("Filtering, enriching, and validating terms using LLM and SNOMED snapshot completed")

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


@router.get("/terms/health")
async def terms_health(
    token: str = Depends(verify_token)
):
    """
    Verifies the LLM-based term discovery step is working.

    Runs a sample clinical text through generate_summary + discover_terms
    to ensure the pipeline is up and correctly extracting terms.
    """
    test_text = """Swollen LL, limited mobility, pain and redness over R LL. Possible PE post THR and TKR.
        IV Streptokinase stat. IV NS 500ml run fast. SC Clean 200U stat. Refer to IR for possible embolectomy"""

    try:
        tokens_used = {}

        # Generate summary for the test text
        clinical_summary, summary_token_usage = await generate_summary(test_text)
        tokens_used['generate_summary'] = TokenUsage(**summary_token_usage)

        # Discover terms via the LLM
        discovered_terms_json, discover_token_usage = await discover_terms(clinical_summary)
        tokens_used['discover_terms'] = TokenUsage(**discover_token_usage)
        discovered_terms = json.loads(discovered_terms_json)

        # Calculate total terms found to determine "aliveness"
        total_terms = sum(
            len(discovered_terms.get(section, []))
            for section in ["anatomical_sites", "procedures", "symptoms", "diagnosis", "medications"]
        )

        is_alive = total_terms > 0
        status = "alive" if is_alive else "not_responding"

        return {
            "status": status,
            "alive": is_alive,
            "total_terms": total_terms,
            "terms": discovered_terms,
            "tokens_used": {k: v.dict() for k, v in tokens_used.items()}
        }
    except Exception as e:
        return {
            "status": "error",
            "alive": False,
            "total_terms": 0,
            "error": str(e),
            "terms": {},
            "tokens_used": {k: v.dict() for k, v in tokens_used.items()} if tokens_used else {}
        }
