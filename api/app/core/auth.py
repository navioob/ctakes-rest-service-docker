from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
import os
import bcrypt

load_dotenv()

# Load bearer token hash from environment variable
# This should be a bcrypt hash of your token
BEARER_TOKEN_HASH = os.getenv("API_BEARER_TOKEN_HASH", "")

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verify bearer token from request using bcrypt.
    
    Args:
        credentials: HTTP authorization credentials from request header
    
    Returns:
        str: The token if valid
    
    Raises:
        HTTPException: If token is missing or invalid
    """
    provided_token = credentials.credentials.encode('utf-8')
    
    # If no token hash is configured, allow all requests (development mode)
    if not BEARER_TOKEN_HASH:
        return credentials.credentials
    
    # Verify token using bcrypt
    try:
        stored_hash = BEARER_TOKEN_HASH.encode('utf-8')
        if bcrypt.checkpw(provided_token, stored_hash):
            return credentials.credentials
    except Exception as e:
        # If bcrypt check fails, token is invalid
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Token doesn't match
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

