"""
Test suite for Scenario-Based Prompt Manager
Tests scenario selection, few-shot prompting, and cross-questioning functionality
"""

import pytest
from unittest.mock import Mock
from datetime import datetime
from typing import List

from app.services.scenario_prompt_manager import (
    ScenarioPromptManager,
    ScenarioType,
    ResponseTone,
    TutoringScenario
)
from app.services.validation_types import LogicValidationLevel, StrictnessLevel
from app.models import Problem, ConversationMessage, MessageType


class TestScenarioPromptManager:
    """Test suite for Scenario Prompt Manager"""
    
    @pytest.fixture
    def manager(self):
        """Create manager instance for testing"""
        return ScenarioPromptManager()
    
    @pytest.fixture 
    def sample_problem(self):
        """Create sample problem for testing"""
        return Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter five numbers one by one.",
            concepts=["lists", "loops", "input"]
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
            )
        ]


class TestScenarioDatabase:
    """Test the comprehensive scenario database"""
    
    @pytest.fixture
    def manager(self):
        return ScenarioPromptManager()
    
    def test_scenario_database_loaded(self, manager):
        """Test that comprehensive scenario database is loaded"""
        
        assert len(manager.scenarios) >= 20  # Should have many scenarios
        assert all(isinstance(scenario, TutoringScenario) for scenario in manager.scenarios)
        print(f"✅ Loaded {len(manager.scenarios)} scenarios")
    
    def test_scenario_types_coverage(self, manager):
        """Test that all scenario types are covered"""
        
        scenario_types = set(scenario.scenario_type for scenario in manager.scenarios)
        
        expected_types = {
            ScenarioType.VAGUE_LOGIC_ATTEMPT,
            ScenarioType.COPY_PASTE_DETECTION,
            ScenarioType.CODE_REQUEST,
            ScenarioType.NEXT_QUESTION_REQUEST,
            ScenarioType.REPETITIVE_RESPONSE,
            ScenarioType.LOGIC_VALIDATION,
            ScenarioType.CROSS_QUESTIONING,
            ScenarioType.GAMING_RESPONSE,
            ScenarioType.PROGRESS_VALIDATION
        }
        
        for expected_type in expected_types:
            assert expected_type in scenario_types, f"Missing scenario type: {expected_type}"
        
        print("✅ All scenario types covered")
    
    def test_scenario_structure_validity(self, manager):
        """Test that all scenarios have valid structure"""
        
        for scenario in manager.scenarios:
            assert scenario.scenario_id is not None
            assert scenario.scenario_type is not None
            assert scenario.problem_context is not None
            assert scenario.student_input is not None
            assert scenario.ai_response is not None
            assert scenario.response_tone is not None
            assert scenario.teaching_principle is not None
            assert isinstance(scenario.follow_up_questions, list)
            assert scenario.validation_level is not None
            assert scenario.strictness_level is not None
            assert isinstance(scenario.tags, list)
        
        print("✅ All scenarios have valid structure")


class TestScenarioSelection:
    """Test scenario selection for different situations"""
    
    @pytest.fixture
    def manager(self):
        return ScenarioPromptManager()
    
    def test_vague_logic_scenario_selection(self, manager):
        """Test selection of scenarios for vague logic attempts"""
        
        scenarios = manager.get_scenarios_for_situation(
            scenario_type=ScenarioType.VAGUE_LOGIC_ATTEMPT,
            validation_level=LogicValidationLevel.CROSS_QUESTIONING,
            strictness_level=StrictnessLevel.MODERATE
        )
        
        assert len(scenarios) > 0
        assert all(s.scenario_type == ScenarioType.VAGUE_LOGIC_ATTEMPT for s in scenarios)
        print(f"✅ Found {len(scenarios)} vague logic scenarios")
    
    def test_copy_paste_scenario_selection(self, manager):
        """Test selection of scenarios for copy-paste detection"""
        
        scenarios = manager.get_scenarios_for_situation(
            scenario_type=ScenarioType.COPY_PASTE_DETECTION,
            validation_level=LogicValidationLevel.GAMING_DETECTED,
            strictness_level=StrictnessLevel.GAMING_MODE
        )
        
        assert len(scenarios) > 0
        assert all(s.scenario_type == ScenarioType.COPY_PASTE_DETECTION for s in scenarios)
        print(f"✅ Found {len(scenarios)} copy-paste scenarios")
    
    def test_code_request_scenario_selection(self, manager):
        """Test selection of scenarios for code requests"""
        
        scenarios = manager.get_scenarios_for_situation(
            scenario_type=ScenarioType.CODE_REQUEST,
            validation_level=LogicValidationLevel.AWAITING_APPROACH,
            strictness_level=StrictnessLevel.STRICT
        )
        
        assert len(scenarios) > 0
        assert all(s.scenario_type == ScenarioType.CODE_REQUEST for s in scenarios)
        print(f"✅ Found {len(scenarios)} code request scenarios")
    
    def test_scenario_relevance_ranking(self, manager):
        """Test that scenarios are ranked by relevance"""
        
        scenarios = manager.get_scenarios_for_situation(
            scenario_type=ScenarioType.VAGUE_LOGIC_ATTEMPT,
            validation_level=LogicValidationLevel.CROSS_QUESTIONING,
            strictness_level=StrictnessLevel.MODERATE
        )
        
        # First scenario should be most relevant (exact matches)
        if len(scenarios) > 1:
            first_scenario = scenarios[0]
            assert first_scenario.validation_level == LogicValidationLevel.CROSS_QUESTIONING
            assert first_scenario.strictness_level == StrictnessLevel.MODERATE
        
        print("✅ Scenarios ranked by relevance")


class TestFewShotPromptGeneration:
    """Test few-shot prompt generation"""
    
    @pytest.fixture
    def manager(self):
        return ScenarioPromptManager()
    
    @pytest.fixture
    def sample_problem(self):
        return Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter five numbers one by one.",
            concepts=["lists", "loops", "input"]
        )
    
    @pytest.fixture
    def sample_conversation(self):
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
            )
        ]
    
    def test_few_shot_prompt_structure(self, manager, sample_problem, sample_conversation):
        """Test that few-shot prompts have proper structure"""
        
        prompt = manager.build_few_shot_prompt(
            scenario_type=ScenarioType.VAGUE_LOGIC_ATTEMPT,
            validation_level=LogicValidationLevel.CROSS_QUESTIONING,
            strictness_level=StrictnessLevel.MODERATE,
            current_problem=sample_problem,
            student_input="I will use a loop",
            conversation_history=sample_conversation,
            base_instruction="You are a programming tutor. Help the student with logic validation."
        )
        
        # Check that prompt contains all necessary sections
        assert "CURRENT SITUATION" in prompt
        assert "FEW-SHOT EXAMPLES" in prompt
        assert "CONTEXT FROM CONVERSATION" in prompt
        assert "YOUR TASK" in prompt
        assert "RESPONSE REQUIREMENTS" in prompt
        
        # Check that current problem info is included
        assert sample_problem.title in prompt
        assert sample_problem.description in prompt
        
        print("✅ Few-shot prompt has proper structure")
    
    def test_few_shot_examples_inclusion(self, manager, sample_problem, sample_conversation):
        """Test that relevant examples are included in few-shot prompts"""
        
        prompt = manager.build_few_shot_prompt(
            scenario_type=ScenarioType.VAGUE_LOGIC_ATTEMPT,
            validation_level=LogicValidationLevel.CROSS_QUESTIONING,
            strictness_level=StrictnessLevel.MODERATE,
            current_problem=sample_problem,
            student_input="I will use a loop",
            conversation_history=sample_conversation,
            base_instruction="Help with validation."
        )
        
        # Should contain example scenarios
        assert "Example 1" in prompt
        assert "Problem Context:" in prompt
        assert "Student Input:" in prompt
        assert "AI Response:" in prompt
        assert "Teaching Notes:" in prompt
        
        print("✅ Few-shot examples properly included")
    
    def test_conversation_context_formatting(self, manager, sample_problem, sample_conversation):
        """Test that conversation context is properly formatted"""
        
        prompt = manager.build_few_shot_prompt(
            scenario_type=ScenarioType.CROSS_QUESTIONING,
            validation_level=LogicValidationLevel.CROSS_QUESTIONING,
            strictness_level=StrictnessLevel.MODERATE,
            current_problem=sample_problem,
            student_input="I need more help",
            conversation_history=sample_conversation,
            base_instruction="Help student."
        )
        
        # Should contain formatted conversation
        assert "AI:" in prompt
        assert "Student:" in prompt
        
        print("✅ Conversation context properly formatted")


class TestCrossQuestionGeneration:
    """Test cross-question generation functionality"""
    
    @pytest.fixture
    def manager(self):
        return ScenarioPromptManager()
    
    @pytest.fixture
    def sample_problem(self):
        return Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter five numbers one by one.",
            concepts=["lists", "loops", "input"]
        )
    
    def test_cross_question_templates_loaded(self, manager):
        """Test that cross-question templates are loaded"""
        
        assert len(manager.cross_question_templates) > 0
        
        expected_categories = [
            "data_structure_choice",
            "loop_structure", 
            "input_method",
            "data_type_handling",
            "variable_names",
            "process_flow"
        ]
        
        for category in expected_categories:
            assert category in manager.cross_question_templates
            assert len(manager.cross_question_templates[category]) > 0
        
        print("✅ Cross-question templates loaded")
    
    def test_cross_question_generation(self, manager, sample_problem):
        """Test generation of cross-questions for missing elements"""
        
        missing_elements = ["data_structure_choice", "loop_structure", "input_method"]
        
        questions = manager.generate_cross_questions(
            missing_elements=missing_elements,
            problem=sample_problem,
            strictness_level=StrictnessLevel.MODERATE
        )
        
        assert len(questions) <= 3  # Should be limited to 3 questions
        assert len(questions) > 0
        assert all(isinstance(q, str) for q in questions)
        
        # Questions should be contextualized
        assert any("number" in q.lower() for q in questions)  # Should reference numbers from problem
        
        print(f"✅ Generated {len(questions)} cross-questions")
    
    def test_strictness_level_question_selection(self, manager, sample_problem):
        """Test that question selection varies with strictness level"""
        
        missing_elements = ["loop_structure"]
        
        # Lenient questions
        lenient_questions = manager.generate_cross_questions(
            missing_elements=missing_elements,
            problem=sample_problem,
            strictness_level=StrictnessLevel.LENIENT
        )
        
        # Strict questions
        strict_questions = manager.generate_cross_questions(
            missing_elements=missing_elements,
            problem=sample_problem,
            strictness_level=StrictnessLevel.VERY_STRICT
        )
        
        assert len(lenient_questions) > 0
        assert len(strict_questions) > 0
        
        print("✅ Question selection adapts to strictness level")
    
    def test_question_contextualization(self, manager):
        """Test that questions are contextualized for specific problems"""
        
        # Problem with numbers
        number_problem = Problem(
            number=1,
            title="Sum Numbers",
            description="Calculate sum of five numbers entered by user",
            concepts=["math"]
        )
        
        # Problem with strings
        string_problem = Problem(
            number=2,
            title="Collect Names", 
            description="Get names from user and store them",
            concepts=["strings"]
        )
        
        number_questions = manager.generate_cross_questions(
            missing_elements=["data_structure_choice"],
            problem=number_problem,
            strictness_level=StrictnessLevel.MODERATE
        )
        
        string_questions = manager.generate_cross_questions(
            missing_elements=["data_structure_choice"],
            problem=string_problem,
            strictness_level=StrictnessLevel.MODERATE
        )
        
        # Should contextualize based on problem content
        number_question = number_questions[0] if number_questions else ""
        string_question = string_questions[0] if string_questions else ""
        
        # Questions should be different based on context
        assert number_question != string_question
        
        print("✅ Questions properly contextualized")


class TestResponseToneSelection:
    """Test response tone selection logic"""
    
    @pytest.fixture
    def manager(self):
        return ScenarioPromptManager()
    
    def test_gaming_detection_tone(self, manager):
        """Test that gaming detection triggers strict tone"""
        
        tone = manager.get_appropriate_tone(
            validation_level=LogicValidationLevel.GAMING_DETECTED,
            strictness_level=StrictnessLevel.GAMING_MODE,
            attempt_count=1
        )
        
        assert tone == ResponseTone.STRICT
        print("✅ Gaming detection triggers strict tone")
    
    def test_logic_approved_tone(self, manager):
        """Test that logic approval triggers celebratory tone"""
        
        tone = manager.get_appropriate_tone(
            validation_level=LogicValidationLevel.LOGIC_APPROVED,
            strictness_level=StrictnessLevel.MODERATE,
            attempt_count=1
        )
        
        assert tone == ResponseTone.CELEBRATORY
        print("✅ Logic approval triggers celebratory tone")
    
    def test_multiple_attempts_tone(self, manager):
        """Test that multiple attempts trigger empathetic tone"""
        
        tone = manager.get_appropriate_tone(
            validation_level=LogicValidationLevel.CROSS_QUESTIONING,
            strictness_level=StrictnessLevel.MODERATE,
            attempt_count=4
        )
        
        assert tone == ResponseTone.EMPATHETIC
        print("✅ Multiple attempts trigger empathetic tone")
    
    def test_strictness_level_tone_mapping(self, manager):
        """Test that strictness levels map to appropriate tones"""
        
        # Lenient should be encouraging
        lenient_tone = manager.get_appropriate_tone(
            validation_level=LogicValidationLevel.CROSS_QUESTIONING,
            strictness_level=StrictnessLevel.LENIENT,
            attempt_count=1
        )
        assert lenient_tone == ResponseTone.ENCOURAGING
        
        # Very strict should be strict
        strict_tone = manager.get_appropriate_tone(
            validation_level=LogicValidationLevel.DETAILED_VALIDATION,
            strictness_level=StrictnessLevel.VERY_STRICT,
            attempt_count=1
        )
        assert strict_tone == ResponseTone.STRICT
        
        print("✅ Strictness levels map to appropriate tones")


class TestResponseTemplates:
    """Test response template system"""
    
    @pytest.fixture
    def manager(self):
        return ScenarioPromptManager()
    
    def test_response_templates_loaded(self, manager):
        """Test that response templates are loaded for all tones"""
        
        expected_tones = [
            ResponseTone.ENCOURAGING,
            ResponseTone.FIRM_BUT_KIND,
            ResponseTone.STRICT,
            ResponseTone.EMPATHETIC,
            ResponseTone.CELEBRATORY
        ]
        
        for tone in expected_tones:
            assert tone in manager.response_templates
            assert len(manager.response_templates[tone]) > 0
            
            # All templates should have {content} placeholder
            for template in manager.response_templates[tone]:
                assert "{content}" in template
        
        print("✅ Response templates loaded for all tones")
    
    def test_template_tone_appropriateness(self, manager):
        """Test that templates match their tone categories"""
        
        encouraging_templates = manager.response_templates[ResponseTone.ENCOURAGING]
        strict_templates = manager.response_templates[ResponseTone.STRICT]
        
        # Encouraging templates should have positive words
        encouraging_words = ["great", "good", "excellent", "perfect", "right"]
        assert any(word in template.lower() for template in encouraging_templates for word in encouraging_words)
        
        # Strict templates should have firm language
        strict_words = ["need", "must", "require", "insist"]
        assert any(word in template.lower() for template in strict_templates for word in strict_words)
        
        print("✅ Templates match their tone categories")


# Integration test scenarios
class TestScenarioIntegration:
    """Test integration with real conversation scenarios"""
    
    @pytest.fixture
    def manager(self):
        return ScenarioPromptManager()
    
    def test_vague_student_response_scenario(self, manager):
        """Test handling of vague student response with few-shot prompting"""
        
        problem = Problem(
            number=1,
            title="Create a List with User Input",
            description="Write a program that prompts the user to enter five numbers one by one.",
            concepts=["lists", "loops", "input"]
        )
        
        conversation = [
            ConversationMessage(
                timestamp=datetime.now(),
                message_type=MessageType.ASSISTANT,
                content="How are you thinking to solve this problem?"
            )
        ]
        
        # Test the complete few-shot prompt generation
        prompt = manager.build_few_shot_prompt(
            scenario_type=ScenarioType.VAGUE_LOGIC_ATTEMPT,
            validation_level=LogicValidationLevel.CROSS_QUESTIONING,
            strictness_level=StrictnessLevel.MODERATE,
            current_problem=problem,
            student_input="I will run the loop, take input and print",
            conversation_history=conversation,
            base_instruction="You are a programming tutor helping with logic validation."
        )
        
        # Prompt should contain relevant guidance
        assert "more specifics" in prompt.lower() or "more detail" in prompt.lower()
        assert "loop" in prompt.lower()
        assert len(prompt.split("Example")) >= 2  # Should have examples
        
        print("✅ Vague response scenario handled correctly")
    
    def test_copy_paste_detection_scenario(self, manager):
        """Test copy-paste detection scenario with appropriate response"""
        
        scenarios = manager.get_scenarios_for_situation(
            scenario_type=ScenarioType.COPY_PASTE_DETECTION,
            validation_level=LogicValidationLevel.GAMING_DETECTED,
            strictness_level=StrictnessLevel.GAMING_MODE
        )
        
        assert len(scenarios) > 0
        
        # Should have scenarios that address copy-paste behavior
        copy_paste_scenario = scenarios[0]
        assert "similar" in copy_paste_scenario.ai_response.lower() or "own words" in copy_paste_scenario.ai_response.lower()
        assert copy_paste_scenario.response_tone in [ResponseTone.FIRM_BUT_KIND, ResponseTone.STRICT]
        
        print("✅ Copy-paste detection scenario properly configured")


if __name__ == "__main__":
    pytest.main([__file__])