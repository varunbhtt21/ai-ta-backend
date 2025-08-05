"""
Enhanced Logic Validation Service
Implements strict logic-first validation with cross-questioning and anti-gaming measures.
Follows Service Layer Pattern with comprehensive validation logic.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import logging
import re
from dataclasses import dataclass

from app.models import (
    ConversationMessage, MessageType, Problem, User
)
from app.services.openai_client import openai_client
from app.core.config import settings

logger = logging.getLogger(__name__)


# Import shared validation types to prevent circular imports
from app.services.validation_types import LogicValidationLevel, StrictnessLevel
from app.services.scenario_prompt_manager import ScenarioPromptManager, ScenarioType


@dataclass
class LogicValidationResult:
    """Result of logic validation with detailed feedback"""
    is_approved: bool
    validation_level: LogicValidationLevel
    strictness_level: StrictnessLevel
    feedback_message: str
    cross_questions: List[str]
    missing_elements: List[str]
    gaming_indicators: List[str]
    confidence_score: float  # 0.0 to 1.0
    next_action: str


@dataclass
class GamingDetectionResult:
    """Result of gaming detection analysis"""
    is_gaming: bool
    gaming_type: str  # "copy_paste", "vague_repetition", "bypass_attempt"
    confidence: float
    evidence: List[str]
    recommended_action: str


class EnhancedLogicValidator:
    """Enhanced logic validation service with cross-questioning and anti-gaming"""
    
    def __init__(self):
        self.openai_client = openai_client
        
        # Initialize scenario-based prompt manager for Phase 2
        self.scenario_manager = ScenarioPromptManager()
        
        # Few-shot examples for cross-questioning (legacy - now replaced by scenario manager)
        self.validation_scenarios = self._load_validation_scenarios()
        
        # Gaming detection patterns
        self.gaming_patterns = self._load_gaming_patterns()
        
        logger.info(f"🎯 LOGIC_VALIDATOR: Initialized with scenario-based prompting support")
    
    async def validate_logic_explanation(
        self,
        student_response: str,
        problem: Problem,
        conversation_history: List[ConversationMessage],
        current_level: LogicValidationLevel = LogicValidationLevel.INITIAL_REQUEST,
        strictness_level: StrictnessLevel = StrictnessLevel.LENIENT
    ) -> LogicValidationResult:
        """
        Comprehensive logic validation with multi-level cross-questioning
        """
        logger.info(f"🔍 LOGIC_VALIDATOR: Validating logic at level {current_level.value}")
        logger.info(f"📊 LOGIC_VALIDATOR: Strictness level {strictness_level.value}")
        
        try:
            # Step 1: Gaming detection
            gaming_result = await self._detect_gaming_attempts(
                student_response, conversation_history, problem
            )
            
            if gaming_result.is_gaming:
                # Use scenario-based prompting for gaming response
                feedback_message = await self._generate_scenario_based_response(
                    ScenarioType.GAMING_RESPONSE,
                    LogicValidationLevel.GAMING_DETECTED,
                    StrictnessLevel.GAMING_MODE,
                    problem,
                    student_response,
                    conversation_history,
                    gaming_context=gaming_result
                )
                
                return LogicValidationResult(
                    is_approved=False,
                    validation_level=LogicValidationLevel.GAMING_DETECTED,
                    strictness_level=StrictnessLevel.GAMING_MODE,
                    feedback_message=feedback_message,
                    cross_questions=[],
                    missing_elements=[],
                    gaming_indicators=gaming_result.evidence,
                    confidence_score=0.0,
                    next_action="require_original_thinking"
                )
            
            # Step 2: Content analysis
            logic_analysis = await self._analyze_logic_content(
                student_response, problem, strictness_level
            )
            
            # Step 3: Determine validation level based on analysis
            new_validation_level = self._determine_validation_level(
                logic_analysis, current_level, strictness_level
            )
            
            # Step 4: Generate appropriate response based on validation level
            if new_validation_level == LogicValidationLevel.LOGIC_APPROVED:
                # Use scenario-based prompting for approval
                feedback_message = await self._generate_scenario_based_response(
                    ScenarioType.LOGIC_VALIDATION,
                    new_validation_level,
                    strictness_level,
                    problem,
                    student_response,
                    conversation_history,
                    logic_analysis=logic_analysis
                )
                
                return LogicValidationResult(
                    is_approved=True,
                    validation_level=new_validation_level,
                    strictness_level=strictness_level,
                    feedback_message=feedback_message,
                    cross_questions=[],
                    missing_elements=[],
                    gaming_indicators=[],
                    confidence_score=logic_analysis['confidence_score'],
                    next_action="proceed_to_coding"
                )
            else:
                # Determine scenario type based on validation level and student behavior
                scenario_type = self._determine_scenario_type(
                    new_validation_level, student_response, logic_analysis
                )
                
                # Generate scenario-based feedback with cross-questions
                feedback_message = await self._generate_scenario_based_response(
                    scenario_type,
                    new_validation_level,
                    self._escalate_strictness(strictness_level),
                    problem,
                    student_response,
                    conversation_history,
                    logic_analysis=logic_analysis
                )
                
                # Generate cross-questions using scenario manager
                cross_questions = self.scenario_manager.generate_cross_questions(
                    missing_elements=logic_analysis.get('missing_elements', []),
                    problem=problem,
                    strictness_level=self._escalate_strictness(strictness_level)
                )
                
                return LogicValidationResult(
                    is_approved=False,
                    validation_level=new_validation_level,
                    strictness_level=self._escalate_strictness(strictness_level),
                    feedback_message=feedback_message,
                    cross_questions=cross_questions,
                    missing_elements=logic_analysis.get('missing_elements', []),
                    gaming_indicators=[],
                    confidence_score=logic_analysis['confidence_score'],
                    next_action="require_more_detail"
                )
                
        except Exception as e:
            logger.error(f"❌ LOGIC_VALIDATOR: Error during validation: {e}")
            return LogicValidationResult(
                is_approved=False,
                validation_level=LogicValidationLevel.CROSS_QUESTIONING,
                strictness_level=strictness_level,
                feedback_message="I need you to explain your approach in more detail. Please provide a step-by-step explanation of how you plan to solve this problem.",
                cross_questions=["What is your first step?", "How will you handle the input?", "What data structure will you use?"],
                missing_elements=["detailed_steps"],
                gaming_indicators=[],
                confidence_score=0.0,
                next_action="require_more_detail"
            )
    
    async def _detect_gaming_attempts(
        self,
        student_response: str,
        conversation_history: List[ConversationMessage],
        problem: Problem
    ) -> GamingDetectionResult:
        """Detect if student is trying to game the system"""
        
        gaming_indicators = []
        confidence = 0.0
        gaming_type = "none"
        
        # Check for copy-paste from AI responses
        ai_messages = [msg.content for msg in conversation_history[-10:] 
                      if msg.message_type == MessageType.ASSISTANT]
        
        for ai_msg in ai_messages:
            similarity = self._calculate_similarity(student_response, ai_msg)
            if similarity > 0.8:  # High similarity threshold
                gaming_indicators.append(f"Response very similar to AI message: '{ai_msg[:50]}...'")
                confidence += 0.4
                gaming_type = "copy_paste"
        
        # Check for vague repetitive responses (but allow progressive improvement)
        user_messages = [msg.content for msg in conversation_history[-5:] 
                        if msg.message_type == MessageType.USER]
        
        if len(user_messages) >= 2:
            recent_similarity = self._calculate_similarity(student_response, user_messages[-1])
            # Only flag as gaming if extremely similar AND current response is not significantly longer
            current_length = len(student_response.strip())
            previous_length = len(user_messages[-1].strip())
            
            # If response is significantly longer, it's likely improvement, not repetition
            is_expanding_response = current_length > previous_length * 1.3
            
            if recent_similarity > 0.8 and not is_expanding_response and current_length < 50:
                gaming_indicators.append("Repeating similar vague responses without improvement")
                confidence += 0.2  # Reduced confidence penalty
                gaming_type = "vague_repetition"
        
        # Check for bypass attempts (asking for code, hints, next question)
        bypass_patterns = [
            r"give me code", r"show me code", r"next question", r"skip",
            r"give me hint", r"tell me answer", r"just give", r"can you help"
        ]
        
        for pattern in bypass_patterns:
            if re.search(pattern, student_response.lower()):
                gaming_indicators.append(f"Bypass attempt detected: '{pattern}'")
                confidence += 0.2
                gaming_type = "bypass_attempt"
        
        # Check for extremely short responses
        if len(student_response.strip()) < 20 and gaming_type == "none":
            gaming_indicators.append("Response too short for meaningful logic explanation")
            confidence += 0.1
            gaming_type = "insufficient_effort"
        
        is_gaming = confidence > 0.3  # Gaming threshold
        
        return GamingDetectionResult(
            is_gaming=is_gaming,
            gaming_type=gaming_type,
            confidence=min(confidence, 1.0),
            evidence=gaming_indicators,
            recommended_action="require_original_detailed_explanation" if is_gaming else "continue_validation"
        )
    
    async def _analyze_logic_content(
        self,
        student_response: str,
        problem: Problem,
        strictness_level: StrictnessLevel
    ) -> Dict[str, Any]:
        """Analyze the content and quality of student's logic explanation"""
        
        # Define required elements based on strictness level
        required_elements = self._get_required_elements(problem, strictness_level)
        
        # Use OpenAI to analyze the logic content
        analysis_prompt = self._build_logic_analysis_prompt(
            student_response, problem, required_elements, strictness_level
        )
        
        try:
            # Create messages for our wrapped client
            messages = [
                ConversationMessage(
                    message_type=MessageType.USER,
                    content=analysis_prompt,
                    timestamp=datetime.now()
                )
            ]
            
            response = await self.openai_client.generate_response(
                messages=messages,
                system_prompt="You are an expert programming tutor analyzing student logic explanations.",
                max_tokens=300,
                temperature=0.3,
                model="gpt-4o-mini"
            )
            
            if response.get("success") and response.get("content"):
                ai_analysis = response["content"].strip()
                return self._parse_ai_analysis(ai_analysis, required_elements)
            else:
                logger.warning(f"⚠️ LOGIC_VALIDATOR: AI analysis failed: {response.get('error', 'Unknown error')}")
                return self._fallback_analysis(student_response, required_elements)
                
        except Exception as e:
            logger.error(f"❌ LOGIC_VALIDATOR: Error in AI analysis: {e}")
            return self._fallback_analysis(student_response, required_elements)
    
    def _get_required_elements(self, problem: Problem, strictness_level: StrictnessLevel) -> List[str]:
        """Get required elements based on problem and strictness level"""
        
        base_elements = [
            "data_structure_choice",  # What will store the data
            "input_method",          # How to get user input
            "loop_structure",        # How to repeat actions
            "process_flow"           # Overall step-by-step flow
        ]
        
        if strictness_level.value >= 3:  # STRICT and above
            base_elements.extend([
                "variable_names",     # Specific variable naming
                "data_type_handling", # String to int conversion etc.
                "output_method"       # How to display results
            ])
        
        if strictness_level.value >= 4:  # VERY_STRICT and above
            base_elements.extend([
                "edge_case_consideration", # Empty input, invalid data
                "error_handling_awareness" # What could go wrong
            ])
        
        return base_elements
    
    def _build_logic_analysis_prompt(
        self,
        student_response: str,
        problem: Problem,
        required_elements: List[str],
        strictness_level: StrictnessLevel
    ) -> str:
        """Build prompt for AI analysis of student logic"""
        
        return f"""Analyze this student's logic explanation for completeness and understanding.

PROBLEM: {problem.title}
DESCRIPTION: {problem.description}

STUDENT'S LOGIC EXPLANATION:
"{student_response}"

REQUIRED ELEMENTS TO CHECK:
{chr(10).join(f"- {element}" for element in required_elements)}

STRICTNESS LEVEL: {strictness_level.value}/5

Analyze and respond in this exact format:
CONFIDENCE_SCORE: [0.0-1.0]
MISSING_ELEMENTS: [comma-separated list]
STRENGTHS: [what student got right]
WEAKNESSES: [what needs improvement]
SPECIFIC_GAPS: [specific missing details]
RECOMMENDATION: [APPROVE/CROSS_QUESTION/REQUIRE_MORE_DETAIL]

Be strict but fair. For approval, student must show clear understanding of all required elements."""
    
    def _parse_ai_analysis(self, ai_response: str, required_elements: List[str]) -> Dict[str, Any]:
        """Parse AI analysis response into structured data"""
        
        analysis = {
            'confidence_score': 0.0,
            'missing_elements': [],
            'strengths': [],
            'weaknesses': [],
            'specific_gaps': [],
            'recommendation': 'REQUIRE_MORE_DETAIL'
        }
        
        lines = ai_response.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('CONFIDENCE_SCORE:'):
                try:
                    analysis['confidence_score'] = float(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    analysis['confidence_score'] = 0.0
            elif line.startswith('MISSING_ELEMENTS:'):
                elements_str = line.split(':', 1)[1].strip()
                if elements_str and elements_str != 'None':
                    analysis['missing_elements'] = [e.strip() for e in elements_str.split(',')]
            elif line.startswith('RECOMMENDATION:'):
                analysis['recommendation'] = line.split(':', 1)[1].strip()
        
        return analysis
    
    def _fallback_analysis(self, student_response: str, required_elements: List[str]) -> Dict[str, Any]:
        """Fallback analysis if AI fails - enhanced to better recognize detailed responses"""
        
        response_lower = student_response.lower()
        missing_elements = []
        found_elements = []
        
        # Enhanced element detection
        element_patterns = {
            'data_structure_choice': ['list', 'array', 'container', 'store'],
            'input_method': ['input', 'user input', 'take input', 'get input'],
            'loop_structure': ['loop', 'for loop', 'for', 'repeat', 'iterate'],
            'process_flow': ['first', 'then', 'after', 'step', 'next'],
            'variable_names': ['called', 'name', 'variable'],
            'data_type_handling': ['convert', 'int', 'integer', 'string'],
            'output_method': ['print', 'display', 'show', 'output'],
            'range_usage': ['range', '5 times', 'five times'],
            'list_operations': ['append', 'add to list', 'put in list']
        }
        
        # Check each required element
        for element in required_elements:
            patterns = element_patterns.get(element, [element.replace('_', ' ')])
            if any(pattern in response_lower for pattern in patterns):
                found_elements.append(element)
            else:
                missing_elements.append(element)
        
        # Calculate confidence based on response quality
        base_confidence = len(found_elements) / len(required_elements) if required_elements else 0.0
        
        # Bonus for detailed responses
        response_length = len(student_response.strip())
        detail_bonus = min(0.2, response_length / 200)  # Up to 0.2 bonus for length
        
        # Bonus for specific technical terms
        technical_terms = ['for loop', 'range', 'append', 'input()', 'int()', 'variable']
        technical_bonus = min(0.1, sum(0.02 for term in technical_terms if term in response_lower))
        
        # Bonus for process flow indicators
        flow_terms = ['first', 'then', 'after', 'next', 'finally']
        flow_bonus = min(0.1, sum(0.02 for term in flow_terms if term in response_lower))
        
        final_confidence = min(1.0, base_confidence + detail_bonus + technical_bonus + flow_bonus)
        
        # Determine strengths and weaknesses
        strengths = []
        weaknesses = []
        
        if len(found_elements) > len(required_elements) * 0.7:
            strengths.append('good_concept_coverage')
        if response_length > 50:
            strengths.append('detailed_explanation')
        if any(term in response_lower for term in flow_terms):
            strengths.append('clear_process_flow')
        if any(term in response_lower for term in technical_terms):
            strengths.append('technical_accuracy')
        
        if len(missing_elements) > 2:
            weaknesses.append('missing_key_elements')
        if response_length < 30:
            weaknesses.append('too_brief')
        if not any(term in response_lower for term in flow_terms):
            weaknesses.append('unclear_sequence')
        
        return {
            'confidence_score': final_confidence,
            'missing_elements': missing_elements,
            'strengths': strengths,
            'weaknesses': weaknesses,
            'specific_gaps': missing_elements,
            'recommendation': 'APPROVE' if final_confidence > 0.75 else ('CROSS_QUESTION' if final_confidence > 0.5 else 'REQUIRE_MORE_DETAIL')
        }
    
    def _determine_validation_level(
        self,
        logic_analysis: Dict[str, Any],
        current_level: LogicValidationLevel,
        strictness_level: StrictnessLevel
    ) -> LogicValidationLevel:
        """Determine next validation level based on analysis"""
        
        confidence = logic_analysis['confidence_score']
        recommendation = logic_analysis.get('recommendation', 'REQUIRE_MORE_DETAIL')
        
        # High confidence and approval
        if confidence >= 0.8 and recommendation == 'APPROVE':
            return LogicValidationLevel.LOGIC_APPROVED
        
        # Medium confidence - need cross-questioning
        elif confidence >= 0.5:
            if current_level == LogicValidationLevel.INITIAL_REQUEST:
                return LogicValidationLevel.CROSS_QUESTIONING
            elif current_level == LogicValidationLevel.CROSS_QUESTIONING:
                return LogicValidationLevel.DETAILED_VALIDATION
            else:
                return LogicValidationLevel.EDGE_CASE_TESTING
        
        # Low confidence - need more basic explanation
        else:
            return LogicValidationLevel.BASIC_EXPLANATION
    
    async def _generate_cross_questions(
        self,
        logic_analysis: Dict[str, Any],
        problem: Problem,
        validation_level: LogicValidationLevel,
        strictness_level: StrictnessLevel
    ) -> List[str]:
        """Generate targeted cross-questions based on missing elements"""
        
        missing_elements = logic_analysis.get('missing_elements', [])
        cross_questions = []
        
        # Generate questions for missing elements
        for element in missing_elements:
            if element == 'data_structure_choice':
                cross_questions.append("What data structure will you use to store the numbers?")
            elif element == 'input_method':
                cross_questions.append("How exactly will you get input from the user?")
            elif element == 'loop_structure':
                cross_questions.append("What type of loop will you use and how many times should it run?")
            elif element == 'variable_names':
                cross_questions.append("What will you name your variables? Be specific.")
            elif element == 'data_type_handling':
                cross_questions.append("The input() function returns a string. How will you handle this?")
            elif element == 'edge_case_consideration':
                cross_questions.append("What if the user enters invalid input? How would you handle that?")
        
        # Add level-specific questions
        if validation_level == LogicValidationLevel.DETAILED_VALIDATION:
            cross_questions.append("Can you walk me through your solution step by step, mentioning specific Python functions you'll use?")
        
        if validation_level == LogicValidationLevel.EDGE_CASE_TESTING:
            cross_questions.append("What are some edge cases or potential problems with your approach?")
        
        return cross_questions[:3]  # Limit to 3 questions to avoid overwhelming
    
    async def _generate_validation_feedback(
        self,
        logic_analysis: Dict[str, Any],
        cross_questions: List[str],
        validation_level: LogicValidationLevel,
        strictness_level: StrictnessLevel
    ) -> str:
        """Generate comprehensive feedback message with cross-questions"""
        
        confidence = logic_analysis['confidence_score']
        missing_elements = logic_analysis.get('missing_elements', [])
        
        # Base feedback based on validation level
        if validation_level == LogicValidationLevel.BASIC_EXPLANATION:
            feedback = "I need more details about your approach. Your explanation is too general."
        elif validation_level == LogicValidationLevel.CROSS_QUESTIONING:
            feedback = "You're on the right track, but I need to understand your approach better."
        elif validation_level == LogicValidationLevel.DETAILED_VALIDATION:
            feedback = "Good progress! Now I need more specific implementation details."
        elif validation_level == LogicValidationLevel.EDGE_CASE_TESTING:
            feedback = "Your approach looks solid. Let's make sure you've considered all scenarios."
        else:
            feedback = "Please provide a more detailed explanation of your approach."
        
        # Add missing elements feedback
        if missing_elements:
            feedback += f"\n\nSpecifically, you haven't addressed: {', '.join(missing_elements)}"
        
        # Add cross-questions
        if cross_questions:
            feedback += "\n\nPlease answer these questions:\n"
            for i, question in enumerate(cross_questions, 1):
                feedback += f"{i}. {question}\n"
        
        # Add encouragement based on confidence
        if confidence > 0.5:
            feedback += "\nYou're making good progress! Just need a bit more detail."
        else:
            feedback += "\nTake your time to think through each step carefully."
        
        return feedback
    
    async def _generate_approval_message(
        self,
        logic_analysis: Dict[str, Any],
        problem: Problem
    ) -> str:
        """Generate approval message when logic is validated"""
        
        strengths = logic_analysis.get('strengths', [])
        
        approval_messages = [
            "Excellent logic! Your approach is clear and well thought out.",
            "Perfect! You've demonstrated a solid understanding of the problem.",
            "Great job! Your step-by-step approach shows good problem-solving skills.",
            "Outstanding! You've covered all the essential elements needed."
        ]
        
        import random
        base_message = random.choice(approval_messages)
        
        return f"{base_message} Now you can implement your logic with code. Remember to follow the exact steps you outlined."
    
    async def _generate_gaming_response(self, gaming_result: GamingDetectionResult) -> str:
        """Generate response when gaming is detected"""
        
        if gaming_result.gaming_type == "copy_paste":
            return "I noticed you're repeating information from our conversation. I need YOUR original thinking. Please explain in your own words how you would approach this problem step by step."
        
        elif gaming_result.gaming_type == "vague_repetition":
            return "You're giving the same general response. I need much more specific details. Break down your approach into clear, detailed steps with specific actions you would take."
        
        elif gaming_result.gaming_type == "bypass_attempt":
            return "I understand you want to move forward, but first you must demonstrate your understanding by explaining your logical approach in detail. No shortcuts allowed."
        
        elif gaming_result.gaming_type == "insufficient_effort":
            return "Your response is too brief. I need a comprehensive explanation of your approach. Please provide a detailed, step-by-step breakdown of how you plan to solve this problem."
        
        else:
            return "I need you to provide a genuine, detailed explanation of your approach. Show me that you understand the problem and have a clear plan to solve it."
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (simple implementation)"""
        
        # Convert to lowercase and split into words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _escalate_strictness(self, current_strictness: StrictnessLevel) -> StrictnessLevel:
        """Escalate strictness level for repeated attempts"""
        
        if current_strictness == StrictnessLevel.LENIENT:
            return StrictnessLevel.MODERATE
        elif current_strictness == StrictnessLevel.MODERATE:
            return StrictnessLevel.STRICT
        elif current_strictness == StrictnessLevel.STRICT:
            return StrictnessLevel.VERY_STRICT
        elif current_strictness == StrictnessLevel.VERY_STRICT:
            return StrictnessLevel.GAMING_MODE
        else:
            return StrictnessLevel.GAMING_MODE
    
    def _determine_scenario_type(
        self,
        validation_level: LogicValidationLevel,
        student_response: str,
        logic_analysis: Dict[str, Any]
    ) -> ScenarioType:
        """Determine appropriate scenario type based on validation context"""
        
        # Check for vague responses
        if len(student_response.strip()) < 50 or logic_analysis.get('confidence_score', 0) < 0.3:
            return ScenarioType.VAGUE_LOGIC_ATTEMPT
        
        # Check for cross-questioning scenarios
        if validation_level == LogicValidationLevel.CROSS_QUESTIONING:
            return ScenarioType.CROSS_QUESTIONING
        
        # Check for detailed validation scenarios
        if validation_level == LogicValidationLevel.DETAILED_VALIDATION:
            return ScenarioType.DETAILED_VALIDATION
        
        # Check for edge case testing
        if validation_level == LogicValidationLevel.EDGE_CASE_TESTING:
            return ScenarioType.EDGE_CASE_TESTING
        
        # Check for insufficient detail
        missing_elements = logic_analysis.get('missing_elements', [])
        if len(missing_elements) > 2:
            return ScenarioType.INSUFFICIENT_DETAIL
        
        # Default to logic validation
        return ScenarioType.LOGIC_VALIDATION
    
    async def _generate_scenario_based_response(
        self,
        scenario_type: ScenarioType,
        validation_level: LogicValidationLevel,
        strictness_level: StrictnessLevel,
        problem: Problem,
        student_response: str,
        conversation_history: List[ConversationMessage],
        gaming_context: Optional[GamingDetectionResult] = None,
        logic_analysis: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate response using scenario-based few-shot prompting"""
        
        logger.info(f"🎯 SCENARIO_RESPONSE: Generating {scenario_type.value} response")
        
        try:
            # Build comprehensive few-shot prompt
            few_shot_prompt = self.scenario_manager.build_few_shot_prompt(
                scenario_type=scenario_type,
                validation_level=validation_level,
                strictness_level=strictness_level,
                current_problem=problem,
                student_input=student_response,
                conversation_history=conversation_history,
                base_instruction="You are an expert programming tutor focused on ensuring students understand logic before coding. Use the examples below to guide your response style and approach."
            )
            
            # Add context-specific information
            if gaming_context:
                few_shot_prompt += f"\n\n**GAMING CONTEXT:**\nGaming detected: {gaming_context.gaming_type}\nEvidence: {', '.join(gaming_context.evidence)}\n"
            
            if logic_analysis:
                few_shot_prompt += f"\n\n**LOGIC ANALYSIS:**\nConfidence: {logic_analysis.get('confidence_score', 0):.2f}\nMissing elements: {', '.join(logic_analysis.get('missing_elements', []))}\n"
            
            # Create messages for our wrapped client
            messages = [
                ConversationMessage(
                    message_type=MessageType.USER,
                    content=few_shot_prompt,
                    timestamp=datetime.now()
                )
            ]
            
            # Get AI response using few-shot prompting
            response = await self.openai_client.generate_response(
                messages=messages,
                system_prompt="You are an expert programming tutor. Follow the style and approach demonstrated in the examples exactly.",
                max_tokens=400,
                temperature=0.2,
                model="gpt-4o-mini"
            )
            
            if response.get("success") and response.get("content"):
                ai_response = response["content"].strip()
                logger.info(f"✅ SCENARIO_RESPONSE: Generated scenario-based response successfully")
                return ai_response
            else:
                logger.warning(f"⚠️ SCENARIO_RESPONSE: AI response failed: {response.get('error', 'Unknown error')}")
                return self._fallback_response(scenario_type, validation_level)
                
        except Exception as e:
            logger.error(f"❌ SCENARIO_RESPONSE: Error generating response: {e}")
            return self._fallback_response(scenario_type, validation_level)
    
    def _fallback_response(
        self,
        scenario_type: ScenarioType,
        validation_level: LogicValidationLevel
    ) -> str:
        """Fallback response when scenario-based generation fails"""
        
        if scenario_type == ScenarioType.VAGUE_LOGIC_ATTEMPT:
            return "I need more specific details about your approach. Please break down your solution step by step with clear actions you would take."
        
        elif scenario_type == ScenarioType.GAMING_RESPONSE:
            return "I need you to provide your own original thinking. Please explain your approach in your own words with specific details."
        
        elif scenario_type == ScenarioType.CROSS_QUESTIONING:
            return "You're on the right track! I need to understand your approach better. Can you provide more specific details about your implementation?"
        
        elif scenario_type == ScenarioType.LOGIC_VALIDATION:
            if validation_level == LogicValidationLevel.LOGIC_APPROVED:
                return "Excellent logic! Your approach is clear and comprehensive. Now you can implement your solution with code."
            else:
                return "Your logic needs more detail. Please provide a clearer step-by-step explanation."
        
        else:
            return "Please provide a more detailed explanation of your approach with specific steps and methods you'll use."
    
    def _load_validation_scenarios(self) -> List[Dict[str, Any]]:
        """Load few-shot validation scenarios for prompting"""
        
        return [
            {
                "student_response": "I will use a loop to get input",
                "missing_elements": ["data_structure_choice", "loop_type", "input_handling"],
                "cross_questions": [
                    "What type of loop will you use?",
                    "How many times should the loop run?",
                    "Where will you store the input values?"
                ],
                "validation_level": "cross_questioning"
            },
            {
                "student_response": "I will create an empty list, use a for loop with range(5) to ask for input 5 times, convert each input to int, append to list, then print the list",
                "missing_elements": [],
                "cross_questions": [],
                "validation_level": "approved"
            }
        ]
    
    def _load_gaming_patterns(self) -> List[Dict[str, Any]]:
        """Load gaming detection patterns"""
        
        return [
            {
                "pattern": r"give me.*code|show me.*code|tell me.*code",
                "type": "code_request",
                "severity": "high"
            },
            {
                "pattern": r"next.*question|skip|move on",
                "type": "skip_attempt", 
                "severity": "high"
            },
            {
                "pattern": r"hint|help me|just tell me",
                "type": "hint_request",
                "severity": "medium"
            }
        ]