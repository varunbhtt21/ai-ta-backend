"""
Test suite for Code Understanding Verifier
Tests understanding verification and code comprehension assessment
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime

from app.services.code_understanding_verifier import (
    CodeUnderstandingVerifier,
    UnderstandingLevel,
    QuestionType,
    UnderstandingAssessment,
    VerificationResult
)
from app.models import ConversationMessage, MessageType, Problem


class TestCodeUnderstandingVerifier:
    """Test suite for Code Understanding Verifier"""
    
    @pytest.fixture
    def verifier(self):
        """Create verifier instance for testing"""
        return CodeUnderstandingVerifier()
    
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
    def sample_code(self):
        """Sample student code for testing"""
        return """
numbers = []
for i in range(5):
    num = input("Enter a number: ")
    numbers.append(int(num))
print(numbers)
"""
    
    @pytest.fixture
    def approved_logic(self):
        """Sample approved logic"""
        return "Create empty list, use for loop with range(5), get input, convert to int, append to list, print result"


class TestCodeStructureAnalysis:
    """Test code structure analysis functionality"""
    
    @pytest.fixture
    def verifier(self):
        return CodeUnderstandingVerifier()
    
    def test_code_structure_analysis_valid_code(self, verifier, sample_code):
        """Test analysis of valid code structure"""
        
        analysis = verifier._analyze_code_structure(sample_code)
        
        expected_concepts = [
            'list_usage', 'for_loop', 'range_iteration', 
            'user_input', 'type_conversion', 'list_append', 
            'output_display', 'variable_assignment'
        ]
        
        for concept in expected_concepts:
            assert concept in analysis['concepts_present'], f"Missing concept: {concept}"
        
        assert analysis['complexity_level'] == 'basic'
        print("✅ Code structure analysis working for valid code")
    
    def test_code_structure_analysis_invalid_code(self, verifier):
        """Test analysis of code with syntax errors"""
        
        invalid_code = """
numbers = []
for i in range(5)  # Missing colon
    num = input("Enter number: ")
    numbers.append(int(num)
"""
        
        analysis = verifier._analyze_code_structure(invalid_code)
        
        assert 'syntax_errors' in analysis['potential_issues']
        assert len(analysis['concepts_present']) > 0  # Should still detect some concepts
        print("✅ Code structure analysis handles invalid code")
    
    def test_complex_code_detection(self, verifier):
        """Test detection of complex code structures"""
        
        complex_code = """
def process_numbers():
    numbers = [int(input(f"Enter number {i+1}: ")) for i in range(5)]
    return numbers if all(isinstance(x, int) for x in numbers) else []

if __name__ == "__main__":
    result = process_numbers()
    print(result)
"""
        
        analysis = verifier._analyze_code_structure(complex_code)
        
        assert analysis['complexity_level'] == 'advanced'
        assert 'function_definition' in analysis['concepts_present']
        print("✅ Complex code detection working")


class TestExplanationAssessment:
    """Test student explanation quality assessment"""
    
    @pytest.fixture
    def verifier(self):
        return CodeUnderstandingVerifier()
    
    @pytest.mark.asyncio
    async def test_comprehensive_explanation_assessment(self, verifier, sample_code, sample_problem):
        """Test assessment of comprehensive explanation"""
        
        comprehensive_explanation = """
My code first creates an empty list called numbers to store the user input. 
Then it uses a for loop with range(5) because we need exactly 5 numbers. 
In each iteration, it uses input() to ask the user for a number, then converts 
the string to an integer with int() because input() returns strings. 
The append() method adds each number to the list. Finally, print() displays the complete list.
"""
        
        code_analysis = verifier._analyze_code_structure(sample_code)
        assessment = await verifier._assess_explanation_quality(
            comprehensive_explanation, sample_code, code_analysis
        )
        
        assert assessment.understanding_level == UnderstandingLevel.CONCEPTUAL
        assert assessment.confidence_score > 0.7
        assert len(assessment.specific_concepts_understood) >= 5
        assert "good_concept_coverage" in assessment.strengths
        print("✅ Comprehensive explanation properly assessed")
    
    @pytest.mark.asyncio
    async def test_vague_explanation_assessment(self, verifier, sample_code, sample_problem):
        """Test assessment of vague explanation"""
        
        vague_explanation = "The code works and does what it's supposed to do."
        
        code_analysis = verifier._analyze_code_structure(sample_code)
        assessment = await verifier._assess_explanation_quality(
            vague_explanation, sample_code, code_analysis
        )
        
        assert assessment.understanding_level == UnderstandingLevel.SURFACE_LEVEL
        assert assessment.confidence_score < 0.3
        assert "explanation_too_brief" in assessment.gaps
        print("✅ Vague explanation properly assessed")
    
    @pytest.mark.asyncio
    async def test_partial_explanation_assessment(self, verifier, sample_code, sample_problem):
        """Test assessment of partial explanation"""
        
        partial_explanation = """
My code creates a list and uses a for loop to get input from the user. 
It runs 5 times and adds each number to the list.
"""
        
        code_analysis = verifier._analyze_code_structure(sample_code)
        assessment = await verifier._assess_explanation_quality(
            partial_explanation, sample_code, code_analysis
        )
        
        assert assessment.understanding_level in [UnderstandingLevel.SURFACE_LEVEL, UnderstandingLevel.CONCEPTUAL]
        assert 0.3 < assessment.confidence_score < 0.7
        assert len(assessment.concepts_needing_work) > 0
        print("✅ Partial explanation properly assessed")


class TestVerificationQuestions:
    """Test generation of verification questions"""
    
    @pytest.fixture
    def verifier(self):
        return CodeUnderstandingVerifier()
    
    def test_surface_level_questions(self, verifier, sample_code, sample_problem):
        """Test generation of surface-level questions"""
        
        code_analysis = verifier._analyze_code_structure(sample_code)
        assessment = UnderstandingAssessment(
            understanding_level=UnderstandingLevel.SURFACE_LEVEL,
            strengths=[],
            gaps=["incomplete_concept_explanation"],
            confidence_score=0.4,
            specific_concepts_understood=[],
            concepts_needing_work=['list_usage', 'for_loop']
        )
        
        questions = verifier._generate_verification_questions(
            code_analysis, assessment, UnderstandingLevel.SURFACE_LEVEL
        )
        
        assert len(questions) > 0
        assert len(questions) <= 3
        
        questions_text = " ".join(questions).lower()
        assert any(keyword in questions_text for keyword in ["list", "loop", "does"])
        print("✅ Surface level questions generated correctly")
    
    def test_conceptual_level_questions(self, verifier, sample_code, sample_problem):
        """Test generation of conceptual-level questions"""
        
        code_analysis = verifier._analyze_code_structure(sample_code)
        assessment = UnderstandingAssessment(
            understanding_level=UnderstandingLevel.CONCEPTUAL,
            strengths=["good_concept_coverage"],
            gaps=[],
            confidence_score=0.7,
            specific_concepts_understood=['list_usage', 'for_loop'],
            concepts_needing_work=[]
        )
        
        questions = verifier._generate_verification_questions(
            code_analysis, assessment, UnderstandingLevel.CONCEPTUAL
        )
        
        assert len(questions) > 0
        questions_text = " ".join(questions).lower()
        assert any(keyword in questions_text for keyword in ["why", "choose", "instead"])
        print("✅ Conceptual level questions generated correctly")
    
    def test_deep_understanding_questions(self, verifier, sample_code, sample_problem):
        """Test generation of deep understanding questions"""
        
        code_analysis = verifier._analyze_code_structure(sample_code)
        assessment = UnderstandingAssessment(
            understanding_level=UnderstandingLevel.DEEP_UNDERSTANDING,
            strengths=["good_concept_coverage", "explains_reasoning"],
            gaps=[],
            confidence_score=0.9,
            specific_concepts_understood=['list_usage', 'for_loop', 'type_conversion'],
            concepts_needing_work=[]
        )
        
        questions = verifier._generate_verification_questions(
            code_analysis, assessment, UnderstandingLevel.DEEP_UNDERSTANDING
        )
        
        assert len(questions) > 0
        questions_text = " ".join(questions).lower()
        assert any(keyword in questions_text for keyword in ["alternative", "modify", "what would happen"])
        print("✅ Deep understanding questions generated correctly")


class TestConceptExplanationDetection:
    """Test detection of concept explanations in student text"""
    
    @pytest.fixture
    def verifier(self):
        return CodeUnderstandingVerifier()
    
    def test_list_concept_detection(self, verifier):
        """Test detection of list concept explanation"""
        
        explanation = "I created a list to store all the numbers that the user enters"
        
        assert verifier._concept_explained_in_text('list_usage', explanation.lower()) == True
        assert verifier._concept_explained_in_text('for_loop', explanation.lower()) == False
        print("✅ List concept detection working")
    
    def test_loop_concept_detection(self, verifier):
        """Test detection of loop concept explanation"""
        
        explanation = "I used a for loop to repeat the process 5 times"
        
        assert verifier._concept_explained_in_text('for_loop', explanation.lower()) == True
        assert verifier._concept_explained_in_text('while_loop', explanation.lower()) == False
        print("✅ Loop concept detection working")
    
    def test_input_concept_detection(self, verifier):
        """Test detection of input concept explanation"""
        
        explanation = "The input() function asks the user to type a number"
        
        assert verifier._concept_explained_in_text('user_input', explanation.lower()) == True
        assert verifier._concept_explained_in_text('output_display', explanation.lower()) == False
        print("✅ Input concept detection working")
    
    def test_type_conversion_detection(self, verifier):
        """Test detection of type conversion explanation"""
        
        explanation = "I convert the string input to an integer using int()"
        
        assert verifier._concept_explained_in_text('type_conversion', explanation.lower()) == True
        print("✅ Type conversion detection working")


class TestVerificationStatusDetermination:
    """Test determination of verification status"""
    
    @pytest.fixture
    def verifier(self):
        return CodeUnderstandingVerifier()
    
    def test_surface_level_verification_pass(self, verifier):
        """Test passing surface level verification"""
        
        assessment = UnderstandingAssessment(
            understanding_level=UnderstandingLevel.SURFACE_LEVEL,
            strengths=["good_concept_coverage"],
            gaps=[],
            confidence_score=0.7,
            specific_concepts_understood=['list_usage', 'for_loop'],
            concepts_needing_work=[]
        )
        
        is_verified = verifier._determine_verification_status(
            assessment, UnderstandingLevel.SURFACE_LEVEL
        )
        
        assert is_verified == True
        print("✅ Surface level verification pass working")
    
    def test_surface_level_verification_fail(self, verifier):
        """Test failing surface level verification"""
        
        assessment = UnderstandingAssessment(
            understanding_level=UnderstandingLevel.SURFACE_LEVEL,
            strengths=[],
            gaps=["incomplete_concept_explanation", "explanation_too_brief"],
            confidence_score=0.3,
            specific_concepts_understood=[],
            concepts_needing_work=['list_usage', 'for_loop']
        )
        
        is_verified = verifier._determine_verification_status(
            assessment, UnderstandingLevel.SURFACE_LEVEL
        )
        
        assert is_verified == False
        print("✅ Surface level verification fail working")
    
    def test_conceptual_level_verification(self, verifier):
        """Test conceptual level verification requirements"""
        
        passing_assessment = UnderstandingAssessment(
            understanding_level=UnderstandingLevel.CONCEPTUAL,
            strengths=["good_concept_coverage", "explains_reasoning"],
            gaps=[],
            confidence_score=0.8,
            specific_concepts_understood=['list_usage', 'for_loop', 'user_input'],
            concepts_needing_work=[]
        )
        
        is_verified = verifier._determine_verification_status(
            passing_assessment, UnderstandingLevel.CONCEPTUAL
        )
        
        assert is_verified == True
        print("✅ Conceptual level verification working")


class TestFullVerificationFlow:
    """Test complete verification flow"""
    
    @pytest.fixture
    def verifier(self):
        return CodeUnderstandingVerifier()
    
    @pytest.mark.asyncio
    async def test_successful_verification_flow(self, verifier, sample_code, sample_problem, approved_logic):
        """Test complete successful verification"""
        
        good_explanation = """
My code creates an empty list called numbers to store the input. 
Then it uses a for loop with range(5) to iterate exactly 5 times. 
In each iteration, input() gets a number from the user, int() converts 
the string to an integer, and append() adds it to the list. 
Finally, print() displays the complete list.
"""
        
        result = await verifier.verify_code_understanding(
            student_code=sample_code,
            student_explanation=good_explanation,
            problem=sample_problem,
            approved_logic=approved_logic,
            verification_level=UnderstandingLevel.SURFACE_LEVEL
        )
        
        assert result.is_verified == True
        assert result.assessment.confidence_score > 0.6
        assert len(result.assessment.specific_concepts_understood) >= 4
        assert not result.requires_more_verification
        print("✅ Successful verification flow working")
    
    @pytest.mark.asyncio
    async def test_failed_verification_flow(self, verifier, sample_code, sample_problem, approved_logic):
        """Test verification that requires more work"""
        
        poor_explanation = "The code works fine and does what it needs to do."
        
        result = await verifier.verify_code_understanding(
            student_code=sample_code,
            student_explanation=poor_explanation,
            problem=sample_problem,
            approved_logic=approved_logic,
            verification_level=UnderstandingLevel.SURFACE_LEVEL
        )
        
        assert result.is_verified == False
        assert result.assessment.confidence_score < 0.4
        assert len(result.next_questions) > 0
        assert result.requires_more_verification == True
        print("✅ Failed verification flow working")


if __name__ == "__main__":
    pytest.main([__file__])