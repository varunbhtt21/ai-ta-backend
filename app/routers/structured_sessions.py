"""
Structured Sessions Router - Implements OOP prototype teaching methodology
This router provides endpoints for the structured tutoring approach.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging

from app.models import ResponseBase, User
from app.routers.auth import get_current_user
from app.services.enhanced_session_service import enhanced_session_service
from app.services.assignment_service import assignment_service

router = APIRouter()
logger = logging.getLogger(__name__)


class StartStructuredSessionRequest(BaseModel):
    assignment_id: str


class StructuredMessageRequest(BaseModel):
    session_id: str
    message: str
    problem_context: Optional[Dict[str, Any]] = None


class StructuredSessionResponse(BaseModel):
    session_id: str
    session_number: int
    compression_level: str
    current_problem: int
    total_problems: int
    message: str
    student_state: str
    teaching_notes: Optional[List[str]] = []
    resumed: Optional[bool] = False


class StructuredMessageResponse(BaseModel):
    message: str
    student_state: str
    tutoring_mode: str
    next_expected_input: str
    teaching_notes: List[str]
    current_problem: int
    session_id: str


@router.post("/structured/start", response_model=ResponseBase)
async def start_structured_session(
    request: StartStructuredSessionRequest,
    current_user: User = Depends(get_current_user)
):
    """Start a structured tutoring session using OOP prototype methodology"""
    
    logger.info(f"Starting structured session for user {current_user.id} on assignment {request.assignment_id}")
    
    try:
        # Verify assignment exists
        assignment = await assignment_service.get_assignment(request.assignment_id)
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
        
        # Start the intelligent session
        session_data = await enhanced_session_service.start_intelligent_session(
            user_id=str(current_user.id),
            assignment_id=request.assignment_id
        )
        
        return ResponseBase(
            success=True,
            message="Structured tutoring session started successfully",
            data=StructuredSessionResponse(**session_data)
        )
        
    except ValueError as e:
        logger.error(f"Validation error starting structured session: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting structured session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start structured session"
        )


@router.post("/structured/message", response_model=ResponseBase)
async def send_structured_message(
    request: StructuredMessageRequest,
    current_user: User = Depends(get_current_user)
):
    """Send a message in a structured tutoring session"""
    
    logger.info("🚀 BACKEND: Received structured message request")
    logger.info(f"📤 BACKEND: Session ID: {request.session_id}")
    logger.info(f"💬 BACKEND: User message: '{request.message}'")
    logger.info(f"👤 BACKEND: User ID: {current_user.id}")
    logger.info(f"📋 BACKEND: Problem context provided: {bool(request.problem_context)}")
    if request.problem_context:
        logger.info(f"📝 BACKEND: Problem context: {request.problem_context}")
    
    try:
        # Verify session exists and belongs to user
        logger.info("🔍 BACKEND: Verifying session exists...")
        session = await enhanced_session_service.get_session(request.session_id)
        if not session:
            logger.error(f"❌ BACKEND: Session {request.session_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        logger.info(f"✅ BACKEND: Session found - User: {session.user_id}")
        
        if session.user_id != str(current_user.id):
            logger.error(f"❌ BACKEND: Access denied - Session user: {session.user_id}, Current user: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )
        
        logger.info("✅ BACKEND: Session validation passed")
        
        # Process the message using structured approach
        logger.info("🧠 BACKEND: Calling enhanced_session_service.process_student_message...")
        response_data = await enhanced_session_service.process_student_message(
            session_id=request.session_id,
            user_input=request.message,
            problem_context=request.problem_context
        )
        
        logger.info("✅ BACKEND: Message processed successfully")
        logger.info(f"🤖 BACKEND: AI response: '{response_data.get('message', 'No message')}'")
        logger.info(f"📊 BACKEND: Student state: {response_data.get('student_state', 'Unknown')}")
        logger.info(f"🎯 BACKEND: Tutoring mode: {response_data.get('tutoring_mode', 'Unknown')}")
        
        # Check if this is a fallback response
        ai_message = response_data.get('message', '')
        if ai_message == "Can you think about what the problem is asking you to do step by step?":
            logger.error("🚨 BACKEND: DETECTED FALLBACK RESPONSE! OpenAI call likely failed!")
        else:
            logger.info("✅ BACKEND: Response appears to be dynamically generated")
        
        structured_response = StructuredMessageResponse(**response_data)
        logger.info(f"📦 BACKEND: Returning response: {structured_response}")
        
        return ResponseBase(
            success=True,
            message="Message processed successfully",
            data=structured_response
        )
        
    except ValueError as e:
        logger.error(f"Validation error processing message: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error processing structured message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )


@router.get("/structured/{session_id}/status", response_model=ResponseBase)
async def get_structured_session_status(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get current status of a structured tutoring session"""
    
    try:
        # Verify session exists and belongs to user
        session = await enhanced_session_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )
        
        # Get assignment details
        assignment = await assignment_service.get_assignment(session.assignment_id)
        
        # Get current problem number
        current_problem_number = await enhanced_session_service._get_current_problem_number(
            session.user_id, session.assignment_id
        )
        
        status_data = {
            "session_id": session_id,
            "session_number": session.session_number,
            "status": session.status.value,
            "compression_level": session.compression_level.value,
            "current_problem": current_problem_number,
            "total_problems": len(assignment.problems) if assignment else 0,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.updated_at.isoformat() if session.updated_at else None,
            "current_student_state": getattr(session, 'current_student_state', 'unknown'),
            "tutoring_mode": getattr(session, 'tutoring_mode', 'unknown')
        }
        
        return ResponseBase(
            success=True,
            message="Session status retrieved successfully",
            data=status_data
        )
        
    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session status"
        )


@router.post("/structured/{session_id}/end", response_model=ResponseBase)
async def end_structured_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """End a structured tutoring session"""
    
    try:
        # Verify session exists and belongs to user
        session = await enhanced_session_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )
        
        # End the session
        success = await enhanced_session_service.end_session(session_id)
        
        if success:
            return ResponseBase(
                success=True,
                message="Structured session ended successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to end session"
            )
        
    except Exception as e:
        logger.error(f"Error ending structured session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to end session"
        )


@router.get("/structured/debug/conversation/{session_id}", response_model=ResponseBase)
async def get_structured_conversation_debug(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Debug endpoint to view structured conversation flow"""
    
    try:
        # Verify session exists and belongs to user
        session = await enhanced_session_service.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        if session.user_id != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this session"
            )
        
        # Get conversation history
        conversation = await enhanced_session_service._get_session_conversation(session_id)
        
        debug_data = {
            "session_id": session_id,
            "total_messages": len(conversation),
            "conversation": [
                {
                    "timestamp": msg.timestamp,
                    "type": msg.message_type.value,
                    "content": msg.content,
                    "metadata": msg.metadata
                }
                for msg in conversation
            ],
            "current_state": getattr(session, 'current_student_state', 'unknown'),
            "tutoring_mode": getattr(session, 'tutoring_mode', 'unknown')
        }
        
        return ResponseBase(
            success=True,
            message="Debug conversation data retrieved",
            data=debug_data
        )
        
    except Exception as e:
        logger.error(f"Error getting debug conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get debug conversation"
        )


@router.get("/structured/methodology", response_model=ResponseBase)
async def get_structured_methodology():
    """Get information about the structured tutoring methodology"""
    
    methodology_info = {
        "name": "OOP Prototype Structured Teaching Methodology",
        "description": "A structured approach to AI tutoring that follows specific conversation flows",
        "key_principles": [
            "Never give direct solutions or code examples",
            "Only present problem statement when student is ready",
            "Ask 'How are you thinking to solve this?' after presenting problem",
            "Guide through questions, NOT answers",
            "When student is stuck, break problem into smaller pieces",
            "Give hints that lead to discovery, never direct solutions",
            "Only provide code after student has figured out logic themselves"
        ],
        "conversation_flow": [
            "Student says ready → Present ONLY the problem statement",
            "Ask: 'How are you thinking to solve this question?'",
            "Listen to their approach",
            "If correct approach → encourage and ask for code",
            "If stuck → ask guiding questions or simplify the problem",
            "If code has issues → point out issue with hints, don't fix it",
            "Only when they solve correctly → celebrate and move to next problem"
        ],
        "student_states": [
            "INITIAL_GREETING - Student just joined",
            "READY_TO_START - Student indicated readiness",
            "PROBLEM_PRESENTED - Problem has been shown",
            "AWAITING_APPROACH - Waiting for student's solution approach",
            "WORKING_ON_CODE - Student is coding",
            "STUCK_NEEDS_HELP - Student needs guidance",
            "CODE_REVIEW - Analyzing student's code",
            "PROBLEM_COMPLETED - Student solved the problem"
        ],
        "tutoring_modes": [
            "PROBLEM_PRESENTATION - Showing the problem",
            "APPROACH_INQUIRY - Asking for approach",
            "GUIDED_QUESTIONING - Guiding with questions",
            "CODE_ANALYSIS - Analyzing submitted code",
            "HINT_PROVIDING - Giving guided hints",
            "ENCOURAGEMENT - Providing motivation",
            "CELEBRATION - Celebrating success"
        ]
    }
    
    return ResponseBase(
        success=True,
        message="Structured methodology information",
        data=methodology_info
    )