from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging

from app.models import (
    ConversationMessage, MessageType, InputType, 
    ContextCompressionLevel, ResumeType, ProblemStatus
)
from app.services.prompt_manager import smart_prompt_manager, PromptTemplate
from app.services.context_compression import context_compression_manager
from app.services.input_classifier import input_classifier
from app.services.openai_client import openai_client
from app.services.session_service import session_service
from app.services.assignment_service import assignment_service

logger = logging.getLogger(__name__)


class ResponseGenerationContext:
    """Context object containing all information needed for intelligent response generation"""
    
    def __init__(
        self,
        user_id: str,
        session_id: str,
        assignment_id: str,
        user_input: str,
        current_problem: Optional[Dict[str, Any]] = None,
        session_data: Optional[Dict[str, Any]] = None,
        learning_profile: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[ConversationMessage]] = None,
        input_classification: Optional[Any] = None,
        compression_result: Optional[Dict[str, Any]] = None
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.assignment_id = assignment_id
        self.user_input = user_input
        self.current_problem = current_problem
        self.session_data = session_data
        self.learning_profile = learning_profile
        self.conversation_history = conversation_history or []
        self.input_classification = input_classification
        self.compression_result = compression_result


class SmartResponseGenerator:
    """
    Advanced AI response generation system that intelligently selects teaching strategies,
    adapts to context compression levels, and provides personalized tutoring responses.
    """
    
    def __init__(self):
        self.prompt_manager = smart_prompt_manager
        self.compression_manager = context_compression_manager
        self.input_classifier = input_classifier
        self.openai_client = openai_client
        self.session_service = session_service
        self.assignment_service = assignment_service
    
    async def generate_intelligent_response(self, context: ResponseGenerationContext) -> Dict[str, Any]:
        """
        Generate contextually intelligent response based on student input and learning state
        """
        
        try:
            # Step 1: Classify student input
            if not context.input_classification:
                context.input_classification = self.input_classifier.classify_input(
                    context.user_input,
                    context={"session": context.session_data, "recent_messages": context.conversation_history[-5:]}
                )
            
            # Step 2: Determine appropriate teaching strategy
            teaching_strategy = await self._determine_teaching_strategy(context)
            
            # Step 3: Select optimal prompt template
            prompt_template = self._select_prompt_template(context, teaching_strategy)
            
            # Step 4: Generate contextual prompt
            prompt_result = await self.prompt_manager.generate_contextual_prompt(
                template=prompt_template,
                user_id=context.user_id,
                assignment_id=context.assignment_id,
                current_problem=context.current_problem,
                student_input=context.user_input,
                session_context={"session_data": context.session_data},
                learning_profile=context.learning_profile,
                compression_result=context.compression_result
            )
            
            # Step 5: Prepare conversation messages
            messages = self._prepare_conversation_messages(context, prompt_result)
            
            # Step 6: Generate AI response
            ai_response = await self.openai_client.generate_response_with_retry(
                messages=messages,
                system_prompt=prompt_result["system_prompt"],
                temperature=self._determine_temperature(context, teaching_strategy),
                max_tokens=self._determine_max_tokens(context)
            )
            
            if not ai_response["success"]:
                raise Exception(f"AI response generation failed: {ai_response.get('error', 'Unknown error')}")
            
            # Step 7: Post-process response
            processed_response = await self._post_process_response(
                ai_response["content"], context, teaching_strategy
            )
            
            return {
                "success": True,
                "response": processed_response,
                "teaching_strategy": teaching_strategy,
                "prompt_template": prompt_template.value,
                "input_classification": context.input_classification.input_type.value,
                "context_level": prompt_result.get("context_level"),
                "compression_level": prompt_result.get("compression_level"),
                "tokens_used": ai_response.get("usage", {}).get("total_tokens", 0),
                "adaptations_applied": prompt_result.get("adaptations_applied", []),
                "metadata": {
                    "generation_timestamp": datetime.utcnow(),
                    "confidence": context.input_classification.confidence,
                    "response_length": len(processed_response),
                    "teaching_context": teaching_strategy
                }
            }
        
        except Exception as e:
            logger.error(f"Smart response generation failed: {e}")
            return await self._generate_fallback_response(context, str(e))
    
    async def _determine_teaching_strategy(self, context: ResponseGenerationContext) -> Dict[str, Any]:
        """Determine the optimal teaching strategy based on context"""
        
        strategy = {
            "primary_approach": "collaborative",
            "focus_areas": [],
            "adaptation_level": "moderate",
            "encouragement_needed": False,
            "difficulty_adjustment": "maintain"
        }
        
        # Analyze input classification
        input_type = context.input_classification.input_type
        confidence = context.input_classification.confidence
        
        if input_type == InputType.CODE_SUBMISSION:
            strategy["primary_approach"] = "code_review"
            strategy["focus_areas"] = ["correctness", "best_practices", "learning_reinforcement"]
            
            # Check if code has obvious issues (low confidence might indicate unclear code)
            if confidence < 0.7:
                strategy["focus_areas"].append("clarification_needed")
        
        elif input_type == InputType.QUESTION:
            strategy["primary_approach"] = "explanation"
            strategy["focus_areas"] = ["concept_teaching", "understanding_check"]
            
            # High confidence questions get direct teaching, low confidence get clarification
            if confidence < 0.6:
                strategy["focus_areas"].append("clarification_first")
        
        elif input_type == InputType.NEXT_PROBLEM:
            strategy["primary_approach"] = "progress_transition"
            strategy["focus_areas"] = ["progress_celebration", "problem_introduction"]
        
        elif input_type == InputType.READY_TO_START:
            strategy["primary_approach"] = "motivational_guidance"
            strategy["focus_areas"] = ["encouragement", "problem_setup"]
        
        # Analyze learning profile for adaptations
        if context.learning_profile:
            competency = context.learning_profile.get("estimated_competency", "intermediate")
            
            if competency == "beginner":
                strategy["adaptation_level"] = "high_support"
                strategy["focus_areas"].append("foundational_concepts")
            elif competency == "advanced":
                strategy["adaptation_level"] = "challenge_focused"
                strategy["focus_areas"].append("advanced_techniques")
            
            # Check for struggling indicators
            if "debugging" in context.learning_profile.get("areas_for_improvement", []):
                strategy["focus_areas"].append("debugging_skills")
                strategy["encouragement_needed"] = True
        
        # Analyze conversation history for emotional state
        if context.conversation_history:
            recent_messages = context.conversation_history[-3:]
            recent_text = " ".join([msg.content.lower() for msg in recent_messages])
            
            struggling_indicators = ["stuck", "confused", "don't understand", "help", "difficult"]
            if any(indicator in recent_text for indicator in struggling_indicators):
                strategy["encouragement_needed"] = True
                strategy["adaptation_level"] = "high_support"
                strategy["difficulty_adjustment"] = "reduce"
        
        # Consider current problem complexity
        if context.current_problem:
            difficulty = context.current_problem.get("difficulty", "medium")
            if difficulty == "hard" and strategy["adaptation_level"] != "challenge_focused":
                strategy["focus_areas"].append("step_by_step_guidance")
        
        return strategy
    
    def _select_prompt_template(
        self, 
        context: ResponseGenerationContext, 
        teaching_strategy: Dict[str, Any]
    ) -> PromptTemplate:
        """Select the most appropriate prompt template"""
        
        input_type = context.input_classification.input_type
        primary_approach = teaching_strategy["primary_approach"]
        
        # Primary template selection based on input type
        if input_type == InputType.CODE_SUBMISSION:
            return PromptTemplate.CODE_FEEDBACK
        elif input_type == InputType.QUESTION:
            return PromptTemplate.EXPLANATION
        elif input_type == InputType.NEXT_PROBLEM:
            return PromptTemplate.PROBLEM_INTRODUCTION
        elif input_type == InputType.READY_TO_START:
            # Check if this is a session resume
            if context.session_data and context.session_data.get("resume_type") != ResumeType.FRESH_START:
                return PromptTemplate.SESSION_RESUME
            else:
                return PromptTemplate.WELCOME
        
        # Secondary template selection based on teaching strategy
        if teaching_strategy["encouragement_needed"]:
            return PromptTemplate.ENCOURAGEMENT
        elif "debugging_skills" in teaching_strategy["focus_areas"]:
            return PromptTemplate.DEBUGGING_HELP
        elif "concept_teaching" in teaching_strategy["focus_areas"]:
            return PromptTemplate.CONCEPT_TEACHING
        elif "progress_celebration" in teaching_strategy["focus_areas"]:
            return PromptTemplate.PROGRESS_CELEBRATION
        
        # Default fallback
        return PromptTemplate.EXPLANATION
    
    def _prepare_conversation_messages(
        self, 
        context: ResponseGenerationContext, 
        prompt_result: Dict[str, Any]
    ) -> List[ConversationMessage]:
        """Prepare conversation messages for AI generation"""
        
        messages = []
        
        # Add conversation context if available
        conversation_context = prompt_result.get("conversation_context", "")
        if conversation_context:
            messages.append(ConversationMessage(
                message_type=MessageType.SYSTEM,
                content=f"Previous conversation context:\n{conversation_context}",
                timestamp=datetime.utcnow()
            ))
        
        # Add current user input
        messages.append(ConversationMessage(
            message_type=MessageType.USER,
            content=context.user_input,
            timestamp=datetime.utcnow()
        ))
        
        return messages
    
    def _determine_temperature(
        self, 
        context: ResponseGenerationContext, 
        teaching_strategy: Dict[str, Any]
    ) -> float:
        """Determine AI temperature based on context and strategy"""
        
        base_temperature = 0.7
        
        # Lower temperature for code feedback (more precise)
        if context.input_classification.input_type == InputType.CODE_SUBMISSION:
            base_temperature = 0.4
        
        # Higher temperature for encouragement (more creative)
        elif teaching_strategy["encouragement_needed"]:
            base_temperature = 0.8
        
        # Lower temperature for explanations (more structured)
        elif context.input_classification.input_type == InputType.QUESTION:
            base_temperature = 0.5
        
        return base_temperature
    
    def _determine_max_tokens(self, context: ResponseGenerationContext) -> int:
        """Determine max tokens based on context complexity"""
        
        base_tokens = 500
        
        # More tokens for code feedback
        if context.input_classification.input_type == InputType.CODE_SUBMISSION:
            base_tokens = 800
        
        # More tokens for explanations
        elif context.input_classification.input_type == InputType.QUESTION:
            base_tokens = 700
        
        # Fewer tokens for minimal context
        if context.compression_result:
            compression_level = context.compression_result.get("compression_level")
            if compression_level == ContextCompressionLevel.HIGH_LEVEL_SUMMARY:
                base_tokens = min(base_tokens, 400)
        
        return base_tokens
    
    async def _post_process_response(
        self, 
        ai_response: str, 
        context: ResponseGenerationContext,
        teaching_strategy: Dict[str, Any]
    ) -> str:
        """Post-process the AI response for quality and appropriateness"""
        
        processed_response = ai_response.strip()
        
        # Add encouraging note if student seems to be struggling
        if teaching_strategy["encouragement_needed"] and not any(
            phrase in processed_response.lower() 
            for phrase in ["great", "good", "well done", "excellent", "nice"]
        ):
            processed_response = f"You're making good progress! {processed_response}"
        
        # Ensure code submissions get constructive feedback structure
        if context.input_classification.input_type == InputType.CODE_SUBMISSION:
            if not any(phrase in processed_response.lower() for phrase in ["looks", "good", "working"]):
                # If no positive feedback detected, ensure balanced approach
                processed_response = f"Let me take a look at your code.\n\n{processed_response}"
        
        return processed_response
    
    async def _generate_fallback_response(
        self, 
        context: ResponseGenerationContext, 
        error: str
    ) -> Dict[str, Any]:
        """Generate a fallback response when main generation fails"""
        
        logger.warning(f"Using fallback response due to error: {error}")
        
        fallback_responses = {
            InputType.CODE_SUBMISSION: "I see you've submitted some code. Let me help you work through it step by step. Can you tell me what specific part you'd like me to focus on?",
            InputType.QUESTION: "That's a great question! I want to make sure I give you the most helpful explanation. Could you provide a bit more context about what specifically you'd like me to clarify?",
            InputType.NEXT_PROBLEM: "Excellent work on making progress! Let's move forward to the next challenge. Are you feeling ready to tackle something new?",
            InputType.READY_TO_START: "Great! I'm excited to work with you on this assignment. Let's begin by taking a look at what we'll be learning today.",
            InputType.GENERAL_CHAT: "I'm here to help you learn programming! What would you like to work on or discuss?"
        }
        
        input_type = context.input_classification.input_type if context.input_classification else InputType.GENERAL_CHAT
        fallback_text = fallback_responses.get(input_type, fallback_responses[InputType.GENERAL_CHAT])
        
        return {
            "success": True,
            "response": fallback_text,
            "teaching_strategy": {"primary_approach": "fallback"},
            "prompt_template": "fallback",
            "input_classification": input_type.value if context.input_classification else "unknown",
            "fallback": True,
            "error": error,
            "metadata": {
                "generation_timestamp": datetime.utcnow(),
                "is_fallback": True
            }
        }


# Global instance
smart_response_generator = SmartResponseGenerator()