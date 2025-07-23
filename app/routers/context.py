from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional, Dict, Any
import logging

from app.models import ResponseBase
from app.services.session_manager import session_manager
from app.services.context_compression import context_compression_manager
from app.services.conversation_service import conversation_service

router = APIRouter()
logger = logging.getLogger(__name__)

# TODO: Implement proper authentication and get current user
async def get_current_user() -> str:
    """Temporary function - replace with real authentication"""
    return "temp-user-id"


@router.get("/{session_id}", response_model=ResponseBase)
async def get_context_state(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get current context state and compression information"""
    try:
        context = await session_manager.get_session_context(session_id, current_user)
        
        return ResponseBase(
            success=True,
            message="Context state retrieved",
            data={
                "session_id": session_id,
                "compression_level": context.session.compression_level,
                "total_context_tokens": context.total_context_tokens,
                "session_number": context.session.session_number,
                "compression_metadata": context.compression_metadata,
                "has_compressed_summary": bool(context.compressed_summary),
                "has_learning_profile": bool(context.learning_profile_data),
                "recent_message_count": len(context.recent_messages)
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting context state: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve context state"
        )


@router.post("/{session_id}/compress", response_model=ResponseBase)
async def trigger_context_compression(
    session_id: str,
    target_level: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """Manually trigger context compression"""
    try:
        # Get current context
        context = await session_manager.get_session_context(session_id, current_user)
        
        # Get all conversations for compression
        all_messages = await conversation_service.get_conversation_history(
            session_id, include_archived=True
        )
        
        # Determine target compression level
        if target_level:
            from app.models import ContextCompressionLevel
            try:
                target_compression_level = ContextCompressionLevel(target_level)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid compression level: {target_level}"
                )
        else:
            # Auto-determine based on current state
            session_count = context.session.session_number
            total_tokens = context.total_context_tokens
            target_compression_level, compression_reason = await context_compression_manager.determine_compression_level(
                current_user, context.session.assignment_id, session_count, total_tokens
            )
        
        # Apply compression
        compression_result = await context_compression_manager.compress_context(
            current_user, context.session.assignment_id, all_messages, target_compression_level
        )
        
        # Update session with new compression level
        await session_manager.session_service.update_session(
            session_id,
            {
                "compression_level": target_compression_level,
                "context_metadata.compression_triggered": True,
                "context_metadata.compression_reason": "manual",
                "context_metadata.original_token_count": context.total_context_tokens,
                "context_metadata.compressed_token_count": compression_result.get("total_tokens")
            }
        )
        
        return ResponseBase(
            success=True,
            message="Context compression completed",
            data={
                "session_id": session_id,
                "compression_level": target_compression_level.value,
                "original_tokens": context.total_context_tokens,
                "compressed_tokens": compression_result.get("total_tokens"),
                "compression_ratio": compression_result.get("compression_metadata", {}).get("compression_ratio", 1.0),
                "compression_quality": compression_result.get("compression_metadata", {}).get("compression_quality", 0.0),
                "compression_time": compression_result.get("compression_metadata", {}).get("compression_time_seconds", 0.0)
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error triggering context compression: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compress context"
        )


@router.get("/{session_id}/summary", response_model=ResponseBase)
async def get_context_summary(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get compressed context summary"""
    try:
        context = await session_manager.get_session_context(session_id, current_user)
        
        return ResponseBase(
            success=True,
            message="Context summary retrieved",
            data={
                "session_id": session_id,
                "compression_level": context.session.compression_level,
                "compressed_summary": context.compressed_summary,
                "learning_profile": context.learning_profile_data,
                "compression_metadata": context.compression_metadata,
                "total_context_tokens": context.total_context_tokens
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting context summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve context summary"
        )


@router.get("/user/{username}/compression-stats", response_model=ResponseBase)
async def get_user_compression_stats(
    username: str,
    current_user: str = Depends(get_current_user)
):
    """Get user's compression statistics across all sessions"""
    try:
        # TODO: Implement proper user ID resolution
        user_id = username
        
        from app.database.connection import get_database
        db = await get_database()
        
        # Get compression statistics
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": "$compression_level",
                    "session_count": {"$sum": 1},
                    "avg_tokens": {"$avg": "$total_tokens"},
                    "total_tokens": {"$sum": "$total_tokens"}
                }
            }
        ]
        
        compression_stats = await db.sessions.aggregate(pipeline).to_list(10)
        
        # Get summary statistics
        total_sessions = await db.sessions.count_documents({"user_id": user_id})
        
        return ResponseBase(
            success=True,
            message="User compression statistics retrieved",
            data={
                "user_id": user_id,
                "total_sessions": total_sessions,
                "compression_distribution": compression_stats,
                "average_tokens_per_session": sum(stat["avg_tokens"] for stat in compression_stats) / len(compression_stats) if compression_stats else 0
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting user compression stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compression statistics"
        )


@router.delete("/{session_id}/summaries", response_model=ResponseBase)
async def clear_compressed_summaries(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Clear cached compressed summaries for a session"""
    try:
        # Verify session access
        context = await session_manager.get_session_context(session_id, current_user)
        
        from app.database.connection import get_database
        db = await get_database()
        
        # Clear compressed summaries
        result = await db.compressed_summaries.delete_many({
            "user_id": current_user,
            "assignment_id": context.session.assignment_id
        })
        
        return ResponseBase(
            success=True,
            message=f"Cleared {result.deleted_count} compressed summaries",
            data={
                "session_id": session_id,
                "summaries_cleared": result.deleted_count
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error clearing compressed summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear compressed summaries"
        )