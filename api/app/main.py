import asyncio

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routers.generation import router as generation_router
from app.core.auth import verify_token
from app.core.functions import _get_cat

# Initialize FastAPI application
app = FastAPI(
    title="Clinical Notes Enhancer API",
    description="FastAPI service for MedCAT with LLM-based refinement and SNOMED-CT mapping",
    version="1.0.0"
)

# Configure CORS (Cross-Origin Resource Sharing) middleware
# This allows the API to be accessed from different domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, this should be restricted to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
# The generation router handles clinical note processing and SNOMED-CT term extraction
app.include_router(generation_router)


@app.on_event("startup")
async def warm_up_medcat():
    """
    Load the MedCAT model pack at container startup instead of on the first
    real request - shaves the ~80s model-pack load off whichever user
    happens to hit generate_tags first (and off any nginx/gateway timeout
    budget it would otherwise eat into).
    """
    await asyncio.to_thread(_get_cat)


@app.get("/")
async def root(token: str = Depends(verify_token)):
    """Root endpoint to verify API connectivity."""
    return {"message": "Clinical Notes Enhancer API"}


@app.get("/health")
async def health(token: str = Depends(verify_token)):
    """Health check endpoint for the main FastAPI service."""
    return {"status": "healthy"}

