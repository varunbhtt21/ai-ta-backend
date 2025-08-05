"""
Structured Tutoring Engine - Implementation of the OOP prototype teaching methodology
This engine follows the exact conversation flow and prompting strategy from the provided prototype.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import logging
from dataclasses import dataclass

from app.models import (
    ConversationMessage, MessageType, InputType, 
    SessionContext, Problem, Assignment, User
)
from app.services.openai_client import openai_client
from app.services.enhanced_logic_validator import (
    EnhancedLogicValidator, LogicValidationResult
)
from app.services.code_implementation_validator import (
    CodeImplementationValidator, CodeValidationResult, CodeValidationLevel
)
from app.services.code_understanding_verifier import (
    CodeUnderstandingVerifier, VerificationResult, UnderstandingLevel
)
from app.services.validation_types import LogicValidationLevel, StrictnessLevel
from app.utils.response_formatter import format_response
from app.core.config import settings

logger = logging.getLogger(__name__)


class StudentState(Enum):
    """Track where the student is in the learning process"""
    INITIAL_GREETING = "initial_greeting"
    READY_TO_START = "ready_to_start"
    PROBLEM_PRESENTED = "problem_presented"
    AWAITING_APPROACH = "awaiting_approach"
    LOGIC_VALIDATION = "logic_validation"
    LOGIC_APPROVED = "logic_approved"
    READY_FOR_CODING = "ready_for_coding"          # Phase 5: Logic approved, ready to code
    GUIDED_CODE_DISCOVERY = "guided_code_discovery" # Phase 5: Leading questions for code
    CODE_SUBMITTED = "code_submitted"              # Phase 5: Student submitted code
    CODE_ALIGNMENT_CHECK = "code_alignment_check"  # Phase 5: Checking logic-code alignment
    CODE_UNDERSTANDING = "code_understanding"      # Phase 5: Verifying code understanding
    WORKING_ON_CODE = "working_on_code"           # Legacy state
    STUCK_NEEDS_HELP = "stuck_needs_help"
    CODE_REVIEW = "code_review"
    PROBLEM_COMPLETED = "problem_completed"


class TutoringMode(Enum):
    """Different tutoring response modes"""
    PROBLEM_PRESENTATION = "problem_presentation"
    APPROACH_INQUIRY = "approach_inquiry"
    LOGIC_VALIDATION = "logic_validation"
    LOGIC_CLARIFICATION = "logic_clarification"
    GUIDED_QUESTIONING = "guided_questioning"
    CODE_ANALYSIS = "code_analysis"
    HINT_PROVIDING = "hint_providing"
    ENCOURAGEMENT = "encouragement"
    CELEBRATION = "celebration"
    CURRICULUM_INFORMATION = "curriculum_information"
    # Phase 5: Code Implementation Modes
    LEADING_QUESTIONS = "leading_questions"         # Guide with discovery questions
    CODE_ALIGNMENT_CHECK = "code_alignment_check"   # Verify logic-code match
    UNDERSTANDING_VERIFICATION = "understanding_verification" # Test code comprehension
    CODE_GUIDANCE = "code_guidance"                 # Help fix code issues


@dataclass
class StructuredResponse:
    """Structured response from the tutoring engine"""
    response_text: str
    tutoring_mode: TutoringMode
    student_state: StudentState
    next_expected_input: str
    teaching_notes: List[str]
    current_problem: Optional[int] = None
    logic_explanation: Optional[str] = None


class StructuredTutoringEngine:
    """
    Implementation of the OOP prototype's structured teaching methodology.
    
    This engine follows the exact conversation flow:
    1. Student says ready → Present ONLY the problem statement
    2. Ask "How are you thinking to solve this?"
    3. Listen to their approach
    4. Guide through questions, NOT answers
    5. When stuck → break problem into smaller pieces
    6. Point out issues with hints, don't fix them
    7. Only celebrate when they solve correctly
    """
    
    def __init__(self):
        self.openai_client = openai_client
        self.enhanced_logic_validator = EnhancedLogicValidator()
        
        # Phase 5: Code Implementation Validators
        self.code_implementation_validator = CodeImplementationValidator()
        self.code_understanding_verifier = CodeUnderstandingVerifier()
        
        # Track validation state per session
        self.validation_states = {}  # session_id -> validation state
        
        # Few-shot examples from the OOP prototype
        self.few_shot_examples = [
            {
                "scenario": "Student struggling with basic concept",
                "student_response": "I kind of not clear how to write the code",
                "ai_response": "Let's do one thing - I'll create a simple version of this problem. Instead of focusing on 5 numbers, let's just focus on one number at a time. No need for a loop. How will you do it?"
            },
            {
                "scenario": "Type confusion issue",
                "student_code": "x = input()\\ny = []\\ny.append(x)",
                "ai_response": "Good, but there is one issue. I'll give you a hint: Look at what you are inserting into the list and check its type."
            },
            {
                "scenario": "Student needs encouragement",
                "student_response": "I am not getting it",
                "ai_response": "Read this statement from the question: 'take input 5 numbers'. Is x an integer or string?"
            },
            {
                "scenario": "Progressive learning",
                "student_understanding": "Got the basic concept",
                "ai_response": "Great! Now can you do the same process for 5 numbers using a for loop?"
            },
            {
                "scenario": "Code analysis with hints",
                "student_code": "for i in range(1,6):\\n    y.append(i)\\nprint(y)",
                "ai_response": "I see you're using a loop, which is great! But notice that you're appending 'i' (the loop counter) instead of taking user input. What should you append to get the user's numbers?"
            },
            {
                "scenario": "Celebrating progress", 
                "student_achievement": "Solved basic version",
                "ai_response": "Excellent work! You've got the hang of it. Now that you understand the concept, let's tackle the original problem with all 5 numbers."
            }
        ]
    
    def _create_structured_system_prompt(
        self, 
        curriculum_content: str, 
        current_problem: Problem, 
        student_state: StudentState,
        conversation_history: List[ConversationMessage]
    ) -> str:
        """Create system prompt following the OOP prototype methodology"""
        
        # Extract problem details
        problem_title = current_problem.title
        problem_statement = current_problem.description
        sample_input = getattr(current_problem, 'sample_input', '')
        sample_output = getattr(current_problem, 'sample_output', '')
        explanation = getattr(current_problem, 'explanation', '')
        
        system_prompt = f"""You are an AI Python Programming Tutor following a STRICT structured teaching methodology. Your role is to guide students through programming assignments step-by-step WITHOUT giving direct solutions.

CURRICULUM CONTENT THAT HAS BEEN TAUGHT TO STUDENTS:
{curriculum_content}

IMPORTANT: Use the curriculum content above as context for what students have already learned. Reference specific concepts, examples, and terminology from the curriculum when providing guidance. Connect problems to concepts they've already studied.

CURRENT PROBLEM:
Title: {problem_title}
Problem Statement: {problem_statement}
Sample Input: {sample_input}
Sample Output: {sample_output}
Explanation: {explanation}

STUDENT'S CURRENT STATE: {student_state.value}

CRITICAL TEACHING RULES - FOLLOW THESE EXACTLY:

1. **NEVER GIVE DIRECT SOLUTIONS OR CODE EXAMPLES**
2. **ONLY present the problem statement when student is ready**
3. **Ask "How are you thinking to solve this?" after presenting the problem**
4. **Guide through questions, NOT answers**
5. **When student is stuck, break problem into smaller pieces**
6. **Give hints that lead to discovery, never direct solutions**
7. **Only provide code after student has figured out the logic themselves**

RESPONSE FORMATTING REQUIREMENTS - ALWAYS FORMAT YOUR RESPONSES:

- Use **bold headings** for main sections (e.g., **Let's break this down step-by-step:**)
- Use numbered lists (1., 2., 3.) for sequential steps or instructions
- Use indented bullet points (   - content) for sub-points under numbered items
- Add proper spacing with empty lines between sections for readability
- End guidance sections with **Your Turn:** or **Think about this:** followed by questions
- Structure responses to be scannable and easy to follow, NOT paragraph format
- Example format:
  ```
  **Let's break this down step-by-step:**

  1. First step here
     - Additional detail for step 1
     - Another detail

  2. Second step here
     - Detail for step 2

  **Your Turn:**
  What do you think the next step should be?
  ```

EXACT CONVERSATION FLOW TO FOLLOW:

1. When student says ready → Present ONLY the problem statement + ask "How are you thinking to solve this? Tell me the logic first and do not use code language."
2. When student gives logic explanation → Validate the logic in natural language. If correct, approve and ask for code. If incomplete, ask for clarification.
3. When logic is approved → Student can now write code
4. When student submits code → Analyze and give hints about issues, DON'T fix the code
5. When student tries to code before logic approval → Redirect them back to explain logic first
6. When student is stuck → Break into simpler version and ask for logic explanation
7. Only when correct → Celebrate and move to next problem

EXAMPLES OF CORRECT RESPONSES:

When student says "ready":
"**Problem 1: Create a List with User Input**
Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list.

**Sample Input:**
Enter number 1: 3
Enter number 2: 7
Enter number 3: 2
Enter number 4: 9
Enter number 5: 5

**Sample Output:**
[3, 7, 2, 9, 5]

How are you thinking to solve this question? Tell me the logic first and do not use code language."

When student gives logic explanation:
Student: "I will create an empty list, then use a loop to ask the user for 5 numbers one by one, convert each input to integer, and add it to the list, then print the final list"
You: "Excellent logic! Your approach correctly identifies all the key steps: creating an empty list, looping 5 times, converting input to integers, and appending to the list. Now convert this logic into code."

When student is stuck on logic:
Student: "I don't know how to approach this"
You: "Let's break this down. Instead of 5 numbers, let's start with just 1 number. In plain English, how would you get one number from the user and put it in a list?"

When student tries to submit code before logic approval:
Student: "x = input(); y = []; y.append(x)"
You: "I see you want to write code, but first let's make sure we have the right logic. Can you explain your approach in natural language (no code) - how are you thinking to solve this step by step?"

When student submits code after logic approval:
Student Code: "x = input(); y = []; y.append(x)"
You: "Good start! But check what type of data you're adding to the list. The problem asks for numbers - what does input() return?"

SPECIFIC HINTS FOR COMMON ISSUES:
- Type confusion: "Look at what you are inserting into the list and check its type"
- Loop counter confusion: "You're appending 'i' (the loop counter) instead of taking user input. What should you append?"
- Basic concept unclear: "Let's simplify - instead of 5 numbers, how would you do it with just 1 number?"

NEVER DO THESE:
❌ Don't give step-by-step solutions
❌ Don't provide example code upfront  
❌ Don't solve the problem for them
❌ Don't give multiple hints at once
❌ Don't explain the entire approach

ALWAYS DO THESE:
✅ Present only the problem statement first
✅ Ask how they're thinking to solve it
✅ Guide with questions
✅ Break down problems when they're stuck
✅ Celebrate small wins
✅ Point out issues without fixing them

Your goal is to help them discover the solution through guided questions, not to provide the solution directly."""

        return system_prompt
    
    def _detect_repetition_pattern(self, user_input: str, conversation_history: List[ConversationMessage]) -> Dict[str, Any]:
        """Detect if student is repeating messages, indicating confusion or misunderstanding"""
        
        # Look at recent user messages (last 6 messages)
        recent_user_messages = [
            msg.content.strip().lower() for msg in conversation_history[-6:] 
            if msg.message_type == MessageType.USER
        ]
        
        current_input_lower = user_input.strip().lower()
        
        # Count exact or very similar matches
        exact_matches = 0
        similar_matches = 0
        
        for prev_message in recent_user_messages:
            if prev_message == current_input_lower:
                exact_matches += 1
            elif self._are_messages_similar(current_input_lower, prev_message):
                similar_matches += 1
        
        # Determine repetition level
        is_repeating = exact_matches >= 1 or similar_matches >= 2
        repetition_count = exact_matches + similar_matches
        
        # Check if it's code repetition specifically
        code_indicators = ['=', 'for ', 'while ', 'if ', 'def ', 'print(', 'input(', 'append(', 'range(']
        is_code_repetition = any(indicator in user_input for indicator in code_indicators) and is_repeating
        
        return {
            'is_repeating': is_repeating,
            'repetition_count': repetition_count,
            'is_code_repetition': is_code_repetition,
            'exact_matches': exact_matches,
            'similar_matches': similar_matches
        }
    
    def _are_messages_similar(self, msg1: str, msg2: str, threshold: float = 0.8) -> bool:
        """Check if two messages are very similar (simple similarity check)"""
        
        # Simple word-based similarity
        words1 = set(msg1.split())
        words2 = set(msg2.split())
        
        if not words1 or not words2:
            return False
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold
    
    def _detect_student_state(
        self, 
        user_input: str, 
        conversation_history: List[ConversationMessage],
        current_state: StudentState
    ) -> StudentState:
        """Detect what state the student is in based on their input and conversation history"""
        
        user_input_lower = user_input.lower().strip()
        
        # Check conversation length for context
        conversation_length = len(conversation_history)
        
        # Ready to start indicators
        ready_indicators = ['ready', 'start', 'begin', 'yes', 'ok', 'sure', 'let\'s go', 'continue']
        if any(indicator in user_input_lower for indicator in ready_indicators):
            if conversation_length <= 3:  # Early in conversation
                return StudentState.READY_TO_START
        
        # Code submission detection - Use proper syntax detection, not keyword matching
        if self._is_code_submission(user_input):
            if current_state == StudentState.LOGIC_APPROVED:
                return StudentState.CODE_REVIEW
            else:
                # STRICT: Any actual code before logic approval gets redirected to awaiting approach
                return StudentState.AWAITING_APPROACH
        
        # Stuck/confusion indicators (expanded list)
        stuck_indicators = [
            'not clear', 'don\'t understand', 'stuck', 'confused', 'not getting it', 'help',
            'hint', 'unable to think', 'can\'t figure', 'don\'t know', 'no idea', 
            'lost', 'struggling', 'difficult', 'hard to', 'can you help',
            'give me', 'show me', 'i need', 'how do i', 'what should i'
        ]
        if any(indicator in user_input_lower for indicator in stuck_indicators):
            return StudentState.STUCK_NEEDS_HELP
        
        # Logic explanation indicators
        logic_indicators = [
            'logic', 'approach', 'thinking', 'solve', 'strategy', 'plan', 'steps',
            'idea', 'way to', 'method', 'algorithm', 'process'
        ]
        if any(indicator in user_input_lower for indicator in logic_indicators):
            if current_state == StudentState.AWAITING_APPROACH:
                return StudentState.LOGIC_VALIDATION
        
        # Question about approach
        question_indicators = ['how', 'what', 'should i', 'do i need', 'can i', 'is it']
        if any(indicator in user_input_lower for indicator in question_indicators):
            if current_state == StudentState.PROBLEM_PRESENTED:
                return StudentState.AWAITING_APPROACH
            else:
                return StudentState.WORKING_ON_CODE
        
        # Next problem indicators (when user is ready to move forward)
        next_indicators = ['next', 'done', 'completed', 'finished', 'move on']
        if any(indicator in user_input_lower for indicator in next_indicators):
            # CRITICAL: Do NOT automatically transition to next problem
            # This will be handled in enhanced_session_service with proper validation
            # Just return current state to prevent unauthorized progression
            return current_state
        
        # Default state transitions with logic validation requirement
        if current_state == StudentState.READY_TO_START:
            return StudentState.PROBLEM_PRESENTED
        elif current_state == StudentState.PROBLEM_PRESENTED:
            return StudentState.AWAITING_APPROACH
        elif current_state == StudentState.AWAITING_APPROACH:
            # Any substantial response should be treated as logic attempt
            if len(user_input.strip()) > 10:  # More than just short responses
                return StudentState.LOGIC_VALIDATION
            return StudentState.AWAITING_APPROACH
        elif current_state == StudentState.LOGIC_VALIDATION:
            return StudentState.LOGIC_VALIDATION  # Stay in validation until approved
        elif current_state == StudentState.LOGIC_APPROVED:
            return StudentState.WORKING_ON_CODE
        # Phase 5: Code Implementation State Transitions
        elif current_state == StudentState.READY_FOR_CODING:
            return StudentState.GUIDED_CODE_DISCOVERY
        elif current_state == StudentState.GUIDED_CODE_DISCOVERY:
            # If user submits code, move to code submission
            if self._contains_code(user_input):
                return StudentState.CODE_SUBMITTED
            else:
                return StudentState.GUIDED_CODE_DISCOVERY  # Continue guided discovery
        elif current_state == StudentState.CODE_SUBMITTED:
            return StudentState.CODE_ALIGNMENT_CHECK
        elif current_state == StudentState.CODE_ALIGNMENT_CHECK:
            return StudentState.CODE_UNDERSTANDING
        elif current_state == StudentState.CODE_UNDERSTANDING:
            return StudentState.PROBLEM_COMPLETED  # After understanding verification
        else:
            return StudentState.WORKING_ON_CODE
    
    def _determine_tutoring_mode(
        self, 
        student_state: StudentState, 
        user_input: str,
        conversation_history: List[ConversationMessage]
    ) -> TutoringMode:
        """Determine what type of tutoring response is needed"""
        
        # Check for curriculum-related questions first
        if self._is_curriculum_question(user_input):
            return TutoringMode.CURRICULUM_INFORMATION
        
        if student_state == StudentState.READY_TO_START:
            return TutoringMode.PROBLEM_PRESENTATION
        elif student_state == StudentState.PROBLEM_PRESENTED:
            return TutoringMode.APPROACH_INQUIRY
        elif student_state == StudentState.AWAITING_APPROACH:
            return TutoringMode.GUIDED_QUESTIONING
        elif student_state == StudentState.LOGIC_VALIDATION:
            return TutoringMode.LOGIC_VALIDATION
        elif student_state == StudentState.LOGIC_APPROVED:
            return TutoringMode.ENCOURAGEMENT
        elif student_state == StudentState.CODE_REVIEW:
            return TutoringMode.CODE_ANALYSIS
        elif student_state == StudentState.STUCK_NEEDS_HELP:
            return TutoringMode.HINT_PROVIDING
        elif student_state == StudentState.PROBLEM_COMPLETED:
            return TutoringMode.CELEBRATION
        # Phase 5: Code Implementation Tutoring Modes
        elif student_state == StudentState.READY_FOR_CODING:
            return TutoringMode.LEADING_QUESTIONS
        elif student_state == StudentState.GUIDED_CODE_DISCOVERY:
            return TutoringMode.LEADING_QUESTIONS
        elif student_state == StudentState.CODE_SUBMITTED:
            return TutoringMode.CODE_ALIGNMENT_CHECK
        elif student_state == StudentState.CODE_ALIGNMENT_CHECK:
            return TutoringMode.CODE_GUIDANCE
        elif student_state == StudentState.CODE_UNDERSTANDING:
            return TutoringMode.UNDERSTANDING_VERIFICATION
        else:
            return TutoringMode.GUIDED_QUESTIONING
    
    def _is_code_submission(self, text: str) -> bool:
        """Detect if the input contains actual code syntax (not just mentions of concepts)"""
        if not text or len(text.strip()) < 10:
            return False
        
        # Check for actual code syntax patterns, not just concept mentions
        actual_code_patterns = [
            r'\w+\s*=\s*\w+',           # Variable assignment: x = 5
            r'for\s+\w+\s+in\s+\w+:',   # For loop syntax: for i in range:
            r'while\s+\w+.*:',          # While loop syntax: while x > 0:
            r'if\s+\w+.*:',             # If statement syntax: if x > 0:
            r'def\s+\w+\s*\(',          # Function definition: def func(
            r'print\s*\(',              # Function call: print(
            r'input\s*\(',              # Function call: input(
            r'\w+\.append\s*\(',        # Method call: list.append(
            r'range\s*\(',              # Function call: range(
            r'\[\]',                    # Empty list literal: []
            r'\w+\[\d+\]',              # List indexing: list[0]
        ]
        
        import re
        # Must have at least 2 actual code syntax patterns
        pattern_count = sum(1 for pattern in actual_code_patterns if re.search(pattern, text))
        
        # Also check for multi-line code structure
        has_indentation = '\n    ' in text or '\n\t' in text
        has_multiple_lines = text.count('\n') >= 2
        
        return pattern_count >= 2 or (pattern_count >= 1 and has_indentation and has_multiple_lines)
    
    def _contains_code(self, text: str) -> bool:
        """Phase 5: Detect if the input contains substantial code (more strict than _is_code_submission)"""
        if not text or len(text.strip()) < 20:
            return False
        
        # Use the same logic but require higher threshold for Phase 5
        import re
        actual_code_patterns = [
            r'\w+\s*=\s*\w+',           # Variable assignment
            r'for\s+\w+\s+in\s+\w+:',   # For loop syntax  
            r'while\s+\w+.*:',          # While loop syntax
            r'if\s+\w+.*:',             # If statement syntax
            r'def\s+\w+\s*\(',          # Function definition
            r'print\s*\(',              # Function call
            r'input\s*\(',              # Function call
            r'\w+\.append\s*\(',        # Method call
            r'range\s*\(',              # Function call
            r'\[\]',                    # Empty list literal
            r'\w+\[\d+\]',              # List indexing
        ]
        
        pattern_count = sum(1 for pattern in actual_code_patterns if re.search(pattern, text))
        
        # Check for code structure indicators
        has_indentation = '\n    ' in text or '\n\t' in text
        has_multiple_lines = text.count('\n') >= 2
        
        # Higher threshold for Phase 5 - need clear code structure
        return pattern_count >= 3 or (pattern_count >= 2 and has_indentation and has_multiple_lines)
    
    def _is_curriculum_question(self, text: str) -> bool:
        """Detect if the input is asking about curriculum topics or learning materials"""
        text_lower = text.lower()
        curriculum_indicators = [
            'curriculum', 'topics', 'what have i learned', 'what did i learn',
            'what topics', 'learning materials', 'course content',
            'tell me the topics', 'topics present in curriculum',
            'context of curriculum', 'have the context', 'curriculum content',
            'what concepts', 'what have we covered', 'covered so far',
            'syllabus', 'course outline', 'learning objectives'
        ]
        return any(indicator in text_lower for indicator in curriculum_indicators)
    
    def _analyze_code_issues(self, code: str, problem: Problem) -> List[str]:
        """Analyze common code issues and return specific hints"""
        issues = []
        
        # Type confusion (input() without int())
        if 'input()' in code and 'int(' not in code:
            issues.append("type_confusion")
        
        # Loop counter instead of user input
        if '.append(i)' in code:
            issues.append("loop_counter_confusion")
        
        # Range confusion
        if 'range(1,' in code:
            issues.append("range_confusion")
        
        # Missing loop for multiple inputs
        if 'input(' in code and 'for ' not in code and 'while ' not in code:
            if "5 numbers" in problem.description:
                issues.append("missing_loop")
        
        return issues
    
    def _get_hint_for_issue(self, issue: str) -> str:
        """Get specific hint for a detected issue"""
        hints = {
            "type_confusion": "Good, but there is one issue. I'll give you a hint: Look at what you are inserting into the list and check its type.",
            "loop_counter_confusion": "I see you're using a loop, which is great! But notice that you're appending 'i' (the loop counter) instead of taking user input. What should you append to get the user's numbers?",
            "range_confusion": "Check your range - range(1,6) gives you 1,2,3,4,5. Is that what you want for the loop?",
            "missing_loop": "You're taking input, but the problem asks for 5 numbers. How can you repeat the input process 5 times?"
        }
        return hints.get(issue, "Try to think about what the problem is asking step by step.")
    
    async def generate_structured_response(
        self,
        user_input: str,
        user_id: str,
        assignment: Assignment,
        current_problem: Problem,
        conversation_history: List[ConversationMessage],
        current_state: StudentState = StudentState.INITIAL_GREETING,
        problem_context: Optional[Dict[str, Any]] = None
    ) -> StructuredResponse:
        """Generate structured tutoring response following OOP prototype methodology"""
        
        logger.info("🎯 STRUCTURED_TUTORING_ENGINE: Starting response generation")
        logger.info(f"💬 STRUCTURED_TUTORING_ENGINE: User input: '{user_input}'")
        logger.info(f"👤 STRUCTURED_TUTORING_ENGINE: User ID: {user_id}")
        logger.info(f"📚 STRUCTURED_TUTORING_ENGINE: Assignment: {assignment.title if assignment else 'None'}")
        logger.info(f"🎯 STRUCTURED_TUTORING_ENGINE: Problem: {current_problem.title if current_problem else 'None'}")
        logger.info(f"💭 STRUCTURED_TUTORING_ENGINE: Current state: {current_state}")
        logger.info(f"📋 STRUCTURED_TUTORING_ENGINE: Problem context: {problem_context}")
        
        # Extract curriculum content for context
        curriculum_content = ""
        if assignment and hasattr(assignment, 'curriculum_content'):
            curriculum_content = assignment.curriculum_content or ""
            logger.info(f"📖 STRUCTURED_TUTORING_ENGINE: Curriculum content length: {len(curriculum_content)} characters")
        else:
            logger.warning("⚠️ STRUCTURED_TUTORING_ENGINE: No curriculum content available")
        
        try:
            # Check if user is requesting next problem without completing current one
            user_input_lower = user_input.lower().strip()
            next_problem_indicators = ['next problem', 'next', 'move on', 'skip', 'go to next']
            
            if any(indicator in user_input_lower for indicator in next_problem_indicators):
                logger.info("🛑 STRUCTURED_TUTORING_ENGINE: Detected next problem request - need validation")
                # This will trigger validation in enhanced_session_service
                # Return a special response indicating validation is needed
                return StructuredResponse(
                    response_text="VALIDATION_REQUIRED_FOR_PROGRESSION",  # Special marker
                    tutoring_mode=TutoringMode.GUIDED_QUESTIONING,
                    student_state=current_state,
                    next_expected_input="validation_check",
                    teaching_notes=["Next problem requested - requires completion validation"]
                )
            
            # Check if user is asking for problem statement/explanation
            problem_request_indicators = [
                'give me the problem', 'show me the problem', 'what is the problem',
                'explain the problem', 'problem statement', 'what am i supposed to do',
                'what should i do', 'describe the problem', 'tell me the problem'
            ]
            
            if any(indicator in user_input_lower for indicator in problem_request_indicators):
                logger.info("✅ STRUCTURED_TUTORING_ENGINE: Detected problem statement request")
                
                # Use problem_context from frontend if available, otherwise use current_problem
                if problem_context and 'description' in problem_context:
                    logger.info("📋 STRUCTURED_TUTORING_ENGINE: Using problem context from frontend")
                    response_text = f"""Here is the problem statement:

**{problem_context.get('title', 'Problem')}**

{problem_context['description']}

How are you thinking to solve this question?"""
                else:
                    logger.info("📚 STRUCTURED_TUTORING_ENGINE: Using current_problem data")
                    response_text = self._present_problem(current_problem)
                
                logger.info(f"📝 STRUCTURED_TUTORING_ENGINE: Problem statement response: '{response_text[:100]}...'")
                
                return StructuredResponse(
                    response_text=format_response(response_text),
                    tutoring_mode=TutoringMode.PROBLEM_PRESENTATION,
                    student_state=StudentState.PROBLEM_PRESENTED,
                    next_expected_input="approach_explanation", 
                    teaching_notes=["Problem statement provided", "Awaiting student's approach"]
                )
            
            # Detect student's current state
            new_student_state = self._detect_student_state(user_input, conversation_history, current_state)
            
            # Determine tutoring mode
            tutoring_mode = self._determine_tutoring_mode(new_student_state, user_input, conversation_history)
            
            # Handle specific scenarios based on state and mode
            if tutoring_mode == TutoringMode.PROBLEM_PRESENTATION:
                response_text = self._present_problem_with_logic_request(current_problem)
                next_expected = "logic_explanation"
                teaching_notes = ["Problem presented", "Awaiting student's logic explanation"]
                
            elif tutoring_mode == TutoringMode.APPROACH_INQUIRY:
                # Always ask OpenAI to generate an approach inquiry response with emphasis on logic
                response_text = await self._generate_logic_inquiry(user_input, current_problem, conversation_history, curriculum_content)
                next_expected = "logic_explanation"
                teaching_notes = ["Generated logic inquiry via OpenAI", "Waiting for natural language logic"]
                
            elif tutoring_mode == TutoringMode.LOGIC_VALIDATION:
                # Check for repetition in logic attempts too
                repetition_info = self._detect_repetition_pattern(user_input, conversation_history)
                
                if repetition_info['is_repeating'] and repetition_info['repetition_count'] >= 2:
                    # Generate fresh empathetic response for repeated logic attempts
                    response_text = await self._generate_logic_confusion_response(user_input, current_problem, conversation_history, curriculum_content, repetition_info)
                    next_expected = "clarified_logic_explanation"
                    teaching_notes = ["Generated fresh response for repeated logic attempts"]
                else:
                    # Normal logic validation
                    response_text, teaching_notes, is_logic_correct = await self._validate_logic_explanation(
                        logic_explanation=user_input,
                        problem=current_problem,
                        conversation_history=conversation_history,
                        user_id=user_id,
                        curriculum_content=curriculum_content
                    )
                    
                    # If the logic is correct, approve it and transition to Phase 5 coding
                    if is_logic_correct:
                        new_student_state = StudentState.READY_FOR_CODING  # Phase 5: Ready for guided coding
                        tutoring_mode = TutoringMode.LEADING_QUESTIONS      # Phase 5: Use leading questions
                        
                        # Generate Phase 5 coding start response with leading questions
                        coding_start_response = await self._generate_coding_phase_start(
                            user_input, current_problem, conversation_history, curriculum_content
                        )
                        response_text = f"{response_text}\n\n{coding_start_response}"
                        next_expected = "guided_code_discovery"
                        teaching_notes.append("Logic approved - Phase 5: Starting guided code discovery")
                    else:
                        # Keep in logic validation, ask for clarification
                        next_expected = "revised_logic_explanation"
                        teaching_notes.append("Logic needs clarification - staying in validation phase")
                
            elif tutoring_mode == TutoringMode.ENCOURAGEMENT and new_student_state == StudentState.LOGIC_APPROVED:
                # Generate fresh encouragement instead of template
                response_text = await self._generate_logic_approval_response(user_input, current_problem, curriculum_content)
                next_expected = "code_implementation"
                teaching_notes = ["Generated fresh logic approval", "Ready for code implementation"]
                
            elif tutoring_mode == TutoringMode.CODE_ANALYSIS:
                # STRICT ENFORCEMENT: NO code analysis until logic is approved
                if current_state != StudentState.LOGIC_APPROVED:
                    # Check for repetition first
                    repetition_info = self._detect_repetition_pattern(user_input, conversation_history)
                    
                    if repetition_info['is_code_repetition']:
                        # Generate empathetic response for repeated code attempts
                        response_text = await self._generate_strict_logic_redirect_response(user_input, current_problem, conversation_history, curriculum_content, repetition_info)
                    else:
                        # First time code attempt - generate strict redirect
                        response_text = await self._generate_strict_logic_redirect_response(user_input, current_problem, conversation_history, curriculum_content)
                    
                    new_student_state = StudentState.AWAITING_APPROACH
                    tutoring_mode = TutoringMode.APPROACH_INQUIRY
                    next_expected = "logic_explanation_required"
                    teaching_notes = ["STRICT: Blocked code analysis - requires logic first", "Generated strict redirect"]
                else:
                    # Logic was approved, proceed with code analysis
                    response_text, teaching_notes, is_solution_correct = await self._analyze_code_submission(user_input, current_problem, curriculum_content)
                    
                    # If the solution is correct, transition to celebration mode
                    if is_solution_correct:
                        new_student_state = StudentState.PROBLEM_COMPLETED
                        tutoring_mode = TutoringMode.CELEBRATION
                        response_text = f"{response_text} Ready for the next problem?"
                        next_expected = "next_problem_ready"
                        teaching_notes.append("Problem solved correctly - transitioning to celebration")
                    else:
                        next_expected = "revised_code_or_question"
                
            elif tutoring_mode == TutoringMode.HINT_PROVIDING:
                response_text = await self._provide_guided_help(user_input, current_problem, conversation_history, curriculum_content)
                next_expected = "attempt_or_question"
                teaching_notes = ["Provided guidance", "Broke down problem"]
                
            elif tutoring_mode == TutoringMode.GUIDED_QUESTIONING:
                # Check if this is a code submission in AWAITING_APPROACH state - enforce logic first
                code_indicators = ['=', 'for ', 'while ', 'if ', 'def ', 'print(', 'input(', 'append(', 'range(', 'import ', 'from ', 'class ', 'try:', 'except:', 'len(']
                if (new_student_state == StudentState.AWAITING_APPROACH and 
                    any(indicator in user_input for indicator in code_indicators)):
                    # Student submitted code without logic approval - redirect to logic explanation
                    repetition_info = self._detect_repetition_pattern(user_input, conversation_history)
                    
                    # Count specifically code submission attempts
                    code_submission_count = 0
                    for msg in conversation_history[-10:]:  # Check last 10 messages
                        if (msg.message_type == MessageType.USER and 
                            any(indicator in msg.content for indicator in code_indicators)):
                            code_submission_count += 1
                    
                    logger.warning(f"🚫 STRUCTURED_TUTORING_ENGINE: Code submission #{code_submission_count} without logic approval")
                    
                    if code_submission_count >= 3:
                        # Very strict response after multiple attempts
                        response_text = f"This is your {code_submission_count}th attempt to submit code without providing your logical approach first. I absolutely cannot proceed until you explain your thinking in natural language. Please describe step-by-step how you plan to solve this problem without any code."
                    else:
                        response_text = await self._generate_strict_logic_redirect_response(
                            user_input, current_problem, conversation_history, curriculum_content, repetition_info
                        )
                    
                    next_expected = "logic_explanation_required"
                    teaching_notes = [f"STRICT: Blocked code submission #{code_submission_count}", "Redirected to logic explanation"]
                else:
                    response_text = await self._guide_with_questions(user_input, current_problem, curriculum_content)
                    next_expected = "clarification_or_attempt"
                    teaching_notes = ["Guided with questions", "Avoided direct answers"]
                
            elif tutoring_mode == TutoringMode.CELEBRATION:
                # Check if user is responding to "ready for next problem" question
                next_indicators = ['yes', 'ready', 'next', 'continue', 'sure', 'ok', 'yeah', 'yep']
                user_input_lower = user_input.lower().strip()
                
                if any(indicator in user_input_lower for indicator in next_indicators):
                    # User wants to move to next problem - but don't validate here
                    # The enhanced_session_service will handle the validation
                    logger.info("🚀 STRUCTURED_TUTORING_ENGINE: User confirmed ready for next problem")
                    logger.info(f"🚀 STRUCTURED_TUTORING_ENGINE: Current problem: {current_problem.title if current_problem else 'None'}")
                    logger.info(f"🚀 STRUCTURED_TUTORING_ENGINE: User input: '{user_input}'")
                    new_student_state = StudentState.READY_TO_START
                    tutoring_mode = TutoringMode.PROBLEM_PRESENTATION
                    
                    # Generate transition response via OpenAI
                    response_text = await self._generate_transition_acknowledgment(user_input, current_problem, conversation_history)
                    next_expected = "next_problem_presentation"
                    teaching_notes = ["Generated transition acknowledgment via OpenAI", "Transitioning to next problem"]
                    logger.info("🚀 STRUCTURED_TUTORING_ENGINE: Generated transition acknowledgment via OpenAI")
                    
                else:
                    # Generate celebration response via OpenAI
                    response_text = await self._generate_celebration_response(user_input, current_problem, conversation_history)
                    next_expected = "next_problem_ready"
                    teaching_notes = ["Generated celebration response via OpenAI", "Ready to advance"]
                
            elif tutoring_mode == TutoringMode.CURRICULUM_INFORMATION:
                response_text = await self._provide_curriculum_information(user_input, curriculum_content)
                next_expected = "continue_learning"
                teaching_notes = ["Provided curriculum information", "Answered direct curriculum question"]
            
            # Phase 5: Code Implementation Phase Handlers
            elif tutoring_mode == TutoringMode.LEADING_QUESTIONS:
                response_text, next_expected, new_student_state = await self._handle_leading_questions_mode(
                    user_input, current_problem, conversation_history, new_student_state, curriculum_content
                )
                teaching_notes = ["Phase 5: Leading questions guidance", "No direct code given"]
            
            elif tutoring_mode == TutoringMode.CODE_ALIGNMENT_CHECK:
                response_text, next_expected, new_student_state = await self._handle_code_alignment_mode(
                    user_input, current_problem, conversation_history, new_student_state, curriculum_content
                )
                teaching_notes = ["Phase 5: Code-logic alignment check", "Verifying implementation matches logic"]
            
            elif tutoring_mode == TutoringMode.CODE_GUIDANCE:
                response_text, next_expected, new_student_state = await self._handle_code_guidance_mode(
                    user_input, current_problem, conversation_history, new_student_state, curriculum_content
                )
                teaching_notes = ["Phase 5: Code guidance", "Helping fix implementation issues"]
            
            elif tutoring_mode == TutoringMode.UNDERSTANDING_VERIFICATION:
                response_text, next_expected, new_student_state = await self._handle_understanding_verification_mode(
                    user_input, current_problem, conversation_history, new_student_state, curriculum_content
                )
                teaching_notes = ["Phase 5: Understanding verification", "Testing code comprehension"]
                
            else:
                # Default guided questioning
                response_text = await self._guide_with_questions(user_input, current_problem, curriculum_content)
                next_expected = "clarification_or_attempt"
                teaching_notes = ["Default guidance provided"]
            
            # Check for repetition in other tutoring modes before final response
            repetition_info = self._detect_repetition_pattern(user_input, conversation_history)
            
            # If student is repeating and seems confused, generate empathetic response
            if repetition_info['is_repeating'] and repetition_info['repetition_count'] >= 2:
                logger.info(f"🔄 STRUCTURED_TUTORING_ENGINE: Detected repetition - generating fresh empathetic response")
                
                # Generate contextual response based on current mode and problem
                empathy_response = await self._generate_general_confusion_response(
                    user_input, current_problem, conversation_history, curriculum_content, repetition_info, tutoring_mode
                )
                
                return StructuredResponse(
                    response_text=format_response(empathy_response),
                    tutoring_mode=tutoring_mode,
                    student_state=new_student_state,
                    next_expected_input="clarification_or_help",
                    teaching_notes=["Generated fresh empathetic response for repetition"]
                )
            
            # Apply response formatting for better readability
            formatted_response_text = format_response(response_text)
            
            return StructuredResponse(
                response_text=formatted_response_text,
                tutoring_mode=tutoring_mode,
                student_state=new_student_state,
                next_expected_input=next_expected,
                teaching_notes=teaching_notes
            )
            
        except Exception as e:
            logger.error(f"Error in structured tutoring response generation: {e}")
            # Fallback response
            fallback_text = "I'm here to help you learn. Can you tell me what you're working on or where you're getting stuck?"
            return StructuredResponse(
                response_text=format_response(fallback_text),
                tutoring_mode=TutoringMode.GUIDED_QUESTIONING,
                student_state=StudentState.WORKING_ON_CODE,
                next_expected_input="clarification",
                teaching_notes=["Error fallback response"]
            )
    
    def _present_problem(self, problem: Problem) -> str:
        """Present the problem statement following the exact format from OOP prototype"""
        
        # Format test cases for display
        test_cases_display = ""
        if problem.test_cases and len(problem.test_cases) > 0:
            test_cases_display = "\n\n**Sample Input/Output:**\n"
            for i, test_case in enumerate(problem.test_cases[:2]):  # Show first 2 test cases
                if isinstance(test_case, dict):
                    input_val = test_case.get('input', 'N/A')
                    output_val = test_case.get('expected_output', 'N/A') 
                    description = test_case.get('description', '')
                    
                    test_cases_display += f"\n**Example {i+1}:**\n"
                    test_cases_display += f"Input: {input_val}\n"
                    test_cases_display += f"Output: {output_val}\n"
                    if description and description != 'N/A':
                        test_cases_display += f"Explanation: {description}\n"
        
        return f"""Here is the problem:

**{problem.title}**

{problem.description}{test_cases_display}

How are you thinking to solve this question?"""
    
    def _present_problem_with_logic_request(self, problem: Problem) -> str:
        """Present the problem statement with explicit request for logic explanation first"""
        
        # Format test cases for display
        test_cases_display = ""
        if problem.test_cases and len(problem.test_cases) > 0:
            test_cases_display = "\n\n**Sample Input/Output:**\n"
            for i, test_case in enumerate(problem.test_cases[:2]):  # Show first 2 test cases
                if isinstance(test_case, dict):
                    input_val = test_case.get('input', 'N/A')
                    output_val = test_case.get('expected_output', 'N/A') 
                    description = test_case.get('description', '')
                    
                    test_cases_display += f"\n**Example {i+1}:**\n"
                    test_cases_display += f"Input: {input_val}\n"
                    test_cases_display += f"Output: {output_val}\n"
                    if description and description != 'N/A':
                        test_cases_display += f"Explanation: {description}\n"
        
        return f"""**{problem.title}**

{problem.description}{test_cases_display}

**How are you thinking to solve this question? Tell me the logic first and do not use code language.**"""
    
    async def _analyze_code_submission(self, code: str, problem: Problem, curriculum_content: str = "") -> Tuple[str, List[str], bool]:
        """Analyze code submission and provide specific hints without giving solutions
        
        Returns:
            Tuple[str, List[str], bool]: (response_text, teaching_notes, is_solution_correct)
        """
        
        logger.info("🔍 STRUCTURED_TUTORING_ENGINE: _analyze_code_submission called")
        logger.info(f"💻 STRUCTURED_TUTORING_ENGINE: Analyzing code: '{code}'")
        logger.info(f"📚 STRUCTURED_TUTORING_ENGINE: Problem: {problem.title if problem else 'None'}")
        
        # Use OpenAI to analyze the code dynamically
        system_prompt = f"""You are analyzing student code for this EXACT problem:

CURRICULUM CONTENT THAT HAS BEEN TAUGHT TO STUDENTS:
{curriculum_content}

IMPORTANT: Use the curriculum content above as context for what students have already learned. Reference specific concepts, examples, and terminology from the curriculum when providing feedback.

**Problem Title:** {problem.title}
**Problem Description:** {problem.description}
**Required Concepts:** {', '.join(problem.concepts) if problem.concepts else 'Not specified'}

The student submitted this code:
```
{code}
```

CRITICAL INSTRUCTIONS:
- ANALYZE THE EXACT CODE PROVIDED - look for specific syntax errors, logic errors, and missing elements
- Give SPECIFIC feedback about what's wrong, not generic statements
- If there are syntax errors (like `for i in range:` without parentheses), point them out clearly
- If logic is wrong (like no comparison in finding max), explain exactly what to fix
- If the code correctly solves the ORIGINAL problem, celebrate their success
- Focus on the most critical issue first but be specific about what's wrong
- Keep response to 1-2 sentences maximum but make them precise and actionable

RESPONSE FORMAT:
Start your response with either:
- "CORRECT:" if the code correctly solves the EXACT problem described above
- "ISSUE:" if the code has problems relative to the ORIGINAL problem requirements

FORBIDDEN:
- Do NOT say the code should do something different than what the original problem asks
- Do NOT add requirements like "find maximum/minimum" if not in original problem
- Do NOT change the problem requirements mid-conversation

EXAMPLE CONVERSATIONS:

**Scenario 1: Problem - "Create a list with user input"**
Student Code:
```python
numbers = []
for i in range(5):
    x = int(input())
    numbers.append(x)
print(numbers)
```
CORRECT Response: "CORRECT: Excellent work! Your code correctly collects 5 numbers from the user and displays them in a list."

**Scenario 2: Problem - "Create a list with user input"**
Student Code:
```python
numbers = []
for i in range(5):
    numbers.append(i)
print(numbers)
```
ISSUE Response: "ISSUE: Good start with the loop! But you're adding the loop counter 'i' instead of user input. Try using input() to get numbers from the user."

**Scenario 3: Problem - "Calculate sum of numbers in a list"**  
Student Code:
```python
numbers = [1, 2, 3, 4, 5]
total = 0
for num in numbers:
    total += num
print(total)
```
CORRECT Response: "CORRECT: Perfect! Your code correctly calculates the sum of all numbers in the list."

**Scenario 4: Problem - "Calculate sum of numbers in a list"**
Student Code:
```python
numbers = [1, 2, 3, 4, 5]
print(max(numbers))
```
ISSUE Response: "ISSUE: Your code finds the maximum value, but the problem asks to calculate the sum of all numbers. Try using a loop to add all the numbers together."

**Scenario 5: Problem - "Print even numbers from 1 to 10"**
Student Code:
```python
for i in range(1, 11):
    if i % 2 == 0:
        print(i)
```
CORRECT Response: "CORRECT: Excellent! Your code correctly identifies and prints all even numbers from 1 to 10."

**Scenario 6: Problem - "Create a list with user input" (Complex incorrect)**
Student Code:
```python
numbers = []
for i in range(5):
    x = input("Enter a number: ")
    numbers.append(x)
print(numbers)
```
ISSUE Response: "ISSUE: Good structure with the loop and input! However, you're storing strings in your list instead of numbers. Try converting the input to an integer using int()."

**Scenario 7: Problem - "Calculate sum of numbers in a list" (Multiple issues)**
Student Code:
```python
numbers = [1, 2, 3, 4, 5]
for num in numbers:
    print(num)
```
ISSUE Response: "ISSUE: Your loop correctly goes through each number, but you're printing them instead of adding them together. Try creating a sum variable and adding each number to it."

**Scenario 8: Problem - "Find the largest number in a list" (Requirement invention prevention)**
Student Code:
```python
numbers = [1, 5, 3, 9, 2]
total = sum(numbers)
print(total)
```
ISSUE Response: "ISSUE: Your code calculates the sum of the numbers, but the problem asks you to find the largest number. Try using a variable to track the maximum value as you go through the list."

**Scenario 9: Problem - "Create a list with user input" (Edge case)**
Student Code:
```python
numbers = []
x = int(input())
numbers.append(x)
print(numbers)
```
ISSUE Response: "ISSUE: Great start! You're correctly getting input and adding it to the list. However, the problem asks for multiple inputs, not just one. How could you repeat this process?"

**Scenario 10: Problem - "Find maximum and minimum values" (Syntax Error)**
Student Code:
```python
for i in range:
 max_v=i
```
ISSUE Response: "ISSUE: **Syntax Error:** `range` needs parentheses and parameters like `range(5)`. Also, you need to create a list of numbers first, then iterate over that list instead of using `range`."

**Scenario 11: Problem - "Find maximum and minimum values" (Missing List)**
Student Code:
```python
max_v=9999
for i in range:
 max_v=i
print(max_v)
```
ISSUE Response: "ISSUE: Two problems: 1) **Syntax Error:** `range` needs parentheses like `range(5)`. 2) You need to create your list of numbers first (like `numbers = [10, 5, 20]`) and iterate over that, not `range`."

**Scenario 12: Problem - "Find maximum and minimum values" (No Comparison Logic)**
Student Code:
```python
numbers = [10, 5, 20]
max_v = 0
for i in numbers:
 max_v = i
print(max_v)
```
ISSUE Response: "ISSUE: You're assigning each number to `max_v` without comparing. Use `if i > max_v:` to only update when you find a larger number. Also, remember you need to find BOTH maximum AND minimum values."

**Scenario 13: Problem - "Find maximum and minimum values" (Wrong Initialization)**
Student Code:
```python
numbers = [10, 5, 20]
max_v = 0
for i in numbers:
 if i > max_v:
  max_v = i
print(max_v)
```
ISSUE Response: "ISSUE: Good comparison logic! But initializing `max_v = 0` won't work if all numbers are negative. Initialize with the first element: `max_v = numbers[0]`. Also, you need a `min_v` variable for the minimum value."

CRITICAL FORMATTING REQUIREMENTS - YOU MUST FORMAT LIKE THIS:

**STRUCTURE YOUR RESPONSE EXACTLY LIKE THIS:**

**[Error Type]:** [Brief description]

[If multiple issues, use numbered list:]
1. **[Issue 1]:** [Explanation]
2. **[Issue 2]:** [Explanation]  
3. **[Issue 3]:** [Explanation]

**Your Turn:** [Guiding question]

**MANDATORY EXAMPLES TO FOLLOW:**

For syntax errors:
"**Syntax Error:** There are multiple issues in your code:

1. **`fori` should be separated** into `for i`
2. **`range()` needs parameters** like `range(5)`
3. **You need to create a list** to iterate over

**Your Turn:** What list of numbers do you want to work with?"

For logic errors:
"**Issue:** Your loop structure needs improvement:

1. **Create your list first:** `numbers = [1, 2, 3, 4, 5]`
2. **Add comparison logic:** Use `if i > max_v:` to update
3. **Track both values:** You need both `max_v` and `min_v`

**Your Turn:** Can you create the list first?"

DO NOT WRITE PARAGRAPH RESPONSES - ALWAYS USE THE STRUCTURE ABOVE!

COMMON ISSUES TO DETECT:
- `for i in range:` (missing parentheses) → "**Syntax Error:** `range` needs parentheses like `range(5)`"
- Using `range` instead of iterating over actual list → "You need to iterate over your list, not `range`"
- Assignment without comparison (`max_v = i`) → "You need to compare before updating: `if i > max_v:`"
- Wrong initialization (like `max_v = 0`) → "Initialize with first element: `max_v = numbers[0]`"
- Missing the actual list creation → "You need to create your list first: `numbers = [10, 5, 20]`"
- Only finding max OR min when problem asks for BOTH

Analyze the EXACT code provided and give a helpful, specific response:"""
        
        logger.info("🤖 STRUCTURED_TUTORING_ENGINE: Calling OpenAI for code analysis...")
        
        try:
            # Create a user message for the code analysis request
            user_message = ConversationMessage(
                timestamp=datetime.utcnow(),
                message_type=MessageType.USER,
                content=f"Analyze this code: {code}"
            )
            
            response = await self.openai_client.generate_response(
                messages=[user_message],
                system_prompt=system_prompt,
                max_tokens=150,
                temperature=0.3
            )
            
            logger.info("📞 STRUCTURED_TUTORING_ENGINE: OpenAI call completed for code analysis")
            logger.info(f"✅ STRUCTURED_TUTORING_ENGINE: OpenAI success: {response.get('success', False)}")
            
            if response["success"]:
                openai_response = response["content"].strip()
                logger.info(f"🎯 STRUCTURED_TUTORING_ENGINE: OpenAI code analysis: '{openai_response}'")
                
                # Determine if the solution is correct based on OpenAI response
                is_correct = openai_response.startswith("CORRECT:")
                
                # Validate that the response doesn't invent new requirements
                problematic_keywords = [
                    "maximum", "minimum", "average", "mean", "median", "mode",
                    "sort", "reverse", "find the largest", "find the smallest",
                    "calculate", "compute", "determine"
                ]
                
                # Check if AI is inventing requirements not in the original problem
                original_problem_lower = problem.description.lower()
                response_lower = openai_response.lower()
                
                invented_requirements = []
                for keyword in problematic_keywords:
                    if keyword in response_lower and keyword not in original_problem_lower:
                        invented_requirements.append(keyword)
                
                if invented_requirements:
                    logger.warning(f"🚨 STRUCTURED_TUTORING_ENGINE: AI invented requirements: {invented_requirements}")
                    logger.warning(f"📚 STRUCTURED_TUTORING_ENGINE: Original problem: {problem.description}")
                    logger.warning(f"🤖 STRUCTURED_TUTORING_ENGINE: AI response: {openai_response}")
                    
                    # Override with problem-consistent response
                    clean_response = f"Let me help you with the original problem: {problem.description}. What specific part would you like guidance on?"
                    return clean_response, ["Prevented requirement invention - redirected to original problem"], False
                
                # Clean up the response by removing the prefix
                if openai_response.startswith("CORRECT:"):
                    clean_response = openai_response[8:].strip()
                elif openai_response.startswith("ISSUE:"):
                    clean_response = openai_response[6:].strip()
                else:
                    clean_response = openai_response
                    # If no prefix, assume it's correct if it contains encouraging words
                    encouraging_words = ["excellent", "great", "good work", "correct", "well done", "perfect"]
                    is_correct = any(word in openai_response.lower() for word in encouraging_words)
                
                logger.info(f"🎯 STRUCTURED_TUTORING_ENGINE: Solution is correct: {is_correct}")
                
                # Apply formatting to the response
                formatted_response = format_response(clean_response)
                
                return formatted_response, ["Dynamic code analysis via OpenAI"], is_correct
            else:
                logger.error(f"❌ STRUCTURED_TUTORING_ENGINE: OpenAI API error in code analysis: {response.get('error', 'Unknown error')}")
                # Fallback to static analysis only on API failure
                issues = self._analyze_code_issues(code, problem)
                if not issues:
                    fallback_response = "Your code looks good! Try running it and see if it works as expected."
                    return format_response(fallback_response), ["Fallback: Code analysis looks correct"], True
                else:
                    primary_issue = issues[0]
                    hint = self._get_hint_for_issue(primary_issue)
                    return format_response(hint), [f"Fallback: Detected issue: {primary_issue}"], False
                
        except Exception as e:
            logger.error(f"❌ STRUCTURED_TUTORING_ENGINE: Exception in code analysis OpenAI call: {e}")
            # Fallback to static analysis on exception
            issues = self._analyze_code_issues(code, problem)
            if not issues:
                exception_response = "Your code looks good! Try running it and see if it works as expected."
                return format_response(exception_response), ["Exception fallback: Code analysis looks correct"], True
            else:
                primary_issue = issues[0]
                hint = self._get_hint_for_issue(primary_issue)
                return format_response(hint), [f"Exception fallback: Detected issue: {primary_issue}"], False
    
    async def _provide_guided_help(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage], curriculum_content: str = "") -> str:
        """Provide guided help when student is stuck - break problem down"""
        
        # Count how many times student has asked for help recently
        help_requests = 0
        help_indicators = [
            'help', 'hint', 'stuck', 'don\'t understand', 'unable to think', 'confused',
            'not getting it', 'can\'t figure', 'don\'t know', 'no idea', 'lost',
            'struggling', 'difficult', 'can you help', 'give me', 'show me'
        ]
        
        # Look at recent user messages (last 6 messages)
        recent_user_messages = [msg for msg in conversation_history[-6:] if msg.message_type == MessageType.USER]
        for msg in recent_user_messages:
            if any(indicator in msg.content.lower() for indicator in help_indicators):
                help_requests += 1
        
        logger.info(f"🆘 STRUCTURED_TUTORING_ENGINE: Student help requests count: {help_requests}")
        
        # Create dynamic guidance based on the specific problem and help request count
        hint_level = "basic" if help_requests <= 1 else "intermediate" if help_requests == 2 else "specific"
        
        system_prompt = f"""You are helping a student who is stuck on this EXACT problem:

CURRICULUM CONTENT THAT HAS BEEN TAUGHT TO STUDENTS:
{curriculum_content}

IMPORTANT: Use the curriculum content above as context for what students have already learned. Reference specific concepts, examples, and terminology from the curriculum when providing guidance.

**Problem Title:** {problem.title}
**Problem Description:** {problem.description}
**Required Concepts:** {', '.join(problem.concepts) if problem.concepts else 'Not specified'}

The student said: "{user_input}"
**Student has asked for help {help_requests} times - provide {hint_level} level guidance**

INSTRUCTIONS:
- This is the student's {help_requests}{'st' if help_requests == 1 else 'nd' if help_requests == 2 else 'rd' if help_requests == 3 else 'th'} request for help
- Break down the ORIGINAL problem into smaller, manageable steps
- Focus ONLY on the requirements stated in the problem description above
- Do NOT add new requirements or change what the problem asks for
- Give encouraging, step-by-step guidance
- Keep response to 2-3 sentences maximum

FORMATTING REQUIREMENTS:
- Use **bold headings** for sections (e.g., **Let's break this down:**)
- Use numbered lists (1., 2., 3.) for steps
- Use proper spacing between sections
- End with **Your Turn:** and a guiding question

PROGRESSIVE HINT STRATEGY:
- 1st request (basic): Ask guiding questions about approach
- 2nd request (intermediate): Give more concrete direction about what to create/use
- 3rd+ request (specific): Provide specific step-by-step breakdown with concrete examples

EXAMPLE BREAKDOWNS:

**For "Create a list with user input" problems:**
"Let's break this down step by step. First, you'll need an empty list to store the numbers. Then, you'll need a way to repeat the input process multiple times. What do you think would be a good way to repeat something in Python?"

**For "Calculate sum of numbers" problems:**
"Let's tackle this one step at a time. You'll need a variable to keep track of the running total, and a way to go through each number in the list. What should be the starting value of your sum variable?"

**For "Print even numbers" problems:**
"Let's break this into smaller parts. First, you need to check each number from 1 to 10. Then, for each number, you need to determine if it's even. What mathematical operation could help you check if a number is even?"

**For "String length" problems:**
"Let's simplify this. The problem is asking you to count something about the string. What exactly do you think 'length' means when we talk about strings in programming?"

**For "Find maximum/minimum" problems:**
BASIC (1st request): "Let's break this down step by step. To find the max and min, you need to compare numbers with each other. What would be a good starting point - maybe assume the first number is both the max and min, then compare the rest?"

INTERMEDIATE (2nd request): "You'll need two variables: one to track the maximum value and one for the minimum. Start by setting both to the first number in your list. Then, loop through the remaining numbers comparing each one to your current max and min."

SPECIFIC (3rd+ request): "Here's the approach: Create variables like 'max_num = numbers[0]' and 'min_num = numbers[0]'. Then use a for loop to go through numbers[1:]. For each number, use 'if number > max_num: max_num = number' and similar for min_num."

**For "Find largest/smallest" problems:**
BASIC (1st request): "Think about this logically: if you were looking through a list of numbers with your eyes, how would you find the biggest one? You'd compare each number to remember the largest so far, right? What variable could help you 'remember' the largest number as you go through the list?"

INTERMEDIATE (2nd request): "You need a variable to 'remember' the largest number you've seen so far. Start with the first number as your 'largest', then check each remaining number - if it's bigger than your current 'largest', update it."

SPECIFIC (3rd+ request): "Try this structure: 'largest = numbers[0]', then 'for num in numbers[1:]:', then inside the loop 'if num > largest: largest = num'. Finally print the largest value."

Provide encouraging, step-by-step guidance for the ORIGINAL problem:"""
        
        try:
            # Create a user message for the guidance request
            user_message = ConversationMessage(
                timestamp=datetime.utcnow(),
                message_type=MessageType.USER,
                content=f"Student needs help: '{user_input}'"
            )
            
            response = await self.openai_client.generate_response(
                messages=[user_message],
                system_prompt=system_prompt,
                max_tokens=150,
                temperature=0.3
            )
            
            if response["success"]:
                return response["content"].strip()
            else:
                # Fallback to simple breakdown
                return f"Let's break down this problem step by step: {problem.description}. What do you think should be your first step?"
                
        except Exception as e:
            logger.error(f"Error in guided help: {e}")
            return f"Let's work through this problem together: {problem.description}. What part would you like me to help you understand?"
    
    async def _guide_with_questions(self, user_input: str, problem: Problem, curriculum_content: str = "") -> str:
        """Guide student with questions rather than answers"""
        
        logger.info("🔮 STRUCTURED_TUTORING_ENGINE: _guide_with_questions called")
        logger.info(f"💬 STRUCTURED_TUTORING_ENGINE: Guiding for input: '{user_input}'")
        logger.info(f"📚 STRUCTURED_TUTORING_ENGINE: Problem: {problem.title if problem else 'None'}")
        
        # Check if student is submitting code without logic approval - STRICT BLOCK
        code_indicators = ['=', 'for ', 'while ', 'if ', 'def ', 'print(', 'input(', 'append(', 'range(', 'import ', 'from ', 'class ', 'try:', 'except:', 'len(']
        if any(indicator in user_input for indicator in code_indicators):
            # ABSOLUTELY NO code analysis - return strict redirect
            logger.warning(f"🚫 STRUCTURED_TUTORING_ENGINE: Code detected in _guide_with_questions - blocking!")
            return "I cannot analyze or discuss your code until you first explain your approach in natural language. Please describe your step-by-step thinking process for solving this problem in plain English, without any code."
        
        # Use OpenAI with the structured system prompt to generate a guiding question
        system_prompt = f"""You are guiding a student through this EXACT problem:

CURRICULUM CONTENT THAT HAS BEEN TAUGHT TO STUDENTS:
{curriculum_content}

IMPORTANT: Use the curriculum content above as context for what students have already learned. Reference specific concepts, examples, and terminology from the curriculum when asking guiding questions.

**Problem Title:** {problem.title}
**Problem Description:** {problem.description}
**Required Concepts:** {', '.join(problem.concepts) if problem.concepts else 'Not specified'}

The student said: "{user_input}"

CRITICAL INSTRUCTIONS:
- ONLY guide them toward solving THE EXACT PROBLEM DESCRIBED ABOVE
- Do NOT invent or suggest new requirements that aren't in the problem description
- Do NOT change what the problem is asking for
- Ask ONE guiding question that helps them think through the next step for THIS SPECIFIC PROBLEM
- Do NOT provide solutions or direct answers
- Focus on helping them understand the ORIGINAL problem requirements

FORBIDDEN:
- Do NOT suggest the code should do something different than what the original problem asks
- Do NOT mention requirements like "find maximum/minimum/average" if not in original problem
- Do NOT change the problem scope or requirements

EXAMPLE CONVERSATIONS:

**Scenario 1: Problem - "Create a list with user input"**
Student: "I don't know how to start"
AI: "What do you think you need to create first - an empty list or something else?"

Student: "I need to create an empty list"  
AI: "Great! And how many numbers does the problem ask you to collect from the user?"

Student: "5 numbers"
AI: "Perfect! What kind of loop could you use to repeat the input process 5 times?"

Student: "A for loop with range(5)"
AI: "Excellent thinking! Inside that loop, how would you get a number from the user?"

**Scenario 2: Problem - "Calculate sum of numbers in a list"**
Student: "I want to add all the numbers together"
AI: "Good approach! What variable would you use to keep track of the running total?"

Student: "A sum variable"
AI: "Perfect! What should be the starting value of your sum variable?"

Student: "Zero"
AI: "Exactly! Now, how would you go through each number in the list to add them to your sum?"

**Scenario 3: Problem - "Print even numbers from 1 to 10"**
Student: "How do I check if a number is even?"
AI: "What mathematical operation could you use to determine if a number divides evenly by 2?"

Student: "The modulo operator"
AI: "Great! What would the result of num % 2 be for an even number?"

Student: "It would be 0"
AI: "Perfect! How would you use this in an if statement to only print even numbers?"

**Scenario 4: Problem - "Find the length of a string"**
Student: "I'm confused about this problem"
AI: "What do you think 'length of a string' means in programming?"

Student: "The number of characters?"
AI: "Exactly right! What Python function could help you count the characters in a string?"

**Scenario 5: Problem - "Create a list with user input" (Multi-turn example)**
Student: "I don't understand what the problem wants"
AI: "The problem asks you to create a list with user input. What do you think that means?"

Student: "I need to make a list and put numbers in it?"
AI: "Perfect understanding! How many numbers does the problem say you should collect?"

Student: "It says 5 numbers"
AI: "Great! So you need to ask the user for 5 different numbers. What Python function would you use to get input from a user?"

Student: "input()?"
AI: "Exactly! Now, what would happen if you used input() - what type of data does it return?"

Student: "A string?"
AI: "Correct! So if you want to work with numbers, what would you need to do to convert the string input?"

**Scenario 6: Problem - "Calculate sum of numbers in a list" (Multi-turn example)**
Student: "I want to add all numbers together but I'm stuck"
AI: "Good thinking! When you're adding numbers one by one, what variable would help you keep track of the total so far?"

Student: "A sum variable or total variable?"
AI: "Perfect! What should be the starting value of your sum variable before you begin adding?"

Student: "Should it start at 0?"
AI: "Exactly right! Now, how would you go through each number in your list to add them to your sum?"

Student: "Use a for loop?"
AI: "Great approach! In your for loop, what would you do with each number you encounter?"

FORMATTING REQUIREMENTS:
- Use **bold text** for emphasis when appropriate
- Keep responses clear and structured
- Use proper spacing for readability

Respond with a SINGLE guiding question for the ORIGINAL problem only:"""
        
        logger.info("🤖 STRUCTURED_TUTORING_ENGINE: Calling OpenAI for guiding question...")
        
        try:
            # Create a user message for the guiding question request
            user_message = ConversationMessage(
                timestamp=datetime.utcnow(),
                message_type=MessageType.USER,
                content=f"The student said: '{user_input}'"
            )
            
            response = await self.openai_client.generate_response(
                messages=[user_message],
                system_prompt=system_prompt,
                max_tokens=100,
                temperature=0.3
            )
            
            logger.info("📞 STRUCTURED_TUTORING_ENGINE: OpenAI call completed")
            logger.info(f"✅ STRUCTURED_TUTORING_ENGINE: OpenAI success: {response.get('success', False)}")
            
            if response["success"]:
                openai_response = response["content"].strip()
                logger.info(f"🎯 STRUCTURED_TUTORING_ENGINE: OpenAI response: '{openai_response}'")
                
                # Validate that the questioning doesn't invent new requirements
                problematic_keywords = [
                    "maximum", "minimum", "average", "mean", "median", "mode",
                    "sort", "reverse", "find the largest", "find the smallest",
                    "calculate", "compute", "determine"
                ]
                
                # Check if AI is inventing requirements not in the original problem
                original_problem_lower = problem.description.lower()
                response_lower = openai_response.lower()
                
                invented_requirements = []
                for keyword in problematic_keywords:
                    if keyword in response_lower and keyword not in original_problem_lower:
                        invented_requirements.append(keyword)
                
                if invented_requirements:
                    logger.warning(f"🚨 STRUCTURED_TUTORING_ENGINE: Questioning invented requirements: {invented_requirements}")
                    logger.warning(f"📚 STRUCTURED_TUTORING_ENGINE: Original problem: {problem.description}")
                    logger.warning(f"🤖 STRUCTURED_TUTORING_ENGINE: AI response: {openai_response}")
                    
                    # Override with problem-consistent question
                    return f"Let's focus on the original problem: {problem.description}. What part of this problem would you like help understanding?"
                
                return openai_response
            else:
                logger.error(f"❌ STRUCTURED_TUTORING_ENGINE: OpenAI API error: {response.get('error', 'Unknown error')}")
                logger.error("🚨 STRUCTURED_TUTORING_ENGINE: Returning fallback response")
                return f"Can you think about what this problem is asking you to do: {problem.description}?"
                
        except Exception as e:
            logger.error(f"❌ STRUCTURED_TUTORING_ENGINE: Exception in OpenAI call: {e}")
            logger.error("🚨 STRUCTURED_TUTORING_ENGINE: Returning fallback response due to exception")
            return "Can you think about what the problem is asking you to do step by step?"

    async def _generate_logic_inquiry(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage], curriculum_content: str = "") -> str:
        """Generate logic inquiry response via OpenAI with emphasis on natural language explanation"""
        
        try:
            from app.services.openai_client import openai_client
            
            # Build conversation context
            conversation_context = "\n".join([
                f"{msg.message_type.value}: {msg.content}" 
                for msg in conversation_history[-6:]  # Last 6 messages for context
            ])
            
            prompt = f"""You are an AI tutor helping a student learn programming. The student has just seen this problem:

CURRICULUM CONTENT THAT HAS BEEN TAUGHT TO STUDENTS:
{curriculum_content}

IMPORTANT: Use the curriculum content above as context for what students have already learned.

Problem: {problem.title}
Description: {problem.description}

Recent conversation:
{conversation_context}

Student's latest response: "{user_input}"

CRITICAL: The student must explain their logic in NATURAL LANGUAGE FIRST before writing any code.

Generate a response that:
1. Asks the student to explain their approach in plain English
2. Emphasizes NO CODE should be used in the explanation
3. Asks them to think through the step-by-step logic

EXAMPLE RESPONSE:
"Great! I can see you understand the problem. Now, before we write any code, please explain your approach in natural language only. How are you thinking to solve this step by step? Please don't use any code language - just describe your logic in plain English."

Do NOT allow code. Focus on getting their thinking process first."""

            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful programming tutor who requires logic explanation before code."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            else:
                return "How are you thinking to solve this problem? Please explain your logic in natural language first - no code."
                
        except Exception as e:
            logger.error(f"❌ Error generating logic inquiry: {e}")
            return "How are you thinking to solve this problem? Please explain your logic in natural language first - no code."
    
    async def _validate_logic_explanation(
        self, 
        logic_explanation: str, 
        problem: Problem, 
        conversation_history: List[ConversationMessage],
        user_id: str,
        curriculum_content: str = ""
    ) -> Tuple[str, List[str], bool]:
        """Enhanced logic validation using comprehensive cross-questioning and anti-gaming measures
        
        Returns:
            Tuple[str, List[str], bool]: (response_text, teaching_notes, is_logic_correct)
        """
        
        logger.info("🔍 ENHANCED_LOGIC_VALIDATION: Starting validation process")
        logger.info(f"💭 ENHANCED_LOGIC_VALIDATION: Logic: '{logic_explanation[:100]}...'")
        logger.info(f"📚 ENHANCED_LOGIC_VALIDATION: Problem: {problem.title}")
        
        try:
            # Get or initialize validation state for this user session
            session_key = f"{user_id}_{problem.number}"
            
            if session_key not in self.validation_states:
                self.validation_states[session_key] = {
                    'current_level': LogicValidationLevel.INITIAL_REQUEST,
                    'strictness_level': StrictnessLevel.LENIENT,
                    'attempt_count': 0
                }
            
            validation_state = self.validation_states[session_key]
            validation_state['attempt_count'] += 1
            
            # Use enhanced logic validator
            validation_result = await self.enhanced_logic_validator.validate_logic_explanation(
                student_response=logic_explanation,
                problem=problem,
                conversation_history=conversation_history,
                current_level=validation_state['current_level'],
                strictness_level=validation_state['strictness_level']
            )
            
            # Update validation state
            validation_state['current_level'] = validation_result.validation_level
            validation_state['strictness_level'] = validation_result.strictness_level
            
            # Log validation results
            logger.info(f"🎯 ENHANCED_LOGIC_VALIDATION: Approved: {validation_result.is_approved}")
            logger.info(f"📊 ENHANCED_LOGIC_VALIDATION: Level: {validation_result.validation_level.value}")
            logger.info(f"🔒 ENHANCED_LOGIC_VALIDATION: Strictness: {validation_result.strictness_level.value}")
            logger.info(f"📈 ENHANCED_LOGIC_VALIDATION: Confidence: {validation_result.confidence_score}")
            
            # Handle gaming detection
            if validation_result.validation_level == LogicValidationLevel.GAMING_DETECTED:
                logger.warning(f"🚫 ENHANCED_LOGIC_VALIDATION: Gaming detected: {validation_result.gaming_indicators}")
                return (
                    format_response(validation_result.feedback_message),
                    ["GAMING_DETECTED", f"Evidence: {validation_result.gaming_indicators}"],
                    False
                )
            
            # Handle logic approval
            if validation_result.is_approved:
                logger.info("✅ ENHANCED_LOGIC_VALIDATION: Logic approved - ready for coding")
                # Clear validation state after approval
                if session_key in self.validation_states:
                    del self.validation_states[session_key]
                
                return (
                    format_response(validation_result.feedback_message),
                    ["ENHANCED_VALIDATION_APPROVED", f"Confidence: {validation_result.confidence_score}"],
                    True
                )
            
            # Handle continued validation with cross-questioning
            else:
                logger.info(f"🔄 ENHANCED_LOGIC_VALIDATION: Continuing validation at level {validation_result.validation_level.value}")
                
                # Add cross-questions to feedback if available
                enhanced_feedback = validation_result.feedback_message
                if validation_result.cross_questions:
                    enhanced_feedback += "\n\nPlease answer these specific questions:\n"
                    for i, question in enumerate(validation_result.cross_questions, 1):
                        enhanced_feedback += f"{i}. {question}\n"
                
                teaching_notes = [
                    f"ENHANCED_VALIDATION_{validation_result.validation_level.value.upper()}",
                    f"Strictness: {validation_result.strictness_level.value}",
                    f"Missing: {validation_result.missing_elements}",
                    f"Attempt: {validation_state['attempt_count']}"
                ]
                
                return (
                    format_response(enhanced_feedback),
                    teaching_notes,
                    False
                )
                
        except Exception as e:
            logger.error(f"❌ ENHANCED_LOGIC_VALIDATION: Exception: {e}")
            # Fallback to basic validation
            fallback_response = "I need you to explain your approach in more detail. Please provide a step-by-step explanation of how you plan to solve this problem."
            return (
                format_response(fallback_response), 
                ["ENHANCED_VALIDATION_FALLBACK", f"Error: {str(e)}"], 
                False
            )
    
    async def _generate_code_redirect_response(self, user_input: str, problem: Problem, curriculum_content: str = "") -> str:
        """Generate fresh AI response when student tries to submit code before logic approval"""
        
        try:
            system_prompt = f"""You are an AI tutor helping a student with this programming problem:

CURRICULUM CONTENT:
{curriculum_content}

**Problem:** {problem.title}
**Description:** {problem.description}

The student tried to submit code: "{user_input}"

But they need to explain their logic in natural language FIRST before writing code.

Generate a fresh, encouraging response that:
1. Acknowledges they want to code (don't ignore their attempt)
2. Gently redirects them to explain logic first
3. Shows understanding that they might be eager to code
4. Asks for their thinking process in plain English
5. Be warm and supportive, not robotic

DO NOT use templates or robotic language. Make it feel like a real conversation.

Example variations (don't copy these exactly):
- "I can see you're ready to dive into coding! That's great energy. Before we write the code though, let me understand your thinking process. Can you walk me through how you're planning to solve this step by step?"
- "You're eager to get coding - I love that! But let's make sure we're on the same page with the approach first. In your own words, how do you think we should tackle this problem?"
- "I see you have some code ideas brewing! Before we implement them, help me understand your strategy. What's your game plan for solving this?"

Generate a natural, conversational response:"""
            
            response = await self.openai_client.generate_response(
                messages=[ConversationMessage(
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.USER,
                    content=f"Student submitted code: {user_input}"
                )],
                system_prompt=system_prompt,
                max_tokens=150,
                temperature=0.8  # Higher temperature for more varied responses
            )
            
            if response["success"]:
                return response["content"].strip()
            else:
                # Even fallback should be slightly varied
                fallbacks = [
                    "I can see you're thinking about the code! Before we dive into implementation, can you share your approach with me in plain English?",
                    "You're ready to code - that's awesome! Let's just make sure we have the logic figured out first. How are you thinking about this problem?",
                    "I love the enthusiasm for coding! Before we write it out, help me understand your strategy for solving this."
                ]
                import random
                return random.choice(fallbacks)
                
        except Exception as e:
            logger.error(f"❌ Error generating code redirect response: {e}")
            fallbacks = [
                "I can see you want to code! Let's talk through the logic first though. What's your approach?",
                "Ready to implement? Great! First, walk me through how you're thinking about this problem.",
                "I see those coding wheels turning! Before we write it, what's your strategy here?"
            ]
            import random
            return random.choice(fallbacks)
    
    async def _generate_confusion_response(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage], curriculum_content: str, repetition_info: Dict[str, Any]) -> str:
        """Generate empathetic response when student is repeating messages (indicating confusion)"""
        
        try:
            # Build context of the repetition
            recent_messages = "\n".join([
                f"{msg.message_type.value}: {msg.content}" 
                for msg in conversation_history[-8:]  # More context for confusion
            ])
            
            repetition_count = repetition_info.get('repetition_count', 0)
            
            system_prompt = f"""You are an AI tutor. The student has repeated similar messages {repetition_count} times, which indicates they might be confused or not understanding your previous responses.

CURRICULUM CONTENT:
{curriculum_content}

**Problem:** {problem.title}
**Description:** {problem.description}

**Recent conversation:**
{recent_messages}

**Current repeated input:** "{user_input}"

The student is clearly confused or not getting what they need. Generate a fresh, empathetic response that:

1. Acknowledges they might be confused ("I notice you're trying this again...")
2. Shows understanding and empathy
3. Offers a different approach or explanation
4. Asks if they need clarification on something specific
5. Maybe breaks down the request differently
6. Be genuinely helpful, not robotic

DO NOT repeat previous responses. Make this feel like a real teacher noticing a student's confusion.

Example approaches (don't copy exactly):
- "I notice you're sharing the same code again - it seems like my previous response might not have been clear. Let me try a different way..."
- "I can see this might be confusing. Let me step back and explain what I'm looking for differently..."
- "It looks like we might be talking past each other. Are you unsure about what I mean by 'logic explanation'?"

Generate a genuinely empathetic, fresh response:"""
            
            response = await self.openai_client.generate_response(
                messages=[ConversationMessage(
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.USER,
                    content=f"Student is repeating: {user_input}"
                )],
                system_prompt=system_prompt,
                max_tokens=200,
                temperature=0.9  # Even higher temperature for empathetic, varied responses
            )
            
            if response["success"]:
                return response["content"].strip()
            else:
                # Varied empathetic fallbacks
                fallbacks = [
                    "I notice you're trying the same approach again. Let me be clearer about what I need - can you tell me in your own words, without any code, how you would solve this problem if you were explaining it to a friend?",
                    "It seems like my previous response wasn't helpful. Let me try differently - instead of code, I'd love to hear your thought process. What's your plan for tackling this?",
                    "I can see this might be confusing! When I ask for 'logic,' I mean: can you describe your solution strategy in plain English, like you're explaining it to someone who doesn't know programming?"
                ]
                import random
                return random.choice(fallbacks)
                
        except Exception as e:
            logger.error(f"❌ Error generating confusion response: {e}")
            fallbacks = [
                "I notice we might be going in circles. Is there something specific you're unsure about? I'm here to help clarify!",
                "Let me try a different approach - what part of this problem is most confusing to you right now?",
                "I can see this might not be clicking. What questions do you have about what I'm asking for?"
            ]
            import random
            return random.choice(fallbacks)
    
    async def _generate_approach_inquiry(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage], curriculum_content: str = "") -> str:
        """Generate approach inquiry response via OpenAI (legacy method)"""
        
        try:
            from app.services.openai_client import openai_client
            
            # Build conversation context
            conversation_context = "\n".join([
                f"{msg.message_type.value}: {msg.content}" 
                for msg in conversation_history[-6:]  # Last 6 messages for context
            ])
            
            prompt = f"""You are an AI tutor helping a student learn programming. The student has just seen this problem:

CURRICULUM CONTENT THAT HAS BEEN TAUGHT TO STUDENTS:
{curriculum_content}

IMPORTANT: Use the curriculum content above as context for what students have already learned. Reference specific concepts, examples, and terminology from the curriculum when asking questions.

Problem: {problem.title}
Description: {problem.description}

Recent conversation:
{conversation_context}

Student's latest response: "{user_input}"

Generate a response that asks the student how they're thinking about approaching this problem. Be encouraging and guide them to think through their approach.

STRUCTURE YOUR RESPONSE LIKE THIS:
**[Encouraging statement]:** [Brief comment about the problem]

**Your Turn:** [Specific guiding question about their approach]

EXAMPLES:
"**Great!** This problem asks you to calculate the average of numbers in a list.

**Your Turn:** What do you think are the main steps needed to calculate an average?"

"**Perfect!** You're working on finding maximum and minimum values.

**Your Turn:** How do you think you could compare numbers to find the largest one?"

Do NOT give away the solution. Ask them about their thinking process."""

            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful programming tutor who guides students to discover solutions themselves."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            else:
                return "How are you thinking about approaching this problem?"
                
        except Exception as e:
            logger.error(f"❌ Error generating approach inquiry: {e}")
            return "How are you thinking about approaching this problem?"

    async def _generate_transition_acknowledgment(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage]) -> str:
        """Generate transition acknowledgment via OpenAI"""
        
        try:
            from app.services.openai_client import openai_client
            
            prompt = f"""You are an AI tutor. The student just completed a problem and said: "{user_input}"

They want to move to the next problem. Generate a brief, encouraging response that acknowledges their readiness and transitions them to the next problem. 

Keep it very short (1 sentence) and positive. Something like "Great! Let's move to the next problem." but make it feel natural and encouraging."""

            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": "You are an encouraging programming tutor."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.5
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            else:
                return "Great! Let's move to the next problem."
                
        except Exception as e:
            logger.error(f"❌ Error generating transition acknowledgment: {e}")
            return "Great! Let's move to the next problem."

    async def _generate_celebration_response(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage]) -> str:
        """Generate celebration response via OpenAI"""
        
        try:
            from app.services.openai_client import openai_client
            
            prompt = f"""You are an AI tutor. The student just completed a programming problem successfully. They said: "{user_input}"

Generate an encouraging celebration response that:
1. Acknowledges their success
2. Asks if they're ready for the next problem

FORMATTING REQUIREMENTS:
- Use **bold text** for emphasis and excitement (e.g., **Excellent work!**)
- Keep responses clear and celebratory
- Use proper spacing for readability

Keep it positive and motivating. Examples: "**Excellent work!** You've solved it correctly. Ready for the next problem?" but make it feel natural and personalized."""

            response = await openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an encouraging programming tutor who celebrates student success."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.6
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            else:
                return "Excellent work! You've solved it correctly. Ready for the next problem?"
                
        except Exception as e:
            logger.error(f"❌ Error generating celebration response: {e}")
            return "Excellent work! You've solved it correctly. Ready for the next problem?"
    
    async def _provide_curriculum_information(self, user_input: str, curriculum_content: str) -> str:
        """Provide direct curriculum information when students ask about learning topics"""
        
        if not curriculum_content:
            return "I don't have specific curriculum content available right now, but I'm here to help you with your current programming problems. What would you like to work on?"
        
        try:
            # Use OpenAI to extract and present curriculum topics in a student-friendly way
            response = await openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a helpful programming tutor. The student is asking about the curriculum topics they have learned. 

CURRICULUM CONTENT:
{curriculum_content}

Provide a clear, organized summary of the topics covered in the curriculum. Be encouraging and connect it to their current learning journey.

FORMATTING REQUIREMENTS:
- Use **bold headings** for main sections (e.g., **Based on the curriculum, here are the main topics we've covered:**)
- Use bullet points (•) for topic lists
- Use proper spacing between sections
- End with an encouraging question about what they'd like to focus on

Student's question: {user_input}"""
                    },
                    {
                        "role": "user",
                        "content": user_input
                    }
                ],
                max_tokens=400,
                temperature=0.3
            )
            
            if response and response.choices:
                return response.choices[0].message.content.strip()
            else:
                # Fallback: extract basic topics from curriculum content
                return self._extract_basic_curriculum_topics(curriculum_content)
                
        except Exception as e:
            logger.error(f"❌ Error providing curriculum information: {e}")
            return self._extract_basic_curriculum_topics(curriculum_content)
    
    def _extract_basic_curriculum_topics(self, curriculum_content: str) -> str:
        """Fallback method to extract basic topics from curriculum content"""
        
        if not curriculum_content:
            return "I don't have specific curriculum information available, but I'm here to help you with your programming questions!"
        
        # Basic extraction of topics from curriculum content
        lines = curriculum_content.split('\n')
        topics = []
        
        for line in lines:
            line = line.strip()
            # Look for headers, bullet points, or numbered items
            if line.startswith('#') or line.startswith('-') or line.startswith('*'):
                topics.append(line.replace('#', '').replace('-', '').replace('*', '').strip())
            elif any(keyword in line.lower() for keyword in ['variables', 'loops', 'functions', 'lists', 'dictionaries', 'classes']):
                topics.append(line.strip())
        
        if topics:
            topic_list = '\n'.join([f"• {topic}" for topic in topics[:10]])  # Limit to first 10 topics
            return f"**Based on the curriculum, here are the main topics we've covered:**\n\n{topic_list}\n\nIs there a specific topic you'd like to review or practice?"
        else:
            return f"**Here's what we've been learning:**\n\n{curriculum_content[:300]}...\n\nWhat specific topic would you like to work on?"
    
    async def _generate_strict_logic_redirect_response(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage], curriculum_content: str = "", repetition_info: Dict[str, Any] = None) -> str:
        """Generate STRICT redirect when student tries code before logic approval - NO code analysis"""
        
        try:
            repetition_count = repetition_info.get('repetition_count', 0) if repetition_info else 0
            is_repeating = repetition_count >= 2
            
            system_prompt = f"""CRITICAL RULE ENFORCEMENT: The student is repeatedly trying to submit code WITHOUT explaining their logic first.

**Problem:** {problem.title}
**Repetition count:** {repetition_count}
**This is attempt #{repetition_count + 1} at submitting code without logic**

ABSOLUTE REQUIREMENTS:
- COMPLETELY IGNORE any code they submitted - do not reference it at all
- DO NOT analyze, discuss, or provide feedback on code
- DO NOT give hints about programming concepts
- DO NOT suggest improvements to their code
- DO NOT mention what their code does or tries to do
- ONLY focus on requiring natural language logic explanation

Response must:
1. Be firm but encouraging about the logic-first rule
2. {'Acknowledge their persistence but maintain the boundary' if is_repeating else 'Clearly state the requirement'}
3. Explain that logic must come before code - no exceptions
4. Ask specifically for their step-by-step thinking in plain English
5. Not mention their code submission at all

{'EXTRA FIRM: This is repeated behavior - be more insistent about the rule' if is_repeating else 'First reminder - be encouraging but clear'}

Generate ONLY a logic-first enforcement response:"""
            
            response = await self.openai_client.generate_response(
                messages=[ConversationMessage(
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.USER,
                    content=f"Student submitted code without logic: {user_input}"
                )],
                system_prompt=system_prompt,
                max_tokens=150,
                temperature=0.8
            )
            
            if response["success"]:
                return response["content"].strip()
            else:
                if is_repeating:
                    fallbacks = [
                        "I understand you want to code, but I really need your thinking process in plain English first. What's your strategy for solving this problem?",
                        "I see we keep coming back to this. Before any code, please explain your approach in natural language. How do you plan to tackle this?",
                        "I know this might feel repetitive, but getting your logic clear first is crucial. Can you walk me through your thinking?"
                    ]
                else:
                    fallbacks = [
                        "Before we look at any code, I need to understand your approach. Can you explain your strategy in plain English?",
                        "Let's start with your logic first. How are you thinking about solving this problem step by step?",
                        "I need your natural language explanation before we code. What's your game plan for this problem?"
                    ]
                import random
                return random.choice(fallbacks)
                
        except Exception as e:
            logger.error(f"❌ Error generating strict logic redirect: {e}")
            fallbacks = [
                "I need your logic explanation in natural language first. How are you planning to solve this?",
                "Before any code, please explain your approach in plain English.",
                "Let's get your thinking process first. What's your strategy?"
            ]
            import random
            return random.choice(fallbacks)
    
    async def _generate_strict_no_code_response(self, logic_with_code: str, problem: Problem, curriculum_content: str) -> str:
        """Generate strict response when student includes code in logic explanation"""
        
        try:
            system_prompt = f"""The student is trying to explain their logic but included code snippets.

Problem: {problem.title}
Student's mixed response: "{logic_with_code}"

Generate a response that:
1. Acknowledges they're trying to explain their approach
2. Firmly but kindly asks for ONLY natural language
3. Explains why we need pure logic explanation
4. Is encouraging but clear about the requirement

DO NOT analyze any code they provided. Focus only on getting pure natural language logic.

Generate an encouraging but firm response:"""
            
            response = await self.openai_client.generate_response(
                messages=[ConversationMessage(
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.USER,
                    content=f"Mixed logic and code: {logic_with_code}"
                )],
                system_prompt=system_prompt,
                max_tokens=150,
                temperature=0.8
            )
            
            if response["success"]:
                return response["content"].strip()
            else:
                fallbacks = [
                    "I can see you're thinking through this! But I need your explanation in pure natural language - no code at all. Can you describe your approach using only plain English?",
                    "You're on the right track with your thinking! However, please explain your strategy without any code. How would you describe your approach to a friend?",
                    "I see your logic forming! But let's keep it in natural language only. Can you walk me through your thinking using just words?"
                ]
                import random
                return random.choice(fallbacks)
                
        except Exception as e:
            logger.error(f"❌ Error generating strict no-code response: {e}")
            fallbacks = [
                "Please explain your approach using only natural language - no code. How are you thinking about this?",
                "I need your logic in plain English only. Can you describe your strategy without any code?",
                "Let's keep it to natural language. How would you explain your approach to someone?"
            ]
            import random
            return random.choice(fallbacks)
    
    async def _generate_logic_confusion_response(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage], curriculum_content: str, repetition_info: Dict[str, Any]) -> str:
        """Generate empathetic response when student repeats logic attempts"""
        
        try:
            recent_messages = "\n".join([
                f"{msg.message_type.value}: {msg.content}" 
                for msg in conversation_history[-6:]
            ])
            
            system_prompt = f"""The student has been trying to explain their logic multiple times but seems confused.

CURRICULUM CONTENT:
{curriculum_content}

**Problem:** {problem.title}
**Description:** {problem.description}

**Recent conversation:**
{recent_messages}

**Latest attempt:** "{user_input}"

Generate a fresh, empathetic response that:
1. Acknowledges they're trying hard
2. Offers a different way to think about the problem
3. Maybe gives a simple example or breaks it down differently
4. Shows patience and understanding
5. Asks a more specific question to help them

Be genuinely helpful and encouraging, not robotic."""
            
            response = await self.openai_client.generate_response(
                messages=[ConversationMessage(
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.USER,
                    content=f"Student repeating logic: {user_input}"
                )],
                system_prompt=system_prompt,
                max_tokens=200,
                temperature=0.9
            )
            
            if response["success"]:
                return response["content"].strip()
            else:
                fallbacks = [
                    "I can see you're working hard on this! Let me try asking this differently - if you had to explain this problem to a friend who's never programmed before, what would you tell them?",
                    "You're putting in great effort! Maybe we can approach this from a different angle. What do you think is the very first thing you'd need to do to solve this problem?",
                    "I appreciate your persistence! Let's break this down even more. What's the main goal of this problem in the simplest terms?"
                ]
                import random
                return random.choice(fallbacks)
                
        except Exception as e:
            logger.error(f"❌ Error generating logic confusion response: {e}")
            fallbacks = [
                "I can see this is challenging! Let's try a different approach. What's the first step you think we need to take?",
                "You're really trying hard! Can you tell me what part of this problem feels most confusing to you?",
                "Let me help differently - what do you think this problem is asking you to do in the simplest terms?"
            ]
            import random
            return random.choice(fallbacks)
    
    async def _generate_logic_approval_response(self, user_input: str, problem: Problem, curriculum_content: str) -> str:
        """Generate fresh approval response when logic is correct"""
        
        try:
            system_prompt = f"""The student provided good logic for this problem:

Problem: {problem.title}
Student's logic: "{user_input}"

Generate a fresh, encouraging response that:
1. Specifically acknowledges what they got right
2. Shows enthusiasm for their thinking
3. Transitions them naturally to coding
4. Feels genuine and personal, not templated

Example variations (don't copy exactly):
- "Excellent thinking! I love how you broke that down step by step. Now let's see that logic in action - write the code!"
- "Perfect approach! You've got the strategy down solid. Time to turn those ideas into Python code!"
- "Spot on! Your logic is exactly right. Now comes the fun part - implementing it!"

Generate a natural, enthusiastic approval:"""
            
            response = await self.openai_client.generate_response(
                messages=[ConversationMessage(
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.USER,
                    content=f"Approve this logic: {user_input}"
                )],
                system_prompt=system_prompt,
                max_tokens=100,
                temperature=0.8
            )
            
            if response["success"]:
                return response["content"].strip()
            else:
                fallbacks = [
                    "Excellent logic! Now let's bring that thinking to life with code.",
                    "Perfect approach! Time to implement those ideas.",
                    "Great thinking! Now show me how that looks in Python.",
                    "Spot on! Let's code that strategy up."
                ]
                import random
                return random.choice(fallbacks)
                
        except Exception as e:
            logger.error(f"❌ Error generating logic approval response: {e}")
            fallbacks = [
                "Fantastic logic! Let's see it in code now.",
                "Great approach! Time to implement it.",
                "Perfect thinking! Now code it up."
            ]
            import random
            return random.choice(fallbacks)
    
    async def _generate_general_confusion_response(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage], curriculum_content: str, repetition_info: Dict[str, Any], current_mode: TutoringMode) -> str:
        """Generate empathetic response for any type of repetition/confusion"""
        
        try:
            recent_messages = "\n".join([
                f"{msg.message_type.value}: {msg.content}" 
                for msg in conversation_history[-6:]
            ])
            
            repetition_count = repetition_info.get('repetition_count', 0)
            
            system_prompt = f"""The student has repeated similar messages {repetition_count} times, showing confusion.

CURRICULUM CONTENT:
{curriculum_content}

**Problem:** {problem.title}
**Current tutoring mode:** {current_mode.value}

**Recent conversation:**
{recent_messages}

**Repeated input:** "{user_input}"

Generate a fresh, empathetic response that:
1. Acknowledges the repetition with understanding
2. Offers help in a different way
3. Asks what specifically is confusing
4. Shows patience and support
5. Suggests a different approach or clarification

Be genuinely helpful, warm, and understanding. Not robotic or templated."""
            
            response = await self.openai_client.generate_response(
                messages=[ConversationMessage(
                    timestamp=datetime.utcnow(),
                    message_type=MessageType.USER,
                    content=f"General repetition: {user_input}"
                )],
                system_prompt=system_prompt,
                max_tokens=200,
                temperature=0.9
            )
            
            if response["success"]:
                return response["content"].strip()
            else:
                fallbacks = [
                    "I notice we're going in circles a bit. What part of this is most confusing? I'm here to help!",
                    "Let me try helping in a different way. What specific part would you like me to clarify?",
                    "I can see this might be frustrating. What questions do you have? Let's work through this together."
                ]
                import random
                return random.choice(fallbacks)
                
        except Exception as e:
            logger.error(f"❌ Error generating general confusion response: {e}")
            fallbacks = [
                "I notice you might be stuck. What can I help clarify?",
                "Let's try a different approach. What's most confusing right now?",
                "I'm here to help! What questions do you have?"
            ]
            import random
            return random.choice(fallbacks)
    
    
    # ==== PHASE 5: CODE IMPLEMENTATION PHASE HANDLERS ====
    
    async def _generate_coding_phase_start(
        self, 
        user_input: str, 
        problem: Problem, 
        conversation_history: List[ConversationMessage],
        curriculum_content: str
    ) -> str:
        """Generate the start of Phase 5 coding phase with leading questions"""
        
        # Get approved logic from conversation history
        approved_logic = self._extract_approved_logic(conversation_history)
        
        # Use code implementation validator to start guided discovery
        try:
            validation_result = await self.code_implementation_validator.validate_code_implementation(
                student_code="",  # No code yet
                approved_logic=approved_logic,
                problem=problem,
                conversation_history=conversation_history,
                current_level=CodeValidationLevel.READY_FOR_CODING
            )
            
            response = validation_result.feedback_message
            if validation_result.leading_questions:
                response += "\n\n" + "\n".join(f"• {q}" for q in validation_result.leading_questions)
            
            return response
            
        except Exception as e:
            logger.error(f"❌ Error starting coding phase: {e}")
            return "Perfect! Your logic is approved. Now let's implement it step by step. What's the very first line of code you need to write?"
    
    async def _handle_leading_questions_mode(
        self,
        user_input: str,
        problem: Problem,
        conversation_history: List[ConversationMessage],
        current_state: StudentState,
        curriculum_content: str
    ) -> Tuple[str, str, StudentState]:
        """Handle leading questions mode - guide with discovery questions"""
        
        approved_logic = self._extract_approved_logic(conversation_history)
        
        # Check if user submitted code
        if self._contains_code(user_input):
            # Move to code submission handling
            return await self._handle_code_submission(
                user_input, problem, conversation_history, approved_logic, curriculum_content
            )
        
        # Continue with leading questions
        try:
            validation_result = await self.code_implementation_validator.validate_code_implementation(
                student_code=user_input,
                approved_logic=approved_logic,
                problem=problem,
                conversation_history=conversation_history,
                current_level=CodeValidationLevel.GUIDED_DISCOVERY
            )
            
            response = validation_result.feedback_message
            if validation_result.leading_questions:
                response += "\n\n" + "\n".join(f"• {q}" for q in validation_result.leading_questions)
            
            return response, "continue_coding_discovery", StudentState.GUIDED_CODE_DISCOVERY
            
        except Exception as e:
            logger.error(f"❌ Error in leading questions mode: {e}")
            return ("Let's continue step by step. What Python syntax would you use for the first part of your logic?", 
                   "continue_coding_discovery", StudentState.GUIDED_CODE_DISCOVERY)
    
    async def _handle_code_submission(
        self,
        student_code: str,
        problem: Problem,
        conversation_history: List[ConversationMessage],
        approved_logic: str,
        curriculum_content: str
    ) -> Tuple[str, str, StudentState]:
        """Handle when student submits code for the first time"""
        
        try:
            validation_result = await self.code_implementation_validator.validate_code_implementation(
                student_code=student_code,
                approved_logic=approved_logic,
                problem=problem,
                conversation_history=conversation_history,
                current_level=CodeValidationLevel.CODE_SUBMITTED
            )
            
            response = validation_result.feedback_message
            if validation_result.leading_questions:
                response += "\n\n" + "\n".join(f"• {q}" for q in validation_result.leading_questions)
            
            if validation_result.validation_level == CodeValidationLevel.CODE_UNDERSTANDING:
                return response, "explain_code_understanding", StudentState.CODE_UNDERSTANDING
            elif validation_result.validation_level == CodeValidationLevel.LOGIC_ALIGNMENT_CHECK:
                return response, "fix_alignment_issues", StudentState.CODE_ALIGNMENT_CHECK
            else:
                return response, "continue_coding_work", StudentState.GUIDED_CODE_DISCOVERY
                
        except Exception as e:
            logger.error(f"❌ Error handling code submission: {e}")
            return ("I see your code! Let me check how well it matches your approved logic. Give me a moment to analyze it.", 
                   "code_analysis_pending", StudentState.CODE_ALIGNMENT_CHECK)
    
    async def _handle_code_alignment_mode(
        self,
        user_input: str,
        problem: Problem,
        conversation_history: List[ConversationMessage],
        current_state: StudentState,
        curriculum_content: str
    ) -> Tuple[str, str, StudentState]:
        """Handle code-logic alignment checking"""
        
        approved_logic = self._extract_approved_logic(conversation_history)
        student_code = self._extract_latest_code(conversation_history, user_input)
        
        try:
            validation_result = await self.code_implementation_validator.validate_code_implementation(
                student_code=student_code,
                approved_logic=approved_logic,
                problem=problem,
                conversation_history=conversation_history,
                current_level=CodeValidationLevel.LOGIC_ALIGNMENT_CHECK
            )
            
            response = validation_result.feedback_message
            if validation_result.leading_questions:
                response += "\n\n" + "\n".join(f"• {q}" for q in validation_result.leading_questions)
            
            if validation_result.validation_level == CodeValidationLevel.CODE_UNDERSTANDING:
                return response, "verify_understanding", StudentState.CODE_UNDERSTANDING
            else:
                return response, "continue_alignment_work", StudentState.CODE_ALIGNMENT_CHECK
                
        except Exception as e:
            logger.error(f"❌ Error in alignment check: {e}")
            return ("Let's make sure your code matches your approved logic. Can you walk me through how each part of your code implements your plan?", 
                   "explain_code_logic_match", StudentState.CODE_ALIGNMENT_CHECK)
    
    async def _handle_code_guidance_mode(
        self,
        user_input: str,
        problem: Problem,
        conversation_history: List[ConversationMessage],
        current_state: StudentState,
        curriculum_content: str
    ) -> Tuple[str, str, StudentState]:
        """Handle code guidance for fixing issues"""
        
        # This is similar to alignment mode but focuses on helping fix specific issues
        return await self._handle_code_alignment_mode(
            user_input, problem, conversation_history, current_state, curriculum_content
        )
    
    async def _handle_understanding_verification_mode(
        self,
        user_input: str,
        problem: Problem,
        conversation_history: List[ConversationMessage],
        current_state: StudentState,
        curriculum_content: str
    ) -> Tuple[str, str, StudentState]:
        """Handle code understanding verification"""
        
        approved_logic = self._extract_approved_logic(conversation_history)
        student_code = self._extract_latest_code(conversation_history, user_input)
        
        try:
            verification_result = await self.code_understanding_verifier.verify_code_understanding(
                student_code=student_code,
                student_explanation=user_input,
                problem=problem,
                approved_logic=approved_logic,
                verification_level=UnderstandingLevel.SURFACE_LEVEL
            )
            
            response = verification_result.feedback_message
            if verification_result.next_questions:
                response += "\n\n" + "\n".join(f"• {q}" for q in verification_result.next_questions)
            
            if verification_result.is_verified:
                return response, "implementation_complete", StudentState.PROBLEM_COMPLETED
            else:
                return response, "continue_understanding_verification", StudentState.CODE_UNDERSTANDING
                
        except Exception as e:
            logger.error(f"❌ Error in understanding verification: {e}")
            return ("Great! Now I need to verify that you truly understand your code. Can you explain what each line does and why you wrote it that way?", 
                   "explain_code_understanding", StudentState.CODE_UNDERSTANDING)
    
    def _extract_approved_logic(self, conversation_history: List[ConversationMessage]) -> str:
        """Extract the approved logic explanation from conversation history"""
        
        # Look for the most recent substantial user message before logic approval
        user_messages = [msg for msg in conversation_history if msg.message_type == MessageType.USER]
        
        for msg in reversed(user_messages):
            if len(msg.content.strip()) > 50:  # Substantial message
                # Check if it's likely a logic explanation
                logic_indicators = ['loop', 'list', 'input', 'variable', 'step', 'first', 'then']
                if any(indicator in msg.content.lower() for indicator in logic_indicators):
                    return msg.content
        
        # Fallback - return last substantial user message
        if user_messages:
            return user_messages[-1].content
        
        return "Student's approved logic explanation"
    
    def _extract_latest_code(self, conversation_history: List[ConversationMessage], current_input: str) -> str:
        """Extract the latest code submission from conversation or current input"""
        
        # Check current input first
        if self._contains_code(current_input):
            return current_input
        
        # Look through recent messages for code
        for msg in reversed(conversation_history):
            if msg.message_type == MessageType.USER and self._contains_code(msg.content):
                return msg.content
        
        return current_input  # Fallback to current input


# Global instance for easy import
structured_tutoring_engine = StructuredTutoringEngine()

# Integration function to use with existing AI-TA system
def integrate_structured_tutoring():
    """Integration point for the existing AI-TA system"""
    return StructuredTutoringEngine()