"""
Code Execution Router - API endpoints for safe Python code execution
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from app.models import ResponseBase, User
from app.routers.auth import get_current_user
from app.services.code_execution_service import code_execution_service

router = APIRouter()
logger = logging.getLogger(__name__)


class CodeExecutionRequest(BaseModel):
    code: str
    language: str = "python"
    mock_inputs: Optional[List[str]] = None


class CodeExecutionResponse(BaseModel):
    output: str
    error: str
    execution_time: float
    success: bool
    timestamp: str


@router.post("/execute", response_model=ResponseBase)
async def execute_code(
    request: CodeExecutionRequest,
    current_user: User = Depends(get_current_user)
):
    """Execute Python code safely in a sandboxed environment"""
    
    logger.info(f"🚀 CODE_EXECUTION: User {current_user.id} executing code")
    logger.info(f"💻 CODE_EXECUTION: Language: {request.language}")
    logger.info(f"📝 CODE_EXECUTION: Code length: {len(request.code)} characters")
    
    try:
        # Currently only support Python
        if request.language.lower() != "python":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only Python code execution is currently supported"
            )
        
        # Validate code is not empty
        if not request.code.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code cannot be empty"
            )
        
        # Execute the code
        logger.info("⚡ CODE_EXECUTION: Calling code_execution_service.execute_code...")
        result = await code_execution_service.execute_code(
            code=request.code,
            mock_inputs=request.mock_inputs
        )
        
        logger.info(f"✅ CODE_EXECUTION: Execution completed - Success: {result.success}")
        if result.success:
            logger.info(f"📤 CODE_EXECUTION: Output: {result.output[:100]}...")
        else:
            logger.error(f"❌ CODE_EXECUTION: Error: {result.error}")
        
        # Create response
        execution_response = CodeExecutionResponse(
            output=result.output,
            error=result.error,
            execution_time=result.execution_time,
            success=result.success,
            timestamp=result.timestamp.isoformat()
        )
        
        return ResponseBase(
            success=True,
            message="Code executed successfully" if result.success else "Code execution completed with errors",
            data=execution_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"💥 CODE_EXECUTION: Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Code execution service error"
        )


@router.get("/stats", response_model=ResponseBase)
async def get_execution_stats(
    current_user: User = Depends(get_current_user)
):
    """Get code execution service statistics"""
    
    try:
        stats = code_execution_service.get_execution_stats()
        
        return ResponseBase(
            success=True,
            message="Execution stats retrieved successfully",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Error getting execution stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve execution stats"
        )


@router.get("/supported-languages", response_model=ResponseBase)
async def get_supported_languages():
    """Get list of supported programming languages"""
    
    supported_languages = [
        {
            "language": "python",
            "display_name": "Python 3",
            "version": "3.x",
            "supported": True,
            "features": [
                "Basic syntax",
                "Variables and data types",
                "Control structures (if, for, while)",
                "Functions",
                "Lists, dictionaries, sets",
                "String manipulation",
                "Basic I/O operations"
            ],
            "limitations": [
                "No file system access",
                "No network operations", 
                "No external libraries",
                "Limited execution time",
                "Simulated input() function"
            ]
        }
    ]
    
    return ResponseBase(
        success=True,
        message="Supported languages retrieved successfully",
        data=supported_languages
    )