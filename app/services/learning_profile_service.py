from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database.connection import get_database
from app.models import LearningProfile, LearningVelocity, TeachingStyle, CodeCompetencyLevel
from app.services.progress_service import progress_service

logger = logging.getLogger(__name__)


class LearningProfileService:
    """Service for managing student learning profiles and adaptive tutoring"""
    
    def __init__(self):
        self.db = None
        self.progress_service = progress_service
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    async def get_or_create_learning_profile(self, user_id: str) -> LearningProfile:
        """Get existing learning profile or create new one"""
        
        db = await self._get_db()
        
        # Try to find existing profile
        profile_data = await db.learning_profiles.find_one({"user_id": user_id})
        
        if profile_data:
            return LearningProfile.model_validate(profile_data)
        
        # Create new profile with defaults
        profile = LearningProfile(
            user_id=user_id,
            current_problem=0,
            mastered_concepts=[],
            active_struggles=[],
            learning_velocity=LearningVelocity.MODERATE,
            preferred_teaching_style=TeachingStyle.COLLABORATIVE,
            code_competency={},
            session_pattern={},
            total_sessions=0
        )
        
        result = await db.learning_profiles.insert_one(profile.dict(by_alias=True))
        profile.id = result.inserted_id
        
        logger.info(f"Created new learning profile for user {user_id}")
        return profile
    
    async def update_learning_profile_from_session(
        self,
        user_id: str,
        assignment_id: str,
        session_data: Dict[str, Any]
    ) -> LearningProfile:
        """Update learning profile based on session activity"""
        
        profile = await self.get_or_create_learning_profile(user_id)
        
        # Get recent progress data
        progress_records = await self.progress_service.get_student_progress(user_id, assignment_id)
        
        # Update session count and patterns
        profile.total_sessions += 1
        
        # Calculate learning velocity based on recent performance
        new_velocity = await self._calculate_learning_velocity(user_id, assignment_id, progress_records)
        if new_velocity != profile.learning_velocity:
            logger.info(f"Learning velocity updated for user {user_id}: {profile.learning_velocity} → {new_velocity}")
            profile.learning_velocity = new_velocity
        
        # Update competency assessments
        profile.code_competency = await self._assess_code_competency(progress_records)
        
        # Update mastered concepts and struggles
        profile.mastered_concepts = await self._identify_mastered_concepts(progress_records)
        profile.active_struggles = await self._identify_active_struggles(user_id, assignment_id)
        
        # Update current problem
        profile.current_problem = self._determine_current_problem(progress_records)
        
        # Update session patterns
        profile.session_pattern = await self._analyze_session_patterns(user_id)
        
        # Calculate derived metrics
        if progress_records:
            completed_problems = len([p for p in progress_records if p.status == "completed"])
            attempted_problems = len(progress_records)
            profile.problems_completed = completed_problems
            profile.problems_attempted = attempted_problems
            profile.success_rate = completed_problems / attempted_problems if attempted_problems > 0 else 0.0
            
            # Calculate total time
            total_time = sum(p.time_spent_minutes for p in progress_records)
            profile.total_time_spent_minutes = total_time
            
            if profile.total_sessions > 0:
                profile.average_session_duration_minutes = total_time / profile.total_sessions
        
        # Save updated profile
        await self._save_learning_profile(profile)
        
        return profile
    
    async def _calculate_learning_velocity(
        self,
        user_id: str,
        assignment_id: str,
        progress_records: List
    ) -> LearningVelocity:
        """Calculate learning velocity based on performance patterns"""
        
        if not progress_records:
            return LearningVelocity.MODERATE
        
        completed_problems = [p for p in progress_records if p.status == "completed"]
        
        if len(completed_problems) < 2:
            return LearningVelocity.MODERATE
        
        # Calculate average time per completed problem
        total_time = sum(p.time_spent_minutes for p in completed_problems)
        avg_time_per_problem = total_time / len(completed_problems)
        
        # Calculate average attempts per completed problem
        total_attempts = sum(p.attempts for p in completed_problems)
        avg_attempts_per_problem = total_attempts / len(completed_problems)
        
        # Classify based on speed and efficiency
        if avg_time_per_problem < 20 and avg_attempts_per_problem <= 2:
            return LearningVelocity.FAST
        elif avg_time_per_problem > 60 or avg_attempts_per_problem > 5:
            return LearningVelocity.SLOW
        else:
            return LearningVelocity.MODERATE
    
    async def _assess_code_competency(
        self,
        progress_records: List
    ) -> Dict[str, CodeCompetencyLevel]:
        """Assess code competency in different areas"""
        
        competency = {}
        
        if not progress_records:
            return competency
        
        completed_problems = [p for p in progress_records if p.status == "completed"]
        
        # Overall programming competency
        if len(completed_problems) >= 10:
            avg_attempts = sum(p.attempts for p in completed_problems) / len(completed_problems)
            if avg_attempts <= 2:
                competency["overall"] = CodeCompetencyLevel.ADVANCED
            elif avg_attempts <= 4:
                competency["overall"] = CodeCompetencyLevel.INTERMEDIATE
            else:
                competency["overall"] = CodeCompetencyLevel.BEGINNER
        elif len(completed_problems) >= 3:
            competency["overall"] = CodeCompetencyLevel.INTERMEDIATE
        else:
            competency["overall"] = CodeCompetencyLevel.BEGINNER
        
        # Specific skill areas (would need problem tagging to be more accurate)
        competency["problem_solving"] = competency.get("overall", CodeCompetencyLevel.BEGINNER)
        competency["syntax"] = competency.get("overall", CodeCompetencyLevel.BEGINNER)
        competency["debugging"] = competency.get("overall", CodeCompetencyLevel.BEGINNER)
        
        return competency
    
    async def _identify_mastered_concepts(self, progress_records: List) -> List[str]:
        """Identify concepts the student has mastered"""
        
        mastered = []
        
        if not progress_records:
            return mastered
        
        completed_problems = [p for p in progress_records if p.status == "completed"]
        
        # Basic mastery indicators
        if len(completed_problems) >= 3:
            mastered.append("basic_syntax")
        
        if len(completed_problems) >= 5:
            mastered.append("problem_solving_approach")
        
        if len(completed_problems) >= 8:
            mastered.append("code_structure")
        
        # Look for consistent performance (low attempts across multiple problems)
        consistent_performance = [p for p in completed_problems if p.attempts <= 2]
        if len(consistent_performance) >= len(completed_problems) * 0.7:
            mastered.append("consistent_execution")
        
        return mastered
    
    async def _identify_active_struggles(self, user_id: str, assignment_id: str) -> List[str]:
        """Identify current areas where student is struggling"""
        
        struggles = await self.progress_service.identify_struggle_patterns(user_id, assignment_id)
        return struggles
    
    def _determine_current_problem(self, progress_records: List) -> int:
        """Determine which problem the student should work on next"""
        
        if not progress_records:
            return 1
        
        # Find the highest problem number
        max_problem = max(p.problem_number for p in progress_records)
        
        # Check if the highest problem is completed
        highest_problem_record = next(p for p in progress_records if p.problem_number == max_problem)
        
        if highest_problem_record.status == "completed":
            return max_problem + 1
        else:
            return max_problem
    
    async def _analyze_session_patterns(self, user_id: str) -> Dict[str, Any]:
        """Analyze user's session patterns for insights"""
        
        db = await self._get_db()
        
        # Get recent session data
        sessions = await db.sessions.find({
            "user_id": user_id
        }).sort("started_at", -1).limit(10).to_list(10)
        
        if not sessions:
            return {}
        
        # Analyze session timing patterns
        session_hours = []
        session_durations = []
        
        for session in sessions:
            if session.get("started_at"):
                session_hours.append(session["started_at"].hour)
            
            if session.get("ended_at") and session.get("started_at"):
                duration = (session["ended_at"] - session["started_at"]).total_seconds() / 60
                session_durations.append(duration)
        
        patterns = {}
        
        if session_hours:
            # Most common session hours
            hour_counts = {}
            for hour in session_hours:
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
            most_common_hour = max(hour_counts, key=hour_counts.get)
            patterns["preferred_time"] = f"{most_common_hour}:00"
        
        if session_durations:
            patterns["average_session_duration"] = sum(session_durations) / len(session_durations)
            patterns["typical_session_length"] = "short" if patterns["average_session_duration"] < 30 else "long"
        
        patterns["recent_session_count"] = len(sessions)
        
        return patterns
    
    async def _save_learning_profile(self, profile: LearningProfile):
        """Save updated learning profile to database"""
        
        db = await self._get_db()
        
        profile.updated_at = datetime.utcnow()
        
        await db.learning_profiles.update_one(
            {"user_id": profile.user_id},
            {"$set": profile.dict(by_alias=True)},
            upsert=True
        )
    
    async def get_teaching_recommendations(self, user_id: str) -> Dict[str, Any]:
        """Get personalized teaching recommendations for a student"""
        
        profile = await self.get_or_create_learning_profile(user_id)
        
        recommendations = {
            "teaching_style": profile.preferred_teaching_style.value,
            "learning_velocity": profile.learning_velocity.value,
            "focus_areas": profile.active_struggles,
            "strengths_to_leverage": profile.mastered_concepts,
            "suggested_problem_difficulty": "medium"
        }
        
        # Adjust difficulty based on competency
        overall_competency = profile.code_competency.get("overall", CodeCompetencyLevel.BEGINNER)
        
        if overall_competency == CodeCompetencyLevel.ADVANCED:
            recommendations["suggested_problem_difficulty"] = "hard"
        elif overall_competency == CodeCompetencyLevel.BEGINNER:
            recommendations["suggested_problem_difficulty"] = "easy"
        
        # Teaching style recommendations based on struggles
        if "High attempt count" in profile.active_struggles:
            recommendations["teaching_approach"] = "Break problems into smaller steps"
        elif "Extended time spent" in profile.active_struggles:
            recommendations["teaching_approach"] = "Provide more guidance and hints"
        elif profile.learning_velocity == LearningVelocity.FAST:
            recommendations["teaching_approach"] = "Provide more challenging extensions"
        else:
            recommendations["teaching_approach"] = "Continue with current collaborative approach"
        
        return recommendations
    
    async def update_teaching_style_preference(
        self,
        user_id: str,
        new_teaching_style: TeachingStyle,
        feedback_reason: str = None
    ) -> bool:
        """Update user's preferred teaching style based on feedback"""
        
        db = await self._get_db()
        
        result = await db.learning_profiles.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "preferred_teaching_style": new_teaching_style.value,
                    "updated_at": datetime.utcnow()
                },
                "$push": {
                    "teaching_style_history": {
                        "style": new_teaching_style.value,
                        "reason": feedback_reason,
                        "updated_at": datetime.utcnow()
                    }
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Teaching style updated for user {user_id}: {new_teaching_style.value}")
            return True
        
        return False
    
    async def get_learning_analytics(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive learning analytics for a student"""
        
        profile = await self.get_or_create_learning_profile(user_id)
        
        analytics = {
            "profile_summary": {
                "learning_velocity": profile.learning_velocity.value,
                "preferred_teaching_style": profile.preferred_teaching_style.value,
                "overall_competency": profile.code_competency.get("overall", "beginner"),
                "total_sessions": profile.total_sessions,
                "problems_completed": profile.problems_completed,
                "success_rate": profile.success_rate
            },
            "strengths": profile.mastered_concepts,
            "improvement_areas": profile.active_struggles,
            "competency_breakdown": profile.code_competency,
            "session_patterns": profile.session_pattern,
            "recommendations": await self.get_teaching_recommendations(user_id)
        }
        
        return analytics


# Global instance
learning_profile_service = LearningProfileService()