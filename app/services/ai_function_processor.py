from typing import Dict, Any, List, Optional
import json
import logging
import asyncio
import re
from datetime import datetime
from openai import AsyncOpenAI

from app.core.config import settings
from app.models import ConversationMessage, MessageType

logger = logging.getLogger(__name__)


class AIFunctionProcessor:
    """AI service using OpenAI function calling for structured content processing"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_REQUEST_TIMEOUT
        )
        self.processing_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "tokens_used": 0
        }
    
    async def process_curriculum_content(self, content: str) -> Dict[str, Any]:
        """Process curriculum content using function calling"""
        
        try:
            self.processing_stats["total_calls"] += 1
            
            # Define the function schema for curriculum processing
            curriculum_function = {
                "name": "process_curriculum_content",
                "description": "Process and structure curriculum content for educational use",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "processed_content": {
                            "type": "string",
                            "description": "Clean, well-structured curriculum content with proper markdown formatting"
                        },
                        "title": {
                            "type": "string", 
                            "description": "Extracted or generated title for the curriculum content"
                        },
                        "learning_objectives": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key learning objectives extracted or inferred from the content"
                        },
                        "topics_covered": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Main topics and concepts covered in the curriculum"
                        },
                        "difficulty_level": {
                            "type": "string",
                            "enum": ["beginner", "intermediate", "advanced"],
                            "description": "Assessed difficulty level of the content"
                        },
                        "estimated_reading_time": {
                            "type": "integer",
                            "description": "Estimated reading time in minutes"
                        }
                    },
                    "required": ["processed_content", "title", "learning_objectives", "topics_covered", "difficulty_level"]
                }
            }
            
            # Create the prompt for curriculum processing
            system_prompt = """You are an expert educational content processor. Your task is to analyze curriculum content and structure it properly for educational use.

Instructions:
1. Clean and organize the content with proper markdown formatting
2. Extract or generate a meaningful title
3. Identify key learning objectives
4. List main topics covered
5. Assess the difficulty level
6. Estimate reading time

Ensure the processed content is well-structured and educational."""

            user_prompt = f"""Please process this curriculum content:

```
{content}
```

Structure it properly and extract all educational metadata."""

            # Make the function call
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                functions=[curriculum_function],
                function_call={"name": "process_curriculum_content"},
                temperature=0.3,
                max_tokens=3000
            )
            
            # Extract function call result
            function_call = response.choices[0].message.function_call
            if function_call and function_call.name == "process_curriculum_content":
                result = json.loads(function_call.arguments)
                
                self.processing_stats["successful_calls"] += 1
                self.processing_stats["tokens_used"] += response.usage.total_tokens
                
                return {
                    "success": True,
                    "data": result,
                    "tokens_used": response.usage.total_tokens,
                    "processing_time": datetime.utcnow().isoformat()
                }
            else:
                raise ValueError("Function call failed")
                
        except Exception as e:
            self.processing_stats["failed_calls"] += 1
            logger.error(f"Curriculum processing failed: {e}")
            
            # Fallback to original content
            return {
                "success": False,
                "data": {
                    "processed_content": content,
                    "title": "Curriculum Content",
                    "learning_objectives": [],
                    "topics_covered": [],
                    "difficulty_level": "intermediate",
                    "estimated_reading_time": max(1, len(content.split()) // 200)
                },
                "error": str(e),
                "fallback_used": True
            }
    
    async def process_assignment_problems(self, content: str) -> Dict[str, Any]:
        """Process assignment problems using function calling"""
        
        try:
            self.processing_stats["total_calls"] += 1
            logger.info(f"Processing problems content (length: {len(content)})")
            logger.info(f"Content preview: {content[:500]}...")
            
            # Check content size and truncate if too large
            max_content_length = 15000  # Reasonable limit for OpenAI
            if len(content) > max_content_length:
                logger.warning(f"Content too large ({len(content)} chars), truncating to {max_content_length}")
                content = content[:max_content_length] + "\n\n[Content truncated due to size limit]"
            
            # Define the function schema for problems processing
            problems_function = {
                "name": "extract_assignment_problems",
                "description": "Extract and structure programming problems from assignment content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "problems": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "number": {
                                        "type": "integer",
                                        "description": "Problem number"
                                    },
                                    "title": {
                                        "type": "string",
                                        "description": "Problem title extracted or generated"
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "INSTRUCTION ONLY: What the programmer should code (e.g., 'Write a program to filter even numbers from a list'). MUST NOT contain arrays, numbers, or sample data like [1,2,3,4,5]."
                                    },
                                    "sample_input": {
                                        "type": "string",
                                        "description": "Sample input for the problem (null if not provided)"
                                    },
                                    "sample_output": {
                                        "type": "string", 
                                        "description": "Expected sample output (null if not provided)"
                                    },
                                    "explanation": {
                                        "type": "string",
                                        "description": "Explanation of the problem approach, algorithm, or solution method. ALWAYS provide if the problem has clear steps or methodology."
                                    },
                                    "difficulty": {
                                        "type": "string",
                                        "enum": ["easy", "medium", "hard"],
                                        "description": "Assessed difficulty level"
                                    },
                                    "concepts": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Programming concepts involved (e.g., arrays, loops, filtering, conditionals, functions). ALWAYS provide at least 2-3 relevant concepts."
                                    },
                                    "hints": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Helpful hints for solving the problem"
                                    },
                                    "starter_code": {
                                        "type": "string",
                                        "description": "Optional starter code template for the problem (null if not needed)"
                                    },
                                    "test_cases": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Generate 2-3 test cases with different scenarios (edge cases, normal cases). Always provide meaningful test cases."
                                    },
                                    "estimated_minutes": {
                                        "type": "integer",
                                        "description": "Estimated time to solve in minutes"
                                    }
                                },
                                "required": ["number", "title", "description", "difficulty", "concepts", "hints", "test_cases"]
                            },
                            "description": "List of extracted and enhanced problems"
                        },
                        "total_problems": {
                            "type": "integer",
                            "description": "Total number of problems found"
                        },
                        "extraction_notes": {
                            "type": "string",
                            "description": "Notes about the extraction process"
                        }
                    },
                    "required": ["problems", "total_problems"]
                }
            }
            
            # Create the prompt for problems processing  
            system_prompt = """You are an expert at extracting and enhancing programming problems from educational content.

CRITICAL RULES - MUST FOLLOW EXACTLY:

1. **Description Field Rules - ABSOLUTELY CRITICAL**:
   - NEVER EVER put arrays like [1,2,3,4,5] in description field
   - NEVER put sample data, numbers, or brackets in description
   - ALWAYS write what the programmer should DO as an instruction
   - Examples: "Write a program to...", "Create a function that...", "Implement a solution to..."
   - WRONG: "[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]"
   - RIGHT: "Create a list of numbers from 1 to 20. Write a function that filters out all even numbers and appends them to a new list."

2. **Data Classification - STRICT SEPARATION**:
   - Arrays like [1,2,3,4,5] → sample_input field ONLY
   - Results like [2,4,6,8,10] → sample_output field ONLY  
   - Description = INSTRUCTION (what to code) - NO DATA ALLOWED
   - Sample Input = EXAMPLE DATA (arrays, numbers, strings)
   - Sample Output = EXPECTED RESULT (what the program should produce)

3. **Title-Based Description Generation**:
   - "Filter Even Numbers" → "Create a list of numbers from 1 to 20. Write a function that filters out all even numbers and appends them to a new list. Print the new list of even numbers."
   - "Find Maximum" → "Write a function to find the maximum value in a list"
   - "Calculate Sum" → "Write a program to calculate the sum of all numbers in a list"

4. **VALIDATION CHECK BEFORE RESPONDING**:
   - If description contains brackets [] → INVALID, rewrite as instruction
   - If description contains numbers like 1,2,3,4,5 → INVALID, rewrite as instruction  
   - If description looks like data instead of instruction → INVALID, rewrite as instruction
   - Description must ALWAYS be a human-readable instruction starting with action words

5. **Required Fields**:
   - concepts: ALWAYS provide 3-5 programming concepts (loops, arrays, conditionals, etc.)
   - test_cases: ALWAYS generate 2-3 meaningful test cases (normal case, edge case, boundary case)
   - explanation: ALWAYS provide algorithm/approach explanation unless truly not applicable
   - hints: Can be empty array if not needed

6. **Explanation Requirements**:
   - Explain the algorithm or approach to solve the problem
   - Mention key programming concepts or methods
   - Describe the logic flow or steps involved
   - Examples: "Use a loop to iterate through the list and check each number using modulo operator"

7. **Test Cases Requirements**:
   - Generate realistic test scenarios
   - Include normal cases, edge cases (empty list, single element)
   - Format: "Test with [input] → Expected: [output]"
   - Examples: "Test with empty list → Expected: []", "Test with [1,3,5] → Expected: []"

8. **DOUBLE CHECK RULE**:
   Before finalizing, verify that description field contains ONLY instructions, not data."""

            user_prompt = f"""Extract and enhance all programming problems from this content:

```
{content}
```

EXAMPLES of CORRECT processing:

For "4. Filter Even Numbers" with data [1,2,3,4,5,6,7,8,9,10] → [2,4,6,8,10]:

CORRECT:
- title: "Filter Even Numbers"
- description: "Write a program that takes a list of integers and returns only the even numbers"
- sample_input: "[1,2,3,4,5,6,7,8,9,10]"
- sample_output: "[2,4,6,8,10]"
- concepts: ["arrays", "loops", "conditionals", "filtering"]

WRONG (DO NOT DO THIS):
- description: "[1,2,3,4,5,6,7,8,9,10]" ← THIS IS WRONG! Data goes in sample_input, NOT description

VALIDATION CHECK:
- If description contains [brackets] with numbers → WRONG, rewrite as instruction
- If description looks like data → WRONG, rewrite as "Write a program to..."

Process each problem completely with all details."""

            # Make the function call with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await self.client.chat.completions.create(
                        model=settings.OPENAI_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        functions=[problems_function],
                        function_call={"name": "extract_assignment_problems"},
                        temperature=0.3,
                        max_tokens=4000,
                        timeout=settings.OPENAI_REQUEST_TIMEOUT
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    if "timeout" in str(e).lower() and attempt < max_retries - 1:
                        logger.warning(f"OpenAI timeout on attempt {attempt + 1}, retrying...")
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        raise e  # Re-raise if not timeout or last attempt
            
            # Extract function call result
            function_call = response.choices[0].message.function_call
            if function_call and function_call.name == "extract_assignment_problems":
                result = json.loads(function_call.arguments)
                
                # Post-process validation and fixing
                result = self._validate_and_fix_problems(result)
                
                self.processing_stats["successful_calls"] += 1
                self.processing_stats["tokens_used"] += response.usage.total_tokens
                
                return {
                    "success": True,
                    "data": result,
                    "tokens_used": response.usage.total_tokens,
                    "processing_time": datetime.utcnow().isoformat()
                }
            else:
                raise ValueError("Function call failed")
                
        except Exception as e:
            self.processing_stats["failed_calls"] += 1
            error_message = str(e)
            logger.error(f"Problems processing failed: {error_message}")
            
            # Enhanced fallback for timeout errors
            if "timeout" in error_message.lower():
                logger.info("Attempting fallback processing due to timeout...")
                try:
                    # Try basic parsing as fallback
                    fallback_problems = self._basic_fallback_parsing(content)
                    if fallback_problems:
                        return {
                            "success": True,
                            "data": {
                                "problems": fallback_problems,
                                "total_problems": len(fallback_problems),
                                "extraction_notes": "Used fallback parsing due to timeout"
                            },
                            "fallback_used": True,
                            "processing_method": "fallback_timeout"
                        }
                except Exception as fallback_error:
                    logger.error(f"Fallback parsing also failed: {fallback_error}")
            
            return {
                "success": False,
                "data": {
                    "problems": [],
                    "total_problems": 0,
                    "extraction_notes": "Processing failed"
                },
                "error": error_message,
                "fallback_used": True
            }
    
    def _validate_and_fix_problems(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix common issues in AI-generated problems"""
        
        if "problems" not in result:
            return result
            
        fixed_problems = []
        
        for problem in result["problems"]:
            # Fix description if it contains array data
            description = problem.get("description", "")
            
            # More aggressive detection of array data in descriptions
            has_brackets = "[" in description and "]" in description
            starts_with_bracket = description.strip().startswith("[")
            has_number_sequence = any(str(i) in description for i in range(1, 21))  # Check for 1-20 sequence
            looks_like_array = has_brackets and (has_number_sequence or len(description.split(",")) > 3)
            
            # Check if description looks like data instead of instruction
            if has_brackets or starts_with_bracket or looks_like_array:
                logger.warning(f"Fixing invalid description: {description}")
                
                # Generate proper description from title and context
                title = problem.get("title", "").lower()
                
                # Specific patterns for common problems
                if "filter" in title and "even" in title:
                    description = "Create a list of numbers from 1 to 20. Write a function that filters out all even numbers and appends them to a new list. Print the new list of even numbers."
                elif "create" in title and "list" in title and "input" in title:
                    description = "Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list."
                elif ("maximum" in title and "minimum" in title) or ("max" in title and "min" in title):
                    description = "Given a list of numbers, write a function that finds the maximum and minimum values in the list without using built-in functions like max() or min(). Print both values."
                elif "average" in title or "calculate" in title:
                    description = "Write a function that calculates the average of all numbers in a given list. Do not use the sum() function. Instead, use a loop to calculate the total sum and then divide by the length of the list."
                elif "count" in title and "occurrence" in title:
                    description = "Write a function that takes a list of numbers and a target number as input. Count how many times the target number appears in the list and print the count."
                elif "largest" in title and "second" not in title:
                    description = "Given a list of numbers, write a function that finds the largest number in the list. Do not use sorting functions. Print the largest number."
                elif "replace" in title and "negative" in title:
                    description = "Write a program that takes a list of numbers and replaces all negative numbers with zero. Print the updated list."
                elif "reverse" in title:
                    description = "Write a function that takes a list of numbers and returns a new list with the elements in reverse order. Do not use the reverse() method or slicing. Print the reversed list."
                elif "sum" in title:
                    description = "Write a program to calculate the sum of all numbers in a given list"
                elif "maximum" in title or "max" in title:
                    description = "Write a function to find the maximum value in a list of integers"
                elif "minimum" in title or "min" in title:
                    description = "Write a function to find the minimum value in a list of integers"
                elif "sort" in title:
                    description = "Write a program to sort a list of numbers in ascending order"
                else:
                    # Generic fallback
                    clean_title = problem.get("title", "problem").lower().replace("_", " ").replace("**", "")
                    description = f"Write a program to solve the {clean_title} problem"
                
                problem["description"] = description
                logger.info(f"Fixed description to: {description}")
            
            # Ensure concepts are provided
            if not problem.get("concepts") or len(problem.get("concepts", [])) == 0:
                title = problem.get("title", "").lower()
                concepts = ["programming"]  # Default concept
                
                if "filter" in title or "even" in title:
                    concepts = ["arrays", "loops", "conditionals", "filtering", "modulo operator"]
                elif "sum" in title:
                    concepts = ["arrays", "loops", "arithmetic", "accumulation"]
                elif "max" in title or "min" in title:
                    concepts = ["arrays", "loops", "comparisons", "algorithms"]
                elif "sort" in title:
                    concepts = ["arrays", "sorting algorithms", "comparisons", "loops"]
                
                problem["concepts"] = concepts
                logger.info(f"Added concepts: {concepts}")
            
            # Generate explanation if missing
            if not problem.get("explanation") or problem.get("explanation", "").strip() == "":
                title = problem.get("title", "").lower()
                if "filter" in title and "even" in title:
                    problem["explanation"] = "Use a loop to iterate through the list and check each number using the modulo operator (%). Numbers divisible by 2 are even."
                elif "create" in title and "list" in title and "input" in title:
                    problem["explanation"] = "Use input() function to prompt the user, then append each entered number to the list using the append() method."
                elif ("maximum" in title and "minimum" in title) or ("max" in title and "min" in title):
                    problem["explanation"] = "Iterate through the list keeping track of the largest and smallest values seen so far by comparing each element."
                elif "average" in title or "calculate" in title:
                    problem["explanation"] = "Sum all numbers in the list using a loop, then divide the total by the length of the list to get the average."
                elif "count" in title and "occurrence" in title:
                    problem["explanation"] = "Iterate through the list and increment a counter each time the target number is found."
                elif "reverse" in title:
                    problem["explanation"] = "Create a new list and use a loop to append elements from the original list in reverse order, starting from the last index."
                else:
                    problem["explanation"] = "Break down the problem into steps and use appropriate programming constructs like loops, conditionals, and built-in functions."
                
                logger.info(f"Generated explanation: {problem['explanation']}")
            
            # Generate test cases if missing
            if not problem.get("test_cases") or len(problem.get("test_cases", [])) == 0:
                title = problem.get("title", "").lower()
                test_cases = []
                
                if "filter" in title and "even" in title:
                    test_cases = [
                        "Test with [1,2,3,4,5] → Expected: [2,4]",
                        "Test with [1,3,5,7] → Expected: []",
                        "Test with empty list → Expected: []"
                    ]
                elif "create" in title and "list" in title:
                    test_cases = [
                        "Test with inputs 1,2,3,4,5 → Expected: [1,2,3,4,5]",
                        "Test with negative numbers → Expected: list with negative numbers",
                        "Test with decimal numbers → Expected: list with decimal numbers"
                    ]
                elif "maximum" in title and "minimum" in title:
                    test_cases = [
                        "Test with [1,5,3,9,2] → Expected: Max=9, Min=1",
                        "Test with [5] → Expected: Max=5, Min=5",
                        "Test with negative numbers → Expected: correct max and min"
                    ]
                elif "average" in title:
                    test_cases = [
                        "Test with [1,2,3,4,5] → Expected: 3.0",
                        "Test with [10] → Expected: 10.0",
                        "Test with [2,4,6] → Expected: 4.0"
                    ]
                else:
                    test_cases = [
                        "Test with normal input → Expected: correct output",
                        "Test with edge case → Expected: handle gracefully",
                        "Test with empty/minimal input → Expected: appropriate response"
                    ]
                
                problem["test_cases"] = test_cases
                logger.info(f"Generated test cases: {test_cases}")
            
            # Ensure remaining required fields have defaults
            problem.setdefault("hints", [])
            problem.setdefault("sample_input", "")
            problem.setdefault("sample_output", "")
            problem.setdefault("starter_code", "")
            
            fixed_problems.append(problem)
        
        result["problems"] = fixed_problems
        return result
    
    def _basic_fallback_parsing(self, content: str) -> List[Dict[str, Any]]:
        """Basic fallback parsing when AI processing fails"""
        problems = []
        lines = content.split('\n')
        current_problem = None
        problem_number = 0
        
        for line in lines:
            line = line.strip()
            
            # Look for numbered problems
            if re.match(r'^\d+\.\s*\*\*(.+?)\*\*', line):
                # Save previous problem
                if current_problem:
                    # Apply validation and enhancement
                    current_problem = self._enhance_basic_problem(current_problem)
                    problems.append(current_problem)
                
                # Start new problem
                problem_number += 1
                title = line.split('**')[1] if '**' in line else f"Problem {problem_number}"
                current_problem = {
                    "number": problem_number,
                    "title": title,
                    "description": "",
                    "sample_input": "",
                    "sample_output": "",
                    "explanation": "",
                    "difficulty": "medium",
                    "concepts": [],
                    "hints": [],
                    "test_cases": [],
                    "starter_code": "",
                    "estimated_minutes": 30
                }
            
            elif current_problem and line.startswith("**Problem Statement**"):
                current_problem["description"] = line.replace("**Problem Statement**:", "").strip()
            elif current_problem and line.startswith("**Sample Input**"):
                current_problem["sample_input"] = line.replace("**Sample Input**:", "").strip()
            elif current_problem and line.startswith("**Sample Output**"):
                current_problem["sample_output"] = line.replace("**Sample Output**:", "").strip()
            elif current_problem and line.startswith("**Explanation**"):
                current_problem["explanation"] = line.replace("**Explanation**:", "").strip()
        
        # Add final problem
        if current_problem:
            current_problem = self._enhance_basic_problem(current_problem)
            problems.append(current_problem)
        
        return problems
    
    def _enhance_basic_problem(self, problem: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance a basic problem with missing fields"""
        # Use the same validation logic as the main processor
        enhanced = self._validate_and_fix_problems({"problems": [problem]})
        return enhanced["problems"][0] if enhanced["problems"] else problem
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics"""
        stats = self.processing_stats.copy()
        if stats["total_calls"] > 0:
            stats["success_rate"] = (stats["successful_calls"] / stats["total_calls"]) * 100
        else:
            stats["success_rate"] = 0
        return stats


# Global instance
ai_function_processor = AIFunctionProcessor()