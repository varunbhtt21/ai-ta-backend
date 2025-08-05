"""
Code Implementation Validator Service
Implements Phase 5: Strict code guidance with leading questions and logic-code alignment verification.
Never gives direct code solutions - only guides students to discover solutions themselves.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import logging
import re
import ast

from app.models import ConversationMessage, MessageType, Problem, User
from app.services.openai_client import openai_client
from app.services.validation_types import LogicValidationLevel, StrictnessLevel
from app.core.config import settings

logger = logging.getLogger(__name__)


class CodeValidationLevel(Enum):
    """Code implementation validation levels"""
    READY_FOR_CODING = "ready_for_coding"           # Logic approved, ready to code
    GUIDED_DISCOVERY = "guided_discovery"           # Guide with leading questions
    CODE_SUBMITTED = "code_submitted"               # Student submitted code
    LOGIC_ALIGNMENT_CHECK = "logic_alignment_check" # Verify code matches logic
    CODE_UNDERSTANDING = "code_understanding"       # Test student's understanding
    IMPLEMENTATION_APPROVED = "implementation_approved" # Code approved
    CODE_GAMING_DETECTED = "code_gaming_detected"   # Student trying to game coding phase


class CodeGuidanceType(Enum):
    """Types of code guidance questions"""
    DISCOVERY_QUESTION = "discovery_question"       # Help student discover solution
    CONCEPT_REINFORCEMENT = "concept_reinforcement" # Reinforce learned concepts
    STEP_BY_STEP = "step_by_step"                   # Break down into smaller steps
    SYNTAX_HINT = "syntax_hint"                     # Subtle syntax guidance
    DEBUGGING_GUIDE = "debugging_guide"             # Help fix code issues


@dataclass
class CodeValidationResult:
    """Result of code implementation validation"""
    is_approved: bool
    validation_level: CodeValidationLevel
    feedback_message: str
    leading_questions: List[str]
    code_issues: List[str]
    logic_alignment_score: float  # 0.0 to 1.0
    understanding_gaps: List[str]
    next_guidance_type: CodeGuidanceType
    requires_explanation: bool


@dataclass
class LogicCodeAlignment:
    """Analysis of how well code matches approved logic"""
    alignment_score: float
    matched_elements: List[str]
    missing_elements: List[str]
    extra_elements: List[str]
    logic_deviations: List[str]


class CodeImplementationValidator:
    """Validates code implementation while maintaining strict no-code-giving policy"""
    
    def __init__(self):
        self.openai_client = openai_client
        
        # Leading question templates for different programming concepts
        self.leading_questions = self._load_leading_questions()
        
        # Code analysis patterns for logic alignment
        self.code_patterns = self._load_code_analysis_patterns()
        
        # Concept reinforcement questions
        self.concept_questions = self._load_concept_reinforcement()
        
        logger.info(f"🔧 CODE_VALIDATOR: Initialized with leading questions guidance")
    
    async def validate_code_implementation(
        self,
        student_code: str,
        approved_logic: str,
        problem: Problem,
        conversation_history: List[ConversationMessage],
        current_level: CodeValidationLevel = CodeValidationLevel.READY_FOR_CODING
    ) -> CodeValidationResult:
        """
        Validate code implementation with strict no-code-giving policy
        Guide students to discover solutions through leading questions
        """
        logger.info(f"🔍 CODE_VALIDATOR: Validating code at level {current_level.value}")
        
        try:
            # Step 1: Check if student is trying to game the coding phase
            gaming_detected = await self._detect_code_gaming(
                student_code, conversation_history, problem
            )
            
            if gaming_detected:
                return CodeValidationResult(
                    is_approved=False,
                    validation_level=CodeValidationLevel.CODE_GAMING_DETECTED,
                    feedback_message="I need you to implement the code yourself based on your approved logic. No shortcuts allowed - show me your own implementation.",
                    leading_questions=[],
                    code_issues=["gaming_attempt_detected"],
                    logic_alignment_score=0.0,
                    understanding_gaps=["independent_implementation"],
                    next_guidance_type=CodeGuidanceType.DISCOVERY_QUESTION,
                    requires_explanation=True
                )
            
            # Step 2: Analyze logic-code alignment
            alignment = await self._analyze_logic_code_alignment(
                student_code, approved_logic, problem
            )
            
            # Step 3: Determine validation level and response
            if current_level == CodeValidationLevel.READY_FOR_CODING:
                return await self._handle_coding_start(problem, approved_logic)
            
            elif current_level == CodeValidationLevel.CODE_SUBMITTED:
                return await self._handle_code_submission(
                    student_code, approved_logic, problem, alignment
                )
            
            elif current_level == CodeValidationLevel.LOGIC_ALIGNMENT_CHECK:
                return await self._handle_alignment_check(
                    student_code, approved_logic, alignment, problem
                )
            
            elif current_level == CodeValidationLevel.CODE_UNDERSTANDING:
                return await self._handle_understanding_verification(
                    student_code, approved_logic, problem
                )
            
            else:
                return await self._handle_guided_discovery(
                    student_code, approved_logic, problem, conversation_history
                )
                
        except Exception as e:
            logger.error(f"❌ CODE_VALIDATOR: Error during validation: {e}")
            return self._fallback_guidance_response(problem)
    
    async def _detect_code_gaming(
        self,
        student_code: str,
        conversation_history: List[ConversationMessage],
        problem: Problem
    ) -> bool:
        """Detect if student is trying to game the coding phase"""
        
        if not student_code or len(student_code.strip()) < 10:
            return False
        
        # Check for copy-paste from internet (common patterns)
        gaming_patterns = [
            r"#.*from.*stackoverflow",
            r"#.*copied.*from",
            r"def.*solution.*\(",
            r"class.*Solution",
            r"#.*chatgpt|#.*gpt|#.*ai",
            r"//.*stackoverflow|//.*copied"
        ]
        
        for pattern in gaming_patterns:
            if re.search(pattern, student_code, re.IGNORECASE):
                return True
        
        # Check for overly complex code that doesn't match beginner level
        try:
            tree = ast.parse(student_code)
            complex_nodes = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.ListComp, ast.DictComp, ast.Lambda)):
                    complex_nodes.append(type(node).__name__)
                elif isinstance(node, ast.FunctionDef) and len(node.args.args) > 3:
                    complex_nodes.append("ComplexFunction")
            
            # If too many advanced concepts for beginner problem
            if len(complex_nodes) > 2:
                return True
                
        except SyntaxError:
            # Code has syntax errors - not gaming, just learning
            pass
        
        return False
    
    async def _analyze_logic_code_alignment(
        self,
        student_code: str,
        approved_logic: str,
        problem: Problem
    ) -> LogicCodeAlignment:
        """Analyze how well the code matches the approved logic"""
        
        if not student_code or not approved_logic:
            return LogicCodeAlignment(
                alignment_score=0.0,
                matched_elements=[],
                missing_elements=["no_code_provided"],
                extra_elements=[],
                logic_deviations=[]
            )
        
        # Extract logic elements from approved logic
        logic_elements = self._extract_logic_elements(approved_logic)
        
        # Extract code elements from student code
        code_elements = self._extract_code_elements(student_code)
        
        # Compare elements
        matched = []
        missing = []
        extra = []
        
        for element in logic_elements:
            if self._element_present_in_code(element, code_elements):
                matched.append(element)
            else:
                missing.append(element)
        
        for element in code_elements:
            if not self._element_present_in_logic(element, logic_elements):
                extra.append(element)
        
        # Calculate alignment score
        total_logic_elements = len(logic_elements)
        alignment_score = len(matched) / total_logic_elements if total_logic_elements > 0 else 0.0
        
        return LogicCodeAlignment(
            alignment_score=alignment_score,
            matched_elements=matched,
            missing_elements=missing,
            extra_elements=extra[:3],  # Limit to avoid overwhelming
            logic_deviations=[]
        )
    
    def _extract_logic_elements(self, approved_logic: str) -> List[str]:
        """Extract key elements from approved logic"""
        
        elements = []
        logic_lower = approved_logic.lower()
        
        # Data structure detection
        if 'list' in logic_lower or 'array' in logic_lower:
            elements.append('list_creation')
        if 'variable' in logic_lower or 'store' in logic_lower:
            elements.append('variable_usage')
        
        # Loop detection
        if 'for loop' in logic_lower or 'for' in logic_lower:
            elements.append('for_loop')
        elif 'while loop' in logic_lower or 'while' in logic_lower:
            elements.append('while_loop')
        elif 'loop' in logic_lower:
            elements.append('loop_structure')
        
        # Input/Output detection
        if 'input' in logic_lower:
            elements.append('user_input')
        if 'print' in logic_lower or 'output' in logic_lower:
            elements.append('output_display')
        
        # Data handling
        if 'convert' in logic_lower or 'int(' in logic_lower:
            elements.append('type_conversion')
        if 'append' in logic_lower:
            elements.append('list_append')
        
        # Control flow
        if 'range(' in logic_lower or 'range' in logic_lower:
            elements.append('range_usage')
        if '5 times' in logic_lower or 'five times' in logic_lower:
            elements.append('fixed_iterations')
        
        return elements
    
    def _extract_code_elements(self, student_code: str) -> List[str]:
        """Extract key elements from student code"""
        
        elements = []
        
        try:
            tree = ast.parse(student_code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.List):
                    elements.append('list_creation')
                elif isinstance(node, ast.For):
                    elements.append('for_loop')
                elif isinstance(node, ast.While):
                    elements.append('while_loop')
                elif isinstance(node, ast.Call):
                    if hasattr(node.func, 'id'):
                        if node.func.id == 'input':
                            elements.append('user_input')
                        elif node.func.id == 'print':
                            elements.append('output_display')
                        elif node.func.id == 'int':
                            elements.append('type_conversion')
                        elif node.func.id == 'range':
                            elements.append('range_usage')
                    elif hasattr(node.func, 'attr') and node.func.attr == 'append':
                        elements.append('list_append')
                elif isinstance(node, ast.Assign):
                    elements.append('variable_usage')
                    
        except SyntaxError:
            # Fallback to string analysis for broken code
            code_lower = student_code.lower()
            
            if 'list(' in code_lower or '[]' in code_lower:
                elements.append('list_creation')
            if 'for ' in code_lower:
                elements.append('for_loop')
            if 'while ' in code_lower:
                elements.append('while_loop')
            if 'input(' in code_lower:
                elements.append('user_input')
            if 'print(' in code_lower:
                elements.append('output_display')
            if 'int(' in code_lower:
                elements.append('type_conversion')
            if '.append(' in code_lower:
                elements.append('list_append')
            if 'range(' in code_lower:
                elements.append('range_usage')
            if '=' in code_lower:
                elements.append('variable_usage')
        
        return elements
    
    def _element_present_in_code(self, logic_element: str, code_elements: List[str]) -> bool:
        """Check if logic element is present in code elements"""
        
        # Direct match
        if logic_element in code_elements:
            return True
        
        # Fuzzy matching for similar elements
        if logic_element == 'loop_structure' and ('for_loop' in code_elements or 'while_loop' in code_elements):
            return True
        
        return False
    
    def _element_present_in_logic(self, code_element: str, logic_elements: List[str]) -> bool:
        """Check if code element was mentioned in logic"""
        
        # Direct match
        if code_element in logic_elements:
            return True
        
        # Fuzzy matching
        if code_element in ['for_loop', 'while_loop'] and 'loop_structure' in logic_elements:
            return True
        
        return False
    
    async def _handle_coding_start(
        self,
        problem: Problem,
        approved_logic: str
    ) -> CodeValidationResult:
        """Handle the start of coding phase with leading questions"""
        
        # Generate leading questions to start coding
        questions = self._generate_discovery_questions(problem, approved_logic, "start")
        
        feedback = f"""Perfect! Your logic is approved. Now let's implement it step by step.

Remember: I won't give you the code - you'll discover it through your own thinking.

Let's start with the very first step from your logic."""
        
        return CodeValidationResult(
            is_approved=False,  # Not approved yet - just starting
            validation_level=CodeValidationLevel.GUIDED_DISCOVERY,
            feedback_message=feedback,
            leading_questions=questions,
            code_issues=[],
            logic_alignment_score=0.0,
            understanding_gaps=[],
            next_guidance_type=CodeGuidanceType.DISCOVERY_QUESTION,
            requires_explanation=False
        )
    
    async def _handle_code_submission(
        self,
        student_code: str,
        approved_logic: str,
        problem: Problem,
        alignment: LogicCodeAlignment
    ) -> CodeValidationResult:
        """Handle when student submits code for review"""
        
        # Check syntax first
        syntax_errors = self._check_syntax_errors(student_code)
        
        if syntax_errors:
            questions = self._generate_debugging_questions(syntax_errors)
            return CodeValidationResult(
                is_approved=False,
                validation_level=CodeValidationLevel.GUIDED_DISCOVERY,
                feedback_message="I see some syntax issues in your code. Let's fix them step by step.",
                leading_questions=questions,
                code_issues=syntax_errors,
                logic_alignment_score=0.0,
                understanding_gaps=["syntax_understanding"],
                next_guidance_type=CodeGuidanceType.DEBUGGING_GUIDE,
                requires_explanation=False
            )
        
        # Check logic alignment
        if alignment.alignment_score >= 0.8:
            # High alignment - move to understanding verification
            return CodeValidationResult(
                is_approved=False,
                validation_level=CodeValidationLevel.CODE_UNDERSTANDING,
                feedback_message="Great! Your code matches your logic well. Now let's make sure you understand what you've written.",
                leading_questions=self._generate_understanding_questions(student_code, problem),
                code_issues=[],
                logic_alignment_score=alignment.alignment_score,
                understanding_gaps=[],
                next_guidance_type=CodeGuidanceType.CONCEPT_REINFORCEMENT,
                requires_explanation=True
            )
        
        elif alignment.alignment_score >= 0.5:
            # Medium alignment - guide to fix missing elements
            questions = self._generate_alignment_questions(alignment.missing_elements, problem)
            return CodeValidationResult(
                is_approved=False,
                validation_level=CodeValidationLevel.LOGIC_ALIGNMENT_CHECK,
                feedback_message="Your code is on the right track, but it's missing some elements from your approved logic.",
                leading_questions=questions,
                code_issues=alignment.missing_elements,
                logic_alignment_score=alignment.alignment_score,
                understanding_gaps=alignment.missing_elements,
                next_guidance_type=CodeGuidanceType.STEP_BY_STEP,
                requires_explanation=False
            )
        
        else:
            # Low alignment - back to guided discovery
            questions = self._generate_discovery_questions(problem, approved_logic, "restart")
            return CodeValidationResult(
                is_approved=False,
                validation_level=CodeValidationLevel.GUIDED_DISCOVERY,
                feedback_message="Your code doesn't match your approved logic. Let's go back to implementing your original plan step by step.",
                leading_questions=questions,
                code_issues=["logic_deviation"],
                logic_alignment_score=alignment.alignment_score,
                understanding_gaps=alignment.missing_elements,
                next_guidance_type=CodeGuidanceType.DISCOVERY_QUESTION,
                requires_explanation=False
            )
    
    async def _handle_alignment_check(
        self,
        student_code: str,
        approved_logic: str,
        alignment: LogicCodeAlignment,
        problem: Problem
    ) -> CodeValidationResult:
        """Handle logic-code alignment verification"""
        
        if alignment.alignment_score >= 0.8:
            return CodeValidationResult(
                is_approved=False,
                validation_level=CodeValidationLevel.CODE_UNDERSTANDING,
                feedback_message="Excellent! Now your code properly matches your logic. Let's verify your understanding.",
                leading_questions=self._generate_understanding_questions(student_code, problem),
                code_issues=[],
                logic_alignment_score=alignment.alignment_score,
                understanding_gaps=[],
                next_guidance_type=CodeGuidanceType.CONCEPT_REINFORCEMENT,
                requires_explanation=True
            )
        else:
            questions = self._generate_alignment_questions(alignment.missing_elements, problem)
            return CodeValidationResult(
                is_approved=False,
                validation_level=CodeValidationLevel.LOGIC_ALIGNMENT_CHECK,
                feedback_message="We're getting closer! Still missing a few elements from your logic.",
                leading_questions=questions,
                code_issues=alignment.missing_elements,
                logic_alignment_score=alignment.alignment_score,
                understanding_gaps=alignment.missing_elements,
                next_guidance_type=CodeGuidanceType.STEP_BY_STEP,
                requires_explanation=False
            )
    
    async def _handle_understanding_verification(
        self,
        student_code: str,
        approved_logic: str,
        problem: Problem
    ) -> CodeValidationResult:
        """Handle final understanding verification"""
        
        # This would typically involve asking student to explain their code
        # For now, we'll assume they need to demonstrate understanding
        
        understanding_questions = [
            "Walk me through your code line by line - what does each part do?",
            "Why did you choose this approach over alternatives?",
            "What would happen if you removed the type conversion? Why?"
        ]
        
        return CodeValidationResult(
            is_approved=False,
            validation_level=CodeValidationLevel.CODE_UNDERSTANDING,
            feedback_message="Perfect code! Now demonstrate that you truly understand what you've implemented.",
            leading_questions=understanding_questions,
            code_issues=[],
            logic_alignment_score=1.0,
            understanding_gaps=["code_explanation_required"],
            next_guidance_type=CodeGuidanceType.CONCEPT_REINFORCEMENT,
            requires_explanation=True
        )
    
    async def _handle_guided_discovery(
        self,
        student_code: str,
        approved_logic: str,
        problem: Problem,
        conversation_history: List[ConversationMessage]
    ) -> CodeValidationResult:
        """Handle guided discovery process"""
        
        questions = self._generate_discovery_questions(problem, approved_logic, "continue")
        
        return CodeValidationResult(
            is_approved=False,
            validation_level=CodeValidationLevel.GUIDED_DISCOVERY,
            feedback_message="Let's continue building your solution step by step.",
            leading_questions=questions,
            code_issues=[],
            logic_alignment_score=0.0,
            understanding_gaps=[],
            next_guidance_type=CodeGuidanceType.DISCOVERY_QUESTION,
            requires_explanation=False
        )
    
    def _generate_discovery_questions(
        self,
        problem: Problem,
        approved_logic: str,
        stage: str
    ) -> List[str]:
        """Generate leading questions to help student discover solution"""
        
        questions = []
        logic_lower = approved_logic.lower()
        
        if stage == "start":
            # Starting questions
            if 'list' in logic_lower:
                questions.append("What Python syntax creates an empty list?")
            if 'variable' in logic_lower:
                questions.append("What would be a good name for your storage container?")
            questions.append("What's the very first line of code you need to write?")
        
        elif stage == "continue":
            # Continuing questions based on what's missing
            if 'loop' in logic_lower:
                questions.append("How do you write a loop that runs exactly 5 times?")
            if 'input' in logic_lower:
                questions.append("What function gets input from the user?")
            if 'convert' in logic_lower:
                questions.append("How do you convert text to a number in Python?")
        
        elif stage == "restart":
            # Restart questions
            questions.append("Let's go back to your approved logic - what was your first step?")
            questions.append("How does that first step translate to Python code?")
        
        return questions[:2]  # Limit to 2 questions to avoid overwhelming
    
    def _generate_alignment_questions(
        self,
        missing_elements: List[str],
        problem: Problem
    ) -> List[str]:
        """Generate questions to help fix alignment issues"""
        
        questions = []
        
        for element in missing_elements[:2]:  # Limit to 2 elements
            if element == 'list_creation':
                questions.append("I don't see where you create your list. How do you make an empty list?")
            elif element == 'user_input':
                questions.append("How do you get input from the user in Python?")
            elif element == 'for_loop':
                questions.append("Your logic mentioned a for loop. How do you write one?")
            elif element == 'type_conversion':
                questions.append("The input() function returns text. How do you convert it to a number?")
            elif element == 'list_append':
                questions.append("How do you add an item to a list in Python?")
            elif element == 'output_display':
                questions.append("How do you display your final result?")
        
        return questions
    
    def _generate_understanding_questions(
        self,
        student_code: str,
        problem: Problem
    ) -> List[str]:
        """Generate questions to verify student understands their code"""
        
        questions = [
            "Explain what each line of your code does.",
            "Why did you choose this specific approach?",
            "What would happen if you changed this part of your code?"
        ]
        
        # Add specific questions based on code content
        if 'range(' in student_code:
            questions.append("Why did you use range() here? What does it do?")
        
        if '.append(' in student_code:
            questions.append("Explain what append() does and why you need it.")
        
        if 'int(' in student_code:
            questions.append("Why is the int() conversion necessary here?")
        
        return questions[:3]  # Limit to 3 questions
    
    def _generate_debugging_questions(self, syntax_errors: List[str]) -> List[str]:
        """Generate questions to help fix syntax errors"""
        
        questions = []
        
        for error in syntax_errors[:2]:  # Limit to 2 errors
            if "missing" in error.lower() and "colon" in error.lower():
                questions.append("Which lines need a colon (:) at the end?")
            elif "indentation" in error.lower():
                questions.append("Which lines should be indented? How many spaces?")
            elif "parenthesis" in error.lower() or "bracket" in error.lower():
                questions.append("Check your parentheses and brackets - do they all match up?")
            else:
                questions.append("Look at the error message - which line has the syntax issue?")
        
        return questions
    
    def _check_syntax_errors(self, student_code: str) -> List[str]:
        """Check for syntax errors in student code"""
        
        if not student_code:
            return ["no_code_provided"]
        
        try:
            ast.parse(student_code)
            return []  # No syntax errors
        except SyntaxError as e:
            error_msg = str(e).lower()
            
            if "missing" in error_msg and "colon" in error_msg:
                return ["missing_colon"]
            elif "indentation" in error_msg:
                return ["indentation_error"]
            elif "parenthesis" in error_msg:
                return ["unmatched_parenthesis"]
            elif "bracket" in error_msg:
                return ["unmatched_bracket"]
            else:
                return ["syntax_error"]
    
    def _fallback_guidance_response(self, problem: Problem) -> CodeValidationResult:
        """Fallback response when validation fails"""
        
        return CodeValidationResult(
            is_approved=False,
            validation_level=CodeValidationLevel.GUIDED_DISCOVERY,
            feedback_message="Let's work through this step by step. What's the first thing you need to do according to your logic?",
            leading_questions=[
                "What was the first step in your approved logic?",
                "How would you write that in Python code?"
            ],
            code_issues=[],
            logic_alignment_score=0.0,
            understanding_gaps=[],
            next_guidance_type=CodeGuidanceType.DISCOVERY_QUESTION,
            requires_explanation=False
        )
    
    def _load_leading_questions(self) -> Dict[str, List[str]]:
        """Load leading question templates"""
        
        return {
            "list_creation": [
                "What Python syntax creates an empty list?",
                "How do you make a container to store multiple values?",
                "What symbol represents an empty list in Python?"
            ],
            "loop_structure": [
                "How do you repeat an action multiple times in Python?",
                "What's the syntax for a loop that runs exactly N times?",
                "How do you write a for loop with range()?"
            ],
            "user_input": [
                "What function gets input from the user?",
                "How do you ask the user to type something?",
                "What Python function reads what the user types?"
            ],
            "type_conversion": [
                "The input() function returns text. How do you convert text to a number?",
                "What function changes a string into an integer?",
                "How do you convert '5' to the number 5?"
            ],
            "variable_assignment": [
                "How do you store a value in a variable?",
                "What symbol assigns a value to a variable name?",
                "How do you create a variable to hold your data?"
            ]
        }
    
    def _load_code_analysis_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for code analysis"""
        
        return {
            "list_patterns": [r'\[\]', r'list\(\)', r'\.append\('],
            "loop_patterns": [r'for\s+\w+\s+in\s+range', r'while\s+\w+'],
            "input_patterns": [r'input\(', r'raw_input\('],
            "conversion_patterns": [r'int\(', r'float\(', r'str\(']
        }
    
    def _load_concept_reinforcement(self) -> Dict[str, List[str]]:
        """Load concept reinforcement questions"""
        
        return {
            "understanding_verification": [
                "Explain what this line does in your own words.",
                "Why did you choose this approach?",
                "What would happen if you removed this part?"
            ],
            "code_walkthrough": [
                "Walk me through your code step by step.",
                "What's the purpose of each section?",
                "How does this solve the original problem?"
            ]
        }