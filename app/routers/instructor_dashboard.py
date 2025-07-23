from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

from app.models import ResponseBase, User
from app.routers.auth import get_current_instructor
from app.services.assignment_service import assignment_service
from app.services.session_service import session_service
from app.services.progress_service import progress_service
from app.services.learning_profile_service import learning_profile_service
from app.services.auth_service import auth_service

router = APIRouter()
logger = logging.getLogger(__name__)


class DashboardFilters(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    assignment_id: Optional[str] = None
    student_id: Optional[str] = None


@router.get("/overview", response_model=ResponseBase)
async def get_dashboard_overview(
    current_user: User = Depends(get_current_instructor)
):
    """Get instructor dashboard overview statistics"""
    try:
        # Get basic counts
        total_assignments = await assignment_service.get_instructor_assignment_count(str(current_user.id))
        total_students = await auth_service.get_student_count()
        
        # Get recent activity (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_sessions = await session_service.get_recent_sessions_count(
            instructor_id=str(current_user.id),
            since=seven_days_ago
        )
        
        # Get completion statistics
        completion_stats = await progress_service.get_completion_statistics(
            instructor_id=str(current_user.id)
        )
        
        # Get active sessions
        active_sessions = await session_service.get_active_sessions_count(
            instructor_id=str(current_user.id)
        )
        
        return ResponseBase(
            success=True,
            message="Dashboard overview retrieved successfully",
            data={
                "overview": {
                    "total_assignments": total_assignments,
                    "total_students": total_students,
                    "recent_sessions": recent_sessions,
                    "active_sessions": active_sessions,
                    "completion_stats": completion_stats
                },
                "instructor": {
                    "id": str(current_user.id),
                    "name": current_user.full_name or current_user.username
                },
                "generated_at": datetime.utcnow().isoformat()
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting dashboard overview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard overview"
        )


@router.get("/students/activity", response_model=ResponseBase)
async def get_student_activity_report(
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_instructor)
):
    """Get student activity report for specified time period"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get student activity data
        student_activity = await session_service.get_student_activity_report(
            instructor_id=str(current_user.id),
            start_date=start_date,
            limit=limit
        )
        
        # Get learning progress for active students
        progress_data = []
        for activity in student_activity:
            progress = await progress_service.get_user_progress_summary(
                activity["user_id"]
            )
            progress_data.append({
                "user_id": activity["user_id"],
                "username": activity["username"],
                "activity": activity,
                "progress": progress
            })
        
        return ResponseBase(
            success=True,
            message="Student activity report retrieved successfully",
            data={
                "report": {
                    "period_days": days,
                    "total_students": len(student_activity),
                    "students": progress_data
                },
                "generated_at": datetime.utcnow().isoformat()
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting student activity report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve student activity report"
        )


@router.get("/assignments/performance", response_model=ResponseBase)
async def get_assignment_performance_report(
    assignment_id: Optional[str] = None,
    current_user: User = Depends(get_current_instructor)
):
    """Get assignment performance analytics"""
    try:
        if assignment_id:
            # Get specific assignment performance
            performance = await assignment_service.get_assignment_performance_analytics(
                assignment_id=assignment_id,
                instructor_id=str(current_user.id)
            )
            
            return ResponseBase(
                success=True,
                message="Assignment performance retrieved successfully",
                data={
                    "assignment_id": assignment_id,
                    "performance": performance,
                    "generated_at": datetime.utcnow().isoformat()
                }
            )
        else:
            # Get all assignments performance summary
            assignments = await assignment_service.get_instructor_assignments(
                instructor_id=str(current_user.id)
            )
            
            performance_data = []
            for assignment in assignments:
                performance = await assignment_service.get_assignment_performance_analytics(
                    assignment_id=str(assignment.id),
                    instructor_id=str(current_user.id)
                )
                performance_data.append({
                    "assignment_id": str(assignment.id),
                    "title": assignment.title,
                    "performance": performance
                })
            
            return ResponseBase(
                success=True,
                message="All assignments performance retrieved successfully",
                data={
                    "assignments": performance_data,
                    "total_assignments": len(performance_data),
                    "generated_at": datetime.utcnow().isoformat()
                }
            )
    
    except Exception as e:
        logger.error(f"Error getting assignment performance report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignment performance report"
        )


@router.get("/learning-analytics", response_model=ResponseBase)
async def get_learning_analytics_report(
    current_user: User = Depends(get_current_instructor)
):
    """Get comprehensive learning analytics for instructor's students"""
    try:
        # Get learning profiles analytics
        profiles_analytics = await learning_profile_service.get_learning_profiles_analytics()
        
        # Get teaching style effectiveness
        teaching_effectiveness = await progress_service.get_teaching_style_effectiveness(
            instructor_id=str(current_user.id)
        )
        
        # Get learning velocity trends
        velocity_trends = await progress_service.get_learning_velocity_trends(
            instructor_id=str(current_user.id)
        )
        
        # Get common difficulty patterns
        difficulty_patterns = await progress_service.get_difficulty_patterns(
            instructor_id=str(current_user.id)
        )
        
        return ResponseBase(
            success=True,
            message="Learning analytics retrieved successfully",
            data={
                "analytics": {
                    "learning_profiles": profiles_analytics,
                    "teaching_effectiveness": teaching_effectiveness,
                    "velocity_trends": velocity_trends,
                    "difficulty_patterns": difficulty_patterns
                },
                "instructor_id": str(current_user.id),
                "generated_at": datetime.utcnow().isoformat()
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting learning analytics report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve learning analytics"
        )


@router.get("/engagement/metrics", response_model=ResponseBase)
async def get_engagement_metrics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_instructor)
):
    """Get student engagement metrics"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get session engagement data
        engagement_data = await session_service.get_engagement_metrics(
            instructor_id=str(current_user.id),
            start_date=start_date
        )
        
        # Get completion rates
        completion_rates = await progress_service.get_completion_rates_over_time(
            instructor_id=str(current_user.id),
            start_date=start_date
        )
        
        # Get interaction patterns
        interaction_patterns = await session_service.get_interaction_patterns(
            instructor_id=str(current_user.id),
            start_date=start_date
        )
        
        return ResponseBase(
            success=True,
            message="Engagement metrics retrieved successfully",
            data={
                "metrics": {
                    "period_days": days,
                    "engagement": engagement_data,
                    "completion_rates": completion_rates,
                    "interaction_patterns": interaction_patterns
                },
                "generated_at": datetime.utcnow().isoformat()
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting engagement metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve engagement metrics"
        )


@router.get("/progress/detailed/{student_id}", response_model=ResponseBase)
async def get_detailed_student_progress(
    student_id: str,
    assignment_id: Optional[str] = None,
    current_user: User = Depends(get_current_instructor)
):
    """Get detailed progress report for specific student"""
    try:
        # Get student information
        student = await auth_service.get_user_by_id(student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        # Get detailed progress
        progress = await progress_service.get_detailed_student_progress(
            user_id=student_id,
            assignment_id=assignment_id,
            instructor_id=str(current_user.id)
        )
        
        # Get learning profile
        learning_profile = await learning_profile_service.get_learning_profile(student_id)
        
        # Get recent sessions
        recent_sessions = await session_service.get_user_recent_sessions(
            user_id=student_id,
            limit=10
        )
        
        return ResponseBase(
            success=True,
            message="Detailed student progress retrieved successfully",
            data={
                "student": {
                    "id": student_id,
                    "username": student.username,
                    "full_name": student.full_name
                },
                "progress": progress,
                "learning_profile": learning_profile.model_dump() if learning_profile else None,
                "recent_sessions": recent_sessions,
                "generated_at": datetime.utcnow().isoformat()
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detailed student progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve detailed student progress"
        )


@router.get("/trends/weekly", response_model=ResponseBase)
async def get_weekly_trends(
    weeks: int = Query(12, ge=1, le=52),
    current_user: User = Depends(get_current_instructor)
):
    """Get weekly activity and progress trends"""
    try:
        start_date = datetime.utcnow() - timedelta(weeks=weeks)
        
        # Get weekly session counts
        weekly_sessions = await session_service.get_weekly_session_trends(
            instructor_id=str(current_user.id),
            start_date=start_date
        )
        
        # Get weekly completion trends
        weekly_completions = await progress_service.get_weekly_completion_trends(
            instructor_id=str(current_user.id),
            start_date=start_date
        )
        
        # Get weekly engagement trends
        weekly_engagement = await session_service.get_weekly_engagement_trends(
            instructor_id=str(current_user.id),
            start_date=start_date
        )
        
        return ResponseBase(
            success=True,
            message="Weekly trends retrieved successfully",
            data={
                "trends": {
                    "period_weeks": weeks,
                    "sessions": weekly_sessions,
                    "completions": weekly_completions,
                    "engagement": weekly_engagement
                },
                "generated_at": datetime.utcnow().isoformat()
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting weekly trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve weekly trends"
        )


@router.post("/export", response_model=ResponseBase)
async def export_analytics_data(
    filters: DashboardFilters,
    export_format: str = Query("json", regex="^(json|csv)$"),
    current_user: User = Depends(get_current_instructor)
):
    """Export analytics data in specified format"""
    try:
        # Build export data based on filters
        export_data = await progress_service.export_analytics_data(
            instructor_id=str(current_user.id),
            filters=filters.model_dump(),
            format=export_format
        )
        
        return ResponseBase(
            success=True,
            message="Analytics data exported successfully",
            data={
                "export": {
                    "format": export_format,
                    "filters": filters.model_dump(),
                    "data": export_data
                },
                "exported_by": {
                    "instructor_id": str(current_user.id),
                    "instructor_name": current_user.full_name or current_user.username
                },
                "exported_at": datetime.utcnow().isoformat()
            }
        )
    
    except Exception as e:
        logger.error(f"Error exporting analytics data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export analytics data"
        )