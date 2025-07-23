from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import re

from app.models import (
    ConversationMessage, MessageType, InputType, 
    SessionContext, LearningVelocity, TeachingStyle, ProblemStatus
)
from app.services.openai_client import openai_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class AITutoringEngine:
    """AI-powered tutoring engine that provides personalized programming education"""
    
    def __init__(self):
        self.openai_client = openai_client
    
    def _build_system_prompt(
        self,
        context: SessionContext,
        teaching_style: TeachingStyle = TeachingStyle.COLLABORATIVE,
        learning_velocity: LearningVelocity = LearningVelocity.MODERATE
    ) -> str:
        """Build personalized system prompt based on context and learning profile"""
        
        base_prompt = """You are an expert Python programming tutor working with a student in an interactive learning environment. Your goal is to help them learn programming concepts through guided discovery and practice.

CORE PRINCIPLES:
- Be encouraging and patient
- Guide students to discover solutions rather than giving direct answers
- Provide clear, concise explanations
- Use examples when helpful
- Adapt your teaching style to the student's needs
- Focus on understanding, not just getting the right answer

TEACHING APPROACH:"""
        
        if teaching_style == TeachingStyle.SOCRATIC:
            base_prompt += """
- Ask leading questions that guide the student toward the solution
- Help them think through the problem step by step
- Encourage them to explain their reasoning"""
            
        elif teaching_style == TeachingStyle.DIRECT:
            base_prompt += """
- Provide clear, direct explanations when students are stuck
- Give concrete examples and demonstrations
- Break down complex concepts into simple steps"""
            
        elif teaching_style == TeachingStyle.COLLABORATIVE:
            base_prompt += """
- Work through problems together with the student
- Think out loud to demonstrate problem-solving approaches
- Encourage experimentation and learning from mistakes"""
            
        elif teaching_style == TeachingStyle.SUPPORTIVE:
            base_prompt += """
- Provide lots of encouragement and positive reinforcement
- Be extra patient with struggling students
- Celebrate small wins and progress"""
            
        elif teaching_style == TeachingStyle.CHALLENGING:
            base_prompt += """
- Push students to think deeper about problems
- Ask follow-up questions to extend learning
- Introduce related concepts when appropriate"""
        
        # Add learning velocity considerations
        velocity_guidance = {
            LearningVelocity.FAST: "The student learns quickly, so you can move at a faster pace and introduce more advanced concepts.",
            LearningVelocity.MODERATE: "The student learns at a moderate pace, so provide balanced explanations with examples.",
            LearningVelocity.SLOW: "The student needs more time to understand concepts, so be extra patient and provide detailed explanations."
        }
        
        base_prompt += f"\n\nSTUDENT PROFILE: {velocity_guidance.get(learning_velocity, velocity_guidance[LearningVelocity.MODERATE])}"
        
        # Add context-specific information
        if context.session.current_problem:
            base_prompt += f"\n\nCURRENT PROBLEM: The student is working on problem #{context.session.current_problem}."
        
        if context.session.compression_level:
            base_prompt += f"\nSESSION CONTEXT: This is session #{context.session.session_number} with {context.session.compression_level} context level."
        
        base_prompt += """

RESPONSE GUIDELINES:
- Keep responses concise but helpful (aim for 2-4 sentences)
- Use encouraging language
- When analyzing code, point out both what works and what needs improvement
- For incorrect code, provide gentle hints rather than complete solutions
- If the student seems frustrated, offer encouragement and alternative approaches
- End with a question or prompt to keep the conversation engaging

Remember: Your goal is to help them learn and build confidence, not just solve problems."""

        return base_prompt
    
    async def generate_tutoring_response(
        self,
        context: SessionContext,
        user_input: str,
        input_type: InputType,
        problem_data: Optional[Dict[str, Any]] = None,
        learning_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate contextual tutoring response based on input type and session context"""
        
        try:
            # Extract learning preferences from profile
            teaching_style = TeachingStyle.COLLABORATIVE
            learning_velocity = LearningVelocity.MODERATE
            
            if learning_profile:
                teaching_style = TeachingStyle(learning_profile.get("preferred_teaching_style", "collaborative"))
                learning_velocity = LearningVelocity(learning_profile.get("learning_velocity", "moderate"))
            
            # Build system prompt
            system_prompt = self._build_system_prompt(context, teaching_style, learning_velocity)
            
            # Handle different input types
            if input_type == InputType.CODE_SUBMISSION:
                return await self._handle_code_submission(
                    context, user_input, system_prompt, problem_data
                )
            
            elif input_type == InputType.QUESTION:
                return await self._handle_question(
                    context, user_input, system_prompt, problem_data
                )
            
            elif input_type == InputType.READY_TO_START:
                return await self._handle_ready_signal(
                    context, user_input, system_prompt, problem_data
                )
            
            elif input_type == InputType.NEXT_PROBLEM:
                return await self._handle_next_problem(
                    context, user_input, system_prompt
                )
            
            else:  # GENERAL_CHAT
                return await self._handle_general_chat(
                    context, user_input, system_prompt
                )
        
        except Exception as e:
            logger.error(f"Error generating tutoring response: {e}")
            return {
                "success": False,
                "content": "I'm having trouble processing your request right now. Please try again in a moment.",
                "error": str(e),
                "fallback_response": True
            }
    
    async def _handle_code_submission(
        self,
        context: SessionContext,
        code: str,
        system_prompt: str,
        problem_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle code submission analysis and feedback"""
        
        # Build context for code analysis
        problem_description = "No problem description available"
        if problem_data:
            problem_description = problem_data.get("description", problem_description)
        
        # Create conversation context including the code
        messages = context.recent_messages[-5:] if context.recent_messages else []
        
        # Add the code submission message
        code_message = ConversationMessage(
            timestamp=datetime.utcnow(),
            message_type=MessageType.USER,
            content=f"Here's my code for problem {context.session.current_problem}:\n\n```python\n{code}\n```"
        )
        messages.append(code_message)
        
        # Generate response
        result = await self.openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3  # Lower temperature for more consistent code analysis
        )
        
        if result["success"]:
            # Analyze if code appears correct (basic heuristic)
            is_likely_correct = self._analyze_code_quality(code, result["content"])
            
            return {
                "success": True,
                "content": result["content"],
                "analysis_type": "code_submission",
                "is_likely_correct": is_likely_correct,
                "usage": result.get("usage", {}),
                "suggestions_provided": "suggest" in result["content"].lower()
            }
        
        return {
            "success": False,
            "content": "I'm having trouble analyzing your code right now. Let me know if you have any questions about it!",
            "error": result.get("error"),
            "fallback_response": True
        }
    
    async def _handle_question(
        self,
        context: SessionContext,
        question: str,
        system_prompt: str,
        problem_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle student questions with context-aware responses"""
        
        # Include recent conversation context
        messages = context.recent_messages[-8:] if context.recent_messages else []
        
        # Add current question
        question_message = ConversationMessage(
            timestamp=datetime.utcnow(),
            message_type=MessageType.USER,
            content=question
        )
        messages.append(question_message)
        
        # Generate response
        result = await self.openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.4
        )
        
        if result["success"]:
            return {
                "success": True,
                "content": result["content"],
                "analysis_type": "question_response",
                "usage": result.get("usage", {}),
                "context_used": len(messages) > 1
            }
        
        return {
            "success": False,
            "content": "I want to help with your question, but I'm having technical difficulties. Could you try rephrasing it?",
            "error": result.get("error"),
            "fallback_response": True
        }
    
    async def _handle_ready_signal(
        self,
        context: SessionContext,
        user_input: str,
        system_prompt: str,
        problem_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle ready-to-start signals with problem introduction"""
        
        problem_intro = f"Great! Let's work on problem {context.session.current_problem}."
        
        if problem_data:
            problem_intro = f"Perfect! Let's tackle problem {context.session.current_problem}: {problem_data.get('title', 'Programming Challenge')}\n\n{problem_data.get('description', 'Let me know when you have questions!')}"
        
        # Create simple context for introduction
        messages = [
            ConversationMessage(
                timestamp=datetime.utcnow(),
                message_type=MessageType.USER,
                content=f"I'm ready to start problem {context.session.current_problem}!"
            )
        ]
        
        result = await self.openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt + f"\n\nThe student is ready to start. Problem info: {problem_intro}",
            temperature=0.5
        )
        
        if result["success"]:
            return {
                "success": True,
                "content": result["content"],
                "analysis_type": "introduction",
                "usage": result.get("usage", {}),
                "problem_introduced": True
            }
        
        return {
            "success": True,
            "content": problem_intro + "\n\nTake your time and let me know if you need any help!",
            "fallback_response": True
        }
    
    async def _handle_next_problem(
        self,
        context: SessionContext,
        user_input: str,
        system_prompt: str
    ) -> Dict[str, Any]:
        """Handle requests to move to next problem"""
        
        messages = [
            ConversationMessage(
                timestamp=datetime.utcnow(),
                message_type=MessageType.USER,
                content=f"I want to move on to the next problem (problem {context.session.current_problem + 1})"
            )
        ]
        
        result = await self.openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.4
        )
        
        if result["success"]:
            return {
                "success": True,
                "content": result["content"],
                "analysis_type": "problem_transition",
                "usage": result.get("usage", {}),
                "next_problem": context.session.current_problem + 1
            }
        
        return {
            "success": True,
            "content": f"Excellent work! Let's move on to problem {context.session.current_problem + 1}. You're making great progress!",
            "fallback_response": True
        }
    
    async def _handle_general_chat(
        self,
        context: SessionContext,
        user_input: str,
        system_prompt: str
    ) -> Dict[str, Any]:
        """Handle general conversation and keep focused on learning"""
        
        # Include some recent context
        messages = context.recent_messages[-6:] if context.recent_messages else []
        
        # Add current input
        chat_message = ConversationMessage(
            timestamp=datetime.utcnow(),
            message_type=MessageType.USER,
            content=user_input
        )
        messages.append(chat_message)
        
        result = await self.openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt + "\n\nKeep responses focused on programming learning and encourage the student to work on their current problem.",
            temperature=0.6
        )
        
        if result["success"]:
            return {
                "success": True,
                "content": result["content"],
                "analysis_type": "general_conversation",
                "usage": result.get("usage", {}),
                "redirect_to_learning": "problem" in result["content"].lower()
            }
        
        return {
            "success": True,
            "content": f"I'm here to help you with programming! Let's focus on problem {context.session.current_problem}. What would you like to work on?",
            "fallback_response": True
        }
    
    def _analyze_code_quality(self, code: str, ai_feedback: str) -> bool:
        """Basic heuristic to determine if code appears correct based on AI feedback"""
        
        # Look for positive indicators in AI response
        positive_indicators = [
            "looks good", "correct", "well done", "great job", "excellent",
            "perfect", "right approach", "works", "solution"
        ]
        
        # Look for negative indicators
        negative_indicators = [
            "error", "incorrect", "wrong", "issue", "problem", "bug",
            "fix", "mistake", "doesn't work", "won't run"
        ]
        
        feedback_lower = ai_feedback.lower()
        
        positive_count = sum(1 for indicator in positive_indicators if indicator in feedback_lower)
        negative_count = sum(1 for indicator in negative_indicators if indicator in feedback_lower)
        
        # Also check code for basic Python syntax patterns
        has_basic_structure = bool(re.search(r'(def|if|for|while|return|print)', code))
        
        return positive_count > negative_count and has_basic_structure
    
    async def generate_personalized_hint(
        self,
        context: SessionContext,
        problem_data: Dict[str, Any],
        attempt_count: int,
        previous_code: List[str]
    ) -> Dict[str, Any]:
        """Generate progressive hints based on attempt count and previous submissions"""
        
        hint_level = min(attempt_count, 4)  # Cap at level 4
        
        system_prompt = f"""You are a patient Python programming tutor. The student is struggling with a problem and needs a Level {hint_level} hint.

Hint Level Guidelines:
- Level 1: Conceptual hint about the approach
- Level 2: Suggest specific Python concepts/functions
- Level 3: Provide partial code structure
- Level 4: Give detailed guidance with example patterns

Be encouraging and guide without giving the complete solution."""
        
        # Build context with previous attempts
        attempts_text = "\n\n".join([
            f"Previous attempt {i+1}:\n```python\n{code}\n```" 
            for i, code in enumerate(previous_code[-3:])  # Last 3 attempts
        ])
        
        hint_request = f"""Problem: {problem_data.get('description', 'Programming challenge')}

{attempts_text}

The student has made {attempt_count} attempts and needs a Level {hint_level} hint. Please provide appropriate guidance."""
        
        messages = [
            ConversationMessage(
                timestamp=datetime.utcnow(),
                message_type=MessageType.USER,
                content=hint_request
            )
        ]
        
        result = await self.openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3
        )
        
        if result["success"]:
            return {
                "success": True,
                "content": result["content"],
                "hint_level": hint_level,
                "usage": result.get("usage", {}),
                "attempt_count": attempt_count
            }
        
        # Fallback hints based on attempt count
        fallback_hints = {
            1: "Think about what the problem is asking you to do step by step. What's the main goal?",
            2: "Consider what Python functions or concepts might be helpful for this type of problem.",
            3: "Try breaking the problem down into smaller parts. What would your code structure look like?",
            4: "Let's think about this differently. What specific part is giving you trouble?"
        }
        
        return {
            "success": True,
            "content": fallback_hints.get(hint_level, fallback_hints[4]),
            "hint_level": hint_level,
            "fallback_response": True,
            "attempt_count": attempt_count
        }


# Global instance
ai_tutoring_engine = AITutoringEngine()