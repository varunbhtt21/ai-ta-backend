"""
Test suite for Code Implementation Validator
Tests Phase 5: Leading questions, logic-code alignment, and independent implementation tracking
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import List

from app.services.code_implementation_validator import (
    CodeImplementationValidator,
    CodeValidationLevel,
    CodeGuidanceType,
    CodeValidationResult,
    LogicCodeAlignment
)
from app.models import ConversationMessage, MessageType, Problem


class TestCodeImplementationValidator:
    """Test suite for Code Implementation Validator"""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance for testing"""
        return CodeImplementationValidator()
    
    @pytest.fixture
    def sample_problem(self):
        """Create sample problem for testing"""
        return Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter five numbers one by one. Append each number to a list and print the final list of numbers.",
            concepts=["lists", "loops", "input"]
        )
    
    @pytest.fixture
    def approved_logic(self):
        """Sample approved logic from Phase 1-4"""
        return """I will create an empty list called numbers. Then I will use a for loop with range(5) 
        to iterate exactly 5 times. In each iteration, I will use input() function to ask user for a number, 
        convert the string input to integer using int() function, and append the integer to my numbers list 
        using append() method. After the loop completes, I will print the final list."""
    
    @pytest.fixture
    def sample_conversation(self):
        """Create sample conversation history"""
        return [
            ConversationMessage(
                timestamp=datetime.now(),
                message_type=MessageType.ASSISTANT,
                content="How are you thinking to solve this problem?"
            ),
            ConversationMessage(
                timestamp=datetime.now(),
                message_type=MessageType.USER,
                content="I will create a list and use a for loop to get 5 numbers from user"
            )
        ]


class TestCodingPhaseStart:
    """Test starting the coding phase with leading questions"""
    
    @pytest.fixture
    def validator(self):
        return CodeImplementationValidator()
    
    @pytest.mark.asyncio
    async def test_coding_phase_start_generates_leading_questions(self, validator, sample_problem, approved_logic, sample_conversation):
        """Test that coding phase start generates appropriate leading questions"""
        
        result = await validator.validate_code_implementation(
            student_code="",
            approved_logic=approved_logic,
            problem=sample_problem,
            conversation_history=sample_conversation,
            current_level=CodeValidationLevel.READY_FOR_CODING
        )
        
        assert result.validation_level == CodeValidationLevel.GUIDED_DISCOVERY
        assert result.next_guidance_type == CodeGuidanceType.DISCOVERY_QUESTION
        assert len(result.leading_questions) > 0
        assert "Python syntax" in result.leading_questions[0] or "empty list" in result.leading_questions[0]
        assert result.requires_explanation == False
        print("✅ Coding phase start generates leading questions")
    
    @pytest.mark.asyncio
    async def test_leading_questions_are_contextual(self, validator, sample_problem, approved_logic, sample_conversation):
        """Test that leading questions are contextual to the problem"""
        
        result = await validator.validate_code_implementation(
            student_code="",
            approved_logic=approved_logic,
            problem=sample_problem,
            conversation_history=sample_conversation,
            current_level=CodeValidationLevel.READY_FOR_CODING
        )
        
        questions_text = " ".join(result.leading_questions).lower()
        
        # Should contain problem-relevant concepts
        assert any(concept in questions_text for concept in ["list", "loop", "input", "variable"])
        print("✅ Leading questions are contextual")


class TestLogicCodeAlignment:
    """Test logic-code alignment verification"""
    
    @pytest.fixture
    def validator(self):
        return CodeImplementationValidator()
    
    @pytest.mark.asyncio
    async def test_high_alignment_code(self, validator, sample_problem, approved_logic, sample_conversation):
        """Test code that closely matches approved logic"""
        
        well_aligned_code = """
numbers = []
for i in range(5):
    num = input("Enter a number: ")
    numbers.append(int(num))
print(numbers)
"""
        
        result = await validator.validate_code_implementation(
            student_code=well_aligned_code,
            approved_logic=approved_logic,
            problem=sample_problem,
            conversation_history=sample_conversation,
            current_level=CodeValidationLevel.CODE_SUBMITTED
        )
        
        assert result.logic_alignment_score > 0.7  # High alignment
        assert result.validation_level == CodeValidationLevel.CODE_UNDERSTANDING
        assert len(result.code_issues) == 0
        print("✅ High alignment code properly recognized")
    
    @pytest.mark.asyncio
    async def test_low_alignment_code(self, validator, sample_problem, approved_logic, sample_conversation):
        """Test code that doesn't match approved logic"""
        
        poorly_aligned_code = """
x = input("Enter numbers separated by commas: ")
numbers = x.split(",")
print(numbers)
"""
        
        result = await validator.validate_code_implementation(
            student_code=poorly_aligned_code,
            approved_logic=approved_logic,
            problem=sample_problem,
            conversation_history=sample_conversation,
            current_level=CodeValidationLevel.CODE_SUBMITTED
        )
        
        assert result.logic_alignment_score < 0.5  # Low alignment
        assert result.validation_level == CodeValidationLevel.GUIDED_DISCOVERY
        assert "logic_deviation" in result.code_issues
        print("✅ Low alignment code properly detected")
    
    def test_logic_element_extraction(self, validator, approved_logic):
        """Test extraction of logic elements from approved logic"""
        
        elements = validator._extract_logic_elements(approved_logic)
        
        expected_elements = ["list_creation", "for_loop", "user_input", "type_conversion", "list_append", "output_display"]
        
        for expected in expected_elements:
            assert expected in elements, f"Missing expected element: {expected}"
        
        print("✅ Logic element extraction working correctly")
    
    def test_code_element_extraction(self, validator):
        """Test extraction of code elements from student code"""
        
        code = """
numbers = []
for i in range(5):
    num = input("Enter number: ")
    numbers.append(int(num))
print(numbers)
"""
        
        elements = validator._extract_code_elements(code)
        
        expected_elements = ["list_creation", "for_loop", "user_input", "type_conversion", "list_append", "output_display"]
        
        for expected in expected_elements:
            assert expected in elements, f"Missing expected element: {expected}"
        
        print("✅ Code element extraction working correctly")


class TestCodeGamingDetection:
    """Test gaming detection in code implementation phase"""
    
    @pytest.fixture
    def validator(self):
        return CodeImplementationValidator()
    
    @pytest.mark.asyncio
    async def test_copy_paste_detection(self, validator, sample_problem, approved_logic, sample_conversation):
        """Test detection of copy-paste code from internet"""
        
        gaming_code = """
# copied from stackoverflow
def solution():
    numbers = []
    for i in range(5):
        num = input("Enter a number: ")
        numbers.append(int(num))
    print(numbers)
solution()
"""
        
        result = await validator.validate_code_implementation(
            student_code=gaming_code,
            approved_logic=approved_logic,
            problem=sample_problem,
            conversation_history=sample_conversation,
            current_level=CodeValidationLevel.CODE_SUBMITTED
        )
        
        assert result.validation_level == CodeValidationLevel.CODE_GAMING_DETECTED
        assert "gaming_attempt_detected" in result.code_issues
        assert result.next_guidance_type == CodeGuidanceType.DISCOVERY_QUESTION
        print("✅ Copy-paste detection working")
    
    @pytest.mark.asyncio
    async def test_complex_code_detection(self, validator, sample_problem, approved_logic, sample_conversation):
        """Test detection of overly complex code for beginner level"""
        
        complex_code = """
numbers = [int(input(f"Enter number {i+1}: ")) for i in range(5)]
print(numbers if all(isinstance(x, int) for x in numbers) else "Invalid input")
"""
        
        gaming_detected = await validator._detect_code_gaming(
            complex_code, sample_conversation, sample_problem
        )
        
        assert gaming_detected == True
        print("✅ Complex code detection working")
    
    def test_legitimate_code_not_flagged(self, validator):
        """Test that legitimate beginner code is not flagged as gaming"""
        
        legitimate_code = """
numbers = []
for i in range(5):
    num = input("Enter a number: ")
    numbers.append(int(num))
print(numbers)
"""
        
        import asyncio
        
        async def run_test():
            return await validator._detect_code_gaming(
                legitimate_code, [], Problem(1, "Test", "Test", [])
            )
        
        gaming_detected = asyncio.run(run_test())
        
        assert gaming_detected == False
        print("✅ Legitimate code not flagged as gaming")


class TestSyntaxErrorHandling:
    """Test handling of syntax errors in student code"""
    
    @pytest.fixture
    def validator(self):
        return CodeImplementationValidator()
    
    def test_syntax_error_detection(self, validator):
        """Test detection of basic syntax errors"""
        
        code_with_errors = """
numbers = []
for i in range(5)  # Missing colon
    num = input("Enter number: ")
    numbers.append(int(num)
print(numbers)  # Missing closing parenthesis
"""
        
        syntax_errors = validator._check_syntax_errors(code_with_errors)
        
        assert len(syntax_errors) > 0
        assert "syntax_error" in syntax_errors or "missing_colon" in syntax_errors
        print("✅ Syntax error detection working")
    
    def test_valid_syntax_no_errors(self, validator):
        """Test that valid code has no syntax errors"""
        
        valid_code = """
numbers = []
for i in range(5):
    num = input("Enter number: ")
    numbers.append(int(num))
print(numbers)
"""
        
        syntax_errors = validator._check_syntax_errors(valid_code)
        
        assert len(syntax_errors) == 0
        print("✅ Valid syntax properly recognized")


class TestDiscoveryQuestions:
    """Test generation of discovery questions"""
    
    @pytest.fixture
    def validator(self):
        return CodeImplementationValidator()
    
    def test_start_stage_questions(self, validator, sample_problem, approved_logic):
        """Test questions generated at start of coding"""
        
        questions = validator._generate_discovery_questions(
            sample_problem, approved_logic, "start"
        )
        
        assert len(questions) > 0
        assert len(questions) <= 2  # Should be limited
        
        questions_text = " ".join(questions).lower()
        assert any(keyword in questions_text for keyword in ["list", "variable", "first"])
        print("✅ Start stage questions generated correctly")
    
    def test_continue_stage_questions(self, validator, sample_problem, approved_logic):
        """Test questions generated during coding continuation"""
        
        questions = validator._generate_discovery_questions(
            sample_problem, approved_logic, "continue"
        )
        
        assert len(questions) > 0
        questions_text = " ".join(questions).lower()
        assert any(keyword in questions_text for keyword in ["loop", "input", "convert"])
        print("✅ Continue stage questions generated correctly")


class TestAlignmentQuestions:
    """Test generation of alignment-fixing questions"""
    
    @pytest.fixture
    def validator(self):
        return CodeImplementationValidator()
    
    def test_missing_elements_questions(self, validator, sample_problem):
        """Test questions for missing logic elements"""
        
        missing_elements = ["list_creation", "user_input", "type_conversion"]
        
        questions = validator._generate_alignment_questions(
            missing_elements, sample_problem
        )
        
        assert len(questions) > 0
        assert len(questions) <= 2  # Should be limited to avoid overwhelming
        
        questions_text = " ".join(questions).lower()
        assert any(keyword in questions_text for keyword in ["list", "input", "convert"])
        print("✅ Alignment questions generated correctly")


if __name__ == "__main__":
    pytest.main([__file__])