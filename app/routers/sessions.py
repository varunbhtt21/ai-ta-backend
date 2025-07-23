from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import logging

from app.models import ResponseBase, SessionRequest, MessageRequest, SessionResponse
from app.services.session_manager import session_manager
from app.services.conversation_service import conversation_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Import authentication dependency
from app.routers.auth import get_current_user
from app.models import User


@router.post("/start", response_model=SessionResponse)
async def start_session(
    request: SessionRequest,
    current_user: User = Depends(get_current_user)
):
    """Start new tutoring session"""
    try:
        session_response = await session_manager.start_or_resume_session(
            user_id=str(current_user.id),
            request=request
        )
        return session_response
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start session"
        )


@router.get("/{session_id}", response_model=ResponseBase)
async def get_session_details(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get session details"""
    try:
        context = await session_manager.get_session_context(session_id, str(current_user.id))
        
        return ResponseBase(
            success=True,
            message="Session details retrieved",
            data={
                "session_id": session_id,
                "status": context.session.status,
                "current_problem": context.session.current_problem,
                "compression_level": context.session.compression_level,
                "total_tokens": context.total_context_tokens,
                "session_number": context.session.session_number,
                "started_at": context.session.started_at,
                "ended_at": context.session.ended_at
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting session details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session details"
        )


@router.post("/{session_id}/continue", response_model=ResponseBase)
async def continue_session(
    session_id: str,
    request: MessageRequest,
    current_user: User = Depends(get_current_user)
):
    """Continue existing session"""
    try:
        response_data = await session_manager.process_student_input(
            session_id=session_id,
            user_id=str(current_user.id),
            message_request=request
        )
        
        return ResponseBase(
            success=True,
            message="Message processed",
            data=response_data
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error continuing session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )


@router.put("/{session_id}/end", response_model=ResponseBase)
async def end_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """End session"""
    try:
        success = await session_manager.end_session(session_id, str(current_user.id))
        
        if success:
            return ResponseBase(
                success=True,
                message="Session ended successfully",
                data={"session_id": session_id}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to end session"
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error ending session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end session"
        )


@router.get("/{session_id}/messages", response_model=ResponseBase)
async def get_conversation_history(
    session_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get conversation history"""
    try:
        # Verify session access
        context = await session_manager.get_session_context(session_id, str(current_user.id))
        
        # Get conversation history
        messages = await conversation_service.get_conversation_history(
            session_id=session_id,
            limit=limit
        )
        
        message_data = []
        for msg in messages:
            message_data.append({
                "timestamp": msg.timestamp,
                "message_type": msg.message_type.value,
                "content": msg.content,
                "metadata": msg.metadata
            })
        
        return ResponseBase(
            success=True,
            message="Conversation history retrieved",
            data={
                "session_id": session_id,
                "messages": message_data,
                "total_messages": len(message_data)
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation history"
        )


@router.get("/user/{username}/sessions", response_model=ResponseBase)
async def get_user_sessions(
    username: str,
    assignment_id: str = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Get user's session history"""
    try:
        # TODO: Implement proper user authorization check
        
        from app.services.session_service import session_service
        sessions = await session_service.get_user_sessions(
            user_id=str(current_user.id),  # Use authenticated user ID
            assignment_id=assignment_id,
            limit=limit
        )
        
        session_data = []
        for session in sessions:
            session_data.append({
                "session_id": str(session.id),
                "assignment_id": session.assignment_id,
                "session_number": session.session_number,
                "status": session.status,
                "compression_level": session.compression_level,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
                "current_problem": session.current_problem,
                "total_messages": session.total_messages,
                "total_tokens": session.total_tokens
            })
        
        return ResponseBase(
            success=True,
            message="User sessions retrieved",
            data={
                "username": current_user.username,
                "sessions": session_data,
                "total_sessions": len(session_data)
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user sessions"
        )