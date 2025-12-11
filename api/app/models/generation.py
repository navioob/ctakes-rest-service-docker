from pydantic import BaseModel

# Request/Response Models
class GenerateNoteRequest(BaseModel):
    """Request schema for generating clinical note summary."""
    text: str


class GenerateNoteResponse(BaseModel):
    """Response schema for generated clinical note."""
    text: str


class GenerateTermsRequest(BaseModel):
    """Request schema for generating SNOMED-CT terms."""
    text: str


class SNOMEDTerm(BaseModel):
    """Schema for a single SNOMED-CT term."""
    term: str
    code: str


class SNOMEDTermsResponse(BaseModel):
    """Response schema for SNOMED-CT terms grouped by category."""
    anatomical_sites: list[SNOMEDTerm] = []
    procedures: list[SNOMEDTerm] = []
    symptoms: list[SNOMEDTerm] = []
    diagnosis: list[SNOMEDTerm] = []
    medications: list[SNOMEDTerm] = []


class GenerateTermsResponse(BaseModel):
    """Response schema for generated SNOMED-CT terms."""
    terms: SNOMEDTermsResponse
