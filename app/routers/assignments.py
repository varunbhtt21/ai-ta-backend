from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.models import ResponseBase, User
from app.routers.auth import get_current_user, get_current_instructor
from app.services.assignment_service import assignment_service
from app.services.file_upload_service import file_upload_service
from app.services.ai_markdown_converter import ai_markdown_converter
from app.services.ai_function_processor import ai_function_processor

router = APIRouter()
logger = logging.getLogger(__name__)


class AssignmentCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    curriculum_content: str = ""
    problems: List[dict] = []
    tags: List[str] = []


class AssignmentUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    curriculum_content: Optional[str] = None
    problems: Optional[List[dict]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class AIProcessCurriculumRequest(BaseModel):
    content: str
    
    
class AIProcessProblemsRequest(BaseModel):
    content: str


@router.get("/", response_model=ResponseBase)
async def list_assignments(
    active_only: bool = True,
    tags: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: User = Depends(get_current_user)
):
    """List all available assignments"""
    try:
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else None
        
        assignments = await assignment_service.list_assignments(
            active_only=active_only,
            tags=tag_list,
            limit=limit,
            skip=skip
        )
        
        assignment_data = []
        for assignment in assignments:
            assignment_data.append({
                "id": str(assignment.id),
                "title": assignment.title,
                "description": assignment.description,
                "total_problems": assignment.total_problems,
                "tags": assignment.tags,
                "created_at": assignment.created_at,
                "is_active": assignment.is_active
            })
        
        return ResponseBase(
            success=True,
            message="Assignments retrieved successfully",
            data={
                "assignments": assignment_data,
                "total": len(assignment_data),
                "limit": limit,
                "skip": skip
            }
        )
    
    except Exception as e:
        logger.error(f"Error listing assignments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignments"
        )


@router.get("/{assignment_id}", response_model=ResponseBase)
async def get_assignment(
    assignment_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get specific assignment details"""
    try:
        assignment = await assignment_service.get_assignment(assignment_id)
        
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
        
        # Get assignment statistics for instructors
        statistics = None
        from app.services.auth_service import auth_service
        if auth_service.is_instructor(current_user):
            statistics = await assignment_service.get_assignment_statistics(assignment_id)
        
        assignment_data = {
            "id": str(assignment.id),
            "title": assignment.title,
            "description": assignment.description,
            "curriculum_content": assignment.curriculum_content,
            "problems": [problem.dict() for problem in assignment.problems],
            "total_problems": assignment.total_problems,
            "tags": assignment.tags,
            "created_at": assignment.created_at,
            "is_active": assignment.is_active
        }
        
        if statistics:
            assignment_data["statistics"] = statistics
        
        return ResponseBase(
            success=True,
            message="Assignment retrieved successfully",
            data=assignment_data
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignment"
        )


@router.post("/", response_model=ResponseBase)
async def create_assignment(
    request: AssignmentCreateRequest,
    current_user: User = Depends(get_current_instructor)
):
    """Create new assignment (instructor only)"""
    try:
        assignment = await assignment_service.create_assignment(
            title=request.title,
            description=request.description,
            curriculum_content=request.curriculum_content,
            problems=request.problems,
            tags=request.tags,
            instructor_id=str(current_user.id)
        )
        
        return ResponseBase(
            success=True,
            message="Assignment created successfully",
            data={
                "assignment_id": str(assignment.id),
                "title": assignment.title,
                "total_problems": assignment.total_problems
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create assignment"
        )


@router.put("/{assignment_id}", response_model=ResponseBase)
async def update_assignment(
    assignment_id: str,
    request: AssignmentUpdateRequest,
    current_user: User = Depends(get_current_instructor)
):
    """Update assignment"""
    try:
        # Check if assignment exists
        assignment = await assignment_service.get_assignment(assignment_id)
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
        
        # Build updates dictionary
        updates = {}
        if request.title is not None:
            updates["title"] = request.title
        if request.description is not None:
            updates["description"] = request.description
        if request.curriculum_content is not None:
            updates["curriculum_content"] = request.curriculum_content
        if request.problems is not None:
            updates["problems"] = request.problems
        if request.tags is not None:
            updates["tags"] = request.tags
        if request.is_active is not None:
            updates["is_active"] = request.is_active
        
        success = await assignment_service.update_assignment(assignment_id, updates)
        
        if success:
            return ResponseBase(
                success=True,
                message="Assignment updated successfully",
                data={"assignment_id": assignment_id}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No changes made to assignment"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update assignment"
        )


@router.delete("/{assignment_id}", response_model=ResponseBase)
async def delete_assignment(
    assignment_id: str,
    current_user: User = Depends(get_current_instructor)
):
    """Delete assignment (soft delete)"""
    try:
        success = await assignment_service.delete_assignment(assignment_id)
        
        if success:
            return ResponseBase(
                success=True,
                message="Assignment deleted successfully",
                data={"assignment_id": assignment_id}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete assignment"
        )


@router.post("/from-files", response_model=ResponseBase)
async def create_assignment_from_files(
    file: UploadFile = File(...),
    title: str = Form(...),
    current_user: User = Depends(get_current_instructor)
):
    """Create assignment from uploaded files"""
    try:
        result = await file_upload_service.process_assignment_file(
            file=file,
            title=title,
            instructor_id=str(current_user.id)
        )
        
        return ResponseBase(
            success=True,
            message="Assignment created from file successfully",
            data=result
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating assignment from file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create assignment from file"
        )


@router.get("/search", response_model=ResponseBase)
async def search_assignments(
    query: str,
    tags: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Search assignments"""
    try:
        tag_list = [tag.strip() for tag in tags.split(",")] if tags else None
        
        assignments = await assignment_service.search_assignments(
            query=query,
            tags=tag_list,
            limit=limit
        )
        
        assignment_data = []
        for assignment in assignments:
            assignment_data.append({
                "id": str(assignment.id),
                "title": assignment.title,
                "description": assignment.description,
                "total_problems": assignment.total_problems,
                "tags": assignment.tags,
                "created_at": assignment.created_at
            })
        
        return ResponseBase(
            success=True,
            message="Search completed successfully",
            data={
                "assignments": assignment_data,
                "query": query,
                "total_results": len(assignment_data)
            }
        )
    
    except Exception as e:
        logger.error(f"Error searching assignments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.post("/{assignment_id}/duplicate", response_model=ResponseBase)
async def duplicate_assignment(
    assignment_id: str,
    new_title: str = Form(...),
    current_user: User = Depends(get_current_instructor)
):
    """Duplicate an existing assignment"""
    try:
        new_assignment = await assignment_service.duplicate_assignment(
            assignment_id=assignment_id,
            new_title=new_title,
            instructor_id=str(current_user.id)
        )
        
        return ResponseBase(
            success=True,
            message="Assignment duplicated successfully",
            data={
                "original_assignment_id": assignment_id,
                "new_assignment_id": str(new_assignment.id),
                "new_title": new_assignment.title,
                "total_problems": new_assignment.total_problems
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error duplicating assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to duplicate assignment"
        )


@router.post("/ai/process-curriculum", response_model=ResponseBase)
async def ai_process_curriculum(
    request: AIProcessCurriculumRequest,
    current_user: User = Depends(get_current_instructor)
):
    """Process curriculum content using AI function calling"""
    try:
        # Use function calling to process curriculum content
        ai_result = await ai_function_processor.process_curriculum_content(request.content)
        
        if ai_result["success"]:
            data = ai_result["data"]
            return ResponseBase(
                success=True,
                message="Curriculum content processed successfully with function calling",
                data={
                    "original_length": len(request.content),
                    "processed_content": data["processed_content"],
                    "processed_length": len(data["processed_content"]),
                    "title": data.get("title"),
                    "learning_objectives": data.get("learning_objectives", []),
                    "topics_covered": data.get("topics_covered", []),
                    "difficulty_level": data.get("difficulty_level"),
                    "estimated_reading_time": data.get("estimated_reading_time"),
                    "ai_enhanced": True,
                    "tokens_used": ai_result.get("tokens_used", 0),
                    "processing_method": "function_calling"
                }
            )
        else:
            # Function calling failed, return fallback
            data = ai_result["data"]
            return ResponseBase(
                success=True,
                message="Curriculum content processed (fallback mode)",
                data={
                    "original_length": len(request.content),
                    "processed_content": data["processed_content"],
                    "processed_length": len(data["processed_content"]),
                    "title": data.get("title"),
                    "learning_objectives": data.get("learning_objectives", []),
                    "topics_covered": data.get("topics_covered", []),
                    "difficulty_level": data.get("difficulty_level"),
                    "estimated_reading_time": data.get("estimated_reading_time"),
                    "ai_enhanced": False,
                    "error": ai_result.get("error"),
                    "processing_method": "fallback"
                }
            )
    
    except Exception as e:
        logger.error(f"Error processing curriculum with AI function calling: {e}")
        # Ultimate fallback
        return ResponseBase(
            success=True,
            message="Curriculum content processed (basic fallback)",
            data={
                "original_length": len(request.content),
                "processed_content": request.content,
                "processed_length": len(request.content),
                "title": "Curriculum Content",
                "learning_objectives": [],
                "topics_covered": [],
                "difficulty_level": "intermediate",
                "estimated_reading_time": max(1, len(request.content.split()) // 200),
                "ai_enhanced": False,
                "error": str(e),
                "processing_method": "basic_fallback"
            }
        )


@router.post("/ai/process-problems", response_model=ResponseBase)
async def ai_process_problems(
    request: AIProcessProblemsRequest,
    current_user: User = Depends(get_current_instructor)
):
    """Process problems content using AI function calling to extract and enhance problems"""
    try:
        # Use function calling to process assignment problems
        ai_result = await ai_function_processor.process_assignment_problems(request.content)
        
        if ai_result["success"]:
            data = ai_result["data"]
            problems = data.get("problems", [])
            
            return ResponseBase(
                success=True,
                message=f"Problems processed successfully with function calling - {len(problems)} problems found",
                data={
                    "original_length": len(request.content),
                    "problems": problems,
                    "problems_count": len(problems),
                    "total_problems": data.get("total_problems", len(problems)),
                    "extraction_notes": data.get("extraction_notes", ""),
                    "ai_enhanced": True,
                    "tokens_used": ai_result.get("tokens_used", 0),
                    "processing_method": "function_calling"
                }
            )
        else:
            # Function calling failed
            data = ai_result["data"]
            return ResponseBase(
                success=False,
                message="Failed to process problems with function calling",
                data={
                    "original_length": len(request.content),
                    "problems": data.get("problems", []),
                    "problems_count": data.get("total_problems", 0),
                    "total_problems": data.get("total_problems", 0),
                    "extraction_notes": data.get("extraction_notes", "Processing failed"),
                    "ai_enhanced": False,
                    "error": ai_result.get("error"),
                    "processing_method": "failed"
                }
            )
    
    except Exception as e:
        logger.error(f"Error processing problems with AI function calling: {e}")
        # Ultimate fallback
        return ResponseBase(
            success=False,
            message="Failed to process problems - system error",
            data={
                "original_length": len(request.content),
                "problems": [],
                "problems_count": 0,
                "total_problems": 0,
                "extraction_notes": "System error occurred",
                "ai_enhanced": False,
                "error": str(e),
                "processing_method": "system_error"
            }
        )