from typing import Dict, Any, Optional, List
import os
import hashlib
from pathlib import Path
from datetime import datetime
import aiofiles
import logging

from fastapi import UploadFile
from app.core.config import settings
from app.services.assignment_service import assignment_service
from app.services.ai_markdown_converter import AIMarkdownConverter

logger = logging.getLogger(__name__)


class FileUploadService:
    """Service for handling file uploads and processing for assignments"""
    
    def __init__(self):
        self.upload_path = Path(settings.UPLOAD_PATH)
        self.max_file_size = settings.MAX_UPLOAD_SIZE
        self.allowed_extensions = settings.allowed_extensions_list
        self.ai_converter = AIMarkdownConverter()
        
        # Ensure upload directory exists
        self.upload_path.mkdir(parents=True, exist_ok=True)
    
    def _get_file_hash(self, content: bytes) -> str:
        """Generate SHA-256 hash of file content"""
        return hashlib.sha256(content).hexdigest()
    
    def _is_allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        file_extension = Path(filename).suffix.lower()
        return file_extension in self.allowed_extensions
    
    def _get_safe_filename(self, filename: str, file_hash: str) -> str:
        """Generate safe filename with hash to prevent conflicts"""
        name = Path(filename).stem
        extension = Path(filename).suffix
        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in ('-', '_')).strip()
        return f"{safe_name}_{file_hash[:8]}{extension}"
    
    async def validate_upload(self, file: UploadFile) -> Dict[str, Any]:
        """Validate uploaded file before processing"""
        
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check file extension
        if not self._is_allowed_file(file.filename):
            validation_result["valid"] = False
            validation_result["errors"].append(
                f"File type not allowed. Allowed extensions: {', '.join(self.allowed_extensions)}"
            )
        
        # Check file size
        if file.size and file.size > self.max_file_size:
            validation_result["valid"] = False
            validation_result["errors"].append(
                f"File too large. Maximum size: {self.max_file_size / (1024*1024):.1f}MB"
            )
        
        # Check if filename is provided
        if not file.filename:
            validation_result["valid"] = False
            validation_result["errors"].append("No filename provided")
        
        return validation_result
    
    async def save_uploaded_file(
        self,
        file: UploadFile,
        subfolder: str = "assignments"
    ) -> Dict[str, Any]:
        """Save uploaded file to disk"""
        
        try:
            # Read file content
            content = await file.read()
            
            # Generate file hash
            file_hash = self._get_file_hash(content)
            
            # Create safe filename
            safe_filename = self._get_safe_filename(file.filename, file_hash)
            
            # Create subfolder path
            folder_path = self.upload_path / subfolder
            folder_path.mkdir(parents=True, exist_ok=True)
            
            # Full file path
            file_path = folder_path / safe_filename
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            file_info = {
                "original_filename": file.filename,
                "saved_filename": safe_filename,
                "file_path": str(file_path),
                "file_size": len(content),
                "file_hash": file_hash,
                "content_type": file.content_type,
                "uploaded_at": datetime.utcnow(),
                "subfolder": subfolder
            }
            
            logger.info(f"File uploaded successfully: {file.filename} -> {safe_filename}")
            return file_info
            
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {e}")
            raise ValueError(f"Failed to save file: {str(e)}")
    
    async def process_assignment_file(
        self,
        file: UploadFile,
        title: str,
        instructor_id: str = None
    ) -> Dict[str, Any]:
        """Process uploaded file and create assignment"""
        
        # Validate file
        validation = await self.validate_upload(file)
        if not validation["valid"]:
            raise ValueError(f"File validation failed: {', '.join(validation['errors'])}")
        
        # Save file
        file_info = await self.save_uploaded_file(file, subfolder="assignments")
        
        try:
            # Read file content for processing
            async with aiofiles.open(file_info["file_path"], 'r', encoding='utf-8') as f:
                content = await f.read()
            
            # Determine file type and process accordingly
            file_extension = Path(file.filename).suffix.lower()
            assignment_title = title
            
            if file_extension == '.md':
                # Try AI-powered parsing first, fallback to basic parsing
                try:
                    logger.info("Attempting AI-powered markdown parsing")
                    ai_parsed_data = await self.ai_converter.convert_markdown_to_assignment(
                        markdown_content=content,
                        title=assignment_title,
                        fallback_to_basic=True
                    )
                    
                    assignment = await assignment_service.create_assignment(
                        title=assignment_title,
                        description=ai_parsed_data.get("description"),
                        curriculum_content=ai_parsed_data.get("curriculum_content", ""),
                        problems=ai_parsed_data.get("problems", []),
                        tags=ai_parsed_data.get("tags", []),
                        instructor_id=instructor_id
                    )
                    logger.info("Successfully used AI-powered parsing")
                    
                except Exception as ai_error:
                    logger.warning(f"AI parsing failed, falling back to basic parsing: {ai_error}")
                    assignment = await assignment_service.create_assignment_from_markdown(
                        title=assignment_title,
                        markdown_content=content,
                        instructor_id=instructor_id
                    )
            
            elif file_extension == '.json':
                assignment = await assignment_service.create_assignment_from_json(
                    json_content=content,
                    instructor_id=instructor_id
                )
            
            elif file_extension in ['.yml', '.yaml']:
                assignment = await assignment_service.create_assignment_from_yaml(
                    yaml_content=content,
                    instructor_id=instructor_id
                )
            
            elif file_extension == '.txt':
                # Treat as markdown
                assignment = await assignment_service.create_assignment_from_markdown(
                    title=assignment_title,
                    markdown_content=content,
                    instructor_id=instructor_id
                )
            
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            result = {
                "success": True,
                "assignment_id": str(assignment.id),
                "assignment_title": assignment.title,
                "total_problems": assignment.total_problems,
                "file_info": file_info,
                "processing_details": {
                    "file_type": file_extension,
                    "content_length": len(content),
                    "problems_extracted": assignment.total_problems
                }
            }
            
            logger.info(f"Assignment created from file: {assignment.title} ({assignment.total_problems} problems)")
            return result
            
        except Exception as e:
            # Clean up file if processing failed
            try:
                os.unlink(file_info["file_path"])
            except:
                pass
            
            logger.error(f"Failed to process assignment file: {e}")
            raise ValueError(f"Failed to process assignment: {str(e)}")
    
    async def get_file_content(self, file_path: str) -> str:
        """Get content of uploaded file"""
        
        full_path = self.upload_path / file_path
        
        if not full_path.exists():
            raise ValueError("File not found")
        
        try:
            async with aiofiles.open(full_path, 'r', encoding='utf-8') as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Failed to read file content: {e}")
            raise ValueError(f"Failed to read file: {str(e)}")
    
    async def delete_uploaded_file(self, file_path: str) -> bool:
        """Delete uploaded file"""
        
        full_path = self.upload_path / file_path
        
        if not full_path.exists():
            return False
        
        try:
            os.unlink(full_path)
            logger.info(f"Deleted uploaded file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
    
    def get_upload_stats(self) -> Dict[str, Any]:
        """Get upload statistics"""
        
        try:
            total_files = 0
            total_size = 0
            file_types = {}
            
            for root, dirs, files in os.walk(self.upload_path):
                for file in files:
                    file_path = Path(root) / file
                    try:
                        file_stat = file_path.stat()
                        total_files += 1
                        total_size += file_stat.st_size
                        
                        file_ext = file_path.suffix.lower()
                        file_types[file_ext] = file_types.get(file_ext, 0) + 1
                        
                    except:
                        continue
            
            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "file_types": file_types,
                "upload_path": str(self.upload_path),
                "max_file_size_mb": self.max_file_size / (1024 * 1024),
                "allowed_extensions": self.allowed_extensions
            }
            
        except Exception as e:
            logger.error(f"Failed to get upload stats: {e}")
            return {"error": str(e)}
    
    async def cleanup_old_files(self, days_old: int = 30) -> int:
        """Clean up files older than specified days"""
        
        cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        deleted_count = 0
        
        try:
            for root, dirs, files in os.walk(self.upload_path):
                for file in files:
                    file_path = Path(root) / file
                    try:
                        if file_path.stat().st_mtime < cutoff_time:
                            os.unlink(file_path)
                            deleted_count += 1
                    except:
                        continue
            
            logger.info(f"Cleaned up {deleted_count} old files (>{days_old} days)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return 0
    
    async def validate_assignment_format(self, content: str, file_type: str) -> Dict[str, Any]:
        """Validate assignment file format before processing"""
        
        validation = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "preview": {}
        }
        
        try:
            if file_type == '.md':
                # Basic markdown validation
                lines = content.split('\n')
                problem_count = len([line for line in lines if line.strip().lower().startswith('# problem') or line.strip().lower().startswith('## problem')])
                
                validation["preview"] = {
                    "detected_problems": problem_count,
                    "total_lines": len(lines),
                    "has_problems": problem_count > 0
                }
                
                if problem_count == 0:
                    validation["warnings"].append("No problems detected in markdown file")
            
            elif file_type == '.json':
                import json
                data = json.loads(content)
                
                validation["preview"] = {
                    "has_title": "title" in data,
                    "has_problems": "problems" in data and len(data.get("problems", [])) > 0,
                    "problem_count": len(data.get("problems", [])),
                    "has_description": "description" in data
                }
                
                if not data.get("problems"):
                    validation["warnings"].append("No problems found in JSON structure")
            
            elif file_type in ['.yml', '.yaml']:
                import yaml
                data = yaml.safe_load(content)
                
                validation["preview"] = {
                    "has_title": "title" in data,
                    "has_problems": "problems" in data and len(data.get("problems", [])) > 0,
                    "problem_count": len(data.get("problems", [])),
                    "has_description": "description" in data
                }
                
                if not data.get("problems"):
                    validation["warnings"].append("No problems found in YAML structure")
            
        except Exception as e:
            validation["valid"] = False
            validation["errors"].append(f"Failed to parse {file_type} content: {str(e)}")
        
        return validation


# Global instance
file_upload_service = FileUploadService()