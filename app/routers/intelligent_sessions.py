from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from app.models import (
    ResponseBase, SessionRequest, MessageRequest, SessionResponse,
    MessageType, InputType, ContextCompressionLevel, ResumeType
)
from app.services.session_manager import session_manager
from app.services.context_compression import context_compression_manager
from app.services.resume_detection import resume_detection_service
from app.services.problem_presenter import structured_problem_presenter
from app.services.input_classifier import input_classifier
from app.services.session_service import session_service
from app.services.assignment_service import assignment_service
from app.services.learning_profile_service import learning_profile_service

# Import authentication dependency
from app.routers.auth import get_current_user
from app.models import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/intelligent/start", response_model=SessionResponse)
async def start_intelligent_session(
    request: SessionRequest,
    current_user: User = Depends(get_current_user)
):
    """Start intelligent tutoring session with context compression and resume detection"""
    try:
        user_id = str(current_user.id)
        
        # Step 1: Intelligent resume detection
        resume_analysis = await resume_detection_service.determine_resume_type(
            user_id=user_id,
            assignment_id=request.assignment_id
        )
        
        # Step 2: Start session using intelligent session management
        from app.services.session_manager import SessionManager
        intelligent_session_manager = SessionManager()
        
        # Enhance the request with resume analysis
        enhanced_request = SessionRequest(
            assignment_id=request.assignment_id,
            resume_session=resume_analysis["should_resume"],
            session_id=resume_analysis.get("recommended_session_id")
        )
        
        # Create/resume session
        session_response = await intelligent_session_manager.start_intelligent_session(
            user_id=user_id,
            request=enhanced_request
        )
        
        # Step 3: Get assignment for problem information
        assignment = await assignment_service.get_assignment(request.assignment_id)
        if assignment:
            session_response.total_problems = assignment.total_problems
        
        # Step 4: Add intelligent context to response
        session_response.message = resume_analysis.get("welcome_message", "Session ready")
        
        # Add resume analysis metadata
        return SessionResponse(
            session_id=session_response.session_id,
            assignment_id=session_response.assignment_id,
            status=session_response.status,
            message=session_response.message,
            current_problem=session_response.current_problem,
            total_problems=session_response.total_problems,
            session_number=session_response.session_number,
            compression_level=session_response.compression_level,
            metadata={
                "resume_type": resume_analysis["resume_type"],
                "intelligence_level": "full",
                "features_enabled": [
                    "context_compression",
                    "intelligent_resume", 
                    "smart_prompts",
                    "adaptive_teaching"
                ]
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting intelligent session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start intelligent session"
        )


@router.post("/{session_id}/intelligent/message", response_model=ResponseBase)
async def process_intelligent_message(
    session_id: str,
    request: MessageRequest,
    current_user: User = Depends(get_current_user)
):
    """Process student message using intelligent response generation system"""
    try:
        user_id = str(current_user.id)
        
        # Step 1: Get session context
        session_context = await session_manager.get_session_context(session_id, user_id)
        session_data = session_context.session
        
        # Step 2: Get conversation history for context compression
        from app.services.conversation_service import conversation_service
        conversation_history = await conversation_service.get_conversation_history(
            session_id=session_id,
            limit=None  # Get all for compression analysis
        )
        
        # Step 3: Determine compression level and compress context
        compression_level, compression_reason = await context_compression_manager.determine_compression_level(
            user_id=user_id,
            assignment_id=session_data.assignment_id,
            session_count=session_data.session_number,
            total_tokens=session_data.total_tokens
        )
        
        # Compress context based on determined level
        compression_result = await context_compression_manager.compress_context(
            user_id=user_id,
            assignment_id=session_data.assignment_id,
            conversations=conversation_history,
            target_level=compression_level
        )
        
        # Step 4: Get current problem data
        assignment = await assignment_service.get_assignment(session_data.assignment_id)
        current_problem = None
        if assignment and session_data.current_problem <= len(assignment.problems):
            current_problem = assignment.problems[session_data.current_problem - 1]
        
        # Step 5: Get learning profile
        learning_profile = await learning_profile_service.get_learning_profile(user_id)
        learning_profile_dict = learning_profile.model_dump() if learning_profile else None
        
        # TODO: Replace with structured tutoring engine
        # For now, return a basic response
        response_result = {
            "success": True,
            "response": "I'm here to help you learn! What would you like to work on?",
            "input_classification": "general_chat",
            "teaching_strategy": {"primary_approach": "basic"},
            "prompt_template": "basic",
            "tokens_used": 0
        }
        
        # Step 8: Save user message to conversation
        await conversation_service.add_message(
            session_id=session_id,
            user_id=user_id,
            message_type=MessageType.USER,
            content=request.content,
            metadata={
                "input_classification": response_result.get("input_classification"),
                "compression_level": compression_result.get("compression_level").value if compression_result.get("compression_level") else None,
                "teaching_strategy": response_result.get("teaching_strategy", {}).get("primary_approach")
            }
        )
        
        # Step 9: Save AI response to conversation (if successful)
        if response_result["success"]:
            await conversation_service.add_message(
                session_id=session_id,
                user_id=user_id,
                message_type=MessageType.ASSISTANT,
                content=response_result["response"],
                metadata={
                    "prompt_template": response_result.get("prompt_template"),
                    "teaching_strategy": response_result.get("teaching_strategy"),
                    "tokens_used": response_result.get("tokens_used"),
                    "adaptations_applied": response_result.get("adaptations_applied", []),
                    "compression_level": response_result.get("compression_level")
                }
            )
        
        # Step 10: Update session compression level if needed
        if compression_level != session_data.compression_level:
            await session_service.update_session(
                session_id,
                {"compression_level": compression_level.value}
            )
        
        return ResponseBase(
            success=response_result["success"],
            message="Intelligent response generated",
            data={
                "ai_response": response_result["response"],
                "session_id": session_id,
                "intelligence_metadata": {
                    "prompt_template": response_result.get("prompt_template"),
                    "teaching_strategy": response_result.get("teaching_strategy"),
                    "input_classification": response_result.get("input_classification"),
                    "context_level": response_result.get("context_level"),
                    "compression_level": response_result.get("compression_level"),
                    "adaptations_applied": response_result.get("adaptations_applied", []),
                    "tokens_used": response_result.get("tokens_used"),
                    "compression_ratio": compression_result.get("compression_metadata", {}).get("compression_ratio")
                },
                "session_info": {
                    "current_problem": session_data.current_problem,
                    "session_number": session_data.session_number,
                    "total_tokens": session_data.total_tokens,
                    "compression_triggered": compression_result.get("compression_metadata", {}).get("compression_ratio", 1.0) > 1.0
                }
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error processing intelligent message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process intelligent message"
        )


@router.get("/{session_id}/intelligent/problem", response_model=ResponseBase)
async def get_intelligent_problem_presentation(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get intelligent problem presentation based on student context"""
    try:
        user_id = str(current_user.id)
        
        # Get session context
        session_context = await session_manager.get_session_context(session_id, user_id)
        session_data = session_context.session
        
        # Get assignment and current problem
        assignment = await assignment_service.get_assignment(session_data.assignment_id)
        if not assignment:
            raise ValueError("Assignment not found")
        
        if session_data.current_problem > len(assignment.problems):
            raise ValueError("Invalid problem number")
        
        current_problem = assignment.problems[session_data.current_problem - 1]
        
        # Get learning profile
        learning_profile = await learning_profile_service.get_learning_profile(user_id)
        learning_profile_dict = learning_profile.model_dump() if learning_profile else None
        
        # Get compression context
        from app.services.conversation_service import conversation_service
        conversation_history = await conversation_service.get_conversation_history(
            session_id=session_id,
            limit=100  # Recent history for compression
        )
        
        compression_level, _ = await context_compression_manager.determine_compression_level(
            user_id=user_id,
            assignment_id=session_data.assignment_id,
            session_count=session_data.session_number,
            total_tokens=session_data.total_tokens
        )
        
        compression_result = await context_compression_manager.compress_context(
            user_id=user_id,
            assignment_id=session_data.assignment_id,
            conversations=conversation_history,
            target_level=compression_level
        )
        
        # Generate structured problem presentation
        presentation_result = await structured_problem_presenter.present_problem(
            problem=current_problem,
            user_id=user_id,
            session_id=session_id,
            assignment_id=session_data.assignment_id,
            learning_profile=learning_profile_dict,
            session_context=session_data.model_dump(),
            compression_result=compression_result
        )
        
        return ResponseBase(
            success=presentation_result["success"],
            message="Intelligent problem presentation generated",
            data={
                "problem_presentation": presentation_result["presentation"],
                "problem_info": {
                    "problem_id": presentation_result["problem_id"],
                    "presentation_style": presentation_result["presentation_style"],
                    "problem_complexity": presentation_result["problem_complexity"],
                    "estimated_difficulty": presentation_result["estimated_difficulty"],
                    "adaptations_applied": presentation_result["adaptations_applied"],
                    "learning_objectives": presentation_result["learning_objectives"]
                },
                "intelligence_metadata": {
                    "compression_level": compression_result.get("compression_level").value if compression_result.get("compression_level") else None,
                    "scaffolding_level": presentation_result["metadata"]["scaffolding_level"],
                    "concepts_covered": presentation_result["metadata"]["concepts_covered"],
                    "prerequisite_check": presentation_result["metadata"]["prerequisite_check"]
                }
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating intelligent problem presentation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate intelligent problem presentation"
        )


@router.get("/{session_id}/intelligent/context", response_model=ResponseBase)
async def get_session_intelligence_status(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed intelligence status and context information for the session"""
    try:
        user_id = str(current_user.id)
        
        # Get session context
        session_context = await session_manager.get_session_context(session_id, user_id)
        session_data = session_context.session
        
        # Get conversation history
        from app.services.conversation_service import conversation_service
        conversation_history = await conversation_service.get_conversation_history(
            session_id=session_id,
            limit=None
        )
        
        # Analyze compression needs
        compression_level, compression_reason = await context_compression_manager.determine_compression_level(
            user_id=user_id,
            assignment_id=session_data.assignment_id,
            session_count=session_data.session_number,
            total_tokens=session_data.total_tokens
        )
        
        # Get learning profile
        learning_profile = await learning_profile_service.get_learning_profile(user_id)
        
        # Get recent input classifications
        recent_classifications = []
        for msg in conversation_history[-5:]:  # Last 5 user messages
            if msg.message_type == MessageType.USER:
                classification = input_classifier.classify_input(msg.content)
                recent_classifications.append({
                    "content": msg.content[:50] + "..." if len(msg.content) > 50 else msg.content,
                    "input_type": classification.input_type.value,
                    "confidence": classification.confidence,
                    "timestamp": msg.timestamp
                })
        
        return ResponseBase(
            success=True,
            message="Session intelligence status retrieved",
            data={
                "session_info": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "assignment_id": session_data.assignment_id,
                    "session_number": session_data.session_number,
                    "current_problem": session_data.current_problem,
                    "status": session_data.status,
                    "started_at": session_data.started_at,
                    "total_messages": len(conversation_history),
                    "total_tokens": session_data.total_tokens
                },
                "intelligence_status": {
                    "compression_level": compression_level.value,
                    "compression_reason": compression_reason.value,
                    "compression_recommended": compression_level != ContextCompressionLevel.FULL_DETAIL,
                    "learning_profile_available": learning_profile is not None,
                    "context_compression_active": session_data.compression_level != ContextCompressionLevel.FULL_DETAIL.value
                },
                "learning_profile": {
                    "available": learning_profile is not None,
                    "competency": learning_profile.code_competency if learning_profile else None,
                    "learning_velocity": learning_profile.learning_velocity.value if learning_profile else None,
                    "preferred_teaching_style": learning_profile.preferred_teaching_style.value if learning_profile else None,
                    "total_sessions": learning_profile.total_sessions if learning_profile else 0,
                    "success_rate": learning_profile.success_rate if learning_profile else 0.0
                },
                "recent_interactions": {
                    "input_classifications": recent_classifications,
                    "conversation_patterns": self._analyze_conversation_patterns(conversation_history)
                },
                "performance_metrics": {
                    "avg_response_time": "N/A",  # TODO: Implement
                    "compression_savings": "N/A",  # TODO: Calculate
                    "teaching_effectiveness": "N/A"  # TODO: Implement
                }
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting session intelligence status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session intelligence status"
        )


@router.post("/{session_id}/intelligent/compress", response_model=ResponseBase)
async def trigger_manual_compression(
    session_id: str,
    target_level: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Manually trigger context compression for testing and optimization"""
    try:
        user_id = str(current_user.id)
        
        # Get session context
        session_context = await session_manager.get_session_context(session_id, user_id)
        session_data = session_context.session
        
        # Get conversation history
        from app.services.conversation_service import conversation_service
        conversation_history = await conversation_service.get_conversation_history(
            session_id=session_id,
            limit=None
        )
        
        # Determine target compression level
        if target_level:
            try:
                target_compression = ContextCompressionLevel(target_level)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid compression level: {target_level}"
                )
        else:
            # Auto-determine optimal level
            target_compression, _ = await context_compression_manager.determine_compression_level(
                user_id=user_id,
                assignment_id=session_data.assignment_id,
                session_count=session_data.session_number,
                total_tokens=session_data.total_tokens
            )
        
        # Perform compression
        compression_result = await context_compression_manager.compress_context(
            user_id=user_id,
            assignment_id=session_data.assignment_id,
            conversations=conversation_history,
            target_level=target_compression
        )
        
        # Update session compression level
        await session_service.update_session(
            session_id,
            {"compression_level": target_compression.value}
        )
        
        return ResponseBase(
            success=True,
            message="Manual compression completed",
            data={
                "compression_result": {
                    "original_messages": len(conversation_history),
                    "original_tokens": compression_result.get("compression_metadata", {}).get("original_tokens"),
                    "compressed_tokens": compression_result.get("total_tokens"),
                    "compression_ratio": compression_result.get("compression_metadata", {}).get("compression_ratio"),
                    "compression_level": target_compression.value,
                    "compression_time": compression_result.get("compression_metadata", {}).get("compression_time_seconds"),
                    "compression_quality": compression_result.get("compression_metadata", {}).get("compression_quality")
                },
                "session_updated": True,
                "new_compression_level": target_compression.value
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error triggering manual compression: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger compression"
        )


@router.post("/{session_id}/continue", response_model=ResponseBase)
async def continue_intelligent_session(
    session_id: str,
    request: MessageRequest,
    current_user: User = Depends(get_current_user)
):
    """Compatibility endpoint for intelligent sessions - redirects to intelligent message processing"""
    try:
        # This is essentially an alias for the intelligent message endpoint
        # to maintain compatibility with frontend expecting /continue endpoint
        return await process_intelligent_message(session_id, request, current_user)
    
    except Exception as e:
        logger.error(f"Error in continue intelligent session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to continue intelligent session"
        )


def _analyze_conversation_patterns(conversation_history: List) -> Dict[str, Any]:
    """Analyze conversation patterns for intelligence insights"""
    
    patterns = {
        "total_messages": len(conversation_history),
        "user_messages": len([msg for msg in conversation_history if msg.message_type == MessageType.USER]),
        "assistant_messages": len([msg for msg in conversation_history if msg.message_type == MessageType.ASSISTANT]),
        "avg_message_length": 0,
        "question_frequency": 0,
        "code_submission_frequency": 0,
    }
    
    if conversation_history:
        user_messages = [msg for msg in conversation_history if msg.message_type == MessageType.USER]
        if user_messages:
            patterns["avg_message_length"] = sum(len(msg.content) for msg in user_messages) / len(user_messages)
            
            # Count question patterns
            question_indicators = ["?", "how", "what", "why", "explain", "help"]
            questions = sum(1 for msg in user_messages if any(indicator in msg.content.lower() for indicator in question_indicators))
            patterns["question_frequency"] = questions / len(user_messages)
            
            # Count code patterns
            code_indicators = ["def ", "for ", "if ", "print(", "="]
            code_submissions = sum(1 for msg in user_messages if any(indicator in msg.content for indicator in code_indicators))
            patterns["code_submission_frequency"] = code_submissions / len(user_messages)
    
    return patterns