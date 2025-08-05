from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
from bson import ObjectId
from app.models import ResponseBase, ProblemStatus
from app.services.progress_service import progress_service
from app.services.assignment_service import assignment_service
from app.routers.auth import get_current_user
from app.models import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=ResponseBase)
async def get_progress_summary(
    assignment_id: str = Query(..., description="Assignment ID"),
    user_id: Optional[str] = Query(None, description="User ID (optional, uses current user if not provided)"),
    current_user: User = Depends(get_current_user)
):
    """Get progress summary for user and assignment"""
    logger.info(f"🔄 [PROGRESS_API] GET /progress/ - assignment_id: {assignment_id}, user_id: {user_id}, current_user: {current_user.username}")
    
    try:
        # Use current user if user_id not provided
        target_user_id = user_id or str(current_user.id)
        logger.info(f"📋 [PROGRESS_API] Target user_id: {target_user_id}")
        
        # Validate assignment ID format
        try:
            ObjectId(assignment_id)
            logger.info(f"✅ [PROGRESS_API] Assignment ID format valid: {assignment_id}")
        except Exception as e:
            logger.error(f"❌ [PROGRESS_API] Invalid assignment ID format: {assignment_id}, error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid assignment ID format"
            )
        
        # Get assignment to calculate progress
        logger.info(f"🎯 [PROGRESS_API] Fetching assignment: {assignment_id}")
        assignment = await assignment_service.get_assignment(assignment_id)
        if not assignment:
            logger.error(f"❌ [PROGRESS_API] Assignment not found: {assignment_id}")
            raise HTTPException(
                status_code=404,
                detail="Assignment not found"
            )
        
        logger.info(f"📚 [PROGRESS_API] Assignment found: {assignment.title}, total_problems: {assignment.total_problems or len(assignment.problems)}")
        
        # Get assignment statistics (this handles empty cases gracefully)
        logger.info(f"📊 [PROGRESS_API] Fetching assignment statistics for user {target_user_id}")
        stats = await progress_service.get_assignment_statistics(target_user_id, assignment_id)
        logger.info(f"📈 [PROGRESS_API] Assignment statistics: {stats}")
        
        # Get detailed progress records
        logger.info(f"📋 [PROGRESS_API] Fetching detailed progress records")
        try:
            progress_records = await progress_service.get_student_progress(target_user_id, assignment_id)
            logger.info(f"📝 [PROGRESS_API] Found {len(progress_records)} progress records")
            for i, record in enumerate(progress_records):
                logger.info(f"   Record {i+1}: Problem {record.problem_number}, Status: {record.status}, Attempts: {record.attempts}")
        except Exception as e:
            logger.warning(f"⚠️ [PROGRESS_API] Failed to get progress records for user {target_user_id}, assignment {assignment_id}: {str(e)}")
            progress_records = []
        
        # Calculate overall progress percentage
        total_problems = assignment.total_problems or len(assignment.problems)
        completed_problems = stats["completed"]
        in_progress_problems = stats["in_progress"]
        problems_attempted = len(progress_records)
        
        logger.info(f"🧮 [PROGRESS_API] Calculating progress - total_problems: {total_problems}, completed: {completed_problems}, in_progress: {in_progress_problems}, attempted: {problems_attempted}")
        
        if total_problems > 0:
            # More nuanced progress calculation:
            # - Completed problems count as 100% each
            # - In-progress problems count as 50% each (partial credit for starting)
            # - Alternative: Use attempted problems as a baseline
            
            if completed_problems > 0:
                # Standard calculation for completed problems
                overall_progress = (completed_problems / total_problems) * 100
                logger.info(f"✅ [PROGRESS_API] Progress calculation (completed): {completed_problems}/{total_problems} = {overall_progress}%")
            elif in_progress_problems > 0 or problems_attempted > 0:
                # Give partial credit for attempting problems
                partial_progress = max(in_progress_problems, problems_attempted) * 0.5  # 50% credit for starting
                overall_progress = (partial_progress / total_problems) * 100
                logger.info(f"🟡 [PROGRESS_API] Progress calculation (in-progress): {partial_progress}/{total_problems} = {overall_progress}%")
            else:
                overall_progress = 0.0
                logger.info(f"⚪ [PROGRESS_API] No progress - no problems attempted")
        else:
            overall_progress = 0.0
            logger.info(f"❌ [PROGRESS_API] Cannot calculate progress - total_problems is 0")
        
        # Get recent activity
        try:
            recent_submissions = await progress_service.get_recent_submissions(
                target_user_id, assignment_id, limit=1
            )
        except Exception as e:
            logger.warning(f"Failed to get recent submissions: {str(e)}")
            recent_submissions = []
        last_activity = None
        if recent_submissions:
            last_activity = recent_submissions[0]["timestamp"].isoformat()
        elif progress_records:
            # Use the most recent updated record
            sorted_records = sorted(progress_records, key=lambda x: x.updated_at or x.created_at, reverse=True)
            if sorted_records:
                last_activity = (sorted_records[0].updated_at or sorted_records[0].created_at).isoformat()
        
        # Format progress data
        progress_by_problem = []
        for record in progress_records:
            progress_by_problem.append({
                "problem_number": record.problem_number,
                "status": record.status,
                "attempts": record.attempts,
                "hints_used": record.hints_used,
                "time_spent_minutes": record.time_spent_minutes,
                "started_at": record.started_at.isoformat() if record.started_at else None,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            })
        
        # Prepare final response data
        response_data = {
            "user_id": target_user_id,
            "assignment_id": assignment_id,
            "overall_progress": round(overall_progress, 1),
            "problems_completed": stats.get("completed", 0),
            "problems_attempted": len(progress_records),
            "total_time_spent_minutes": round(stats.get("total_time_spent", 0), 2),
            "last_activity": last_activity or "",
            "progress_by_problem": progress_by_problem
        }
        
        logger.info(f"🎉 [PROGRESS_API] Returning progress summary: {response_data}")
        
        return ResponseBase(
            success=True,
            message="Progress summary retrieved successfully",
            data=response_data
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Error getting progress summary for assignment {assignment_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve progress summary: {str(e)}"
        )


@router.post("/", response_model=ResponseBase)
async def update_progress(
    assignment_id: str,
    problem_number: int,
    status: Optional[str] = None,
    code_submission: Optional[dict] = None,
    time_spent_minutes: Optional[float] = None,
    hints_used: Optional[int] = None,
    current_user: User = Depends(get_current_user)
):
    """Update progress for specific problem"""
    try:
        user_id = str(current_user.id)
        
        # Convert status string to enum if provided
        problem_status = None
        if status:
            try:
                problem_status = ProblemStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}"
                )
        
        # Extract code submission data
        code = None
        is_correct = None
        if code_submission:
            code = code_submission.get("code")
            is_correct = code_submission.get("is_correct")
        
        # Create a session_id placeholder (in real usage, this would come from active session)
        session_id = f"temp_session_{user_id}_{assignment_id}"
        
        # Update progress
        updated_progress = await progress_service.create_or_update_progress(
            user_id=user_id,
            assignment_id=assignment_id,
            session_id=session_id,
            problem_number=problem_number,
            status=problem_status,
            code_submission=code,
            is_correct=is_correct,
            hints_used=hints_used or 0,
            time_increment=time_spent_minutes or 0
        )
        
        return ResponseBase(
            success=True,
            message="Progress updated successfully",
            data={
                "problem_number": updated_progress.problem_number,
                "status": updated_progress.status,
                "attempts": updated_progress.attempts,
                "hints_used": updated_progress.hints_used,
                "time_spent_minutes": updated_progress.time_spent_minutes,
                "updated_at": updated_progress.updated_at.isoformat() if updated_progress.updated_at else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error updating progress: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update progress: {str(e)}"
        )


@router.get("/detailed", response_model=ResponseBase)
async def get_detailed_progress(
    assignment_id: str = Query(..., description="Assignment ID"),
    user_id: Optional[str] = Query(None, description="User ID (optional, uses current user if not provided)"),
    current_user: User = Depends(get_current_user)
):
    """Get detailed progress with insights"""
    try:
        # Use current user if user_id not provided
        target_user_id = user_id or str(current_user.id)
        
        # Get basic progress summary
        summary_response = await get_progress_summary(assignment_id, target_user_id, current_user)
        summary = summary_response.data
        
        # Get detailed progress records
        progress_records = await progress_service.get_student_progress(target_user_id, assignment_id)
        
        # Get struggle patterns
        struggles = await progress_service.identify_struggle_patterns(target_user_id, assignment_id)
        
        # Get learning velocity
        velocity = await progress_service.calculate_learning_velocity(target_user_id, assignment_id)
        
        # Generate insights
        insights = {
            "struggling_concepts": struggles,
            "strong_areas": [],  # TODO: Implement strong area detection
            "recommendations": [],  # TODO: Implement recommendations
            "estimated_completion_time": 0,  # TODO: Implement time estimation
            "learning_velocity": velocity.value
        }
        
        return ResponseBase(
            success=True,
            message="Detailed progress retrieved successfully",
            data={
                "summary": summary,
                "detailed_progress": [
                    {
                        "problem_number": record.problem_number,
                        "status": record.status,
                        "attempts": record.attempts,
                        "hints_used": record.hints_used,
                        "time_spent_minutes": record.time_spent_minutes,
                        "code_submissions": record.code_submissions,
                        "started_at": record.started_at.isoformat() if record.started_at else None,
                        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
                    }
                    for record in progress_records
                ],
                "insights": insights
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting detailed progress: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve detailed progress: {str(e)}"
        )


@router.delete("/", response_model=ResponseBase)
async def reset_progress(
    assignment_id: str = Query(..., description="Assignment ID"),
    user_id: Optional[str] = Query(None, description="User ID (optional, uses current user if not provided)"),
    current_user: User = Depends(get_current_user)
):
    """Reset progress for specific assignment and user"""
    try:
        # Use current user if user_id not provided  
        target_user_id = user_id or str(current_user.id)
        
        # Only allow users to reset their own progress unless they're an instructor/admin
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
        if target_user_id != str(current_user.id) and user_role not in ['instructor', 'admin']:
            raise HTTPException(
                status_code=403, 
                detail="You can only reset your own progress"
            )
        
        # Delete all progress records for this user and assignment
        from app.database.connection import get_database
        db = await get_database()
        
        result = await db.student_progress.delete_many({
            "user_id": target_user_id,
            "assignment_id": assignment_id
        })
        
        return ResponseBase(
            success=True,
            message=f"Progress reset successfully. Deleted {result.deleted_count} records.",
            data={
                "assignment_id": assignment_id,
                "user_id": target_user_id,
                "deleted_records": result.deleted_count
            }
        )
        
    except Exception as e:
        logger.error(f"Error resetting progress: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset progress: {str(e)}"
        )


@router.get("/statistics", response_model=ResponseBase)
async def get_progress_statistics(
    assignment_id: Optional[str] = Query(None, description="Assignment ID (optional, gets stats for all assignments if not provided)"),
    current_user: User = Depends(get_current_user)
):
    """Get progress statistics for instructor dashboard"""
    try:
        # Only instructors and admins can access statistics
        user_role = current_user.role.value if hasattr(current_user.role, 'value') else current_user.role
        if user_role not in ['instructor', 'admin']:
            raise HTTPException(
                status_code=403,
                detail="Only instructors and admins can access progress statistics"
            )
        
        from app.database.connection import get_database
        db = await get_database()
        
        # Build the match stage for aggregation
        match_stage = {}
        if assignment_id:
            match_stage["assignment_id"] = assignment_id
        
        # Get assignment statistics
        assignment_pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": "$assignment_id",
                    "student_count": {"$addToSet": "$user_id"},
                    "total_problems_attempted": {"$sum": 1},
                    "total_problems_completed": {
                        "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                    },
                    "total_time_spent": {"$sum": "$time_spent_minutes"}
                }
            },
            {
                "$addFields": {
                    "student_count": {"$size": "$student_count"},
                    "completion_rate": {
                        "$multiply": [
                            {"$divide": ["$total_problems_completed", "$total_problems_attempted"]},
                            100
                        ]
                    }
                }
            }
        ]
        
        assignment_stats = []
        async for doc in db.student_progress.aggregate(assignment_pipeline):
            # Get assignment details
            assignment = await assignment_service.get_assignment(doc["_id"])
            assignment_title = assignment.title if assignment else "Unknown Assignment"
            
            assignment_stats.append({
                "assignment_id": doc["_id"],
                "assignment_title": assignment_title,
                "student_count": doc["student_count"],
                "average_progress": round(doc["completion_rate"], 1),
                "completion_rate": round(doc["completion_rate"], 1)
            })
        
        # Get student performance statistics
        student_pipeline = [
            {"$match": match_stage},
            {
                "$group": {
                    "_id": "$user_id",
                    "assignments_worked": {"$addToSet": "$assignment_id"},
                    "problems_completed": {
                        "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                    },
                    "problems_attempted": {"$sum": 1},
                    "total_study_time": {"$sum": "$time_spent_minutes"},
                    "last_activity": {"$max": "$updated_at"}
                }
            },
            {
                "$addFields": {
                    "assignments_count": {"$size": "$assignments_worked"},
                    "average_progress": {
                        "$multiply": [
                            {"$divide": ["$problems_completed", "$problems_attempted"]},
                            100
                        ]
                    }
                }
            }
        ]
        
        student_performance = []
        async for doc in db.student_progress.aggregate(student_pipeline):
            # Get user details
            user_doc = await db.users.find_one({"_id": doc["_id"]})
            username = user_doc["username"] if user_doc else "Unknown User"
            
            student_performance.append({
                "user_id": doc["_id"],
                "username": username,
                "assignments_completed": doc["assignments_count"],
                "average_progress": round(doc["average_progress"], 1),
                "total_study_time": round(doc["total_study_time"], 1),
                "last_activity": doc["last_activity"].isoformat() if doc["last_activity"] else None
            })
        
        # Calculate overall statistics
        total_students = len(student_performance)
        active_students = len([s for s in student_performance if s["last_activity"]])
        average_completion_rate = sum([s["average_progress"] for s in student_performance]) / len(student_performance) if student_performance else 0
        
        return ResponseBase(
            success=True,
            message="Progress statistics retrieved successfully",
            data={
                "total_students": total_students,
                "active_students": active_students,
                "average_completion_rate": round(average_completion_rate, 1),
                "assignment_statistics": assignment_stats,
                "student_performance": student_performance
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting progress statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve progress statistics: {str(e)}"
        )