from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database.connection import get_database
from app.models import ResumeType, SessionStatus, ProblemStatus
from app.services.session_service import session_service

logger = logging.getLogger(__name__)


class ResumeDetectionService:
    """
    Intelligent session resume detection system that analyzes user patterns
    to determine the optimal way to resume tutoring sessions.
    """
    
    def __init__(self):
        self.db = None
        self.session_service = session_service
        
        # Configuration for resume detection heuristics
        self.FRESH_START_MAX_AGE_HOURS = 72  # 3 days
        self.MID_CONVERSATION_MAX_GAP_MINUTES = 30
        self.BETWEEN_PROBLEMS_MAX_GAP_HOURS = 24
        self.COMPLETION_RECENCY_HOURS = 48
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    async def determine_resume_type(
        self, 
        user_id: str, 
        assignment_id: str
    ) -> Dict[str, Any]:
        """
        Analyze user's session history to determine optimal resume strategy
        """
        
        try:
            # Get user's session history for this assignment
            recent_sessions = await self.session_service.get_user_assignment_sessions(
                user_id=user_id,
                assignment_id=assignment_id,
                limit=10  # Analyze last 10 sessions
            )
            
            if not recent_sessions:
                return self._create_resume_analysis(
                    ResumeType.FRESH_START,
                    should_resume=False,
                    reason="No previous sessions found",
                    context={"is_first_time": True}
                )
            
            # Get the most recent session
            latest_session = recent_sessions[0]
            session_age = self._calculate_session_age(latest_session)
            
            # Check if there's an active session
            active_session = await self._find_active_session(user_id, assignment_id)
            
            if active_session:
                # Determine if we should resume the active session
                return await self._analyze_active_session(active_session, recent_sessions)
            
            # No active session, analyze completed sessions
            return await self._analyze_completed_sessions(
                latest_session, recent_sessions, session_age
            )
        
        except Exception as e:
            logger.error(f"Resume detection failed: {e}")
            return self._create_resume_analysis(
                ResumeType.FRESH_START,
                should_resume=False,
                reason="Error in resume detection, starting fresh",
                context={"error": str(e)}
            )
    
    async def _find_active_session(self, user_id: str, assignment_id: str) -> Optional[Dict]:
        """Find active session for the user and assignment"""
        try:
            active_session = await self.session_service.get_active_session(
                user_id, assignment_id
            )
            return active_session.model_dump() if active_session else None
        except Exception:
            return None
    
    async def _analyze_active_session(
        self, 
        active_session: Dict, 
        recent_sessions: List[Dict]
    ) -> Dict[str, Any]:
        """Analyze active session to determine resume approach"""
        
        session_age = self._calculate_session_age(active_session)
        
        # If session is very recent (< 30 minutes), likely mid-conversation
        if session_age.total_seconds() < self.MID_CONVERSATION_MAX_GAP_MINUTES * 60:
            # Check for ongoing work pattern
            has_ongoing_work = await self._check_ongoing_work_pattern(
                active_session["_id"], active_session["user_id"]
            )
            
            if has_ongoing_work:
                return self._create_resume_analysis(
                    ResumeType.MID_CONVERSATION,
                    should_resume=True,
                    reason="Recent active session with ongoing work detected",
                    context={
                        "session_age_minutes": session_age.total_seconds() / 60,
                        "last_activity": "working_on_problem",
                        "recommended_session_id": str(active_session["_id"])
                    }
                )
        
        # Session is older, check if it's between problems
        current_problem = active_session.get("current_problem", 1)
        if current_problem > 1:
            return self._create_resume_analysis(
                ResumeType.BETWEEN_PROBLEMS,
                should_resume=True,
                reason="Active session found between problems",
                context={
                    "current_problem": current_problem,
                    "session_age_hours": session_age.total_seconds() / 3600,
                    "recommended_session_id": str(active_session["_id"])
                }
            )
        
        # Default for active sessions
        return self._create_resume_analysis(
            ResumeType.MID_CONVERSATION,
            should_resume=True,
            reason="Active session found",
            context={
                "recommended_session_id": str(active_session["_id"])
            }
        )
    
    async def _analyze_completed_sessions(
        self, 
        latest_session: Dict, 
        recent_sessions: List[Dict],
        session_age: timedelta
    ) -> Dict[str, Any]:
        """Analyze completed sessions to determine resume strategy"""
        
        # Check if assignment is completed
        assignment_completed = await self._check_assignment_completion(
            latest_session["user_id"], latest_session["assignment_id"]
        )
        
        if assignment_completed:
            return self._create_resume_analysis(
                ResumeType.COMPLETED_ASSIGNMENT,
                should_resume=False,
                reason="Assignment already completed",
                context={
                    "completed_at": latest_session.get("ended_at"),
                    "total_sessions": len(recent_sessions)
                }
            )
        
        # Check session age for fresh start threshold
        if session_age.total_seconds() > self.FRESH_START_MAX_AGE_HOURS * 3600:
            return self._create_resume_analysis(
                ResumeType.FRESH_START,
                should_resume=False,
                reason="Sessions are too old, recommend fresh start",
                context={
                    "session_age_hours": session_age.total_seconds() / 3600,
                    "last_session_ended": latest_session.get("ended_at")
                }
            )
        
        # Check for recent progress
        if session_age.total_seconds() < self.BETWEEN_PROBLEMS_MAX_GAP_HOURS * 3600:
            # Likely between problems
            current_problem = latest_session.get("current_problem", 1)
            return self._create_resume_analysis(
                ResumeType.BETWEEN_PROBLEMS,
                should_resume=False,  # Create new session but with context
                reason="Recent activity, likely between problems",
                context={
                    "last_problem_worked_on": current_problem,
                    "session_age_hours": session_age.total_seconds() / 3600,
                    "progress_context": await self._get_progress_context(
                        latest_session["user_id"], latest_session["assignment_id"]
                    )
                }
            )
        
        # Default case - moderate gap, likely needs fresh start
        return self._create_resume_analysis(
            ResumeType.FRESH_START,
            should_resume=False,
            reason="Moderate gap since last session",
            context={
                "session_age_hours": session_age.total_seconds() / 3600,
                "recommended_approach": "gentle_restart"
            }
        )
    
    async def _check_ongoing_work_pattern(self, session_id: str, user_id: str) -> bool:
        """Check if there are signs of ongoing work in the session"""
        
        try:
            db = await self._get_db()
            
            # Look for recent messages in the session
            recent_messages = await db.conversations.find(
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "timestamp": {
                        "$gte": datetime.utcnow() - timedelta(minutes=self.MID_CONVERSATION_MAX_GAP_MINUTES)
                    }
                }
            ).sort("timestamp", -1).limit(5).to_list(5)
            
            if not recent_messages:
                return False
            
            # Check for patterns indicating ongoing work
            recent_content = " ".join([msg.get("content", "") for msg in recent_messages])
            work_indicators = [
                "working on", "trying to", "stuck on", "help with",
                "my code", "error", "function", "def ", "for ", "if "
            ]
            
            return any(indicator in recent_content.lower() for indicator in work_indicators)
        
        except Exception as e:
            logger.warning(f"Failed to check ongoing work pattern: {e}")
            return False
    
    async def _check_assignment_completion(self, user_id: str, assignment_id: str) -> bool:
        """Check if the assignment has been completed"""
        
        try:
            db = await self._get_db()
            
            # Check student progress for completion
            progress_records = await db.student_progress.find({
                "user_id": user_id,
                "assignment_id": assignment_id,
                "status": ProblemStatus.COMPLETED.value
            }).to_list(None)
            
            # Get total problems in assignment
            assignment = await db.assignments.find_one({"_id": ObjectId(assignment_id)})
            if not assignment:
                return False
            
            total_problems = assignment.get("total_problems", len(assignment.get("problems", [])))
            completed_problems = len(progress_records)
            
            return completed_problems >= total_problems
        
        except Exception as e:
            logger.warning(f"Failed to check assignment completion: {e}")
            return False
    
    async def _get_progress_context(self, user_id: str, assignment_id: str) -> Dict[str, Any]:
        """Get context about user's progress on the assignment"""
        
        try:
            db = await self._get_db()
            
            progress_records = await db.student_progress.find({
                "user_id": user_id,
                "assignment_id": assignment_id
            }).to_list(None)
            
            completed_problems = len([p for p in progress_records if p.get("status") == ProblemStatus.COMPLETED.value])
            in_progress_problems = len([p for p in progress_records if p.get("status") == ProblemStatus.IN_PROGRESS.value])
            
            return {
                "completed_problems": completed_problems,
                "in_progress_problems": in_progress_problems,
                "total_attempted": len(progress_records)
            }
        
        except Exception as e:
            logger.warning(f"Failed to get progress context: {e}")
            return {"completed_problems": 0, "in_progress_problems": 0, "total_attempted": 0}
    
    def _calculate_session_age(self, session: Dict) -> timedelta:
        """Calculate how long ago the session was last active"""
        
        # Use ended_at if available, otherwise updated_at, otherwise created_at
        last_activity = (
            session.get("ended_at") or 
            session.get("updated_at") or 
            session.get("created_at") or
            session.get("started_at")
        )
        
        if isinstance(last_activity, str):
            try:
                last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
            except ValueError:
                last_activity = datetime.utcnow()
        elif not isinstance(last_activity, datetime):
            last_activity = datetime.utcnow()
        
        return datetime.utcnow() - last_activity.replace(tzinfo=None)
    
    def _create_resume_analysis(
        self, 
        resume_type: ResumeType, 
        should_resume: bool,
        reason: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create standardized resume analysis result"""
        
        return {
            "resume_type": resume_type.value,
            "should_resume": should_resume,
            "reason": reason,
            "context": context,
            "analysis_timestamp": datetime.utcnow(),
            "welcome_message": self._generate_welcome_message(resume_type, context)
        }
    
    def _generate_welcome_message(self, resume_type: ResumeType, context: Dict[str, Any]) -> str:
        """Generate appropriate welcome message based on resume type"""
        
        if resume_type == ResumeType.FRESH_START:
            if context.get("is_first_time"):
                return "Welcome! I'm excited to help you learn programming. Let's start with your first problem!"
            else:
                return "Welcome back! Ready to dive into some programming challenges?"
        
        elif resume_type == ResumeType.MID_CONVERSATION:
            return "Welcome back! I see we were in the middle of working on something. Ready to continue where we left off?"
        
        elif resume_type == ResumeType.BETWEEN_PROBLEMS:
            completed = context.get("completed_problems", 0)
            if completed > 0:
                return f"Great to see you again! You've completed {completed} problems. Ready for the next challenge?"
            else:
                return "Welcome back! Ready to tackle the next problem?"
        
        elif resume_type == ResumeType.COMPLETED_ASSIGNMENT:
            return "Welcome back! I see you've completed this assignment. Would you like to review any problems or work on additional challenges?"
        
        else:
            return "Welcome back! I'm here to help you with your programming journey."


# Global instance
resume_detection_service = ResumeDetectionService()