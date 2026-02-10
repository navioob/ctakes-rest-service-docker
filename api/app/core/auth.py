from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
import os
import bcrypt

# Load environment variables
load_dotenv()

# Load bearer token hash from environment variable
# The API uses bcrypt to verify the bearer token for security.
# API_BEARER_TOKEN_HASH should be a bcrypt hash of the expected token.
BEARER_TOKEN_HASH = os.getenv("API_BEARER_TOKEN_HASH", "")

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> str:
    """
    Verify the bearer token from the request header using bcrypt.
    
    Args:
        credentials: HTTP authorization credentials from the request header.
    
    Returns:
        str: The token if validation is successful.
    
    Raises:
        HTTPException: If the token is missing, invalid, or doesn't match the hash.
    """
    provided_token = credentials.credentials.encode('utf-8')
    
    # If no token hash is configured, allow all requests (useful for local development)
    if not BEARER_TOKEN_HASH:
        return credentials.credentials
    
    # Verify the provided token against the stored bcrypt hash
    try:
        stored_hash = BEARER_TOKEN_HASH.encode('utf-8')
        if bcrypt.checkpw(provided_token, stored_hash):
            return credentials.credentials
    except Exception as e:
        # Log error if needed and raise unauthorized exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Token doesn't match the hash
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

