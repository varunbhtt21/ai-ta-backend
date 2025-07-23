from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.models import ResponseBase, User
from app.routers.auth import get_current_user, get_current_instructor
from app.services.file_upload_service import file_upload_service

router = APIRouter()
logger = logging.getLogger(__name__)


class FileValidationResponse(BaseModel):
    valid: bool
    errors: List[str]
    warnings: List[str]
    preview: dict


@router.post("/upload", response_model=ResponseBase)
async def upload_file(
    file: UploadFile = File(...),
    subfolder: str = Form("general"),
    current_user: User = Depends(get_current_user)
):
    """Upload a file to the server"""
    try:
        # Validate file
        validation = await file_upload_service.validate_upload(file)
        if not validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {', '.join(validation['errors'])}"
            )
        
        # Save file
        file_info = await file_upload_service.save_uploaded_file(file, subfolder=subfolder)
        
        return ResponseBase(
            success=True,
            message="File uploaded successfully",
            data={
                "file_info": file_info,
                "validation": validation,
                "uploader": {
                    "user_id": str(current_user.id),
                    "username": current_user.username
                }
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file"
        )


@router.post("/validate", response_model=ResponseBase)
async def validate_file_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Validate file before upload without saving it"""
    try:
        validation = await file_upload_service.validate_upload(file)
        
        return ResponseBase(
            success=True,
            message="File validation completed",
            data={
                "validation": validation,
                "file_info": {
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": file.size
                }
            }
        )
    
    except Exception as e:
        logger.error(f"Error validating file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate file"
        )


@router.post("/assignments/create", response_model=ResponseBase)
async def create_assignment_from_upload(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    current_user: User = Depends(get_current_instructor)
):
    """Create assignment from uploaded file (instructors only)"""
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


@router.post("/assignments/validate", response_model=ResponseBase)
async def validate_assignment_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_instructor)
):
    """Validate assignment file format before creating assignment"""
    try:
        # First validate basic file requirements
        validation = await file_upload_service.validate_upload(file)
        
        if not validation["valid"]:
            return ResponseBase(
                success=False,
                message="File validation failed",
                data={"validation": validation}
            )
        
        # Read file content for format validation
        content = await file.read()
        file_content = content.decode('utf-8')
        
        # Reset file position
        await file.seek(0)
        
        # Get file extension
        from pathlib import Path
        file_extension = Path(file.filename).suffix.lower()
        
        # Validate assignment format
        format_validation = await file_upload_service.validate_assignment_format(
            content=file_content,
            file_type=file_extension
        )
        
        return ResponseBase(
            success=format_validation["valid"],
            message="Assignment file validation completed",
            data={
                "basic_validation": validation,
                "format_validation": format_validation,
                "file_info": {
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": len(content),
                    "file_type": file_extension
                }
            }
        )
    
    except Exception as e:
        logger.error(f"Error validating assignment file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate assignment file"
        )


@router.get("/content/{file_path:path}", response_model=ResponseBase)
async def get_file_content(
    file_path: str,
    current_user: User = Depends(get_current_user)
):
    """Get content of uploaded file"""
    try:
        content = await file_upload_service.get_file_content(file_path)
        
        return ResponseBase(
            success=True,
            message="File content retrieved successfully",
            data={
                "file_path": file_path,
                "content": content,
                "content_length": len(content)
            }
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file content"
        )


@router.delete("/{file_path:path}", response_model=ResponseBase)
async def delete_uploaded_file(
    file_path: str,
    current_user: User = Depends(get_current_instructor)
):
    """Delete uploaded file (instructors only)"""
    try:
        success = await file_upload_service.delete_uploaded_file(file_path)
        
        if success:
            return ResponseBase(
                success=True,
                message="File deleted successfully",
                data={"file_path": file_path}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )


@router.get("/stats", response_model=ResponseBase)
async def get_upload_statistics(
    current_user: User = Depends(get_current_instructor)
):
    """Get upload statistics (instructors only)"""
    try:
        stats = file_upload_service.get_upload_stats()
        
        return ResponseBase(
            success=True,
            message="Upload statistics retrieved successfully",
            data=stats
        )
    
    except Exception as e:
        logger.error(f"Error getting upload stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve upload statistics"
        )


@router.post("/cleanup", response_model=ResponseBase)
async def cleanup_old_files(
    days_old: int = Form(30),
    current_user: User = Depends(get_current_instructor)
):
    """Clean up files older than specified days (instructors only)"""
    try:
        if days_old < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="days_old must be at least 1"
            )
        
        deleted_count = await file_upload_service.cleanup_old_files(days_old)
        
        return ResponseBase(
            success=True,
            message="File cleanup completed successfully",
            data={
                "deleted_files_count": deleted_count,
                "days_old": days_old,
                "cleaned_by": {
                    "user_id": str(current_user.id),
                    "username": current_user.username
                }
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during file cleanup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup files"
        )


@router.get("/formats/supported", response_model=ResponseBase)
async def get_supported_formats(
    current_user: User = Depends(get_current_user)
):
    """Get list of supported file formats"""
    try:
        from app.core.config import settings
        
        return ResponseBase(
            success=True,
            message="Supported formats retrieved successfully",
            data={
                "supported_extensions": settings.allowed_extensions_list,
                "max_file_size_mb": settings.MAX_UPLOAD_SIZE / (1024 * 1024),
                "assignment_formats": {
                    ".md": "Markdown format with problem definitions",
                    ".json": "JSON format with structured assignment data",
                    ".yml": "YAML format with structured assignment data",
                    ".yaml": "YAML format with structured assignment data",
                    ".txt": "Plain text (treated as markdown)"
                },
                "upload_path": settings.UPLOAD_PATH
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting supported formats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve supported formats"
        )