from typing import Optional, Dict, Any, List
from datetime import datetime
import time
import logging

from app.models import (
    Session, SessionRequest, MessageRequest, SessionResponse,
    MessageType, InputType, ProblemStatus, SessionContext,
    ConversationMessage
)
from app.services.session_service import session_service
from app.services.conversation_service import conversation_service
from app.services.progress_service import progress_service
from app.services.input_classifier import input_classifier
from app.services.token_tracker import token_tracker
from app.services.context_compression import context_compression_manager
from app.services.resume_detection import resume_detection_service
from app.services.assignment_service import assignment_service
from app.services.structured_tutoring_engine import structured_tutoring_engine
from app.core.config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """High-level session management orchestrating multiple services"""
    
    def __init__(self):
        self.session_service = session_service
        self.conversation_service = conversation_service
        self.progress_service = progress_service
        self.input_classifier = input_classifier
        self.token_tracker = token_tracker
        self.context_compression_manager = context_compression_manager
        self.resume_detection_service = resume_detection_service
        self.structured_tutoring_engine = structured_tutoring_engine
    
    async def start_or_resume_session(
        self, 
        user_id: str, 
        request: SessionRequest
    ) -> SessionResponse:
        """Start new session or resume existing one"""
        
        if request.resume_session and request.session_id:
            # Resume existing session
            session = await self.session_service.get_session(request.session_id)
            if not session or session.user_id != user_id:
                raise ValueError("Session not found or access denied")
            
            # Update session as active if it was paused
            if session.status != "active":
                await self.session_service.update_session(
                    request.session_id,
                    {"status": "active"}
                )
            
            logger.info(f"Resumed session {request.session_id} for user {user_id}")
            
        elif request.resume_session:
            # Find and resume most recent active session
            session = await self.session_service.get_active_session(
                user_id, request.assignment_id
            )
            
            if not session:
                # No active session found, create new one
                session = await self.session_service.create_session(
                    user_id, request.assignment_id
                )
                logger.info(f"No active session found, created new session {session.id}")
                
                # For new sessions, check if we need initial progress record
                progress_records = await self.progress_service.get_student_progress(
                    user_id, request.assignment_id
                )
                if not progress_records:
                    logger.info(f"Creating initial progress record for user {user_id}, problem 1")
                    await self.progress_service.create_or_update_progress(
                        user_id=user_id,
                        assignment_id=request.assignment_id,
                        session_id=str(session.id),
                        problem_number=1,
                        status=ProblemStatus.IN_PROGRESS,
                        time_increment=0.0
                    )
            else:
                logger.info(f"Resumed active session {session.id}")
        
        else:
            # Create new session
            session = await self.session_service.create_session(
                user_id, request.assignment_id
            )
            logger.info(f"Created new session {session.id} for user {user_id}")
        
        # Get current progress to determine problem number
        logger.info(f"📊 [SESSION_START] Getting progress records for user {user_id}, assignment {request.assignment_id}")
        progress_records = await self.progress_service.get_student_progress(
            user_id, request.assignment_id
        )
        logger.info(f"📊 [SESSION_START] Retrieved {len(progress_records)} progress records")
        
        current_problem = self._determine_current_problem(progress_records)
        logger.info(f"🎯 [SESSION_START] Determined current problem: {current_problem}")
        
        # If this is a brand new session with no progress, create initial progress record for problem 1
        if not progress_records and current_problem == 1:
            logger.info(f"Creating initial progress record for user {user_id}, problem 1")
            await self.progress_service.create_or_update_progress(
                user_id=user_id,
                assignment_id=request.assignment_id,
                session_id=str(session.id),
                problem_number=1,
                status=ProblemStatus.IN_PROGRESS,
                time_increment=0.0
            )
        
        # Update session with current problem
        if current_problem != session.current_problem:
            await self.session_service.update_session(
                str(session.id),
                {"current_problem": current_problem}
            )
            session.current_problem = current_problem
        
        return SessionResponse(
            session_id=str(session.id),
            assignment_id=session.assignment_id,
            status=session.status,
            message="Session ready",
            current_problem=current_problem,
            total_problems=None,  # TODO: Get from assignment
            session_number=session.session_number,
            compression_level=session.compression_level
        )
    
    async def start_intelligent_session(
        self, 
        user_id: str, 
        request: SessionRequest
    ) -> Dict[str, Any]:
        """Start session with intelligent resume detection and context-aware welcome"""
        
        logger.info(f"🧠 [INTELLIGENT_SESSION] Starting intelligent session for user {user_id}, assignment {request.assignment_id}")
        
        # Step 1: Intelligent resume detection
        logger.info(f"🕵️ [INTELLIGENT_SESSION] Running resume detection analysis")
        resume_analysis = await self.resume_detection_service.determine_resume_type(
            user_id=user_id,
            assignment_id=request.assignment_id
        )
        logger.info(f"🕵️ [INTELLIGENT_SESSION] Resume analysis result:", resume_analysis)
        
        # Step 2: Create or resume session based on analysis
        if resume_analysis["should_resume"] and resume_analysis.get("recommended_session_id"):
            # Resume specific session
            logger.info(f"🔄 [INTELLIGENT_SESSION] Resuming specific session: {resume_analysis['recommended_session_id']}")
            enhanced_request = SessionRequest(
                assignment_id=request.assignment_id,
                resume_session=True,
                session_id=resume_analysis["recommended_session_id"]
            )
        elif resume_analysis["should_resume"]:
            # Resume most recent session
            logger.info(f"🔄 [INTELLIGENT_SESSION] Resuming most recent session")
            enhanced_request = SessionRequest(
                assignment_id=request.assignment_id,
                resume_session=True,
                session_id=None
            )
        else:
            # Start fresh session
            logger.info(f"🆕 [INTELLIGENT_SESSION] Starting fresh session")
            enhanced_request = SessionRequest(
                assignment_id=request.assignment_id,
                resume_session=False,
                session_id=None
            )
        
        # Use existing session creation logic
        logger.info(f"📱 [INTELLIGENT_SESSION] Creating session with enhanced request")
        session_response = await self.start_or_resume_session(user_id, enhanced_request)
        logger.info(f"📱 [INTELLIGENT_SESSION] Session created/resumed:", {
            "session_id": session_response.session_id,
            "current_problem": session_response.current_problem,
            "status": session_response.status
        })
        
        # Step 3: Generate intelligent welcome message based on resume type
        welcome_message = self._generate_intelligent_welcome(
            resume_analysis["resume_type"],
            resume_analysis.get("context", {})
        )
        
        # Enhance response with intelligent context
        intelligent_response = {
            "session_id": session_response.session_id,
            "assignment_id": session_response.assignment_id,
            "status": session_response.status,
            "message": welcome_message,
            "current_problem": session_response.current_problem,
            "total_problems": session_response.total_problems,
            "session_number": session_response.session_number,
            "compression_level": session_response.compression_level,
            "resume_type": resume_analysis["resume_type"],
            "intelligence_enabled": True,
            "user_id": user_id
        }
        
        logger.info(f"🎉 [INTELLIGENT_SESSION] Intelligent session ready:", intelligent_response)
        return intelligent_response
    
    def _generate_intelligent_welcome(self, resume_type: str, context: Dict[str, Any]) -> str:
        """Generate context-aware welcome message based on resume type"""
        
        from app.models.enums import ResumeType
        
        try:
            resume_enum = ResumeType(resume_type)
        except ValueError:
            resume_enum = ResumeType.FRESH_START
        
        if resume_enum == ResumeType.FRESH_START:
            return "Welcome! I'm excited to help you learn programming. Let's start with your first problem!"
        
        elif resume_enum == ResumeType.MID_CONVERSATION:
            last_problem = context.get("last_problem_worked_on", "the current problem")
            return f"Welcome back! I see we were working on {last_problem}. Ready to continue where we left off?"
        
        elif resume_enum == ResumeType.BETWEEN_PROBLEMS:
            completed_problems = context.get("completed_problems", 0)
            return f"Great to see you again! You've completed {completed_problems} problems. Ready for the next challenge?"
        
        elif resume_enum == ResumeType.COMPLETED_ASSIGNMENT:
            return "Welcome back! I see you've completed this assignment. Would you like to review any problems or work on additional challenges?"
        
        else:
            return "Welcome back! I'm here to help you with your programming journey."
    
    async def process_student_input(
        self,
        session_id: str,
        user_id: str,
        message_request: MessageRequest
    ) -> Dict[str, Any]:
        """Process student input and generate appropriate response"""
        
        # Validate session
        session = await self.session_service.get_session(session_id)
        if not session or session.user_id != user_id:
            raise ValueError("Session not found or access denied")
        
        # Enhanced input classification
        classification = self.input_classifier.classify_input(message_request.content)
        
        # Add user message to conversation with enhanced classification
        user_message = await self.conversation_service.add_message(
            session_id=session_id,
            user_id=user_id,
            message_type=MessageType.USER,
            content=message_request.content,
            metadata={
                "input_type": classification.input_type.value,
                "confidence": classification.confidence,
                "indicators": classification.indicators
            }
        )
        
        # Get session context for AI processing
        context = await self.get_session_context(session_id, user_id)
        
        # Generate AI-powered response
        start_time = time.time()
        response_data = await self._generate_ai_response(
            session, context, message_request.content, classification
        )
        response_time_ms = (time.time() - start_time) * 1000
        
        # Add assistant response to conversation
        if response_data.get("ai_response") and response_data.get("success"):
            assistant_message = await self.conversation_service.add_message(
                session_id=session_id,
                user_id=user_id,
                message_type=MessageType.ASSISTANT,
                content=response_data["ai_response"],
                metadata={
                    "ai_analysis": response_data.get("analysis_type"),
                    "confidence": classification.confidence,
                    "usage": response_data.get("usage", {})
                }
            )
            
            # Track token usage
            if response_data.get("usage"):
                await self.token_tracker.record_usage(
                    user_id=user_id,
                    session_id=session_id,
                    request_type=response_data.get("analysis_type", "tutoring"),
                    model=settings.OPENAI_MODEL,
                    prompt_tokens=response_data["usage"].get("prompt_tokens", 0),
                    completion_tokens=response_data["usage"].get("completion_tokens", 0),
                    response_time_ms=response_time_ms,
                    success=response_data.get("success", False)
                )
        
        # Handle specific actions based on input type
        await self._handle_post_ai_actions(session, classification, response_data)
        
        return {
            **response_data,
            "classification": {
                "input_type": classification.input_type.value,
                "confidence": classification.confidence,
                "explanation": self.input_classifier.get_classification_explanation(classification)
            },
            "session_id": session_id,
            "response_time_ms": response_time_ms
        }
    
    async def _generate_ai_response(
        self,
        session: Session,
        context: SessionContext,
        user_input: str,
        classification
    ) -> Dict[str, Any]:
        """Generate AI-powered response using the tutoring engine"""
        
        try:
            # TODO: Get actual problem data and learning profile
            problem_data = await self._get_current_problem_data(session)
            learning_profile = await self._get_learning_profile(session.user_id)
            
            # Get curriculum content from assignment
            curriculum_content = ""
            try:
                assignment = await assignment_service.get_assignment(session.assignment_id)
                if assignment and hasattr(assignment, 'curriculum_content'):
                    curriculum_content = assignment.curriculum_content or ""
                    logger.info(f"📖 SESSION_MANAGER: Curriculum content length: {len(curriculum_content)} characters")
                else:
                    logger.warning("⚠️ SESSION_MANAGER: No curriculum content available")
            except Exception as e:
                logger.warning(f"⚠️ SESSION_MANAGER: Failed to get curriculum content: {e}")
            
            # Get assignment and problem objects for structured tutoring engine
            assignment = await assignment_service.get_assignment(session.assignment_id)
            current_problem = None
            if assignment and session.current_problem <= len(assignment.problems):
                current_problem = assignment.problems[session.current_problem - 1]
            
            if not assignment or not current_problem:
                # Fallback if we can't get assignment/problem data
                ai_response = {
                    "success": True,
                    "content": "I'm here to help you learn! What would you like to work on?",
                    "analysis_type": "fallback_response"
                }
            else:
                # Generate AI response using structured tutoring engine
                recent_messages = context.recent_messages if context else []
                structured_response = await self.structured_tutoring_engine.generate_structured_response(
                    user_input=user_input,
                    user_id=session.user_id,
                    assignment=assignment,
                    current_problem=current_problem,
                    conversation_history=recent_messages
                )
                
                ai_response = {
                    "success": structured_response.success,
                    "content": structured_response.message,
                    "analysis_type": "structured_tutoring",
                    "student_state": structured_response.student_state.value if structured_response.student_state else None,
                    "tutoring_mode": structured_response.tutoring_mode.value if structured_response.tutoring_mode else None,
                    "teaching_notes": structured_response.teaching_notes
                }
            
            return {
                "success": ai_response.get("success", True),
                "ai_response": ai_response.get("content", "I'm here to help! Let me know what you need."),
                "analysis_type": ai_response.get("analysis_type", "general_tutoring"),
                "usage": ai_response.get("usage", {}),
                "requires_followup": ai_response.get("requires_followup", False),
                "problem_number": session.current_problem,
                "metadata": {
                    "classification_confidence": classification.confidence,
                    "input_indicators": classification.indicators
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return {
                "success": False,
                "ai_response": "I'm having trouble processing your request right now. Please try again!",
                "analysis_type": "error_fallback",
                "error": str(e),
                "problem_number": session.current_problem
            }
    
    async def _handle_post_ai_actions(
        self,
        session: Session,
        classification,
        response_data: Dict[str, Any]
    ):
        """Handle specific actions after AI response based on input type"""
        
        if classification.input_type == InputType.CODE_SUBMISSION:
            await self._handle_code_submission_actions(session, response_data)
        
        elif classification.input_type == InputType.NEXT_PROBLEM:
            await self._handle_next_problem_actions(session, response_data)
        
        # TODO: Add other post-processing actions as needed
    
    async def _handle_code_submission_actions(
        self,
        session: Session,
        response_data: Dict[str, Any]
    ):
        """Handle actions specific to code submissions"""
        
        # Update progress with code submission
        await self.progress_service.create_or_update_progress(
            user_id=session.user_id,
            assignment_id=session.assignment_id,
            session_id=str(session.id),
            problem_number=session.current_problem,
            status=ProblemStatus.IN_PROGRESS,
            # TODO: Extract actual code from the conversation
            code_submission=response_data.get("extracted_code", ""),
            # TODO: Determine correctness from AI analysis
            is_correct=response_data.get("is_likely_correct"),
            time_increment=1.0  # TODO: Calculate actual time spent
        )
    
    async def _handle_next_problem_actions(
        self,
        session: Session,
        response_data: Dict[str, Any]
    ):
        """Handle actions for next problem requests"""
        
        # Mark current problem as completed if not already
        current_progress = await self.progress_service.get_problem_progress(
            session.user_id,
            session.assignment_id,
            session.current_problem
        )
        
        if current_progress and current_progress.status != ProblemStatus.COMPLETED.value:
            await self.progress_service.create_or_update_progress(
                user_id=session.user_id,
                assignment_id=session.assignment_id,
                session_id=str(session.id),
                problem_number=session.current_problem,
                status=ProblemStatus.COMPLETED
            )
        
        # Move to next problem
        next_problem = session.current_problem + 1
        await self.session_service.update_session(
            str(session.id),
            {"current_problem": next_problem}
        )
    
    async def _get_current_problem_data(self, session: Session) -> Optional[Dict[str, Any]]:
        """Get current problem data - placeholder for future assignment service integration"""
        # TODO: Integrate with assignment service
        return {
            "number": session.current_problem,
            "title": f"Problem {session.current_problem}",
            "description": f"This is programming problem number {session.current_problem}.",
            "difficulty": "medium"
        }
    
    async def _get_learning_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user's learning profile - placeholder for future implementation"""
        # TODO: Integrate with learning profile service
        return {
            "learning_velocity": "moderate",
            "preferred_teaching_style": "collaborative",
            "total_sessions": 1
        }
    
    
    def _determine_current_problem(self, progress_records: List) -> int:
        """Determine which problem student should work on next"""
        
        logger.info(f"🔍 [CURRENT_PROBLEM] Determining current problem from {len(progress_records)} progress records")
        
        if not progress_records:
            logger.info("🔍 [CURRENT_PROBLEM] No progress records found, starting with problem 1")
            return 1
        
        # Log all progress records for debugging
        for i, progress in enumerate(progress_records):
            logger.info(f"   📊 Record {i+1}: Problem {progress.problem_number}, Status: {progress.status}, Attempts: {progress.attempts}")
        
        # Sort progress records by problem number to ensure proper order
        sorted_progress = sorted(progress_records, key=lambda p: p.problem_number)
        
        # Find first problem that is not completed
        for progress in sorted_progress:
            if progress.status in [ProblemStatus.NOT_STARTED.value, ProblemStatus.IN_PROGRESS.value, ProblemStatus.STUCK.value]:
                logger.info(f"🎯 [CURRENT_PROBLEM] Found incomplete problem: {progress.problem_number} (status: {progress.status})")
                return progress.problem_number
        
        # If all tracked problems are completed, return the next problem number
        max_problem = max(p.problem_number for p in progress_records)
        next_problem = max_problem + 1
        logger.info(f"🎯 [CURRENT_PROBLEM] All tracked problems completed (max: {max_problem}), moving to next: {next_problem}")
        return next_problem
    
    async def end_session(self, session_id: str, user_id: str) -> bool:
        """End a tutoring session"""
        
        # Validate session ownership
        session = await self.session_service.get_session(session_id)
        if not session or session.user_id != user_id:
            raise ValueError("Session not found or access denied")
        
        success = await self.session_service.end_session(session_id)
        
        if success:
            logger.info(f"Ended session {session_id} for user {user_id}")
        
        return success
    
    async def get_session_context(self, session_id: str, user_id: str) -> SessionContext:
        """Get comprehensive session context with intelligent compression"""
        
        # Get session
        session = await self.session_service.get_session(session_id)
        if not session or session.user_id != user_id:
            raise ValueError("Session not found or access denied")
        
        # Get all conversation messages for compression analysis
        all_messages = await self.conversation_service.get_conversation_history(
            session_id, include_archived=True
        )
        
        # Get user's total session count for compression level determination
        user_sessions = await self.session_service.get_user_sessions(
            user_id, session.assignment_id
        )
        session_count = len(user_sessions)
        
        # Count current total tokens
        total_tokens = self.context_compression_manager._count_message_tokens(all_messages)
        
        # Determine appropriate compression level
        target_level, compression_reason = await self.context_compression_manager.determine_compression_level(
            user_id, session.assignment_id, session_count, total_tokens
        )
        
        # Update session compression level if it has changed
        if session.compression_level != target_level:
            await self.session_service.update_session(
                session_id,
                {
                    "compression_level": target_level,
                    "context_metadata.compression_triggered": True,
                    "context_metadata.compression_reason": compression_reason.value,
                    "context_metadata.original_token_count": total_tokens,
                    "context_metadata.compression_timestamp": datetime.utcnow()
                }
            )
            session.compression_level = target_level
            logger.info(f"Session {session_id} compression level updated to {target_level.value}")
        
        # Apply compression
        compression_result = await self.context_compression_manager.compress_context(
            user_id, session.assignment_id, all_messages, target_level
        )
        
        # Build compressed prompt context
        compressed_summary = await self.context_compression_manager.build_compressed_prompt_context(
            compression_result, await self._get_current_problem_data(session)
        )
        
        # Get current problem progress
        current_progress = await self.progress_service.get_problem_progress(
            user_id, session.assignment_id, session.current_problem
        )
        
        # Get recent messages for immediate context (already included in compression result)
        recent_message_count = compression_result.get("recent_message_count", 10)
        recent_messages = all_messages[-recent_message_count:] if all_messages else []
        
        context = SessionContext(
            session=session,
            recent_messages=recent_messages,
            compressed_summary=compressed_summary,
            current_problem_data=current_progress.dict() if current_progress else None,
            total_context_tokens=compression_result.get("total_tokens", total_tokens),
            learning_profile_data=compression_result.get("learning_profile_summary"),
            compression_metadata=compression_result.get("compression_metadata")
        )
        
        return context


session_manager = SessionManager()