from typing import Dict, Any, List, Optional, Tuple
import json
import logging
import asyncio
from datetime import datetime

from app.services.openai_client import openai_client
from app.models import ConversationMessage, MessageType
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIMarkdownConverter:
    """AI-powered markdown conversion service that intelligently parses any markdown format"""
    
    def __init__(self):
        self.conversion_stats = {
            "total_conversions": 0,
            "successful_conversions": 0,
            "failed_conversions": 0,
            "average_processing_time": 0.0,
            "tokens_used": 0
        }
    
    async def convert_markdown_to_assignment(
        self,
        markdown_content: str,
        title: Optional[str] = None,
        fallback_to_basic: bool = True
    ) -> Dict[str, Any]:
        """
        Convert any markdown format to structured assignment data using AI analysis
        
        Args:
            markdown_content: Raw markdown content
            title: Optional title override
            fallback_to_basic: Whether to fallback to basic parsing if AI fails
            
        Returns:
            Structured assignment data with problems, curriculum content, etc.
        """
        start_time = datetime.now()
        conversion_id = f"conv_{int(start_time.timestamp())}"
        
        logger.info(f"Starting AI markdown conversion {conversion_id}")
        
        try:
            self.conversion_stats["total_conversions"] += 1
            
            # Step 1: Analyze structure and identify sections
            structure_analysis = await self._analyze_markdown_structure(markdown_content)
            
            if not structure_analysis["success"]:
                logger.warning(f"Structure analysis failed for {conversion_id}, trying fallback")
                if fallback_to_basic:
                    return await self._fallback_conversion(markdown_content, title)
                raise ValueError("Failed to analyze markdown structure")
            
            # Step 2: Extract curriculum content vs problems
            content_extraction = await self._extract_content_sections(
                markdown_content, 
                structure_analysis["data"]
            )
            
            if not content_extraction["success"]:
                logger.warning(f"Content extraction failed for {conversion_id}, trying fallback")
                if fallback_to_basic:
                    return await self._fallback_conversion(markdown_content, title)
                raise ValueError("Failed to extract content sections")
            
            # Step 3: Process and enhance problems
            problems = await self._process_and_enhance_problems(
                content_extraction["data"]["problems"]
            )
            
            # Step 4: Generate metadata and tags
            metadata = await self._generate_assignment_metadata(
                markdown_content,
                content_extraction["data"]["curriculum_content"],
                problems
            )
            
            # Compile final result
            result = {
                "title": title or metadata.get("suggested_title", "AI Generated Assignment"),
                "description": metadata.get("description", ""),
                "curriculum_content": content_extraction["data"]["curriculum_content"],
                "problems": problems,
                "tags": metadata.get("tags", []),
                "estimated_duration_minutes": metadata.get("estimated_duration", None),
                "ai_conversion_metadata": {
                    "conversion_id": conversion_id,
                    "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                    "ai_enhanced": True,
                    "structure_confidence": structure_analysis["data"].get("confidence", 0.0),
                    "problems_enhanced": len(problems),
                    "fallback_used": False
                }
            }
            
            # Update stats
            self.conversion_stats["successful_conversions"] += 1
            self._update_processing_time(start_time)
            
            logger.info(f"AI conversion {conversion_id} completed successfully with {len(problems)} problems")
            return result
            
        except Exception as e:
            self.conversion_stats["failed_conversions"] += 1
            logger.error(f"AI conversion {conversion_id} failed: {e}")
            
            if fallback_to_basic:
                logger.info(f"Attempting fallback conversion for {conversion_id}")
                fallback_result = await self._fallback_conversion(markdown_content, title)
                fallback_result["ai_conversion_metadata"] = {
                    "conversion_id": conversion_id,
                    "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
                    "ai_enhanced": False,
                    "fallback_used": True,
                    "error": str(e)
                }
                return fallback_result
            
            raise ValueError(f"AI markdown conversion failed: {str(e)}")
    
    async def _analyze_markdown_structure(self, markdown_content: str) -> Dict[str, Any]:
        """Analyze the structure of markdown content to identify sections"""
        
        system_prompt = """You are an expert at analyzing educational content in markdown format. 
        Your task is to analyze the structure of markdown content and identify:
        
        1. Main sections (curriculum/theory vs problems/exercises)
        2. Problem boundaries and numbering
        3. Content organization patterns
        4. Confidence level in the analysis
        
        Return your analysis as a JSON object with this structure:
        {
            "sections": [
                {
                    "type": "curriculum|problem|metadata",
                    "start_line": int,
                    "end_line": int,
                    "title": "string",
                    "confidence": float
                }
            ],
            "problems_detected": int,
            "structure_type": "well_structured|semi_structured|unstructured",
            "confidence": float,
            "notes": "string"
        }
        
        Be precise and analytical."""
        
        user_prompt = f"""Please analyze this markdown content structure:

```markdown
{markdown_content}
```

Identify all major sections, problem boundaries, and provide a confidence assessment."""
        
        messages = [
            ConversationMessage(
                message_type=MessageType.USER,
                content=user_prompt,
                timestamp=datetime.utcnow()
            )
        ]
        
        response = await openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.1,  # Low temperature for analytical tasks
            max_tokens=2000
        )
        
        if not response["success"]:
            return {"success": False, "error": response.get("message", "Unknown error")}
        
        try:
            # Extract JSON from response
            analysis_data = self._extract_json_from_response(response["content"])
            return {
                "success": True,
                "data": analysis_data,
                "tokens_used": response["usage"]["total_tokens"]
            }
        except Exception as e:
            logger.error(f"Failed to parse structure analysis response: {e}")
            return {"success": False, "error": f"Failed to parse analysis: {str(e)}"}
    
    async def _extract_content_sections(
        self, 
        markdown_content: str, 
        structure_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract and separate curriculum content from problems"""
        
        system_prompt = """You are an expert at extracting educational content from markdown. 
        Your task is to separate curriculum/theory content from problem/exercise content.
        
        For problems, you must be INTELLIGENT about extraction:
        1. **Problem Description**: Extract the main problem statement. If there's a "Problem Statement" section, use that. If not, intelligently identify what the problem is asking for from the context.
        2. **Sample Input/Output**: Extract these if clearly marked
        3. **Explanation**: Extract if present, or if there's explanatory text about the solution/approach
        4. **Title**: Extract from numbered items like "1. **Title**" or create a descriptive title based on the problem
        
        IMPORTANT: Be smart about content identification. Don't leave description empty - always extract or infer what the problem is asking for.
        
        Return a JSON object with this structure:
        {
            "curriculum_content": "string - all curriculum/theory content formatted as markdown",
            "problems": [
                {
                    "raw_content": "string - complete raw markdown for this problem including all sections",
                    "number": int,
                    "title": "string - extracted or intelligently generated title",
                    "description": "string - ALWAYS filled: main problem statement/description, intelligently extracted from content",
                    "sample_input": "string - sample input if present, null otherwise",
                    "sample_output": "string - sample output if present, null otherwise", 
                    "explanation": "string - explanation if present or can be inferred, null otherwise"
                }
            ],
            "extraction_notes": "string"
        }
        
        Remember: NEVER leave description empty. Always extract the core problem requirement from the content."""
        
        structure_info = json.dumps(structure_analysis, indent=2)
        
        user_prompt = f"""Based on this structure analysis:

{structure_info}

Please extract and separate the curriculum content from problems in this markdown:

```markdown
{markdown_content}
```

Separate curriculum content (theory, background, explanations) from problems/exercises."""
        
        messages = [
            ConversationMessage(
                message_type=MessageType.USER,
                content=user_prompt,
                timestamp=datetime.utcnow()
            )
        ]
        
        response = await openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=3000
        )
        
        if not response["success"]:
            return {"success": False, "error": response.get("message", "Unknown error")}
        
        try:
            extraction_data = self._extract_json_from_response(response["content"])
            self.conversion_stats["tokens_used"] += response["usage"]["total_tokens"]
            return {
                "success": True,
                "data": extraction_data,
                "tokens_used": response["usage"]["total_tokens"]
            }
        except Exception as e:
            logger.error(f"Failed to parse content extraction response: {e}")
            return {"success": False, "error": f"Failed to parse extraction: {str(e)}"}
    
    async def _process_and_enhance_problems(self, raw_problems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and enhance problems with AI-generated metadata"""
        
        enhanced_problems = []
        
        for i, problem in enumerate(raw_problems):
            try:
                enhanced_problem = await self._enhance_single_problem(problem, i + 1)
                enhanced_problems.append(enhanced_problem)
            except Exception as e:
                logger.warning(f"Failed to enhance problem {i + 1}: {e}")
                # Use basic enhancement as fallback
                basic_problem = self._basic_problem_enhancement(problem, i + 1)
                enhanced_problems.append(basic_problem)
        
        return enhanced_problems
    
    async def _enhance_single_problem(self, problem: Dict[str, Any], problem_number: int) -> Dict[str, Any]:
        """Enhance a single problem with AI-generated hints, difficulty, and concepts"""
        
        system_prompt = """You are an expert programming educator. Given a programming problem, 
        enhance it with educational metadata while being INTELLIGENT about content processing.
        
        CRITICAL REQUIREMENTS:
        1. **Description**: If empty or missing, INTELLIGENTLY extract/generate the main problem description from the raw content
        2. **Explanation**: If empty but can be inferred from the problem context, generate a helpful explanation
        3. **Sample Input/Output**: Preserve exactly as provided if present
        4. **Enhancement**: Always add educational value through hints, concepts, and difficulty assessment
        
        Return a JSON object with this structure:
        {
            "number": int,
            "title": "string",
            "description": "string - NEVER empty: main problem statement, extracted or intelligently generated",
            "sample_input": "string - preserve original sample input if present, null otherwise",
            "sample_output": "string - preserve original sample output if present, null otherwise",
            "explanation": "string - preserve original OR generate if helpful for understanding, null if truly not applicable",
            "difficulty": "easy|medium|hard",
            "concepts": ["concept1", "concept2", ...],
            "hints": ["hint1", "hint2", ...],
            "starter_code": "string or null",
            "solution_template": "string or null",
            "test_cases": [
                {
                    "input": "string",
                    "expected_output": "string",
                    "description": "string"
                }
            ],
            "estimated_minutes": int
        }
        
        INTELLIGENCE RULES:
        - If description is empty, extract the core requirement from raw_content
        - If explanation is missing but the problem approach is clear, generate a helpful explanation
        - Always provide educational value through proper hints and concepts
        - Generate 2-4 progressive hints, identify 2-5 key concepts, and assess difficulty accurately."""
        
        user_prompt = f"""Please enhance this programming problem:

Problem {problem_number}:
Title: {problem.get('title', f'Problem {problem_number}')}

Description: {problem.get('description', '')}

Sample Input: {problem.get('sample_input', 'Not provided')}

Sample Output: {problem.get('sample_output', 'Not provided')}

Explanation: {problem.get('explanation', 'Not provided')}

Raw Content (for context):
{problem.get('raw_content', '')}

Generate appropriate hints, difficulty level, concepts, and test cases while preserving all original sections."""
        
        messages = [
            ConversationMessage(
                message_type=MessageType.USER,
                content=user_prompt,
                timestamp=datetime.utcnow()
            )
        ]
        
        response = await openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1500
        )
        
        if not response["success"]:
            raise ValueError(f"Failed to enhance problem: {response.get('message')}")
        
        try:
            enhanced_data = self._extract_json_from_response(response["content"])
            self.conversion_stats["tokens_used"] += response["usage"]["total_tokens"]
            return enhanced_data
        except Exception as e:
            raise ValueError(f"Failed to parse enhanced problem data: {str(e)}")
    
    async def _generate_assignment_metadata(
        self, 
        full_content: str, 
        curriculum_content: str, 
        problems: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate assignment-level metadata using AI"""
        
        system_prompt = """You are an educational content analyzer. Generate metadata for a programming assignment.
        
        Return a JSON object with this structure:
        {
            "suggested_title": "string",
            "description": "string - brief description of the assignment",
            "tags": ["tag1", "tag2", ...],
            "estimated_duration": int,  // in minutes
            "difficulty_level": "beginner|intermediate|advanced",
            "topics_covered": ["topic1", "topic2", ...],
            "learning_objectives": ["objective1", "objective2", ...]
        }
        
        Be concise and educational."""
        
        problem_summary = f"Problems included: {len(problems)} problems covering {', '.join(set(concept for p in problems for concept in p.get('concepts', []))[:10])}"
        
        user_prompt = f"""Analyze this programming assignment and generate metadata:

Curriculum Content:
{curriculum_content[:1000]}...

{problem_summary}

Generate appropriate title, description, tags, and duration estimate."""
        
        messages = [
            ConversationMessage(
                message_type=MessageType.USER,
                content=user_prompt,
                timestamp=datetime.utcnow()
            )
        ]
        
        response = await openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=800
        )
        
        if not response["success"]:
            logger.warning("Failed to generate assignment metadata, using defaults")
            return self._default_metadata(problems)
        
        try:
            metadata = self._extract_json_from_response(response["content"])
            self.conversion_stats["tokens_used"] += response["usage"]["total_tokens"]
            return metadata
        except Exception as e:
            logger.warning(f"Failed to parse metadata response: {e}")
            return self._default_metadata(problems)
    
    async def _fallback_conversion(self, markdown_content: str, title: Optional[str]) -> Dict[str, Any]:
        """Fallback to basic markdown parsing when AI conversion fails"""
        
        logger.info("Using fallback basic markdown conversion")
        
        # Import the basic parser from assignment service
        from app.services.assignment_service import AssignmentService
        service = AssignmentService()
        
        try:
            basic_result = service._parse_markdown_assignment(markdown_content)
            
            return {
                "title": title or "Assignment from Markdown",
                "description": basic_result.get("description", ""),
                "curriculum_content": basic_result.get("curriculum_content", markdown_content),
                "problems": basic_result.get("problems", []),
                "tags": basic_result.get("tags", []),
                "estimated_duration_minutes": None
            }
        except Exception as e:
            logger.error(f"Even fallback conversion failed: {e}")
            # Last resort: treat entire content as curriculum
            return {
                "title": title or "Assignment from Markdown",
                "description": "Assignment created from markdown content",
                "curriculum_content": markdown_content,
                "problems": [],
                "tags": ["markdown", "imported"],
                "estimated_duration_minutes": None
            }
    
    def _extract_json_from_response(self, response_content: str) -> Dict[str, Any]:
        """Extract JSON from AI response content"""
        
        # Try to find JSON block
        import re
        
        # Look for JSON code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object in the response
            json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("No JSON found in response")
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Attempted to parse: {json_str[:500]}...")
            raise ValueError(f"Invalid JSON in response: {str(e)}")
    
    def _basic_problem_enhancement(self, problem: Dict[str, Any], problem_number: int) -> Dict[str, Any]:
        """Basic problem enhancement without AI"""
        
        return {
            "number": problem_number,
            "title": problem.get("title", f"Problem {problem_number}"),
            "description": problem.get("description", problem.get("raw_content", "")),
            "difficulty": "medium",
            "concepts": [],
            "hints": [],
            "starter_code": None,
            "solution_template": None,
            "test_cases": [],
            "estimated_minutes": 30
        }
    
    def _default_metadata(self, problems: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate default metadata when AI generation fails"""
        
        return {
            "suggested_title": "Programming Assignment",
            "description": f"Assignment with {len(problems)} programming problems",
            "tags": ["programming", "assignment"],
            "estimated_duration": len(problems) * 30,  # 30 minutes per problem
            "difficulty_level": "intermediate",
            "topics_covered": ["programming"],
            "learning_objectives": ["Practice programming skills"]
        }
    
    def _update_processing_time(self, start_time: datetime):
        """Update average processing time statistics"""
        
        processing_time = (datetime.now() - start_time).total_seconds()
        current_avg = self.conversion_stats["average_processing_time"]
        total_conversions = self.conversion_stats["total_conversions"]
        
        # Calculate new average
        new_avg = ((current_avg * (total_conversions - 1)) + processing_time) / total_conversions
        self.conversion_stats["average_processing_time"] = new_avg
    
    def get_conversion_stats(self) -> Dict[str, Any]:
        """Get conversion statistics"""
        
        stats = self.conversion_stats.copy()
        stats["success_rate"] = (
            (stats["successful_conversions"] / stats["total_conversions"] * 100) 
            if stats["total_conversions"] > 0 else 0
        )
        return stats
    
    async def validate_markdown_before_conversion(self, markdown_content: str) -> Dict[str, Any]:
        """Pre-validate markdown content before attempting conversion"""
        
        validation = {
            "valid": True,
            "warnings": [],
            "recommendations": [],
            "estimated_complexity": "medium"
        }
        
        # Basic validation checks
        lines = markdown_content.split('\n')
        word_count = len(markdown_content.split())
        
        if word_count < 50:
            validation["warnings"].append("Very short content - may not contain sufficient information")
        
        if word_count > 10000:
            validation["warnings"].append("Very long content - conversion may take significant time")
            validation["estimated_complexity"] = "high"
        
        # Check for problem patterns
        problem_patterns = [
            r'#+\s*problem\s*\d+',
            r'#+\s*exercise\s*\d+',
            r'#+\s*question\s*\d+',
            r'\d+\.\s+',
        ]
        
        problem_indicators = 0
        for pattern in problem_patterns:
            matches = re.findall(pattern, markdown_content, re.IGNORECASE)
            problem_indicators += len(matches)
        
        if problem_indicators == 0:
            validation["warnings"].append("No clear problem structure detected - AI will attempt to identify sections")
        
        # Check for code blocks
        code_blocks = len(re.findall(r'```', markdown_content))
        if code_blocks > 0:
            validation["recommendations"].append("Code blocks detected - good for programming assignments")
        
        return validation


# Global instance
ai_markdown_converter = AIMarkdownConverter()