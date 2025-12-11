from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routers.generation import router as generation_router
from app.core.auth import verify_token

app = FastAPI(
    title="CTakes REST Service API",
    description="FastAPI service for CTakes",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers here
app.include_router(generation_router)

@app.get("/")
async def root(token: str = Depends(verify_token)):
    return {"message": "CTakes REST Service API"}


@app.get("/health")
async def health(token: str = Depends(verify_token)):
    return {"status": "healthy"}

