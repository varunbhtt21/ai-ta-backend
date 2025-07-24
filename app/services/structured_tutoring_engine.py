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
from app.core.config import settings

logger = logging.getLogger(__name__)


class StudentState(Enum):
    """Track where the student is in the learning process"""
    INITIAL_GREETING = "initial_greeting"
    READY_TO_START = "ready_to_start"
    PROBLEM_PRESENTED = "problem_presented"
    AWAITING_APPROACH = "awaiting_approach"
    WORKING_ON_CODE = "working_on_code"
    STUCK_NEEDS_HELP = "stuck_needs_help"
    CODE_REVIEW = "code_review"
    PROBLEM_COMPLETED = "problem_completed"


class TutoringMode(Enum):
    """Different tutoring response modes"""
    PROBLEM_PRESENTATION = "problem_presentation"
    APPROACH_INQUIRY = "approach_inquiry"
    GUIDED_QUESTIONING = "guided_questioning"
    CODE_ANALYSIS = "code_analysis"
    HINT_PROVIDING = "hint_providing"
    ENCOURAGEMENT = "encouragement"
    CELEBRATION = "celebration"


@dataclass
class StructuredResponse:
    """Structured response from the tutoring engine"""
    response_text: str
    tutoring_mode: TutoringMode
    student_state: StudentState
    next_expected_input: str
    teaching_notes: List[str]
    current_problem: Optional[int] = None


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

CURRICULUM CONTENT TAUGHT:
{curriculum_content}

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

EXACT CONVERSATION FLOW TO FOLLOW:

1. When student says ready → Present ONLY the problem statement + ask "How are you thinking to solve this?"
2. When student gives approach → If correct, encourage and ask for code. If wrong, guide with questions.
3. When student submits code → Analyze and give hints about issues, DON'T fix the code
4. When student is stuck → Break into simpler version (like 1 number instead of 5)
5. When student shows understanding → Gradually build up to full problem
6. Only when correct → Celebrate and move to next problem

EXAMPLES OF CORRECT RESPONSES:

When student says "ready":
"Here is the first problem:

**Problem 1: Create a List with User Input**
Write a program that prompts the user to enter 5 numbers (one by one). Append each number to a list and print the final list.

**Sample Input:**
Enter number 1: 3
Enter number 2: 7
Enter number 3: 2
Enter number 4: 9
Enter number 5: 5

**Sample Output:**
[3, 7, 2, 9, 5]

How are you thinking to solve this question?"

When student gives approach:
Student: "I need to use a loop to take 5 inputs"
You: "Correct! That's a good approach. Can you try writing the code?"

When student is stuck:
Student: "I don't know how to write the code"
You: "Let's break this down. Instead of 5 numbers, let's start with just 1 number. How would you take one input and put it in a list?"

When student submits code with issues:
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
        
        # Code submission indicators
        code_indicators = ['=', 'for ', 'while ', 'if ', 'def ', 'print(', 'input(', 'append(', 'range(']
        if any(indicator in user_input for indicator in code_indicators):
            return StudentState.CODE_REVIEW
        
        # Stuck/confusion indicators
        stuck_indicators = ['not clear', 'don\'t understand', 'stuck', 'confused', 'not getting it', 'help']
        if any(indicator in user_input_lower for indicator in stuck_indicators):
            return StudentState.STUCK_NEEDS_HELP
        
        # Question about approach
        question_indicators = ['how', 'what', 'should i', 'do i need', 'can i', 'is it']
        if any(indicator in user_input_lower for indicator in question_indicators):
            if current_state == StudentState.PROBLEM_PRESENTED:
                return StudentState.AWAITING_APPROACH
            else:
                return StudentState.WORKING_ON_CODE
        
        # Next problem indicators (when user is ready to move forward)
        next_indicators = ['next', 'done', 'completed', 'finished', 'move on', 'yes', 'ready', 'continue']
        if any(indicator in user_input_lower for indicator in next_indicators):
            # Only transition to next problem if currently in celebration mode
            if current_state == StudentState.PROBLEM_COMPLETED:
                return StudentState.READY_TO_START  # Ready for next problem
            else:
                return StudentState.PROBLEM_COMPLETED
        
        # Default state transitions
        if current_state == StudentState.READY_TO_START:
            return StudentState.PROBLEM_PRESENTED
        elif current_state == StudentState.PROBLEM_PRESENTED:
            return StudentState.AWAITING_APPROACH
        else:
            return StudentState.WORKING_ON_CODE
    
    def _determine_tutoring_mode(
        self, 
        student_state: StudentState, 
        user_input: str,
        conversation_history: List[ConversationMessage]
    ) -> TutoringMode:
        """Determine what type of tutoring response is needed"""
        
        if student_state == StudentState.READY_TO_START:
            return TutoringMode.PROBLEM_PRESENTATION
        elif student_state == StudentState.PROBLEM_PRESENTED:
            return TutoringMode.APPROACH_INQUIRY
        elif student_state == StudentState.AWAITING_APPROACH:
            return TutoringMode.GUIDED_QUESTIONING
        elif student_state == StudentState.CODE_REVIEW:
            return TutoringMode.CODE_ANALYSIS
        elif student_state == StudentState.STUCK_NEEDS_HELP:
            return TutoringMode.HINT_PROVIDING
        elif student_state == StudentState.PROBLEM_COMPLETED:
            return TutoringMode.CELEBRATION
        else:
            return TutoringMode.GUIDED_QUESTIONING
    
    def _is_code_submission(self, text: str) -> bool:
        """Detect if the input contains code"""
        code_indicators = ['=', 'for ', 'while ', 'if ', 'def ', 'print(', 'input(', 'append(', 'range(', 'len(']
        return any(indicator in text for indicator in code_indicators)
    
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
        
        try:
            # Check if user is asking for problem statement/explanation
            user_input_lower = user_input.lower()
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
                    response_text=response_text,
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
                response_text = self._present_problem(current_problem)
                next_expected = "approach_explanation"
                teaching_notes = ["Problem presented", "Awaiting student's approach"]
                
            elif tutoring_mode == TutoringMode.APPROACH_INQUIRY:
                response_text = "How are you thinking to solve this question?"
                next_expected = "solution_approach"
                teaching_notes = ["Asked for approach", "Guide based on their response"]
                
            elif tutoring_mode == TutoringMode.CODE_ANALYSIS:
                response_text, teaching_notes, is_solution_correct = await self._analyze_code_submission(user_input, current_problem)
                
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
                response_text = await self._provide_guided_help(user_input, current_problem, conversation_history)
                next_expected = "attempt_or_question"
                teaching_notes = ["Provided guidance", "Broke down problem"]
                
            elif tutoring_mode == TutoringMode.GUIDED_QUESTIONING:
                response_text = await self._guide_with_questions(user_input, current_problem)
                next_expected = "clarification_or_attempt"
                teaching_notes = ["Guided with questions", "Avoided direct answers"]
                
            elif tutoring_mode == TutoringMode.CELEBRATION:
                response_text = "Excellent work! You've solved it correctly. Ready for the next problem?"
                next_expected = "next_problem_ready"
                teaching_notes = ["Celebrated success", "Ready to advance"]
                
            else:
                # Default guided questioning
                response_text = await self._guide_with_questions(user_input, current_problem)
                next_expected = "clarification_or_attempt"
                teaching_notes = ["Default guidance provided"]
            
            return StructuredResponse(
                response_text=response_text,
                tutoring_mode=tutoring_mode,
                student_state=new_student_state,
                next_expected_input=next_expected,
                teaching_notes=teaching_notes
            )
            
        except Exception as e:
            logger.error(f"Error in structured tutoring response generation: {e}")
            # Fallback response
            return StructuredResponse(
                response_text="I'm here to help you learn. Can you tell me what you're working on or where you're getting stuck?",
                tutoring_mode=TutoringMode.GUIDED_QUESTIONING,
                student_state=StudentState.WORKING_ON_CODE,
                next_expected_input="clarification",
                teaching_notes=["Error fallback response"]
            )
    
    def _present_problem(self, problem: Problem) -> str:
        """Present the problem statement following the exact format from OOP prototype"""
        
        sample_input = getattr(problem, 'sample_input', '')
        sample_output = getattr(problem, 'sample_output', '')
        
        return f"""Here is the problem:

**{problem.title}**

{problem.description}

**Sample Input:**
{sample_input}

**Sample Output:**
{sample_output}

How are you thinking to solve this question?"""
    
    async def _analyze_code_submission(self, code: str, problem: Problem) -> Tuple[str, List[str], bool]:
        """Analyze code submission and provide specific hints without giving solutions
        
        Returns:
            Tuple[str, List[str], bool]: (response_text, teaching_notes, is_solution_correct)
        """
        
        logger.info("🔍 STRUCTURED_TUTORING_ENGINE: _analyze_code_submission called")
        logger.info(f"💻 STRUCTURED_TUTORING_ENGINE: Analyzing code: '{code}'")
        logger.info(f"📚 STRUCTURED_TUTORING_ENGINE: Problem: {problem.title if problem else 'None'}")
        
        # Use OpenAI to analyze the code dynamically
        system_prompt = f"""You are analyzing student code for this EXACT problem:

**Problem Title:** {problem.title}
**Problem Description:** {problem.description}
**Required Concepts:** {', '.join(problem.concepts) if problem.concepts else 'Not specified'}

The student submitted this code:
```
{code}
```

CRITICAL INSTRUCTIONS:
- ONLY analyze if the code solves THE EXACT PROBLEM DESCRIBED ABOVE
- Do NOT invent or add new requirements that aren't in the problem description
- Do NOT change what the problem is asking for
- If the code has issues relative to the ORIGINAL problem, give ONE specific hint
- If the code correctly solves the ORIGINAL problem, celebrate their success
- Keep response to 1-2 sentences maximum
- Focus on the most important issue first

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

Give a helpful response for their code relative to the ORIGINAL problem only:"""
        
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
                
                return clean_response, ["Dynamic code analysis via OpenAI"], is_correct
            else:
                logger.error(f"❌ STRUCTURED_TUTORING_ENGINE: OpenAI API error in code analysis: {response.get('error', 'Unknown error')}")
                # Fallback to static analysis only on API failure
                issues = self._analyze_code_issues(code, problem)
                if not issues:
                    return "Your code looks good! Try running it and see if it works as expected.", ["Fallback: Code analysis looks correct"], True
                else:
                    primary_issue = issues[0]
                    hint = self._get_hint_for_issue(primary_issue)
                    return hint, [f"Fallback: Detected issue: {primary_issue}"], False
                
        except Exception as e:
            logger.error(f"❌ STRUCTURED_TUTORING_ENGINE: Exception in code analysis OpenAI call: {e}")
            # Fallback to static analysis on exception
            issues = self._analyze_code_issues(code, problem)
            if not issues:
                return "Your code looks good! Try running it and see if it works as expected.", ["Exception fallback: Code analysis looks correct"], True
            else:
                primary_issue = issues[0]
                hint = self._get_hint_for_issue(primary_issue)
                return hint, [f"Exception fallback: Detected issue: {primary_issue}"], False
    
    async def _provide_guided_help(self, user_input: str, problem: Problem, conversation_history: List[ConversationMessage]) -> str:
        """Provide guided help when student is stuck - break problem down"""
        
        # Create dynamic guidance based on the specific problem
        system_prompt = f"""You are helping a student who is stuck on this EXACT problem:

**Problem Title:** {problem.title}
**Problem Description:** {problem.description}
**Required Concepts:** {', '.join(problem.concepts) if problem.concepts else 'Not specified'}

The student said: "{user_input}"

INSTRUCTIONS:
- Break down the ORIGINAL problem into smaller, manageable steps
- Focus ONLY on the requirements stated in the problem description above
- Do NOT add new requirements or change what the problem asks for
- Give encouraging, step-by-step guidance
- Keep response to 2-3 sentences maximum

EXAMPLE BREAKDOWNS:

**For "Create a list with user input" problems:**
"Let's break this down step by step. First, you'll need an empty list to store the numbers. Then, you'll need a way to repeat the input process multiple times. What do you think would be a good way to repeat something in Python?"

**For "Calculate sum of numbers" problems:**
"Let's tackle this one step at a time. You'll need a variable to keep track of the running total, and a way to go through each number in the list. What should be the starting value of your sum variable?"

**For "Print even numbers" problems:**
"Let's break this into smaller parts. First, you need to check each number from 1 to 10. Then, for each number, you need to determine if it's even. What mathematical operation could help you check if a number is even?"

**For "String length" problems:**
"Let's simplify this. The problem is asking you to count something about the string. What exactly do you think 'length' means when we talk about strings in programming?"

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
    
    async def _guide_with_questions(self, user_input: str, problem: Problem) -> str:
        """Guide student with questions rather than answers"""
        
        logger.info("🔮 STRUCTURED_TUTORING_ENGINE: _guide_with_questions called")
        logger.info(f"💬 STRUCTURED_TUTORING_ENGINE: Guiding for input: '{user_input}'")
        logger.info(f"📚 STRUCTURED_TUTORING_ENGINE: Problem: {problem.title if problem else 'None'}")
        
        # Use OpenAI with the structured system prompt to generate a guiding question
        system_prompt = f"""You are guiding a student through this EXACT problem:

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


# Integration function to use with existing AI-TA system
def integrate_structured_tutoring():
    """Integration point for the existing AI-TA system"""
    return StructuredTutoringEngine()