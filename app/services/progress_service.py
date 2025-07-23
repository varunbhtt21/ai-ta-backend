from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging

from app.database.connection import get_database
from app.models import (
    StudentProgressDocument, ProblemStatus, CodeSubmission,
    StudentProgress, LearningVelocity
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class ProgressService:
    def __init__(self):
        self.db = None
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    async def create_or_update_progress(
        self,
        user_id: str,
        assignment_id: str,
        session_id: str,
        problem_number: int,
        status: Optional[ProblemStatus] = None,
        code_submission: Optional[str] = None,
        is_correct: Optional[bool] = None,
        hints_used: int = 0,
        time_increment: float = 0.0
    ) -> StudentProgressDocument:
        """Create or update student progress for a specific problem"""
        db = await self._get_db()
        
        # Find existing progress record
        existing = await db.student_progress.find_one({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "problem_number": problem_number
        })
        
        if existing:
            # Update existing record
            updates = {}
            
            if status:
                updates["status"] = status.value
                if status == ProblemStatus.COMPLETED:
                    updates["completed_at"] = datetime.utcnow()
                elif status == ProblemStatus.IN_PROGRESS and not existing.get("started_at"):
                    updates["started_at"] = datetime.utcnow()
            
            if code_submission:
                # Add new code submission
                submission_number = len(existing.get("code_submissions", [])) + 1
                new_submission = {
                    "submission_number": submission_number,
                    "code": code_submission,
                    "timestamp": datetime.utcnow(),
                    "is_correct": is_correct,
                    "result": "correct" if is_correct else "incorrect" if is_correct is not None else "pending"
                }
                
                updates["$push"] = {"code_submissions": new_submission}
                updates["$inc"] = {"attempts": 1}
                
                if is_correct:
                    updates["final_solution"] = code_submission
            
            if hints_used > 0:
                updates["$inc"] = updates.get("$inc", {})
                updates["$inc"]["hints_used"] = hints_used
            
            if time_increment > 0:
                updates["$inc"] = updates.get("$inc", {})
                updates["$inc"]["time_spent_minutes"] = time_increment
            
            updates["session_id"] = session_id
            updates["updated_at"] = datetime.utcnow()
            
            await db.student_progress.update_one(
                {"_id": existing["_id"]},
                updates
            )
            
            # Fetch updated document
            updated_doc = await db.student_progress.find_one({"_id": existing["_id"]})
            return StudentProgressDocument(**updated_doc)
        
        else:
            # Create new progress record
            code_submissions = []
            if code_submission:
                code_submissions = [{
                    "submission_number": 1,
                    "code": code_submission,
                    "timestamp": datetime.utcnow(),
                    "is_correct": is_correct,
                    "result": "correct" if is_correct else "incorrect" if is_correct is not None else "pending"
                }]
            
            progress = StudentProgressDocument(
                user_id=user_id,
                assignment_id=assignment_id,
                session_id=session_id,
                problem_number=problem_number,
                status=status.value if status else ProblemStatus.NOT_STARTED.value,
                attempts=1 if code_submission else 0,
                hints_used=hints_used,
                time_spent_minutes=time_increment,
                code_submissions=code_submissions,
                started_at=datetime.utcnow() if status == ProblemStatus.IN_PROGRESS else None,
                completed_at=datetime.utcnow() if status == ProblemStatus.COMPLETED else None,
                final_solution=code_submission if is_correct else None
            )
            
            result = await db.student_progress.insert_one(progress.dict(by_alias=True))
            progress.id = result.inserted_id
            
            logger.info(f"Created progress record for user {user_id}, problem {problem_number}")
            return progress
    
    async def get_student_progress(
        self,
        user_id: str,
        assignment_id: str
    ) -> List[StudentProgressDocument]:
        """Get all progress records for a student's assignment"""
        db = await self._get_db()
        
        cursor = db.student_progress.find({
            "user_id": user_id,
            "assignment_id": assignment_id
        }).sort("problem_number", 1)
        
        progress_records = []
        async for doc in cursor:
            progress_records.append(StudentProgressDocument(**doc))
        
        return progress_records
    
    async def get_problem_progress(
        self,
        user_id: str,
        assignment_id: str,
        problem_number: int
    ) -> Optional[StudentProgressDocument]:
        """Get progress for a specific problem"""
        db = await self._get_db()
        
        doc = await db.student_progress.find_one({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "problem_number": problem_number
        })
        
        return StudentProgressDocument(**doc) if doc else None
    
    async def get_assignment_statistics(
        self,
        user_id: str,
        assignment_id: str
    ) -> Dict[str, Any]:
        """Get overall statistics for a student's assignment progress"""
        db = await self._get_db()
        
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "assignment_id": assignment_id
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_problems": {"$sum": 1},
                    "completed": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", ProblemStatus.COMPLETED.value]}, 1, 0]
                        }
                    },
                    "in_progress": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", ProblemStatus.IN_PROGRESS.value]}, 1, 0]
                        }
                    },
                    "stuck": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", ProblemStatus.STUCK.value]}, 1, 0]
                        }
                    },
                    "total_attempts": {"$sum": "$attempts"},
                    "total_hints_used": {"$sum": "$hints_used"},
                    "total_time_spent": {"$sum": "$time_spent_minutes"},
                    "avg_attempts_per_problem": {"$avg": "$attempts"}
                }
            }
        ]
        
        result = await db.student_progress.aggregate(pipeline).to_list(1)
        
        if result:
            stats = result[0]
            completion_rate = (stats["completed"] / stats["total_problems"]) * 100 if stats["total_problems"] > 0 else 0
            stats["completion_rate"] = round(completion_rate, 2)
            return stats
        
        return {
            "total_problems": 0,
            "completed": 0,
            "in_progress": 0,
            "stuck": 0,
            "total_attempts": 0,
            "total_hints_used": 0,
            "total_time_spent": 0,
            "avg_attempts_per_problem": 0,
            "completion_rate": 0
        }
    
    async def calculate_learning_velocity(
        self,
        user_id: str,
        assignment_id: str
    ) -> LearningVelocity:
        """Calculate student's learning velocity based on progress patterns"""
        db = await self._get_db()
        
        # Get completed problems with timing data
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "assignment_id": assignment_id,
                    "status": ProblemStatus.COMPLETED.value,
                    "started_at": {"$ne": None},
                    "completed_at": {"$ne": None}
                }
            },
            {
                "$addFields": {
                    "problem_duration": {
                        "$subtract": ["$completed_at", "$started_at"]
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_duration": {"$avg": "$problem_duration"},
                    "avg_attempts": {"$avg": "$attempts"},
                    "total_completed": {"$sum": 1}
                }
            }
        ]
        
        result = await db.student_progress.aggregate(pipeline).to_list(1)
        
        if not result or result[0]["total_completed"] < 2:
            return LearningVelocity.MODERATE
        
        stats = result[0]
        avg_duration_minutes = stats["avg_duration"] / (1000 * 60) if stats["avg_duration"] else 0
        avg_attempts = stats["avg_attempts"] or 0
        
        # Classify based on average duration and attempts
        if avg_duration_minutes < 15 and avg_attempts <= 2:
            return LearningVelocity.FAST
        elif avg_duration_minutes > 45 or avg_attempts > 5:
            return LearningVelocity.SLOW
        else:
            return LearningVelocity.MODERATE
    
    async def identify_struggle_patterns(
        self,
        user_id: str,
        assignment_id: str
    ) -> List[str]:
        """Identify patterns where student is struggling"""
        db = await self._get_db()
        
        struggles = []
        
        # Get problems with high attempt counts
        high_attempt_problems = await db.student_progress.find({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "attempts": {"$gte": 5}
        }).to_list(100)
        
        if high_attempt_problems:
            struggles.append(f"High attempt count on {len(high_attempt_problems)} problems")
        
        # Get stuck problems
        stuck_problems = await db.student_progress.find({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "status": ProblemStatus.STUCK.value
        }).to_list(100)
        
        if stuck_problems:
            struggles.append(f"Currently stuck on {len(stuck_problems)} problems")
        
        # Get problems with excessive hint usage
        high_hint_problems = await db.student_progress.find({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "hints_used": {"$gte": 3}
        }).to_list(100)
        
        if high_hint_problems:
            struggles.append(f"High hint usage on {len(high_hint_problems)} problems")
        
        # Get problems with long duration
        long_duration_problems = await db.student_progress.find({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "time_spent_minutes": {"$gte": 60}  # More than 1 hour
        }).to_list(100)
        
        if long_duration_problems:
            struggles.append(f"Extended time spent on {len(long_duration_problems)} problems")
        
        return struggles
    
    async def get_recent_submissions(
        self,
        user_id: str,
        assignment_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent code submissions across all problems"""
        db = await self._get_db()
        
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "assignment_id": assignment_id,
                    "code_submissions": {"$ne": []}
                }
            },
            {"$unwind": "$code_submissions"},
            {"$sort": {"code_submissions.timestamp": -1}},
            {"$limit": limit},
            {
                "$project": {
                    "problem_number": 1,
                    "submission": "$code_submissions",
                    "status": 1
                }
            }
        ]
        
        results = []
        async for doc in db.student_progress.aggregate(pipeline):
            results.append({
                "problem_number": doc["problem_number"],
                "code": doc["submission"]["code"],
                "timestamp": doc["submission"]["timestamp"],
                "is_correct": doc["submission"].get("is_correct"),
                "submission_number": doc["submission"]["submission_number"],
                "problem_status": doc["status"]
            })
        
        return results


progress_service = ProgressService()