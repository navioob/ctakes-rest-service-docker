from pydantic import BaseModel, Field
from typing import Dict, Any

# --- Token Usage Models ---

class TokenUsage(BaseModel):
    """
    Schema for tracking token consumption by the LLM.
    Useful for monitoring costs and performance.
    """
    input_token: int
    output_token: int


# --- Clinical Note Generation Models ---

class GenerateNoteRequest(BaseModel):
    """
    Request schema for the /generate/note endpoint.
    Expects raw clinical text from a doctor.
    """
    text: str


class GenerateNoteResponse(BaseModel):
    """
    Response schema for the /generate/note endpoint.
    Returns the refined professional summary and token usage details.
    """
    text: str
    tokens_used: Dict[str, TokenUsage] = Field(default_factory=dict)


# --- SNOMED-CT Term Generation Models ---

class GenerateTermsRequest(BaseModel):
    """
    Request schema for the /generate/terms endpoint.
    Expects refined clinical text for term extraction.
    """
    text: str


class SNOMEDTerm(BaseModel):
    """
    Represents a single SNOMED-CT concept.
    Includes the human-readable term and its unique Concept ID (code).
    """
    term: str
    code: str


class DiagnosisResponse(BaseModel):
    """
    Specialized schema for diagnosis, split into communicable 
    and non-communicable diseases as per clinical requirements.
    """
    communicable_disease: list[SNOMEDTerm] = []
    non_communicable_disease: list[SNOMEDTerm] = []


class SNOMEDTermsResponse(BaseModel):
    """
    Aggregated response for all extracted SNOMED-CT terms, 
    grouped by their clinical category.
    """
    anatomical_sites: list[SNOMEDTerm] = []
    procedures: list[SNOMEDTerm] = []
    symptoms: list[SNOMEDTerm] = []
    diagnosis: DiagnosisResponse = Field(default_factory=DiagnosisResponse)
    medications: list[SNOMEDTerm] = []


class GenerateTermsResponse(BaseModel):
    """
    Final response schema for the /generate/terms endpoint.
    Includes the categorized terms and token usage for all processing steps.
    """
    terms: SNOMEDTermsResponse
    tokens_used: Dict[str, TokenUsage] = Field(default_factory=dict)
