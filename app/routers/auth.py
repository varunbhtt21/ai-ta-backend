from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import logging

from app.models import ResponseBase, UserRole, User
from app.services.auth_service import auth_service
from app.services.learning_profile_service import learning_profile_service

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.STUDENT


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user from JWT token"""
    user = await auth_service.get_current_user(credentials.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_instructor(current_user: User = Depends(get_current_user)) -> User:
    """Ensure current user has instructor role"""
    if not auth_service.is_instructor(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Instructor role required."
        )
    return current_user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure current user has admin role"""
    if not auth_service.is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin role required."
        )
    return current_user


@router.post("/register", response_model=ResponseBase)
async def register(request: RegisterRequest):
    """Register new user account"""
    logger.info(f"Registration attempt: username={request.username}, email={request.email}, role={request.role}")
    try:
        user = await auth_service.register_user(
            username=request.username,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            role=request.role
        )
        
        # Create initial learning profile for students
        if user.role == UserRole.STUDENT:
            await learning_profile_service.get_or_create_learning_profile(str(user.id))
        
        return ResponseBase(
            success=True,
            message="User registered successfully",
            data={
                "user_id": str(user.id),
                "username": user.username,
                "role": user.role.value
            }
        )
    
    except ValueError as e:
        logger.error(f"Registration validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=ResponseBase)
async def login(request: LoginRequest):
    """User authentication"""
    try:
        user = await auth_service.authenticate_user(request.username, request.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        access_token = await auth_service.create_access_token_for_user(user)
        
        return ResponseBase(
            success=True,
            message="Login successful",
            data={
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role.value
                }
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.get("/me", response_model=ResponseBase)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile"""
    
    # Get user statistics
    user_stats = await auth_service.get_user_stats(str(current_user.id))
    
    return ResponseBase(
        success=True,
        message="Profile retrieved successfully",
        data={
            "user": {
                "id": str(current_user.id),
                "username": current_user.username,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "role": current_user.role.value,
                "is_active": current_user.is_active,
                "last_login": current_user.last_login,
                "created_at": current_user.created_at,
                "preferences": current_user.preferences
            },
            "statistics": user_stats
        }
    )


@router.put("/me", response_model=ResponseBase)
async def update_current_user_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """Update current user's profile"""
    
    try:
        updates = {}
        if request.full_name is not None:
            updates["full_name"] = request.full_name
        
        success = False
        if updates:
            success = await auth_service.update_user_profile(str(current_user.id), updates)
        
        if request.preferences is not None:
            pref_success = await auth_service.update_user_preferences(
                str(current_user.id), request.preferences
            )
            success = success or pref_success
        
        if success:
            return ResponseBase(
                success=True,
                message="Profile updated successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No changes made to profile"
            )
    
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )


@router.post("/change-password", response_model=ResponseBase)
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user)
):
    """Change user password"""
    
    try:
        success = await auth_service.change_password(
            str(current_user.id),
            request.current_password,
            request.new_password
        )
        
        if success:
            return ResponseBase(
                success=True,
                message="Password changed successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to change password"
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.get("/users/{username}", response_model=ResponseBase)
async def get_user_profile(
    username: str,
    current_user: User = Depends(get_current_user)
):
    """Get user profile by username (instructors can view all, students only themselves)"""
    
    # Check permissions
    if not auth_service.is_instructor(current_user) and current_user.username != username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own profile"
        )
    
    user = await auth_service.get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get user statistics
    user_stats = await auth_service.get_user_stats(str(user.id))
    
    return ResponseBase(
        success=True,
        message="User profile retrieved",
        data={
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email if current_user.username == username or auth_service.is_instructor(current_user) else None,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active,
                "last_login": user.last_login,
                "created_at": user.created_at
            },
            "statistics": user_stats
        }
    )


@router.get("/users", response_model=ResponseBase)
async def list_users(
    role: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: User = Depends(get_current_instructor)
):
    """List users (instructors and admins only)"""
    
    try:
        user_role = None
        if role:
            try:
                user_role = UserRole(role)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {role}"
                )
        
        users = await auth_service.list_users(
            role=user_role,
            limit=limit,
            skip=skip
        )
        
        user_data = []
        for user in users:
            user_data.append({
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active,
                "last_login": user.last_login,
                "created_at": user.created_at
            })
        
        return ResponseBase(
            success=True,
            message="Users retrieved successfully",
            data={
                "users": user_data,
                "total": len(user_data),
                "limit": limit,
                "skip": skip
            }
        )
    
    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )