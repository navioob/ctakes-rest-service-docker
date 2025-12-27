from pydantic import BaseModel, Field

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


class DiagnosisResponse(BaseModel):
    """Schema for diagnosis split into communicable and non-communicable diseases."""
    communicable_disease: list[SNOMEDTerm] = []
    non_communicable_disease: list[SNOMEDTerm] = []


class SNOMEDTermsResponse(BaseModel):
    """Response schema for SNOMED-CT terms grouped by category."""
    anatomical_sites: list[SNOMEDTerm] = []
    procedures: list[SNOMEDTerm] = []
    symptoms: list[SNOMEDTerm] = []
    diagnosis: DiagnosisResponse = Field(default_factory=DiagnosisResponse)
    medications: list[SNOMEDTerm] = []


class GenerateTermsResponse(BaseModel):
    """Response schema for generated SNOMED-CT terms."""
    terms: SNOMEDTermsResponse
