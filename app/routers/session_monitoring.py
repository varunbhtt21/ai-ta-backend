"""
Session Monitoring API Router
Provides endpoints for session monitoring, health checks, and cleanup operations
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, Dict, Any
import logging

from app.models import ResponseBase, User
from app.routers.auth import get_current_instructor, get_current_admin
from app.services.session_monitoring import session_monitoring_service
from app.services.cleanup_scheduler import cleanup_scheduler

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=ResponseBase)
async def get_session_health(
    current_user: User = Depends(get_current_instructor)
):
    """Get session system health status"""
    try:
        health_report = await session_monitoring_service.generate_health_report()
        
        return ResponseBase(
            success=True,
            message="Session health report generated successfully",
            data=health_report
        )
        
    except Exception as e:
        logger.error(f"Error generating health report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate health report"
        )


@router.get("/statistics", response_model=ResponseBase)
async def get_session_statistics(
    current_user: User = Depends(get_current_instructor)
):
    """Get comprehensive session statistics"""
    try:
        stats = await session_monitoring_service.get_session_statistics()
        
        return ResponseBase(
            success=True,
            message="Session statistics retrieved successfully",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Error getting session statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session statistics"
        )


@router.get("/duplicates", response_model=ResponseBase)
async def detect_duplicate_sessions(
    current_user: User = Depends(get_current_instructor)
):
    """Detect duplicate active sessions"""
    try:
        duplicates = await session_monitoring_service.detect_duplicate_sessions()
        
        return ResponseBase(
            success=True,
            message=f"Found {len(duplicates)} sets of duplicate sessions",
            data={
                "duplicates": duplicates,
                "total_sets": len(duplicates),
                "scan_completed_at": session_monitoring_service._get_db().__class__.__name__
            }
        )
        
    except Exception as e:
        logger.error(f"Error detecting duplicate sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to detect duplicate sessions"
        )


@router.get("/unused", response_model=ResponseBase)
async def detect_unused_sessions(
    hours_threshold: int = Query(default=1, ge=1, le=24),
    current_user: User = Depends(get_current_instructor)
):
    """Detect unused sessions"""
    try:
        unused_sessions = await session_monitoring_service.detect_unused_sessions(
            hours_threshold=hours_threshold
        )
        
        return ResponseBase(
            success=True,
            message=f"Found {len(unused_sessions)} unused sessions",
            data={
                "unused_sessions": unused_sessions,
                "total_count": len(unused_sessions),
                "hours_threshold": hours_threshold,
                "scan_completed_at": session_monitoring_service._get_db().__class__.__name__
            }
        )
        
    except Exception as e:
        logger.error(f"Error detecting unused sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to detect unused sessions"
        )


@router.post("/cleanup/unused", response_model=ResponseBase)
async def cleanup_unused_sessions(
    hours_threshold: int = Query(default=2, ge=1, le=48),
    dry_run: bool = Query(default=False),
    current_user: User = Depends(get_current_admin)
):
    """Clean up unused sessions (Admin only)"""
    try:
        cleaned_count = await session_monitoring_service.cleanup_unused_sessions(
            hours_threshold=hours_threshold,
            dry_run=dry_run
        )
        
        action = "Would clean up" if dry_run else "Cleaned up"
        
        return ResponseBase(
            success=True,
            message=f"{action} {cleaned_count} unused sessions",
            data={
                "cleaned_count": cleaned_count,
                "hours_threshold": hours_threshold,
                "dry_run": dry_run,
                "cleanup_completed_at": session_monitoring_service._get_db().__class__.__name__
            }
        )
        
    except Exception as e:
        logger.error(f"Error cleaning up unused sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clean up unused sessions"
        )


@router.post("/cleanup/conversations", response_model=ResponseBase)
async def cleanup_old_conversations(
    days_threshold: int = Query(default=30, ge=7, le=365),
    dry_run: bool = Query(default=False),
    current_user: User = Depends(get_current_admin)
):
    """Archive old conversation data (Admin only)"""
    try:
        archived_count = await session_monitoring_service.cleanup_old_completed_sessions(
            days_threshold=days_threshold,
            dry_run=dry_run
        )
        
        action = "Would archive" if dry_run else "Archived"
        
        return ResponseBase(
            success=True,
            message=f"{action} conversations for {archived_count} old sessions",
            data={
                "archived_count": archived_count,
                "days_threshold": days_threshold,
                "dry_run": dry_run,
                "cleanup_completed_at": session_monitoring_service._get_db().__class__.__name__
            }
        )
        
    except Exception as e:
        logger.error(f"Error archiving old conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to archive old conversations"
        )


@router.post("/cleanup/force", response_model=ResponseBase)
async def force_cleanup(
    cleanup_type: str = Query(default="all", regex="^(all|unused|conversations|duplicates)$"),
    current_user: User = Depends(get_current_admin)
):
    """Force immediate cleanup (Admin only)"""
    try:
        results = await cleanup_scheduler.force_cleanup(cleanup_type=cleanup_type)
        
        return ResponseBase(
            success=True,
            message=f"Force cleanup completed: {cleanup_type}",
            data=results
        )
        
    except Exception as e:
        logger.error(f"Error in force cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute force cleanup"
        )


@router.get("/scheduler/status", response_model=ResponseBase)
async def get_scheduler_status(
    current_user: User = Depends(get_current_instructor)
):
    """Get cleanup scheduler status"""
    try:
        stats = cleanup_scheduler.get_stats()
        health_status = await cleanup_scheduler.get_health_status()
        
        return ResponseBase(
            success=True,
            message="Scheduler status retrieved successfully",
            data={
                "scheduler_stats": stats,
                "health_status": health_status
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get scheduler status"
        )


@router.post("/scheduler/start", response_model=ResponseBase)
async def start_scheduler(
    current_user: User = Depends(get_current_admin)
):
    """Start cleanup scheduler (Admin only)"""
    try:
        await cleanup_scheduler.start()
        
        return ResponseBase(
            success=True,
            message="Cleanup scheduler started successfully",
            data={"status": "started"}
        )
        
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start scheduler"
        )


@router.post("/scheduler/stop", response_model=ResponseBase)
async def stop_scheduler(
    current_user: User = Depends(get_current_admin)
):
    """Stop cleanup scheduler (Admin only)"""
    try:
        await cleanup_scheduler.stop()
        
        return ResponseBase(
            success=True,
            message="Cleanup scheduler stopped successfully",
            data={"status": "stopped"}
        )
        
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop scheduler"
        )


@router.get("/dashboard", response_model=ResponseBase)
async def get_monitoring_dashboard(
    current_user: User = Depends(get_current_instructor)
):
    """Get comprehensive monitoring dashboard data"""
    try:
        # Get all monitoring data in parallel
        import asyncio
        
        health_report_task = session_monitoring_service.generate_health_report()
        stats_task = session_monitoring_service.get_session_statistics()
        scheduler_stats_task = cleanup_scheduler.get_stats()
        health_status_task = cleanup_scheduler.get_health_status()
        
        health_report, stats, scheduler_stats, health_status = await asyncio.gather(
            health_report_task,
            stats_task,
            asyncio.create_task(asyncio.coroutine(lambda: scheduler_stats)()),
            health_status_task
        )
        
        dashboard_data = {
            "health_report": health_report,
            "session_statistics": stats,
            "scheduler_stats": scheduler_stats,
            "current_health_status": health_status,
            "dashboard_generated_at": session_monitoring_service._get_db().__class__.__name__
        }
        
        return ResponseBase(
            success=True,
            message="Monitoring dashboard data retrieved successfully",
            data=dashboard_data
        )
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard data"
        )