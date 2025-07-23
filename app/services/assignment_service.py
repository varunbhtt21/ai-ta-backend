from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId
import logging
import re
import json
import yaml
import markdown

from app.database.connection import get_database
from app.models import Assignment, Problem
from app.core.config import settings

logger = logging.getLogger(__name__)


class AssignmentService:
    """Service for managing programming assignments and curriculum content"""
    
    def __init__(self):
        self.db = None
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    async def create_assignment(
        self,
        title: str,
        description: Optional[str] = None,
        curriculum_content: str = "",
        problems: List[Dict[str, Any]] = None,
        tags: List[str] = None,
        instructor_id: str = None
    ) -> Assignment:
        """Create a new programming assignment"""
        
        db = await self._get_db()
        
        # Convert problem dictionaries to Problem objects
        problem_objects = []
        if problems:
            for i, problem_data in enumerate(problems):
                problem = Problem(
                    number=problem_data.get("number", i + 1),
                    title=problem_data.get("title", f"Problem {i + 1}"),
                    description=problem_data.get("description", ""),
                    difficulty=problem_data.get("difficulty", "medium"),
                    concepts=problem_data.get("concepts", []),
                    starter_code=problem_data.get("starter_code"),
                    solution_template=problem_data.get("solution_template"),
                    test_cases=problem_data.get("test_cases", []),
                    hints=problem_data.get("hints", [])
                )
                problem_objects.append(problem)
        
        assignment = Assignment(
            title=title,
            description=description,
            curriculum_content=curriculum_content,
            problems=problem_objects,
            total_problems=len(problem_objects),
            tags=tags or [],
            is_active=True
        )
        
        # Add instructor metadata if provided
        if instructor_id:
            assignment.metadata = {"instructor_id": instructor_id}
        
        result = await db.assignments.insert_one(assignment.dict(by_alias=True))
        assignment.id = result.inserted_id
        
        logger.info(f"Created assignment '{title}' with {len(problem_objects)} problems")
        return assignment
    
    async def get_assignment(self, assignment_id: str) -> Optional[Assignment]:
        """Get assignment by ID"""
        
        db = await self._get_db()
        assignment_data = await db.assignments.find_one({"_id": ObjectId(assignment_id)})
        
        if assignment_data:
            return Assignment.model_validate(assignment_data)
        return None
    
    async def list_assignments(
        self,
        active_only: bool = True,
        tags: Optional[List[str]] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Assignment]:
        """List assignments with optional filtering"""
        
        db = await self._get_db()
        
        query = {}
        if active_only:
            query["is_active"] = True
        if tags:
            query["tags"] = {"$in": tags}
        
        cursor = db.assignments.find(query).skip(skip).limit(limit).sort("created_at", -1)
        assignments = []
        
        async for assignment_data in cursor:
            assignments.append(Assignment.model_validate(assignment_data))
        
        return assignments
    
    async def update_assignment(
        self,
        assignment_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update assignment data"""
        
        db = await self._get_db()
        
        # Handle problem updates
        if "problems" in updates:
            problem_objects = []
            for i, problem_data in enumerate(updates["problems"]):
                if isinstance(problem_data, dict):
                    problem = Problem.model_validate(problem_data)
                    problem_objects.append(problem.dict())
                else:
                    problem_objects.append(problem_data)
            updates["problems"] = problem_objects
            updates["total_problems"] = len(problem_objects)
        
        updates["updated_at"] = datetime.utcnow()
        
        result = await db.assignments.update_one(
            {"_id": ObjectId(assignment_id)},
            {"$set": updates}
        )
        
        return result.modified_count > 0
    
    async def delete_assignment(self, assignment_id: str) -> bool:
        """Soft delete assignment (mark as inactive)"""
        
        db = await self._get_db()
        
        result = await db.assignments.update_one(
            {"_id": ObjectId(assignment_id)},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0
    
    async def create_assignment_from_markdown(
        self,
        title: str,
        markdown_content: str,
        instructor_id: str = None
    ) -> Assignment:
        """Parse markdown content and create assignment"""
        
        try:
            # Parse markdown content
            parsed_data = self._parse_markdown_assignment(markdown_content)
            
            return await self.create_assignment(
                title=title,
                description=parsed_data.get("description"),
                curriculum_content=parsed_data.get("curriculum_content", markdown_content),
                problems=parsed_data.get("problems", []),
                tags=parsed_data.get("tags", []),
                instructor_id=instructor_id
            )
            
        except Exception as e:
            logger.error(f"Failed to parse markdown assignment: {e}")
            raise ValueError(f"Invalid markdown format: {str(e)}")
    
    async def create_assignment_from_json(
        self,
        json_content: str,
        instructor_id: str = None
    ) -> Assignment:
        """Parse JSON content and create assignment"""
        
        try:
            data = json.loads(json_content)
            
            return await self.create_assignment(
                title=data.get("title", "Untitled Assignment"),
                description=data.get("description"),
                curriculum_content=data.get("curriculum_content", ""),
                problems=data.get("problems", []),
                tags=data.get("tags", []),
                instructor_id=instructor_id
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {e}")
            raise ValueError(f"Invalid JSON format: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to create assignment from JSON: {e}")
            raise ValueError(f"Assignment creation failed: {str(e)}")
    
    async def create_assignment_from_yaml(
        self,
        yaml_content: str,
        instructor_id: str = None
    ) -> Assignment:
        """Parse YAML content and create assignment"""
        
        try:
            data = yaml.safe_load(yaml_content)
            
            return await self.create_assignment(
                title=data.get("title", "Untitled Assignment"),
                description=data.get("description"),
                curriculum_content=data.get("curriculum_content", ""),
                problems=data.get("problems", []),
                tags=data.get("tags", []),
                instructor_id=instructor_id
            )
            
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML format: {e}")
            raise ValueError(f"Invalid YAML format: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to create assignment from YAML: {e}")
            raise ValueError(f"Assignment creation failed: {str(e)}")
    
    def _parse_markdown_assignment(self, markdown_content: str) -> Dict[str, Any]:
        """Parse markdown content into assignment structure"""
        
        lines = markdown_content.split('\n')
        
        result = {
            "description": "",
            "curriculum_content": "",
            "problems": [],
            "tags": []
        }
        
        current_problem = None
        current_section = "curriculum"
        curriculum_lines = []
        
        for line in lines:
            original_line = line
            line = line.strip()
            
            # Check for problem headers (## Problem 1, # Problem 2, etc.)
            problem_match = re.match(r'^#+\s*Problem\s*(\d+)[:\s]*(.*)$', line, re.IGNORECASE)
            if problem_match:
                # Finalize curriculum content before starting problems
                if current_section == "curriculum":
                    result["curriculum_content"] = '\n'.join(curriculum_lines).strip()
                
                # Save previous problem
                if current_problem:
                    result["problems"].append(current_problem)
                
                # Start new problem
                problem_number = int(problem_match.group(1))
                problem_title = problem_match.group(2).strip() or f"Problem {problem_number}"
                
                current_problem = {
                    "number": problem_number,
                    "title": problem_title,
                    "description": "",
                    "difficulty": "medium",
                    "concepts": [],
                    "hints": [],
                    "test_cases": []
                }
                current_section = "problem_description"
                continue
            
            # Check for section headers within problems
            if current_problem:
                if re.match(r'^#+\s*(Description|Instructions)', line, re.IGNORECASE):
                    current_section = "problem_description"
                    continue
                elif re.match(r'^#+\s*(Hints?|Help)', line, re.IGNORECASE):
                    current_section = "hints"
                    continue
                elif re.match(r'^#+\s*(Test Cases?|Examples?)', line, re.IGNORECASE):
                    current_section = "test_cases"
                    continue
                elif re.match(r'^#+\s*(Concepts?|Topics?)', line, re.IGNORECASE):
                    current_section = "concepts"
                    continue
                elif re.match(r'^#+\s*(Difficulty)', line, re.IGNORECASE):
                    current_section = "difficulty"
                    continue
            
            # Process content based on current section
            if current_section == "curriculum":
                # Add all content before the first problem to curriculum
                curriculum_lines.append(original_line)
            
            elif current_section == "problem_description" and current_problem:
                current_problem["description"] += line + "\n"
            
            elif current_section == "hints" and current_problem:
                # Extract hints (look for bullet points or numbered lists)
                if re.match(r'^[\*\-\d]+\.?\s+', line):
                    hint_text = re.sub(r'^[\*\-\d]+\.?\s+', '', line)
                    current_problem["hints"].append(hint_text)
                elif line:
                    current_problem["hints"].append(line)
            
            elif current_section == "concepts" and current_problem:
                # Extract concepts
                if re.match(r'^[\*\-\d]+\.?\s+', line):
                    concept = re.sub(r'^[\*\-\d]+\.?\s+', '', line)
                    current_problem["concepts"].append(concept)
                elif ',' in line:
                    concepts = [c.strip() for c in line.split(',')]
                    current_problem["concepts"].extend(concepts)
                elif line:
                    current_problem["concepts"].append(line)
            
            elif current_section == "difficulty" and current_problem:
                difficulty_match = re.search(r'(easy|medium|hard)', line, re.IGNORECASE)
                if difficulty_match:
                    current_problem["difficulty"] = difficulty_match.group(1).lower()
            
            elif current_section == "test_cases" and current_problem:
                # Simple test case parsing
                if "input:" in line.lower() or "output:" in line.lower():
                    current_problem["test_cases"].append(line)
        
        # Don't forget the last problem
        if current_problem:
            result["problems"].append(current_problem)
        
        # If we never encountered problems, all content is curriculum
        if current_section == "curriculum":
            result["curriculum_content"] = '\n'.join(curriculum_lines).strip()
        
        # Clean up descriptions and content
        result["description"] = result["description"].strip()
        result["curriculum_content"] = result["curriculum_content"].strip()
        for problem in result["problems"]:
            problem["description"] = problem["description"].strip()
        
        logger.info(f"Parsed {len(result['problems'])} problems from markdown content")
        return result
    
    async def get_assignment_statistics(self, assignment_id: str) -> Dict[str, Any]:
        """Get statistics for an assignment"""
        
        db = await self._get_db()
        
        # Get basic assignment info
        assignment = await self.get_assignment(assignment_id)
        if not assignment:
            raise ValueError("Assignment not found")
        
        # Get student progress statistics
        pipeline = [
            {"$match": {"assignment_id": assignment_id}},
            {
                "$group": {
                    "_id": None,
                    "total_students": {"$addToSet": "$user_id"},
                    "total_attempts": {"$sum": "$attempts"},
                    "completed_problems": {
                        "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                    },
                    "in_progress_problems": {
                        "$sum": {"$cond": [{"$eq": ["$status", "in_progress"]}, 1, 0]}
                    },
                    "avg_time_per_problem": {"$avg": "$time_spent_minutes"}
                }
            }
        ]
        
        progress_stats = await db.student_progress.aggregate(pipeline).to_list(1)
        
        stats = {
            "assignment_id": assignment_id,
            "title": assignment.title,
            "total_problems": assignment.total_problems,
            "total_students": len(progress_stats[0]["total_students"]) if progress_stats else 0,
            "total_attempts": progress_stats[0]["total_attempts"] if progress_stats else 0,
            "completed_problems": progress_stats[0]["completed_problems"] if progress_stats else 0,
            "in_progress_problems": progress_stats[0]["in_progress_problems"] if progress_stats else 0,
            "avg_time_per_problem": progress_stats[0]["avg_time_per_problem"] if progress_stats else 0,
            "completion_rate": 0
        }
        
        if stats["total_students"] > 0 and assignment.total_problems > 0:
            total_possible = stats["total_students"] * assignment.total_problems
            stats["completion_rate"] = (stats["completed_problems"] / total_possible) * 100
        
        return stats
    
    async def search_assignments(
        self,
        query: str,
        tags: Optional[List[str]] = None,
        limit: int = 20
    ) -> List[Assignment]:
        """Search assignments by title, description, or content"""
        
        db = await self._get_db()
        
        search_filter = {
            "is_active": True,
            "$or": [
                {"title": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"curriculum_content": {"$regex": query, "$options": "i"}}
            ]
        }
        
        if tags:
            search_filter["tags"] = {"$in": tags}
        
        cursor = db.assignments.find(search_filter).limit(limit).sort("created_at", -1)
        assignments = []
        
        async for assignment_data in cursor:
            assignments.append(Assignment.model_validate(assignment_data))
        
        return assignments
    
    async def duplicate_assignment(
        self,
        assignment_id: str,
        new_title: str,
        instructor_id: str = None
    ) -> Assignment:
        """Create a copy of an existing assignment"""
        
        original = await self.get_assignment(assignment_id)
        if not original:
            raise ValueError("Original assignment not found")
        
        # Create new assignment with copied data
        return await self.create_assignment(
            title=new_title,
            description=original.description,
            curriculum_content=original.curriculum_content,
            problems=[problem.dict() for problem in original.problems],
            tags=original.tags.copy(),
            instructor_id=instructor_id
        )


# Global instance
assignment_service = AssignmentService()