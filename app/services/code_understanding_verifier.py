"""
Code Understanding Verification Service
Ensures students can explain and understand their own implemented code.
Part of Phase 5: Code Implementation Phase Controls
"""

from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import logging
import ast
import re

from app.models import ConversationMessage, MessageType, Problem
from app.services.openai_client import openai_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class UnderstandingLevel(Enum):
    """Levels of code understanding verification"""
    SURFACE_LEVEL = "surface_level"           # Can describe what code does
    CONCEPTUAL = "conceptual"                 # Understands why it works
    DEEP_UNDERSTANDING = "deep_understanding" # Can explain alternatives and trade-offs
    MASTERY = "mastery"                       # Can teach it to others


class QuestionType(Enum):
    """Types of understanding verification questions"""
    WHAT_DOES_IT_DO = "what_does_it_do"       # Basic functionality
    WHY_THIS_WAY = "why_this_way"             # Design choices
    WHAT_IF_CHANGED = "what_if_changed"       # Hypothetical modifications
    ALTERNATIVES = "alternatives"              # Other approaches
    DEBUGGING = "debugging"                   # Error identification
    TEACHING = "teaching"                     # Explain to others


@dataclass
class UnderstandingAssessment:
    """Assessment of student's code understanding"""
    understanding_level: UnderstandingLevel
    strengths: List[str]
    gaps: List[str]
    confidence_score: float  # 0.0 to 1.0
    specific_concepts_understood: List[str]
    concepts_needing_work: List[str]


@dataclass
class VerificationResult:
    """Result of understanding verification"""
    is_verified: bool
    assessment: UnderstandingAssessment
    next_questions: List[str]
    feedback_message: str
    requires_more_verification: bool
    suggested_practice: List[str]


class CodeUnderstandingVerifier:
    """Verifies that students truly understand their implemented code"""
    
    def __init__(self):
        self.openai_client = openai_client
        
        # Question templates for different verification levels
        self.verification_questions = self._load_verification_questions()
        
        # Code concept patterns for analysis
        self.concept_patterns = self._load_concept_patterns()
        
        # Understanding indicators from student responses
        self.understanding_indicators = self._load_understanding_indicators()
        
        logger.info(f"🧠 UNDERSTANDING_VERIFIER: Initialized with verification questions")
    
    async def verify_code_understanding(
        self,
        student_code: str,
        student_explanation: str,
        problem: Problem,
        approved_logic: str,
        verification_level: UnderstandingLevel = UnderstandingLevel.SURFACE_LEVEL
    ) -> VerificationResult:
        """
        Verify student's understanding of their own code implementation
        """
        logger.info(f"🔍 UNDERSTANDING_VERIFIER: Verifying at level {verification_level.value}")
        
        try:
            # Step 1: Analyze the code to understand its structure
            code_analysis = self._analyze_code_structure(student_code)
            
            # Step 2: Assess student's explanation quality
            explanation_assessment = await self._assess_explanation_quality(
                student_explanation, student_code, code_analysis
            )
            
            # Step 3: Generate targeted questions based on assessment
            next_questions = self._generate_verification_questions(
                code_analysis, explanation_assessment, verification_level
            )
            
            # Step 4: Determine if understanding is verified
            is_verified = self._determine_verification_status(
                explanation_assessment, verification_level
            )
            
            # Step 5: Create comprehensive feedback
            feedback = self._generate_understanding_feedback(
                explanation_assessment, verification_level, is_verified
            )
            
            return VerificationResult(
                is_verified=is_verified,
                assessment=explanation_assessment,
                next_questions=next_questions,
                feedback_message=feedback,
                requires_more_verification=not is_verified,
                suggested_practice=self._get_practice_suggestions(explanation_assessment)
            )
            
        except Exception as e:
            logger.error(f"❌ UNDERSTANDING_VERIFIER: Error during verification: {e}")
            return self._fallback_verification_result()
    
    def _analyze_code_structure(self, student_code: str) -> Dict[str, Any]:
        """Analyze the structure and concepts present in student code"""
        
        analysis = {
            'concepts_present': [],
            'complexity_level': 'basic',
            'code_elements': {},
            'potential_issues': []
        }
        
        if not student_code:
            return analysis
        
        try:
            tree = ast.parse(student_code)
            
            # Analyze AST for concepts
            for node in ast.walk(tree):
                if isinstance(node, ast.List):
                    analysis['concepts_present'].append('list_usage')
                elif isinstance(node, ast.For):
                    analysis['concepts_present'].append('for_loop')
                    # Check if it's a range-based loop
                    if isinstance(node.iter, ast.Call) and hasattr(node.iter.func, 'id') and node.iter.func.id == 'range':
                        analysis['concepts_present'].append('range_iteration')
                elif isinstance(node, ast.While):
                    analysis['concepts_present'].append('while_loop')
                elif isinstance(node, ast.Call):
                    if hasattr(node.func, 'id'):
                        if node.func.id == 'input':
                            analysis['concepts_present'].append('user_input')
                        elif node.func.id == 'print':
                            analysis['concepts_present'].append('output_display')
                        elif node.func.id == 'int':
                            analysis['concepts_present'].append('type_conversion')
                    elif hasattr(node.func, 'attr') and node.func.attr == 'append':
                        analysis['concepts_present'].append('list_append')
                elif isinstance(node, ast.Assign):
                    analysis['concepts_present'].append('variable_assignment')
                elif isinstance(node, ast.If):
                    analysis['concepts_present'].append('conditional_logic')
                    analysis['complexity_level'] = 'intermediate'
                elif isinstance(node, ast.FunctionDef):
                    analysis['concepts_present'].append('function_definition')
                    analysis['complexity_level'] = 'advanced'
            
            # Remove duplicates
            analysis['concepts_present'] = list(set(analysis['concepts_present']))
            
        except SyntaxError:
            # Fallback to string-based analysis
            analysis = self._fallback_code_analysis(student_code)
        
        return analysis
    
    def _fallback_code_analysis(self, student_code: str) -> Dict[str, Any]:
        """Fallback analysis when AST parsing fails"""
        
        analysis = {
            'concepts_present': [],
            'complexity_level': 'basic',
            'code_elements': {},
            'potential_issues': ['syntax_errors']
        }
        
        code_lower = student_code.lower()
        
        # String-based concept detection
        if 'list(' in code_lower or '[]' in code_lower:
            analysis['concepts_present'].append('list_usage')
        if 'for ' in code_lower:
            analysis['concepts_present'].append('for_loop')
        if 'while ' in code_lower:
            analysis['concepts_present'].append('while_loop')
        if 'input(' in code_lower:
            analysis['concepts_present'].append('user_input')
        if 'print(' in code_lower:
            analysis['concepts_present'].append('output_display')
        if 'int(' in code_lower:
            analysis['concepts_present'].append('type_conversion')
        if '.append(' in code_lower:
            analysis['concepts_present'].append('list_append')
        if 'range(' in code_lower:
            analysis['concepts_present'].append('range_iteration')
        if '=' in code_lower:
            analysis['concepts_present'].append('variable_assignment')
        
        return analysis
    
    async def _assess_explanation_quality(
        self,
        student_explanation: str,
        student_code: str,
        code_analysis: Dict[str, Any]
    ) -> UnderstandingAssessment:
        """Assess the quality of student's code explanation"""
        
        if not student_explanation or len(student_explanation.strip()) < 20:
            return UnderstandingAssessment(
                understanding_level=UnderstandingLevel.SURFACE_LEVEL,
                strengths=[],
                gaps=["insufficient_explanation"],
                confidence_score=0.1,
                specific_concepts_understood=[],
                concepts_needing_work=code_analysis['concepts_present']
            )
        
        # Analyze explanation content
        explanation_lower = student_explanation.lower()
        concepts_present = code_analysis['concepts_present']
        
        # Check which concepts are explained
        explained_concepts = []
        for concept in concepts_present:
            if self._concept_explained_in_text(concept, explanation_lower):
                explained_concepts.append(concept)
        
        # Assess understanding depth
        understanding_indicators = {
            'surface': ['does', 'runs', 'works', 'executes'],
            'conceptual': ['because', 'so that', 'in order to', 'the reason'],
            'deep': ['alternatively', 'could also', 'trade-off', 'advantage', 'disadvantage']
        }
        
        surface_count = sum(1 for word in understanding_indicators['surface'] if word in explanation_lower)
        conceptual_count = sum(1 for word in understanding_indicators['conceptual'] if word in explanation_lower)
        deep_count = sum(1 for word in understanding_indicators['deep'] if word in explanation_lower)
        
        # Determine understanding level
        if deep_count >= 2:
            level = UnderstandingLevel.DEEP_UNDERSTANDING
        elif conceptual_count >= 2:
            level = UnderstandingLevel.CONCEPTUAL
        else:
            level = UnderstandingLevel.SURFACE_LEVEL
        
        # Calculate confidence score
        concept_coverage = len(explained_concepts) / max(len(concepts_present), 1)
        depth_bonus = (conceptual_count * 0.1) + (deep_count * 0.2)
        confidence_score = min(concept_coverage + depth_bonus, 1.0)
        
        # Identify strengths and gaps
        strengths = []
        gaps = []
        
        if concept_coverage > 0.7:
            strengths.append("good_concept_coverage")
        else:
            gaps.append("incomplete_concept_explanation")
        
        if conceptual_count > 0:
            strengths.append("explains_reasoning")
        else:
            gaps.append("lacks_reasoning_explanation")
        
        if len(student_explanation) > 100:
            strengths.append("detailed_explanation")
        else:
            gaps.append("explanation_too_brief")
        
        # Concepts needing work
        concepts_needing_work = [c for c in concepts_present if c not in explained_concepts]
        
        return UnderstandingAssessment(
            understanding_level=level,
            strengths=strengths,
            gaps=gaps,
            confidence_score=confidence_score,
            specific_concepts_understood=explained_concepts,
            concepts_needing_work=concepts_needing_work
        )
    
    def _concept_explained_in_text(self, concept: str, explanation_lower: str) -> bool:
        """Check if a specific concept is explained in the text"""
        
        concept_keywords = {
            'list_usage': ['list', 'array', 'container', 'store'],
            'for_loop': ['for loop', 'for', 'iterate', 'repeat'],
            'while_loop': ['while loop', 'while', 'continue until'],
            'user_input': ['input', 'user types', 'user enters', 'ask user'],
            'output_display': ['print', 'display', 'show', 'output'],
            'type_conversion': ['convert', 'int(', 'change to number', 'turn into'],
            'list_append': ['append', 'add to list', 'put in list'],
            'range_iteration': ['range', 'times', 'iterations'],
            'variable_assignment': ['variable', 'store in', 'assign', 'equals']
        }
        
        keywords = concept_keywords.get(concept, [concept])
        return any(keyword in explanation_lower for keyword in keywords)
    
    def _generate_verification_questions(
        self,
        code_analysis: Dict[str, Any],
        assessment: UnderstandingAssessment,
        verification_level: UnderstandingLevel
    ) -> List[str]:
        """Generate targeted questions based on understanding assessment"""
        
        questions = []
        concepts_present = code_analysis['concepts_present']
        concepts_needing_work = assessment.concepts_needing_work
        
        # Surface level questions
        if verification_level == UnderstandingLevel.SURFACE_LEVEL:
            for concept in concepts_needing_work[:2]:  # Limit to 2
                questions.extend(self._get_surface_questions(concept))
        
        # Conceptual questions  
        elif verification_level == UnderstandingLevel.CONCEPTUAL:
            for concept in concepts_present[:2]:  # Focus on 2 main concepts
                questions.extend(self._get_conceptual_questions(concept))
        
        # Deep understanding questions
        elif verification_level == UnderstandingLevel.DEEP_UNDERSTANDING:
            questions.extend(self._get_deep_questions(concepts_present))
        
        return questions[:3]  # Limit to 3 questions total
    
    def _get_surface_questions(self, concept: str) -> List[str]:
        """Get basic 'what does it do' questions"""
        
        surface_questions = {
            'list_usage': ["What does the list in your code do?"],
            'for_loop': ["What does your for loop do?"],
            'user_input': ["What does the input() function do?"],
            'type_conversion': ["Why do you use int() in your code?"],
            'list_append': ["What happens when you use append()?"]
        }
        
        return surface_questions.get(concept, [f"Explain what {concept} does in your code."])
    
    def _get_conceptual_questions(self, concept: str) -> List[str]:
        """Get 'why this way' questions"""
        
        conceptual_questions = {
            'for_loop': ["Why did you choose a for loop instead of a while loop?"],
            'range_iteration': ["Why did you use range() in your loop?"],
            'list_usage': ["Why did you choose a list to store the data?"],
            'type_conversion': ["Why is converting the input to int() necessary?"],
            'variable_assignment': ["Why did you create these specific variables?"]
        }
        
        return conceptual_questions.get(concept, [f"Why did you implement {concept} this way?"])
    
    def _get_deep_questions(self, concepts: List[str]) -> List[str]:
        """Get advanced understanding questions"""
        
        deep_questions = [
            "What would happen if you removed the type conversion? Why?",
            "How would you modify this code to handle invalid input?",
            "What's an alternative approach to solve this problem?"
        ]
        
        # Add concept-specific deep questions
        if 'for_loop' in concepts and 'range_iteration' in concepts:
            deep_questions.append("What are the advantages and disadvantages of using range() vs a while loop?")
        
        if 'list_append' in concepts:
            deep_questions.append("What would happen if you forgot to create the empty list first?")
        
        return deep_questions
    
    def _determine_verification_status(
        self,
        assessment: UnderstandingAssessment,
        verification_level: UnderstandingLevel
    ) -> bool:
        """Determine if understanding is sufficiently verified"""
        
        # Thresholds for different levels
        thresholds = {
            UnderstandingLevel.SURFACE_LEVEL: 0.6,
            UnderstandingLevel.CONCEPTUAL: 0.7,
            UnderstandingLevel.DEEP_UNDERSTANDING: 0.8,
            UnderstandingLevel.MASTERY: 0.9
        }
        
        required_threshold = thresholds.get(verification_level, 0.7)
        
        # Must meet confidence threshold and have minimal gaps
        meets_threshold = assessment.confidence_score >= required_threshold
        acceptable_gaps = len(assessment.gaps) <= 1
        
        return meets_threshold and acceptable_gaps
    
    def _generate_understanding_feedback(
        self,
        assessment: UnderstandingAssessment,
        verification_level: UnderstandingLevel,
        is_verified: bool
    ) -> str:
        """Generate feedback based on understanding assessment"""
        
        if is_verified:
            feedback = "Excellent! You clearly understand your code implementation. "
            
            if assessment.strengths:
                strength_descriptions = {
                    "good_concept_coverage": "You explained most of the key concepts well.",
                    "explains_reasoning": "You provided good reasoning for your choices.",
                    "detailed_explanation": "Your explanation was thorough and detailed."
                }
                
                strengths_text = " ".join([
                    strength_descriptions.get(strength, strength) 
                    for strength in assessment.strengths
                ])
                feedback += strengths_text
            
            feedback += " Your implementation is approved!"
            
        else:
            feedback = "Your code is working, but I need to verify your understanding better. "
            
            if assessment.gaps:
                gap_descriptions = {
                    "insufficient_explanation": "Your explanation needs more detail.",
                    "incomplete_concept_explanation": "You haven't explained all the key concepts in your code.",
                    "lacks_reasoning_explanation": "Explain WHY you made certain choices, not just what the code does.",
                    "explanation_too_brief": "Please provide a more detailed explanation."
                }
                
                gaps_text = " ".join([
                    gap_descriptions.get(gap, gap) 
                    for gap in assessment.gaps[:2]  # Limit feedback
                ])
                feedback += gaps_text
        
        return feedback
    
    def _get_practice_suggestions(self, assessment: UnderstandingAssessment) -> List[str]:
        """Get practice suggestions based on assessment"""
        
        suggestions = []
        
        if "incomplete_concept_explanation" in assessment.gaps:
            suggestions.append("Practice explaining each part of your code in detail")
        
        if "lacks_reasoning_explanation" in assessment.gaps:
            suggestions.append("Work on explaining WHY you made specific programming choices")
        
        if assessment.understanding_level == UnderstandingLevel.SURFACE_LEVEL:
            suggestions.append("Try to think about the purpose behind each line of code")
        
        return suggestions
    
    def _fallback_verification_result(self) -> VerificationResult:
        """Fallback result when verification fails"""
        
        return VerificationResult(
            is_verified=False,
            assessment=UnderstandingAssessment(
                understanding_level=UnderstandingLevel.SURFACE_LEVEL,
                strengths=[],
                gaps=["verification_error"],
                confidence_score=0.0,
                specific_concepts_understood=[],
                concepts_needing_work=[]
            ),
            next_questions=["Please explain what each line of your code does."],
            feedback_message="Let's verify your understanding. Please explain your code in detail.",
            requires_more_verification=True,
            suggested_practice=["Practice explaining code step by step"]
        )
    
    def _load_verification_questions(self) -> Dict[str, List[str]]:
        """Load verification question templates"""
        
        return {
            "surface_level": [
                "What does this line do?",
                "What happens when this runs?",
                "What is the purpose of this part?"
            ],
            "conceptual": [
                "Why did you choose this approach?",
                "What would happen if you changed this?",
                "Why is this step necessary?"
            ],
            "deep_understanding": [
                "What are alternative ways to solve this?",
                "What are the trade-offs of your approach?",
                "How would you optimize this code?"
            ]
        }
    
    def _load_concept_patterns(self) -> Dict[str, List[str]]:
        """Load patterns for concept identification"""
        
        return {
            "list_operations": [r'\[\]', r'\.append\(', r'list\('],
            "loop_structures": [r'for\s+\w+\s+in', r'while\s+'],
            "input_output": [r'input\(', r'print\('],
            "type_conversion": [r'int\(', r'float\(', r'str\(']
        }
    
    def _load_understanding_indicators(self) -> Dict[str, List[str]]:
        """Load indicators of different understanding levels"""
        
        return {
            "surface": ["does", "runs", "executes", "makes", "creates"],
            "conceptual": ["because", "so that", "in order to", "the reason", "purpose"],
            "deep": ["alternatively", "trade-off", "advantage", "disadvantage", "optimize"]
        }