"""
Comprehensive test suite for Enhanced Logic Validator
Tests all validation levels, gaming detection, and cross-questioning functionality
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import List

from app.services.enhanced_logic_validator import (
    EnhancedLogicValidator,
    LogicValidationResult,
    GamingDetectionResult
)
from app.services.validation_types import LogicValidationLevel, StrictnessLevel
from app.models import ConversationMessage, MessageType, Problem


class TestEnhancedLogicValidator:
    """Test suite for Enhanced Logic Validator"""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance for testing"""
        return EnhancedLogicValidator()
    
    @pytest.fixture
    def sample_problem(self):
        """Create sample problem for testing"""
        return Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter five numbers one by one. Append each number to a list and print the final list of numbers.",
            concepts=["lists", "loops", "input"],
            test_cases=[
                {"input": "1,2,3,4,5", "expected_output": "[1,2,3,4,5]", "description": "Normal case"}
            ]
        )
    
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
                content="I will use a loop"
            ),
            ConversationMessage(
                timestamp=datetime.now(),
                message_type=MessageType.ASSISTANT,
                content="What type of loop will you use? How many times should it run? Where will you store the input values?"
            )
        ]


class TestGamingDetection:
    """Test gaming detection functionality"""
    
    @pytest.fixture
    def validator(self):
        return EnhancedLogicValidator()
    
    @pytest.fixture
    def sample_problem(self):
        return Problem(
            number=1,
            title="Test Problem",
            description="Test description",
            concepts=["test"]
        )
    
    @pytest.mark.asyncio
    async def test_copy_paste_detection(self, validator, sample_problem):
        """Test detection of copy-paste from AI responses"""
        
        conversation_history = [
            ConversationMessage(
                timestamp=datetime.now(),
                message_type=MessageType.ASSISTANT,
                content="You need to create an empty list, use a for loop with range(5), and append each input to the list."
            )
        ]
        
        # Student copies AI response exactly
        student_response = "I need to create an empty list, use a for loop with range(5), and append each input to the list."
        
        gaming_result = await validator._detect_gaming_attempts(
            student_response, conversation_history, sample_problem
        )
        
        assert gaming_result.is_gaming == True
        assert gaming_result.gaming_type == "copy_paste"
        assert gaming_result.confidence > 0.3
        assert len(gaming_result.evidence) > 0
    
    @pytest.mark.asyncio
    async def test_vague_repetition_detection(self, validator, sample_problem):
        """Test detection of vague repetitive responses"""
        
        conversation_history = [
            ConversationMessage(
                timestamp=datetime.now(),
                message_type=MessageType.USER,
                content="I will use a loop"
            ),
            ConversationMessage(
                timestamp=datetime.now(),
                message_type=MessageType.ASSISTANT,
                content="What type of loop?"
            )
        ]
        
        # Student repeats same vague response
        student_response = "I will use a loop"
        
        gaming_result = await validator._detect_gaming_attempts(
            student_response, conversation_history, sample_problem
        )
        
        assert gaming_result.is_gaming == True
        assert gaming_result.gaming_type == "vague_repetition"
        assert "similar vague responses" in gaming_result.evidence[0].lower()
    
    @pytest.mark.asyncio
    async def test_bypass_attempt_detection(self, validator, sample_problem):
        """Test detection of bypass attempts"""
        
        bypass_phrases = [
            "give me code",
            "show me the answer",
            "next question",
            "just give me hint"
        ]
        
        for phrase in bypass_phrases:
            gaming_result = await validator._detect_gaming_attempts(
                phrase, [], sample_problem
            )
            
            assert gaming_result.is_gaming == True
            assert gaming_result.gaming_type == "bypass_attempt"
            assert any("bypass attempt" in evidence.lower() for evidence in gaming_result.evidence)
    
    @pytest.mark.asyncio
    async def test_insufficient_effort_detection(self, validator, sample_problem):
        """Test detection of insufficient effort (too short responses)"""
        
        short_response = "use loop"
        
        gaming_result = await validator._detect_gaming_attempts(
            short_response, [], sample_problem
        )
        
        assert gaming_result.is_gaming == True
        assert gaming_result.gaming_type == "insufficient_effort"
        assert "too short" in gaming_result.evidence[0].lower()
    
    @pytest.mark.asyncio
    async def test_legitimate_response_not_flagged(self, validator, sample_problem):
        """Test that legitimate responses are not flagged as gaming"""
        
        legitimate_response = "I will create an empty list called numbers. Then I will use a for loop that runs 5 times. In each iteration, I will ask the user to input a number using input() function, convert it to integer, and append it to my list. Finally, I will print the complete list."
        
        gaming_result = await validator._detect_gaming_attempts(
            legitimate_response, [], sample_problem
        )
        
        assert gaming_result.is_gaming == False
        assert gaming_result.gaming_type == "none"
        assert gaming_result.confidence <= 0.3


class TestLogicAnalysis:
    """Test logic content analysis functionality"""
    
    @pytest.fixture
    def validator(self):
        return EnhancedLogicValidator()
    
    @pytest.fixture
    def sample_problem(self):
        return Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter five numbers one by one. Append each number to a list and print the final list of numbers.",
            concepts=["lists", "loops", "input"]
        )
    
    def test_required_elements_lenient(self, validator, sample_problem):
        """Test required elements for lenient strictness level"""
        
        elements = validator._get_required_elements(sample_problem, StrictnessLevel.LENIENT)
        
        expected_base = ["data_structure_choice", "input_method", "loop_structure", "process_flow"]
        assert all(elem in elements for elem in expected_base)
        assert len(elements) == 4  # Only base elements for lenient
    
    def test_required_elements_strict(self, validator, sample_problem):
        """Test required elements for strict strictness level"""
        
        elements = validator._get_required_elements(sample_problem, StrictnessLevel.STRICT)
        
        expected_base = ["data_structure_choice", "input_method", "loop_structure", "process_flow"]
        expected_strict = ["variable_names", "data_type_handling", "output_method"]
        
        assert all(elem in elements for elem in expected_base)
        assert all(elem in elements for elem in expected_strict)
        assert len(elements) == 7
    
    def test_required_elements_very_strict(self, validator, sample_problem):
        """Test required elements for very strict strictness level"""
        
        elements = validator._get_required_elements(sample_problem, StrictnessLevel.VERY_STRICT)
        
        expected_edge_cases = ["edge_case_consideration", "error_handling_awareness"]
        assert all(elem in elements for elem in expected_edge_cases)
        assert len(elements) == 9  # All elements including edge cases
    
    def test_fallback_analysis_comprehensive(self, validator):
        """Test fallback analysis with comprehensive response"""
        
        comprehensive_response = "I will create a list to store numbers. I will use a for loop to iterate 5 times. In each iteration, I will use input() to get a number from user."
        
        required_elements = ["data_structure_choice", "input_method", "loop_structure", "process_flow"]
        
        analysis = validator._fallback_analysis(comprehensive_response, required_elements)
        
        assert analysis['confidence_score'] > 0.5
        assert len(analysis['missing_elements']) < len(required_elements)
        assert analysis['recommendation'] in ['APPROVE', 'CROSS_QUESTION']
    
    def test_fallback_analysis_incomplete(self, validator):
        """Test fallback analysis with incomplete response"""
        
        incomplete_response = "I will do something with numbers"
        
        required_elements = ["data_structure_choice", "input_method", "loop_structure", "process_flow"]
        
        analysis = validator._fallback_analysis(incomplete_response, required_elements)
        
        assert analysis['confidence_score'] < 0.5
        assert len(analysis['missing_elements']) > 0
        assert analysis['recommendation'] == 'CROSS_QUESTION'


class TestValidationLevelDetermination:
    """Test validation level determination logic"""
    
    @pytest.fixture
    def validator(self):
        return EnhancedLogicValidator()
    
    def test_high_confidence_approval(self, validator):
        """Test that high confidence leads to approval"""
        
        analysis = {
            'confidence_score': 0.9,
            'recommendation': 'APPROVE',
            'missing_elements': []
        }
        
        level = validator._determine_validation_level(
            analysis, 
            LogicValidationLevel.CROSS_QUESTIONING,
            StrictnessLevel.MODERATE
        )
        
        assert level == LogicValidationLevel.LOGIC_APPROVED
    
    def test_medium_confidence_cross_questioning(self, validator):
        """Test that medium confidence leads to cross-questioning"""
        
        analysis = {
            'confidence_score': 0.6,
            'recommendation': 'CROSS_QUESTION',
            'missing_elements': ['data_structure_choice']
        }
        
        level = validator._determine_validation_level(
            analysis,
            LogicValidationLevel.INITIAL_REQUEST,
            StrictnessLevel.LENIENT
        )
        
        assert level == LogicValidationLevel.CROSS_QUESTIONING
    
    def test_low_confidence_basic_explanation(self, validator):
        """Test that low confidence requires basic explanation"""
        
        analysis = {
            'confidence_score': 0.2,
            'recommendation': 'REQUIRE_MORE_DETAIL',
            'missing_elements': ['data_structure_choice', 'loop_structure', 'input_method']
        }
        
        level = validator._determine_validation_level(
            analysis,
            LogicValidationLevel.INITIAL_REQUEST,
            StrictnessLevel.LENIENT
        )
        
        assert level == LogicValidationLevel.BASIC_EXPLANATION
    
    def test_progressive_validation_levels(self, validator):
        """Test progressive validation level escalation"""
        
        medium_analysis = {
            'confidence_score': 0.6,
            'recommendation': 'CROSS_QUESTION',
            'missing_elements': ['variable_names']
        }
        
        # From CROSS_QUESTIONING to DETAILED_VALIDATION
        level1 = validator._determine_validation_level(
            medium_analysis,
            LogicValidationLevel.CROSS_QUESTIONING,
            StrictnessLevel.MODERATE
        )
        assert level1 == LogicValidationLevel.DETAILED_VALIDATION
        
        # From DETAILED_VALIDATION to EDGE_CASE_TESTING
        level2 = validator._determine_validation_level(
            medium_analysis,
            LogicValidationLevel.DETAILED_VALIDATION,
            StrictnessLevel.STRICT
        )
        assert level2 == LogicValidationLevel.EDGE_CASE_TESTING


class TestStrictnessEscalation:
    """Test strictness level escalation"""
    
    @pytest.fixture
    def validator(self):
        return EnhancedLogicValidator()
    
    def test_strictness_escalation_sequence(self, validator):
        """Test complete strictness escalation sequence"""
        
        # LENIENT -> MODERATE
        level1 = validator._escalate_strictness(StrictnessLevel.LENIENT)
        assert level1 == StrictnessLevel.MODERATE
        
        # MODERATE -> STRICT
        level2 = validator._escalate_strictness(StrictnessLevel.MODERATE)
        assert level2 == StrictnessLevel.STRICT
        
        # STRICT -> VERY_STRICT
        level3 = validator._escalate_strictness(StrictnessLevel.STRICT)
        assert level3 == StrictnessLevel.VERY_STRICT
        
        # VERY_STRICT -> GAMING_MODE
        level4 = validator._escalate_strictness(StrictnessLevel.VERY_STRICT)
        assert level4 == StrictnessLevel.GAMING_MODE
        
        # GAMING_MODE -> GAMING_MODE (stays at max)
        level5 = validator._escalate_strictness(StrictnessLevel.GAMING_MODE)
        assert level5 == StrictnessLevel.GAMING_MODE


class TestCrossQuestionGeneration:
    """Test cross-question generation"""
    
    @pytest.fixture
    def validator(self):
        return EnhancedLogicValidator()
    
    @pytest.fixture
    def sample_problem(self):
        return Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter five numbers one by one.",
            concepts=["lists", "loops", "input"]
        )
    
    @pytest.mark.asyncio
    async def test_cross_questions_for_missing_data_structure(self, validator, sample_problem):
        """Test cross-question generation for missing data structure"""
        
        analysis = {
            'missing_elements': ['data_structure_choice'],
            'confidence_score': 0.4
        }
        
        questions = await validator._generate_cross_questions(
            analysis,
            sample_problem,
            LogicValidationLevel.CROSS_QUESTIONING,
            StrictnessLevel.MODERATE
        )
        
        assert len(questions) > 0
        assert any("data structure" in q.lower() for q in questions)
    
    @pytest.mark.asyncio
    async def test_cross_questions_for_missing_loop(self, validator, sample_problem):
        """Test cross-question generation for missing loop structure"""
        
        analysis = {
            'missing_elements': ['loop_structure'],
            'confidence_score': 0.4
        }
        
        questions = await validator._generate_cross_questions(
            analysis,
            sample_problem,
            LogicValidationLevel.CROSS_QUESTIONING,
            StrictnessLevel.MODERATE
        )
        
        assert len(questions) > 0
        assert any("loop" in q.lower() for q in questions)
    
    @pytest.mark.asyncio
    async def test_cross_questions_limit(self, validator, sample_problem):
        """Test that cross-questions are limited to avoid overwhelming student"""
        
        analysis = {
            'missing_elements': ['data_structure_choice', 'loop_structure', 'input_method', 'variable_names', 'data_type_handling'],
            'confidence_score': 0.2
        }
        
        questions = await validator._generate_cross_questions(
            analysis,
            sample_problem,
            LogicValidationLevel.CROSS_QUESTIONING,
            StrictnessLevel.MODERATE
        )
        
        assert len(questions) <= 3  # Should be limited to 3 questions max


class TestSimilarityCalculation:
    """Test text similarity calculation"""
    
    @pytest.fixture
    def validator(self):
        return EnhancedLogicValidator()
    
    def test_identical_texts(self, validator):
        """Test similarity of identical texts"""
        
        text = "I will use a for loop to iterate through the list"
        similarity = validator._calculate_similarity(text, text)
        
        assert similarity == 1.0
    
    def test_completely_different_texts(self, validator):
        """Test similarity of completely different texts"""
        
        text1 = "cats and dogs"
        text2 = "programming with python"
        similarity = validator._calculate_similarity(text1, text2)
        
        assert similarity == 0.0
    
    def test_partial_similarity(self, validator):
        """Test partial similarity calculation"""
        
        text1 = "I will use a for loop"
        text2 = "I will use a while loop"
        similarity = validator._calculate_similarity(text1, text2)
        
        assert 0.0 < similarity < 1.0
        assert similarity > 0.5  # Should be fairly similar
    
    def test_case_insensitive_similarity(self, validator):
        """Test that similarity calculation is case insensitive"""
        
        text1 = "FOR LOOP WITH RANGE"
        text2 = "for loop with range"
        similarity = validator._calculate_similarity(text1, text2)
        
        assert similarity == 1.0


# Integration test scenarios
class TestValidationScenarios:
    """Test complete validation scenarios from real conversations"""
    
    @pytest.fixture
    def validator(self):
        return EnhancedLogicValidator()
    
    @pytest.fixture
    def list_problem(self):
        return Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter five numbers one by one. Append each number to a list and print the final list of numbers.",
            concepts=["lists", "loops", "input"]
        )
    
    @pytest.mark.asyncio
    async def test_vague_response_scenario(self, validator, list_problem):
        """Test handling of vague student response like 'I will run the loop, take input and print'"""
        
        student_response = "I will run the loop, take input and print"
        
        with patch.object(validator, '_analyze_logic_content') as mock_analysis:
            mock_analysis.return_value = {
                'confidence_score': 0.3,
                'missing_elements': ['data_structure_choice', 'loop_structure', 'input_method'],
                'recommendation': 'CROSS_QUESTION'
            }
            
            result = await validator.validate_logic_explanation(
                student_response,
                list_problem,
                [],
                LogicValidationLevel.INITIAL_REQUEST,
                StrictnessLevel.LENIENT
            )
            
            assert result.is_approved == False
            assert result.validation_level == LogicValidationLevel.CROSS_QUESTIONING
            assert len(result.cross_questions) > 0
            assert len(result.missing_elements) > 0
    
    @pytest.mark.asyncio
    async def test_copy_paste_scenario(self, validator, list_problem):
        """Test handling of copy-paste from AI response"""
        
        conversation = [
            ConversationMessage(
                timestamp=datetime.now(),
                message_type=MessageType.ASSISTANT,
                content="You need to initialize an empty list to store the numbers."
            )
        ]
        
        # Student copies AI response
        student_response = "I need to initialize an empty list to store the numbers."
        
        result = await validator.validate_logic_explanation(
            student_response,
            list_problem,
            conversation,
            LogicValidationLevel.INITIAL_REQUEST,
            StrictnessLevel.LENIENT
        )
        
        assert result.is_approved == False
        assert result.validation_level == LogicValidationLevel.GAMING_DETECTED
        assert result.strictness_level == StrictnessLevel.GAMING_MODE
        assert len(result.gaming_indicators) > 0
    
    @pytest.mark.asyncio
    async def test_comprehensive_valid_response(self, validator, list_problem):
        """Test handling of comprehensive valid logic response"""
        
        comprehensive_response = """
        I will solve this step by step:
        1. Create an empty list called 'numbers' to store the user input
        2. Use a for loop with range(5) to iterate exactly 5 times
        3. In each iteration, use input() function to ask user for a number
        4. Convert the string input to integer using int() function
        5. Append the integer to my 'numbers' list using append() method
        6. After the loop completes, print the final list
        """
        
        with patch.object(validator, '_analyze_logic_content') as mock_analysis:
            mock_analysis.return_value = {
                'confidence_score': 0.9,
                'missing_elements': [],
                'recommendation': 'APPROVE'
            }
            
            result = await validator.validate_logic_explanation(
                comprehensive_response,
                list_problem,
                [],
                LogicValidationLevel.CROSS_QUESTIONING,
                StrictnessLevel.MODERATE
            )
            
            assert result.is_approved == True
            assert result.validation_level == LogicValidationLevel.LOGIC_APPROVED
            assert result.next_action == "proceed_to_coding"
            assert "excellent" in result.feedback_message.lower() or "perfect" in result.feedback_message.lower()


if __name__ == "__main__":
    pytest.main([__file__])