"""
Enhanced Session Service with Structured Tutoring Integration
This service integrates the OOP prototype structured teaching methodology.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging
import asyncio

from app.database.connection import get_database
from app.models import (
    Session, SessionStatus, ContextCompressionLevel, 
    SessionRequest, SessionResponse, MessageRequest,
    ConversationDocument, StudentProgressDocument,
    Assignment, Problem, User, ConversationMessage, MessageType,
    ProblemStatus
)
from app.services.structured_tutoring_engine import (
    StructuredTutoringEngine, StudentState, TutoringMode
)
from app.services.assignment_service import assignment_service
from app.services.auth_service import auth_service
from app.services.session_manager import session_manager
from app.services.progress_service import progress_service
from app.utils.response_formatter import format_response
from app.core.config import settings

logger = logging.getLogger(__name__)


class EnhancedSessionService:
    """Enhanced session service with structured tutoring methodology"""
    
    def __init__(self):
        self.db = None
        self.structured_engine = StructuredTutoringEngine()
        self._session_creation_locks: Dict[str, asyncio.Lock] = {}
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    def _get_session_lock(self, user_id: str, assignment_id: str) -> asyncio.Lock:
        """Get or create a lock for this user+assignment combination"""
        key = f"{user_id}:{assignment_id}"
        if key not in self._session_creation_locks:
            self._session_creation_locks[key] = asyncio.Lock()
        return self._session_creation_locks[key]
    
    async def start_intelligent_session(self, user_id: str, assignment_id: str) -> Dict[str, Any]:
        """Start an intelligent session with structured tutoring"""
        
        logger.info(f"🧠 [ENHANCED_SESSION] Starting intelligent session for user {user_id}, assignment {assignment_id}")
        
        # Use lock to prevent concurrent session creation
        lock = self._get_session_lock(user_id, assignment_id)
        
        async with lock:
            logger.info(f"🔒 [SESSION_LOCK] Acquired lock for user {user_id}, assignment {assignment_id}")
            
            try:
                db = await self._get_db()
                
                # STEP 1: Clean up any existing active sessions to prevent duplicates
                logger.info(f"🧹 [ENHANCED_SESSION] Cleaning up any existing active sessions")
                cleanup_count = await self._cleanup_active_sessions(user_id, assignment_id)
                if cleanup_count > 0:
                    logger.info(f"🧹 [ENHANCED_SESSION] Cleaned up {cleanup_count} existing active sessions")
                
                # STEP 2: Check again for active sessions (should be none now)
                logger.info(f"🔍 [ENHANCED_SESSION] Checking for existing active session after cleanup")
                existing_session = await self.get_active_session(user_id, assignment_id)
                if existing_session:
                    logger.warning(f"🚨 [ENHANCED_SESSION] Active session still exists after cleanup: {existing_session.id}, resuming")
                    # Resume existing session
                    return await self._resume_session(existing_session)
                
                logger.info(f"🆕 [ENHANCED_SESSION] No existing session found, creating new one")
                
                # Get assignment details
                assignment = await assignment_service.get_assignment(assignment_id)
                if not assignment:
                    raise ValueError(f"Assignment {assignment_id} not found")
                
                # Get user details
                user = await auth_service.get_user_by_id(user_id)
                if not user:
                    raise ValueError(f"User {user_id} not found")
                
                # Create new session
                session = await self.create_session(user_id, assignment_id)
                logger.info(f"🆕 [SESSION_LOCK] Created new session: {session.id}")
                
                # Load conversation history from previous sessions
                conversation_history = await self._load_conversation_history(user_id, assignment_id)
                
                # Determine current problem based on progress
                logger.info(f"🎯 [ENHANCED_SESSION] Determining current problem")
                current_problem_number = await self._get_current_problem_number(user_id, assignment_id)
                logger.info(f"🎯 [ENHANCED_SESSION] Current problem number: {current_problem_number}")
                
                current_problem = None
                if current_problem_number <= len(assignment.problems):
                    current_problem = assignment.problems[current_problem_number - 1]
                    logger.info(f"📚 [ENHANCED_SESSION] Current problem: {current_problem.title}")
                else:
                    logger.info(f"🏁 [ENHANCED_SESSION] All problems completed (current: {current_problem_number}, total: {len(assignment.problems)})")
                
                # Generate welcome message using structured approach
                welcome_response = await self._generate_welcome_message(
                    user, assignment, current_problem, conversation_history, session
                )
                
                # Save welcome message to conversation
                await self._save_message(
                    session.id, user_id, MessageType.ASSISTANT, welcome_response["message"]
                )
                
                session_data = {
                    "session_id": str(session.id),
                    "session_number": session.session_number,
                    "compression_level": session.compression_level.value,
                    "current_problem": current_problem_number,
                    "total_problems": len(assignment.problems),
                    "message": welcome_response["message"],
                    "student_state": welcome_response["student_state"],
                    "teaching_notes": welcome_response.get("teaching_notes", [])
                }
                
                logger.info(f"✅ [ENHANCED_SESSION] Session created successfully:", session_data)
                return session_data
                
            except Exception as e:
                logger.error(f"💥 [SESSION_LOCK] Error starting intelligent session: {e}")
                raise
    
    async def process_student_message(
        self, 
        session_id: str, 
        user_input: str,
        problem_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process student message using structured tutoring approach"""
        
        logger.info("🔄 ENHANCED_SESSION_SERVICE: Starting message processing")
        logger.info(f"📤 ENHANCED_SESSION_SERVICE: Session ID: {session_id}")
        logger.info(f"💬 ENHANCED_SESSION_SERVICE: User input: '{user_input}'")
        logger.info(f"📋 ENHANCED_SESSION_SERVICE: Problem context: {problem_context}")
        
        try:
            # Get session details
            session = await self.get_session(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # Get assignment and current problem
            assignment = await assignment_service.get_assignment(session.assignment_id)
            current_problem_number = await self._get_current_problem_number(
                session.user_id, session.assignment_id
            )
            current_problem = None
            if current_problem_number <= len(assignment.problems):
                current_problem = assignment.problems[current_problem_number - 1]
            
            # Load conversation history
            conversation_history = await self._get_session_conversation(session_id)
            
            # Save student message
            await self._save_message(session_id, session.user_id, MessageType.USER, user_input)
            
            # Determine current student state from conversation
            current_state = await self._determine_current_student_state(
                conversation_history, user_input
            )
            
            # Generate structured response
            logger.info("🧠 ENHANCED_SESSION_SERVICE: Calling structured_engine.generate_structured_response...")
            logger.info(f"👤 ENHANCED_SESSION_SERVICE: User ID: {session.user_id}")
            logger.info(f"📚 ENHANCED_SESSION_SERVICE: Assignment: {assignment.title if assignment else 'None'}")
            logger.info(f"🎯 ENHANCED_SESSION_SERVICE: Current problem: {current_problem.title if current_problem else 'None'}")
            logger.info(f"📋 ENHANCED_SESSION_SERVICE: Problem description: {current_problem.description if current_problem else 'None'}")
            logger.info(f"🔧 ENHANCED_SESSION_SERVICE: Problem concepts: {current_problem.concepts if current_problem else 'None'}")
            logger.info(f"💭 ENHANCED_SESSION_SERVICE: Current state: {current_state}")
            logger.info(f"📝 ENHANCED_SESSION_SERVICE: Conversation history length: {len(conversation_history)}")
            logger.info(f"📦 ENHANCED_SESSION_SERVICE: Problem context from frontend: {problem_context}")
            
            structured_response = await self.structured_engine.generate_structured_response(
                user_input=user_input,
                user_id=session.user_id,
                assignment=assignment,
                current_problem=current_problem,
                conversation_history=conversation_history,
                current_state=current_state,
                problem_context=problem_context
            )
            
            logger.info("✅ ENHANCED_SESSION_SERVICE: Structured response generated")
            logger.info(f"🤖 ENHANCED_SESSION_SERVICE: Response text: '{structured_response.response_text}'")
            logger.info(f"📊 ENHANCED_SESSION_SERVICE: New student state: {structured_response.student_state}")
            logger.info(f"🎯 ENHANCED_SESSION_SERVICE: Tutoring mode: {structured_response.tutoring_mode}")
            
            # CRITICAL: Handle progression validation requests
            if structured_response.response_text == "VALIDATION_REQUIRED_FOR_PROGRESSION":
                logger.info("🛑 ENHANCED_SESSION_SERVICE: Validation required for progression")
                
                # Check if current problem is actually completed
                is_completed = await progress_service.is_problem_completed(
                    session.user_id, session.assignment_id, current_problem_number
                )
                
                logger.info(f"🔍 ENHANCED_SESSION_SERVICE: Problem {current_problem_number} completed: {is_completed}")
                
                if is_completed:
                    logger.info("✅ ENHANCED_SESSION_SERVICE: Problem completed - allowing progression")
                    # Allow progression - get next problem
                    next_problem_number = current_problem_number + 1
                    if next_problem_number <= len(assignment.problems):
                        next_problem = assignment.problems[next_problem_number - 1]
                        
                        # Update structured response to present next problem
                        structured_response.response_text = await self._generate_problem_presentation(
                            next_problem, next_problem_number, user_input, conversation_history
                        )
                        structured_response.student_state = StudentState.PROBLEM_PRESENTED
                        structured_response.tutoring_mode = TutoringMode.APPROACH_INQUIRY
                        structured_response.next_expected_input = "approach_explanation"
                        structured_response.teaching_notes = ["Problem completed - presenting next problem"]
                        
                        logger.info(f"🎯 ENHANCED_SESSION_SERVICE: Presenting next problem: {next_problem.title}")
                    else:
                        # All problems completed
                        completion_message = "🎉 Congratulations! You've completed all problems in this assignment!"
                        structured_response.response_text = format_response(completion_message)
                        structured_response.student_state = StudentState.PROBLEM_COMPLETED
                        structured_response.tutoring_mode = TutoringMode.CELEBRATION
                        structured_response.teaching_notes = ["All problems completed"]
                        logger.info("🏁 ENHANCED_SESSION_SERVICE: All problems completed!")
                else:
                    logger.info("❌ ENHANCED_SESSION_SERVICE: Problem not completed - blocking progression")
                    # Block progression with educational message
                    blocking_message = f"I see you want to move to the next problem, but you need to complete the current problem first. Please submit your working code for **{current_problem.title}** and I'll help you get it working correctly."
                    structured_response.response_text = format_response(blocking_message)
                    structured_response.student_state = StudentState.WORKING_ON_CODE
                    structured_response.tutoring_mode = TutoringMode.GUIDED_QUESTIONING
                    structured_response.next_expected_input = "code_submission"
                    structured_response.teaching_notes = ["Blocked progression - current problem not completed"]
            
            # Check if problem was completed and handle progression
            elif structured_response.student_state == StudentState.PROBLEM_COMPLETED:
                logger.info("🎉 ENHANCED_SESSION_SERVICE: Problem completed! Updating progress...")
                
                # Mark the problem as completed with the correct solution
                # The structured engine should have validated the code was correct
                await progress_service.create_or_update_progress(
                    user_id=session.user_id,
                    assignment_id=session.assignment_id,
                    session_id=session_id,
                    problem_number=current_problem_number,
                    status=ProblemStatus.COMPLETED,
                    code_submission=user_input,  # Save the correct code
                    is_correct=True,
                    time_increment=0.0
                )
                
                logger.info(f"✅ ENHANCED_SESSION_SERVICE: Problem {current_problem_number} marked as completed")
            
            # Check if user is ready to start next problem
            elif structured_response.student_state == StudentState.READY_TO_START and (
                current_state == StudentState.PROBLEM_COMPLETED or 
                structured_response.tutoring_mode == TutoringMode.PROBLEM_PRESENTATION
            ):
                logger.info("🚀 ENHANCED_SESSION_SERVICE: User ready for next problem!")
                logger.info(f"🔄 ENHANCED_SESSION_SERVICE: State transition - Current: {current_state}, New: {structured_response.student_state}")
                
                # First mark the current problem as completed if not already done
                logger.info(f"✅ ENHANCED_SESSION_SERVICE: Ensuring problem {current_problem_number} is marked completed")
                await self._update_problem_progress(session.user_id, session.assignment_id, current_problem_number)
                
                # Get the updated current problem number after progression
                updated_problem_number = await self._get_current_problem_number(
                    session.user_id, session.assignment_id
                )
                logger.info(f"📊 ENHANCED_SESSION_SERVICE: Updated problem number: {updated_problem_number}")
                logger.info(f"📊 ENHANCED_SESSION_SERVICE: Total problems in assignment: {len(assignment.problems)}")
                logger.info(f"📊 ENHANCED_SESSION_SERVICE: Checking condition: {updated_problem_number} <= {len(assignment.problems)} = {updated_problem_number <= len(assignment.problems)}")
                
                # If we have a next problem, present it
                if updated_problem_number <= len(assignment.problems):
                    next_problem = assignment.problems[updated_problem_number - 1]
                    
                    logger.info(f"🎯 ENHANCED_SESSION_SERVICE: Found next problem: {next_problem.title}")
                    
                    # Generate dynamic problem presentation via OpenAI
                    structured_response.response_text = await self._generate_problem_presentation(
                        next_problem, updated_problem_number, user_input, conversation_history
                    )
                    
                    structured_response.student_state = StudentState.PROBLEM_PRESENTED
                    structured_response.tutoring_mode = TutoringMode.APPROACH_INQUIRY
                    structured_response.next_expected_input = "approach_explanation"
                    
                    logger.info(f"🎯 ENHANCED_SESSION_SERVICE: Presenting next problem: {next_problem.title}")
                else:
                    # All problems completed
                    logger.info(f"🏁 ENHANCED_SESSION_SERVICE: All problems completed! ({updated_problem_number} > {len(assignment.problems)})")
                    structured_response.response_text = await self._generate_assignment_completion_message(
                        user_input, assignment, conversation_history
                    )
                    structured_response.student_state = StudentState.PROBLEM_COMPLETED
                    structured_response.tutoring_mode = TutoringMode.CELEBRATION
                    structured_response.next_expected_input = "assignment_complete"
                    logger.info("🏁 ENHANCED_SESSION_SERVICE: Set state to assignment completed")
                
                # Update response with current problem number for frontend
                structured_response.current_problem = updated_problem_number
            
            # Save AI response
            await self._save_message(
                session_id, session.user_id, MessageType.ASSISTANT, structured_response.response_text
            )
            
            # Update session with new state
            await self.update_session(session_id, {
                "last_activity": datetime.utcnow(),
                "current_student_state": structured_response.student_state.value,
                "tutoring_mode": structured_response.tutoring_mode.value
            })
            
            # Check if student completed the problem
            if structured_response.tutoring_mode == TutoringMode.CELEBRATION:
                await self._handle_problem_completion(session.user_id, session.assignment_id, current_problem_number)
            
            # Use updated problem number if available
            final_problem_number = structured_response.current_problem or current_problem_number
            
            return {
                "message": structured_response.response_text,
                "student_state": structured_response.student_state.value,
                "tutoring_mode": structured_response.tutoring_mode.value,
                "next_expected_input": structured_response.next_expected_input,
                "teaching_notes": structured_response.teaching_notes,
                "current_problem": final_problem_number,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing student message: {e}")
            raise
    
    async def _generate_welcome_message(
        self, 
        user: User, 
        assignment: Assignment, 
        current_problem: Optional[Problem],
        conversation_history: List[ConversationMessage],
        session: Session
    ) -> Dict[str, Any]:
        """Generate welcome message following structured approach"""
        
        if len(conversation_history) > 0:
            # Resuming session - check where they left off
            if current_problem:
                welcome_message = f"""🎓 Welcome back, {user.username}! I can see we were working on the '{assignment.title}' assignment.

**Current Problem: {current_problem.title}**

I can see from our previous conversation that you were making progress. Let's continue from where we left off.

Are you ready to continue with this problem, or would you like me to explain it again?"""
                student_state = StudentState.READY_TO_START
            else:
                welcome_message = f"""🎉 Welcome back, {user.username}! You've completed all problems in the '{assignment.title}' assignment! Great work!

Would you like to review any problems or work on a different assignment?"""
                student_state = StudentState.PROBLEM_COMPLETED
        else:
            # Fresh start
            welcome_message = f"""🎓 Hi {user.username}! I'm your AI tutor, and I'm excited to help you with the '{assignment.title}' assignment!

This assignment will help you practice the concepts we've been learning. I'll guide you through each problem step by step.

**Important:** I won't give you the answers directly. Instead, I'll help you discover the solutions by asking questions and giving hints. This way, you'll really understand the concepts!

Are you ready to start with the first problem?"""
            student_state = StudentState.INITIAL_GREETING
        
        return {
            "message": welcome_message,
            "student_state": student_state.value,
            "teaching_notes": ["Welcome message generated", "Following structured approach"]
        }
    
    async def _determine_current_student_state(
        self, 
        conversation_history: List[ConversationMessage], 
        latest_input: str
    ) -> StudentState:
        """Determine current student state from conversation context"""
        
        if len(conversation_history) <= 2:
            return StudentState.INITIAL_GREETING
        
        # Get last few AI messages to understand context
        last_ai_messages = [
            msg for msg in conversation_history[-5:] 
            if msg.message_type == MessageType.ASSISTANT
        ]
        
        # Get last few user messages to understand progression
        last_user_messages = [
            msg for msg in conversation_history[-5:] 
            if msg.message_type == MessageType.USER
        ]
        
        # Analyze latest input first
        latest_lower = latest_input.lower().strip()
        
        # STRICT LOGIC-FIRST: Code submission detection - check logic approval status first
        code_indicators = ['=', 'for ', 'while ', 'if ', 'def ', 'print(', 'input(', 'append(', 'range(', 'import ', 'from ', 'class ', 'try:', 'except:', 'len(']
        if any(indicator in latest_input for indicator in code_indicators):
            # Check if logic was previously approved by looking for approval keywords in recent AI messages
            logic_approved = False
            for ai_msg in last_ai_messages[-5:]:  # Check last 5 AI messages for approval
                ai_content_lower = ai_msg.content.lower()
                approval_keywords = [
                    'excellent logic', 'perfect logic', 'great logic', 'correct logic', 'good logic',
                    'approved', 'now convert', 'now implement', 'write the code',
                    'code it up', 'implement it', 'time to code', 'convert your logic',
                    'implement your approach', 'translate your logic', 'turn your approach'
                ]
                if any(keyword in ai_content_lower for keyword in approval_keywords):
                    logic_approved = True
                    break
            
            if logic_approved:
                return StudentState.CODE_REVIEW
            else:
                # STRICT: Code submitted without logic approval - redirect to awaiting approach
                logger.info(f"🚫 ENHANCED_SESSION_SERVICE: Code detected without logic approval - redirecting to AWAITING_APPROACH")
                logger.info(f"💬 ENHANCED_SESSION_SERVICE: Code input: '{latest_input[:100]}'")
                return StudentState.AWAITING_APPROACH
        
        # Check for problem completion celebration context
        if last_ai_messages:
            last_ai_message = last_ai_messages[-1].content.lower()
            
            # If AI just said "ready for the next problem?" and user says ready-type response
            if ("ready for the next problem" in last_ai_message or 
                "excellent work" in last_ai_message or 
                "correct" in last_ai_message):
                ready_indicators = ['ready', 'yes', 'next', 'continue', 'ok', 'sure']
                if any(indicator in latest_lower for indicator in ready_indicators):
                    return StudentState.PROBLEM_COMPLETED
            
            # If AI said "Great! Let's move to the next problem" and user says ready
            if ("let's move to the next problem" in last_ai_message and 
                any(indicator in latest_lower for indicator in ['ready', 'yes', 'ok', 'sure', 'start', 'begin'])):
                return StudentState.READY_TO_START
            
            # Check if we just presented a problem or asked for logic
            if ("how are you thinking to solve" in last_ai_message or 
                "logic first" in last_ai_message or
                "natural language" in last_ai_message or
                "explain your approach" in last_ai_message):
                return StudentState.AWAITING_APPROACH
            
            # Check if we're waiting for code
            if "try writing the code" in last_ai_message or "can you try" in last_ai_message:
                return StudentState.WORKING_ON_CODE
            
            # Check if we gave hints
            if "hint" in last_ai_message or "look at" in last_ai_message:
                return StudentState.WORKING_ON_CODE
        
        # Stuck/confusion
        stuck_indicators = ['not clear', 'don\'t understand', 'stuck', 'confused', 'not getting it']
        if any(indicator in latest_lower for indicator in stuck_indicators):
            return StudentState.STUCK_NEEDS_HELP
        
        # Next problem request
        next_indicators = ['next problem', 'next', 'move on', 'continue', 'done', 'finished']
        if any(indicator in latest_lower for indicator in next_indicators):
            return StudentState.PROBLEM_COMPLETED
        
        # Ready to start (general case)
        ready_indicators = ['ready', 'start', 'begin', 'yes', 'ok', 'sure']
        if any(indicator in latest_lower for indicator in ready_indicators):
            return StudentState.READY_TO_START
        
        # Check if we're awaiting logic explanation based on recent AI messages
        if last_ai_messages:
            recent_ai_content = " ".join([msg.content.lower() for msg in last_ai_messages[-2:]])
            if ("logic" in recent_ai_content or "natural language" in recent_ai_content or 
                "explain your approach" in recent_ai_content or "thinking process" in recent_ai_content or
                "how are you thinking" in recent_ai_content):
                return StudentState.AWAITING_APPROACH
        
        # If we reach here and no specific state was determined, check if we should be waiting for logic
        # This prevents students from bypassing the logic-first requirement
        if len(conversation_history) > 2:
            # Look for recent problem presentation without logic approval
            recent_messages = conversation_history[-6:]  # Check last 6 messages
            for msg in recent_messages:
                if (msg.message_type == MessageType.ASSISTANT and 
                    ("how are you thinking to solve" in msg.content.lower() or
                     "explain your approach" in msg.content.lower() or
                     "tell me your logic" in msg.content.lower())):
                    # A problem was recently presented, student should provide logic first
                    return StudentState.AWAITING_APPROACH
        
        return StudentState.WORKING_ON_CODE
    
    async def _load_conversation_history(self, user_id: str, assignment_id: str) -> List[ConversationMessage]:
        """Load conversation history from previous sessions"""
        db = await self._get_db()
        
        # Get all previous sessions for this user and assignment (excluding current)
        sessions = await db.sessions.find({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "status": {"$in": [SessionStatus.COMPLETED, SessionStatus.ACTIVE]}
        }).sort("created_at", 1).to_list(None)
        
        conversation_history = []
        
        for session in sessions:
            # Get messages for this session
            messages = await db.conversations.find({
                "session_id": session["_id"]
            }).sort("timestamp", 1).to_list(None)
            
            for msg in messages:
                conversation_history.append(ConversationMessage(
                    timestamp=msg["timestamp"].isoformat(),
                    message_type=MessageType(msg["message_type"]),
                    content=msg["content"],
                    metadata=msg.get("metadata", {})
                ))
        
        # Return last 20 messages for context
        return conversation_history[-20:]
    
    async def _get_session_conversation(self, session_id: str) -> List[ConversationMessage]:
        """Get conversation for current session"""
        db = await self._get_db()
        
        messages = await db.conversations.find({
            "session_id": ObjectId(session_id)
        }).sort("timestamp", 1).to_list(None)
        
        conversation = []
        for msg in messages:
            conversation.append(ConversationMessage(
                timestamp=msg["timestamp"].isoformat(),
                message_type=MessageType(msg["message_type"]),
                content=msg["content"],
                metadata=msg.get("metadata", {})
            ))
        
        return conversation
    
    async def _get_current_problem_number(self, user_id: str, assignment_id: str) -> int:
        """Get the current problem number for the user based on completion status"""
        
        logger.info(f"🔍 [ENHANCED_SESSION] Getting current problem for user {user_id}, assignment {assignment_id}")
        
        try:
            # Get the highest completed problem number
            highest_completed = await progress_service.get_highest_completed_problem(user_id, assignment_id)
            
            # Current problem is the next problem after the highest completed one
            current_problem = highest_completed + 1
            
            logger.info(f"🎯 [ENHANCED_SESSION] Highest completed problem: {highest_completed}")
            logger.info(f"🎯 [ENHANCED_SESSION] Current problem: {current_problem}")
            
            return current_problem
            
        except Exception as e:
            logger.error(f"❌ [ENHANCED_SESSION] Error determining current problem: {e}")
            return 1  # Fallback to first problem
    
    async def _update_problem_progress(self, user_id: str, assignment_id: str, completed_problem: int):
        """Update student progress when a problem is completed"""
        
        logger.info(f"📈 [ENHANCED_SESSION] Updating progress for user {user_id}")
        logger.info(f"📚 [ENHANCED_SESSION] Assignment {assignment_id}, completed problem {completed_problem}")
        
        try:
            # Use the progress service to properly mark the problem as completed
            from app.models import ProblemStatus
            
            await progress_service.create_or_update_progress(
                user_id=user_id,
                assignment_id=assignment_id,
                session_id=f"structured_session_{user_id}",  # placeholder session ID
                problem_number=completed_problem,
                status=ProblemStatus.COMPLETED,
                time_increment=0.0  # Could track actual time in future
            )
            
            logger.info(f"✅ [ENHANCED_SESSION] Successfully marked problem {completed_problem} as completed")
            
        except Exception as e:
            logger.error(f"❌ [ENHANCED_SESSION] Failed to update progress: {e}")
    
    async def _save_message(self, session_id: str, user_id: str, message_type: MessageType, content: str):
        """Save a message to the conversation"""
        db = await self._get_db()
        
        message_doc = {
            "session_id": ObjectId(session_id),
            "user_id": user_id,
            "message_type": message_type.value,
            "content": content,
            "timestamp": datetime.utcnow(),
            "metadata": {}
        }
        
        await db.conversations.insert_one(message_doc)
    
    async def _handle_problem_completion(self, user_id: str, assignment_id: str, problem_number: int):
        """Handle when student completes a problem"""
        
        logger.info(f"🎉 [ENHANCED_SESSION] Handling problem completion for user {user_id}")
        logger.info(f"📚 [ENHANCED_SESSION] Assignment {assignment_id}, problem {problem_number}")
        
        try:
            # Use the progress service to properly mark the problem as completed
            from app.models import ProblemStatus
            
            await progress_service.create_or_update_progress(
                user_id=user_id,
                assignment_id=assignment_id,
                session_id=f"structured_session_{user_id}",  # placeholder session ID
                problem_number=problem_number,
                status=ProblemStatus.COMPLETED,
                time_increment=0.0  # Could track actual time in future
            )
            
            logger.info(f"✅ [ENHANCED_SESSION] Successfully completed problem {problem_number}")
            
        except Exception as e:
            logger.error(f"❌ [ENHANCED_SESSION] Failed to complete problem: {e}")

    async def _generate_problem_presentation(self, problem, problem_number: int, user_input: str, conversation_history) -> str:
        """Generate dynamic problem presentation via OpenAI"""
        
        try:
            from app.services.openai_client import openai_client
            
            # Build recent conversation context
            recent_context = ""
            if conversation_history and len(conversation_history) > 0:
                recent_messages = conversation_history[-4:]  # Last 4 messages
                recent_context = "\n".join([
                    f"{msg.message_type.value}: {msg.content[:100]}..." if len(msg.content) > 100 else f"{msg.message_type.value}: {msg.content}"
                    for msg in recent_messages
                ])
            
            # Format test cases for display
            test_cases_display = ""
            if problem.test_cases and len(problem.test_cases) > 0:
                test_cases_display = "\n\n**Sample Input/Output:**\n"
                for i, test_case in enumerate(problem.test_cases[:2]):  # Show first 2 test cases
                    if isinstance(test_case, dict):
                        input_val = test_case.get('input', 'N/A')
                        output_val = test_case.get('expected_output', 'N/A') 
                        description = test_case.get('description', '')
                        
                        test_cases_display += f"\n**Example {i+1}:**\n"
                        test_cases_display += f"Input: {input_val}\n"
                        test_cases_display += f"Output: {output_val}\n"
                        if description and description != 'N/A':
                            test_cases_display += f"Explanation: {description}\n"
            
            prompt = f"""You are an AI programming tutor. The student just completed a problem and is ready for the next one.

Recent conversation context:
{recent_context}

Student's latest message: "{user_input}"

Now present this new problem in an encouraging way:

Problem {problem_number}: {problem.title}
Description: {problem.description}{test_cases_display}

Generate a response that:
1. Briefly acknowledges their progress/readiness
2. Presents the new problem clearly with the provided examples
3. Asks how they're thinking about approaching it

Be encouraging and maintain the tutoring conversation flow. Keep it concise but engaging."""

            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an encouraging programming tutor who helps students progress through problems."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            else:
                # Fallback to structured format with test cases
                test_cases_fallback = ""
                if problem.test_cases and len(problem.test_cases) > 0:
                    test_cases_fallback = "\n\n**Sample Input/Output:**\n"
                    for i, test_case in enumerate(problem.test_cases[:2]):  # Show first 2 test cases
                        if isinstance(test_case, dict):
                            input_val = test_case.get('input', 'N/A')
                            output_val = test_case.get('expected_output', 'N/A') 
                            description = test_case.get('description', '')
                            
                            test_cases_fallback += f"\n**Example {i+1}:**\n"
                            test_cases_fallback += f"Input: {input_val}\n"
                            test_cases_fallback += f"Output: {output_val}\n"
                            if description and description != 'N/A':
                                test_cases_fallback += f"Explanation: {description}\n"
                
                return f"""Great! Let's move to the next problem.

**Problem {problem_number}: {problem.title}**

{problem.description}{test_cases_fallback}

How are you thinking to solve this question?"""
                
        except Exception as e:
            logger.error(f"❌ [ENHANCED_SESSION] Error generating problem presentation: {e}")
            # Fallback to structured format with test cases
            test_cases_fallback = ""
            if problem.test_cases and len(problem.test_cases) > 0:
                test_cases_fallback = "\n\n**Sample Input/Output:**\n"
                for i, test_case in enumerate(problem.test_cases[:2]):  # Show first 2 test cases
                    if isinstance(test_case, dict):
                        input_val = test_case.get('input', 'N/A')
                        output_val = test_case.get('expected_output', 'N/A') 
                        description = test_case.get('description', '')
                        
                        test_cases_fallback += f"\n**Example {i+1}:**\n"
                        test_cases_fallback += f"Input: {input_val}\n"
                        test_cases_fallback += f"Output: {output_val}\n"
                        if description and description != 'N/A':
                            test_cases_fallback += f"Explanation: {description}\n"
            
            return f"""Great! Let's move to the next problem.

**Problem {problem_number}: {problem.title}**

{problem.description}{test_cases_fallback}

How are you thinking to solve this question?"""

    async def _generate_assignment_completion_message(self, user_input: str, assignment, conversation_history) -> str:
        """Generate dynamic assignment completion message via OpenAI"""
        
        try:
            from app.services.openai_client import openai_client
            
            prompt = f"""You are an AI programming tutor. The student has just completed ALL problems in the assignment: "{assignment.title}"

Student's latest message: "{user_input}"

Generate a congratulatory message that:
1. Celebrates their achievement
2. Acknowledges they've completed the entire assignment
3. Is encouraging and positive

Keep it warm and personal, showing genuine excitement for their accomplishment. This is a big milestone!"""

            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an enthusiastic programming tutor who celebrates student achievements."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.8
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            else:
                return f"🎉 Congratulations! You've completed all problems in the '{assignment.title}' assignment!"
                
        except Exception as e:
            logger.error(f"❌ [ENHANCED_SESSION] Error generating completion message: {e}")
            return f"🎉 Congratulations! You've completed all problems in the '{assignment.title}' assignment!"
    
    async def _resume_session(self, session: Session) -> Dict[str, Any]:
        """Resume an existing session"""
        # Get assignment details
        assignment = await assignment_service.get_assignment(session.assignment_id)
        current_problem_number = await self._get_current_problem_number(
            session.user_id, session.assignment_id
        )
        
        current_problem = None
        if current_problem_number <= len(assignment.problems):
            current_problem = assignment.problems[current_problem_number - 1]
        
        # Get recent conversation
        conversation_history = await self._get_session_conversation(str(session.id))
        
        resume_message = f"""🎓 Continuing our session...

**Current Problem: {current_problem.title if current_problem else 'All Complete!'}**

Let's pick up where we left off. What would you like to work on?"""
        
        # Save resume message
        await self._save_message(
            str(session.id), session.user_id, MessageType.ASSISTANT, resume_message
        )
        
        return {
            "session_id": str(session.id),
            "session_number": session.session_number,
            "compression_level": session.compression_level.value,
            "current_problem": current_problem_number,
            "total_problems": len(assignment.problems),
            "message": resume_message,
            "student_state": StudentState.READY_TO_START.value,
            "resumed": True
        }
    
    # Include existing methods from the original SessionService
    async def create_session(self, user_id: str, assignment_id: str) -> Session:
        """Create a new tutoring session"""
        db = await self._get_db()
        
        # Get user's session count for this assignment
        session_count = await db.sessions.count_documents({
            "user_id": user_id,
            "assignment_id": assignment_id
        })
        
        # Determine compression level based on session count
        if session_count < 5:
            compression_level = ContextCompressionLevel.FULL_DETAIL
        elif session_count < 10:
            compression_level = ContextCompressionLevel.SUMMARIZED_PLUS_RECENT
        else:
            compression_level = ContextCompressionLevel.HIGH_LEVEL_SUMMARY
        
        # Create new session
        session = Session(
            user_id=user_id,
            assignment_id=assignment_id,
            session_number=session_count + 1,
            compression_level=compression_level,
            status=SessionStatus.ACTIVE
        )
        
        # Save to database
        result = await db.sessions.insert_one(session.dict(by_alias=True))
        session.id = result.inserted_id
        
        logger.info(f"Created session {result.inserted_id} for user {user_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve session by ID"""
        db = await self._get_db()
        
        session_data = await db.sessions.find_one({"_id": ObjectId(session_id)})
        if not session_data:
            return None
        
        return Session.model_validate(session_data)
    
    async def get_active_session(self, user_id: str, assignment_id: str) -> Optional[Session]:
        """Get user's most recent active session for an assignment"""
        db = await self._get_db()
        
        # Get the most recent active session (sorted by created_at descending)
        session_data = await db.sessions.find_one(
            {
                "user_id": user_id,
                "assignment_id": assignment_id,
                "status": SessionStatus.ACTIVE
            },
            sort=[("created_at", -1)]  # Get most recent first
        )
        
        if not session_data:
            return None
        
        # Check if there are multiple active sessions (should not happen after cleanup)
        active_count = await db.sessions.count_documents({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "status": SessionStatus.ACTIVE
        })
        
        if active_count > 1:
            logger.warning(f"🚨 [DUPLICATE_DETECTION] Found {active_count} active sessions for user {user_id}, assignment {assignment_id}")
            # Log session IDs for debugging
            all_active = await db.sessions.find({
                "user_id": user_id,
                "assignment_id": assignment_id,
                "status": SessionStatus.ACTIVE
            }).to_list(None)
            
            session_ids = [str(s["_id"]) for s in all_active]
            logger.warning(f"🚨 [DUPLICATE_DETECTION] Active session IDs: {session_ids}")
        
        return Session.model_validate(session_data)
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data"""
        db = await self._get_db()
        
        updates["updated_at"] = datetime.utcnow()
        
        result = await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": updates}
        )
        
        return result.modified_count > 0
    
    async def _cleanup_active_sessions(self, user_id: str, assignment_id: str) -> int:
        """Clean up any existing active sessions for this user+assignment"""
        db = await self._get_db()
        
        # Find all active sessions for this user+assignment
        active_sessions = await db.sessions.find({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "status": SessionStatus.ACTIVE
        }).to_list(None)
        
        if not active_sessions:
            return 0
        
        logger.info(f"🧹 [CLEANUP] Found {len(active_sessions)} active sessions to cleanup for user {user_id}")
        
        # End all active sessions
        session_ids = [session["_id"] for session in active_sessions]
        
        result = await db.sessions.update_many(
            {"_id": {"$in": session_ids}},
            {
                "$set": {
                    "status": SessionStatus.COMPLETED,
                    "ended_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "session_notes": "Auto-ended due to new session creation"
                }
            }
        )
        
        logger.info(f"🧹 [CLEANUP] Successfully ended {result.modified_count} sessions")
        return result.modified_count
    
    async def end_session(self, session_id: str) -> bool:
        """End a session"""
        db = await self._get_db()
        
        result = await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {
                "status": SessionStatus.COMPLETED,
                "ended_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }}
        )
        
        return result.modified_count > 0
    
    async def _generate_problem_presentation(
        self, 
        problem: "Problem", 
        problem_number: int, 
        user_input: str, 
        conversation_history: List[ConversationMessage]
    ) -> str:
        """Generate problem presentation for the next problem"""
        
        logger.info(f"🎯 [ENHANCED_SESSION] Generating presentation for problem {problem_number}: {problem.title}")
        
        try:
            from app.services.openai_client import openai_client
            
            # Format test cases for display
            test_cases_display = ""
            if problem.test_cases and len(problem.test_cases) > 0:
                test_cases_display = "\n\n**Sample Input/Output:**\n"
                for i, test_case in enumerate(problem.test_cases[:2]):  # Show first 2 test cases
                    if isinstance(test_case, dict):
                        input_val = test_case.get('input', 'N/A')
                        output_val = test_case.get('expected_output', 'N/A') 
                        description = test_case.get('description', '')
                        
                        test_cases_display += f"\n**Example {i+1}:**\n"
                        test_cases_display += f"Input: {input_val}\n"
                        test_cases_display += f"Output: {output_val}\n"
                        if description and description != 'N/A':
                            test_cases_display += f"Explanation: {description}\n"
            
            prompt = f"""You are an AI tutor presenting a new programming problem to a student. Generate an encouraging transition that presents the problem clearly.

The student just completed the previous problem and is ready for:

**Problem {problem_number}: {problem.title}**

{problem.description}{test_cases_display}

Generate a response that:
1. Briefly acknowledges their readiness for the next problem
2. Presents the new problem clearly with the provided examples
3. Asks "How are you thinking to solve this question?" at the end

Keep it encouraging and focused. Don't give away any solutions."""

            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an encouraging programming tutor who presents problems clearly."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.5
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            else:
                # Fallback presentation
                return self._fallback_problem_presentation(problem, problem_number)
                
        except Exception as e:
            logger.error(f"❌ [ENHANCED_SESSION] Error generating problem presentation: {e}")
            return self._fallback_problem_presentation(problem, problem_number)
    
    def _fallback_problem_presentation(self, problem: "Problem", problem_number: int) -> str:
        """Fallback problem presentation when OpenAI fails"""
        # Format test cases for fallback display
        test_cases_fallback = ""
        if problem.test_cases and len(problem.test_cases) > 0:
            test_cases_fallback = "\n\n**Sample Input/Output:**\n"
            for i, test_case in enumerate(problem.test_cases[:2]):  # Show first 2 test cases
                if isinstance(test_case, dict):
                    input_val = test_case.get('input', 'N/A')
                    output_val = test_case.get('expected_output', 'N/A') 
                    description = test_case.get('description', '')
                    
                    test_cases_fallback += f"\n**Example {i+1}:**\n"
                    test_cases_fallback += f"Input: {input_val}\n"
                    test_cases_fallback += f"Output: {output_val}\n"
                    if description and description != 'N/A':
                        test_cases_fallback += f"Explanation: {description}\n"
        
        return f"""Great! Let's move to the next problem.

**Problem {problem_number}: {problem.title}**

{problem.description}{test_cases_fallback}

How are you thinking to solve this question?"""


# Create service instance
enhanced_session_service = EnhancedSessionService()