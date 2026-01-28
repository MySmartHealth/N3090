"""
JWT Authentication Module with Database Integration
Handles token generation, validation, and user authentication against PostgreSQL.
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, User as DBUser

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "INSECURE_DEV_SECRET_CHANGE_IN_PRODUCTION")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """JWT Token payload model."""
    username: Optional[str] = None
    location_id: Optional[str] = None
    expires: Optional[datetime] = None


class User(BaseModel):
    """User model for authentication."""
    username: str
    location_id: str
    disabled: bool = False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a new JWT access token.
    
    Args:
        data: Payload data to encode in token
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> TokenData:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData with decoded payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        location_id: str = payload.get("location_id")
        
        if username is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token_data = TokenData(
            username=username,
            location_id=location_id,
            expires=datetime.fromtimestamp(payload.get("exp"))
        )
        return token_data
        
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    FastAPI dependency to extract and validate current user from JWT token.
    Verifies user exists in database and is active.
    
    Args:
        credentials: HTTP Bearer credentials from request header
        db: Database session
        
    Returns:
        Authenticated User object
        
    Raises:
        HTTPException: If authentication fails
    """
    token = credentials.credentials
    token_data = verify_token(token)
    
    # Look up user in database
    result = await db.execute(
        select(DBUser).where(DBUser.username == token_data.username)
    )
    db_user = result.scalar_one_or_none()
    
    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not db_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Return User model for API
    user = User(
        username=db_user.username,
        location_id=db_user.location_id,
        disabled=not db_user.is_active
    )
    
    return user


async def authenticate_user(username: str, password: str, db: AsyncSession) -> Optional[DBUser]:
    """
    Authenticate user against database.
    
    Args:
        username: Username to authenticate
        password: Plain text password
        db: Database session
        
    Returns:
        User object if authentication successful, None otherwise
    """
    result = await db.execute(
        select(DBUser).where(DBUser.username == username)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# Development mode bypass
ALLOW_INSECURE_DEV = os.getenv("ALLOW_INSECURE_DEV", "true").lower() in {"1", "true", "yes"}

# Default dev user for insecure dev mode
DEV_USER = User(
    username="dev_user",
    location_id="dev_location",
    disabled=False
)

# Optional security scheme that doesn't auto-raise 401
optional_security = HTTPBearer(auto_error=False)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(optional_security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Optional authentication dependency.
    In dev mode (ALLOW_INSECURE_DEV=true), returns a dev user if no token provided.
    In production mode, requires valid authentication.
    """
    # If dev mode and no credentials, return dev user
    if ALLOW_INSECURE_DEV and credentials is None:
        return DEV_USER
    
    # If credentials provided, validate them
    if credentials is not None:
        return await get_current_user(credentials, db)
    
    # Production mode without credentials - reject
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
