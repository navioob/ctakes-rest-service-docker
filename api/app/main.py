from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routers.generation import router as generation_router
from app.core.auth import verify_token

# Initialize FastAPI application
app = FastAPI(
    title="CTakes REST Service API",
    description="FastAPI service for CTakes with LLM-based refinement and SNOMED-CT mapping",
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

@app.get("/")
async def root(token: str = Depends(verify_token)):
    """Root endpoint to verify API connectivity."""
    return {"message": "CTakes REST Service API"}


@app.get("/health")
async def health(token: str = Depends(verify_token)):
    """Health check endpoint for the main FastAPI service."""
    return {"status": "healthy"}

