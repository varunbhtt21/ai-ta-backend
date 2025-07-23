from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging

from app.models import ResponseBase, User, LearningVelocity, TeachingStyle
from app.routers.auth import get_current_user, get_current_instructor
from app.services.learning_profile_service import learning_profile_service

router = APIRouter()
logger = logging.getLogger(__name__)


class LearningProfileUpdateRequest(BaseModel):
    preferred_teaching_style: Optional[TeachingStyle] = None
    learning_velocity: Optional[LearningVelocity] = None
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    preferences: Optional[Dict[str, Any]] = None
    goals: Optional[List[str]] = None


class LearningProfileResponse(BaseModel):
    user_id: str
    preferred_teaching_style: str
    learning_velocity: str
    strengths: List[str]
    weaknesses: List[str]
    preferences: Dict[str, Any]
    goals: List[str]
    adaptation_metrics: Dict[str, Any]
    updated_at: str
    created_at: str


@router.get("/me", response_model=ResponseBase)
async def get_my_learning_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's learning profile"""
    try:
        profile = await learning_profile_service.get_or_create_learning_profile(str(current_user.id))
        
        return ResponseBase(
            success=True,
            message="Learning profile retrieved successfully",
            data={
                "profile": {
                    "user_id": str(profile.user_id),
                    "preferred_teaching_style": profile.preferred_teaching_style.value,
                    "learning_velocity": profile.learning_velocity.value,
                    "strengths": profile.strengths,
                    "weaknesses": profile.weaknesses,
                    "preferences": profile.preferences,
                    "goals": profile.goals,
                    "adaptation_metrics": profile.adaptation_metrics,
                    "updated_at": profile.updated_at,
                    "created_at": profile.created_at
                }
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting learning profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve learning profile"
        )


@router.put("/me", response_model=ResponseBase)
async def update_my_learning_profile(
    request: LearningProfileUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """Update current user's learning profile"""
    try:
        # Build updates dictionary
        updates = {}
        if request.preferred_teaching_style is not None:
            updates["preferred_teaching_style"] = request.preferred_teaching_style
        if request.learning_velocity is not None:
            updates["learning_velocity"] = request.learning_velocity
        if request.strengths is not None:
            updates["strengths"] = request.strengths
        if request.weaknesses is not None:
            updates["weaknesses"] = request.weaknesses
        if request.preferences is not None:
            updates["preferences"] = request.preferences
        if request.goals is not None:
            updates["goals"] = request.goals
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No updates provided"
            )
        
        profile = await learning_profile_service.update_learning_profile(
            user_id=str(current_user.id),
            updates=updates
        )
        
        return ResponseBase(
            success=True,
            message="Learning profile updated successfully",
            data={
                "profile": {
                    "user_id": str(profile.user_id),
                    "preferred_teaching_style": profile.preferred_teaching_style.value,
                    "learning_velocity": profile.learning_velocity.value,
                    "strengths": profile.strengths,
                    "weaknesses": profile.weaknesses,
                    "preferences": profile.preferences,
                    "goals": profile.goals,
                    "updated_at": profile.updated_at
                }
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating learning profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update learning profile"
        )


@router.get("/{user_id}", response_model=ResponseBase)
async def get_user_learning_profile(
    user_id: str,
    current_user: User = Depends(get_current_instructor)
):
    """Get specific user's learning profile (instructors only)"""
    try:
        profile = await learning_profile_service.get_learning_profile(user_id)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Learning profile not found"
            )
        
        return ResponseBase(
            success=True,
            message="Learning profile retrieved successfully",
            data={
                "profile": {
                    "user_id": str(profile.user_id),
                    "preferred_teaching_style": profile.preferred_teaching_style.value,
                    "learning_velocity": profile.learning_velocity.value,
                    "strengths": profile.strengths,
                    "weaknesses": profile.weaknesses,
                    "preferences": profile.preferences,
                    "goals": profile.goals,
                    "adaptation_metrics": profile.adaptation_metrics,
                    "updated_at": profile.updated_at,
                    "created_at": profile.created_at
                }
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user learning profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve learning profile"
        )


@router.get("/analytics/summary", response_model=ResponseBase)
async def get_learning_profiles_analytics(
    current_user: User = Depends(get_current_instructor)
):
    """Get learning profiles analytics summary (instructors only)"""
    try:
        analytics = await learning_profile_service.get_learning_profiles_analytics()
        
        return ResponseBase(
            success=True,
            message="Learning profiles analytics retrieved successfully",
            data=analytics
        )
    
    except Exception as e:
        logger.error(f"Error getting learning profiles analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )


@router.post("/me/reset", response_model=ResponseBase)
async def reset_my_learning_profile(
    current_user: User = Depends(get_current_user)
):
    """Reset current user's learning profile to defaults"""
    try:
        profile = await learning_profile_service.reset_learning_profile(str(current_user.id))
        
        return ResponseBase(
            success=True,
            message="Learning profile reset successfully",
            data={
                "profile": {
                    "user_id": str(profile.user_id),
                    "preferred_teaching_style": profile.preferred_teaching_style.value,
                    "learning_velocity": profile.learning_velocity.value,
                    "strengths": profile.strengths,
                    "weaknesses": profile.weaknesses,
                    "preferences": profile.preferences,
                    "goals": profile.goals,
                    "updated_at": profile.updated_at
                }
            }
        )
    
    except Exception as e:
        logger.error(f"Error resetting learning profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset learning profile"
        )


@router.get("/me/adaptation-history", response_model=ResponseBase)
async def get_my_adaptation_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    """Get current user's learning profile adaptation history"""
    try:
        history = await learning_profile_service.get_adaptation_history(
            user_id=str(current_user.id),
            limit=limit
        )
        
        return ResponseBase(
            success=True,
            message="Adaptation history retrieved successfully",
            data={
                "user_id": str(current_user.id),
                "adaptations": history,
                "total_adaptations": len(history)
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting adaptation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve adaptation history"
        )


@router.get("/bulk/export", response_model=ResponseBase)
async def export_learning_profiles(
    format: str = "json",
    current_user: User = Depends(get_current_instructor)
):
    """Export all learning profiles (instructors only)"""
    try:
        if format not in ["json", "csv"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format must be 'json' or 'csv'"
            )
        
        export_data = await learning_profile_service.export_learning_profiles(format=format)
        
        return ResponseBase(
            success=True,
            message="Learning profiles exported successfully",
            data={
                "format": format,
                "export_data": export_data,
                "exported_at": "now"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting learning profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export learning profiles"
        )