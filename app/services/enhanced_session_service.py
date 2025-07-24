"""
Enhanced Session Service with Structured Tutoring Integration
This service integrates the OOP prototype structured teaching methodology.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database.connection import get_database
from app.models import (
    Session, SessionStatus, ContextCompressionLevel, 
    SessionRequest, SessionResponse, MessageRequest,
    ConversationDocument, StudentProgressDocument,
    Assignment, Problem, User, ConversationMessage, MessageType
)
from app.services.structured_tutoring_engine import (
    StructuredTutoringEngine, StudentState, TutoringMode
)
from app.services.assignment_service import assignment_service
from app.services.auth_service import auth_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class EnhancedSessionService:
    """Enhanced session service with structured tutoring methodology"""
    
    def __init__(self):
        self.db = None
        self.structured_engine = StructuredTutoringEngine()
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    async def start_intelligent_session(self, user_id: str, assignment_id: str) -> Dict[str, Any]:
        """Start an intelligent session with structured tutoring"""
        
        try:
            db = await self._get_db()
            
            # Check for existing active session
            existing_session = await self.get_active_session(user_id, assignment_id)
            if existing_session:
                # Resume existing session
                return await self._resume_session(existing_session)
            
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
            
            # Load conversation history from previous sessions
            conversation_history = await self._load_conversation_history(user_id, assignment_id)
            
            # Determine current problem based on progress
            current_problem_number = await self._get_current_problem_number(user_id, assignment_id)
            current_problem = None
            if current_problem_number <= len(assignment.problems):
                current_problem = assignment.problems[current_problem_number - 1]
            
            # Generate welcome message using structured approach
            welcome_response = await self._generate_welcome_message(
                user, assignment, current_problem, conversation_history, session
            )
            
            # Save welcome message to conversation
            await self._save_message(
                session.id, user_id, MessageType.ASSISTANT, welcome_response["message"]
            )
            
            return {
                "session_id": str(session.id),
                "session_number": session.session_number,
                "compression_level": session.compression_level.value,
                "current_problem": current_problem_number,
                "total_problems": len(assignment.problems),
                "message": welcome_response["message"],
                "student_state": welcome_response["student_state"],
                "teaching_notes": welcome_response.get("teaching_notes", [])
            }
            
        except Exception as e:
            logger.error(f"Error starting intelligent session: {e}")
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
            
            # Check if problem was completed and handle progression
            if structured_response.student_state == StudentState.PROBLEM_COMPLETED:
                logger.info("🎉 ENHANCED_SESSION_SERVICE: Problem completed! Updating progress...")
                await self._update_problem_progress(
                    session.user_id, 
                    session.assignment_id, 
                    current_problem_number
                )
            
            # Check if user is ready to start next problem
            elif structured_response.student_state == StudentState.READY_TO_START and current_state == StudentState.PROBLEM_COMPLETED:
                logger.info("🚀 ENHANCED_SESSION_SERVICE: User ready for next problem!")
                # Get the updated current problem number after progression
                updated_problem_number = await self._get_current_problem_number(
                    session.user_id, session.assignment_id
                )
                logger.info(f"📊 ENHANCED_SESSION_SERVICE: Updated problem number: {updated_problem_number}")
                
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
        
        if last_ai_messages:
            last_ai_message = last_ai_messages[-1].content.lower()
            
            # Check if we just presented a problem
            if "how are you thinking to solve" in last_ai_message:
                return StudentState.PROBLEM_PRESENTED
            
            # Check if we're waiting for code
            if "try writing the code" in last_ai_message or "can you try" in last_ai_message:
                return StudentState.WORKING_ON_CODE
            
            # Check if we gave hints
            if "hint" in last_ai_message or "look at" in last_ai_message:
                return StudentState.WORKING_ON_CODE
        
        # Analyze latest input
        latest_lower = latest_input.lower().strip()
        
        # Code submission
        code_indicators = ['=', 'for ', 'while ', 'if ', 'def ', 'print(', 'input(', 'append(']
        if any(indicator in latest_input for indicator in code_indicators):
            return StudentState.CODE_REVIEW
        
        # Stuck/confusion
        stuck_indicators = ['not clear', 'don\'t understand', 'stuck', 'confused', 'not getting it']
        if any(indicator in latest_lower for indicator in stuck_indicators):
            return StudentState.STUCK_NEEDS_HELP
        
        # Ready to start
        ready_indicators = ['ready', 'start', 'begin', 'yes', 'ok', 'sure']
        if any(indicator in latest_lower for indicator in ready_indicators):
            return StudentState.READY_TO_START
        
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
        """Get the current problem number for the user"""
        db = await self._get_db()
        
        # Check progress records
        progress = await db.student_progress.find_one({
            "user_id": user_id,
            "assignment_id": assignment_id
        }, sort=[("updated_at", -1)])
        
        if progress:
            return progress.get("current_problem", 1)
        
        return 1  # Start with first problem
    
    async def _update_problem_progress(self, user_id: str, assignment_id: str, completed_problem: int):
        """Update student progress when a problem is completed"""
        db = await self._get_db()
        
        logger.info(f"📈 ENHANCED_SESSION_SERVICE: Updating progress for user {user_id}")
        logger.info(f"📚 ENHANCED_SESSION_SERVICE: Assignment {assignment_id}, completed problem {completed_problem}")
        
        # Calculate next problem number
        next_problem = completed_problem + 1
        
        # Update or create progress record
        await db.student_progress.update_one(
            {
                "user_id": user_id,
                "assignment_id": assignment_id
            },
            {
                "$set": {
                    "current_problem": next_problem,
                    "completed_problems": completed_problem,
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        logger.info(f"✅ ENHANCED_SESSION_SERVICE: Progress updated - next problem: {next_problem}")
    
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
        db = await self._get_db()
        
        # Update progress
        await db.student_progress.update_one(
            {"user_id": user_id, "assignment_id": assignment_id},
            {
                "$set": {
                    "current_problem": problem_number + 1,
                    "updated_at": datetime.utcnow()
                },
                "$push": {
                    "completed_problems": problem_number
                }
            },
            upsert=True
        )
    
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
        """Get user's active session for an assignment"""
        db = await self._get_db()
        
        session_data = await db.sessions.find_one({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "status": SessionStatus.ACTIVE
        })
        
        if not session_data:
            return None
        
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


# Create service instance
enhanced_session_service = EnhancedSessionService()