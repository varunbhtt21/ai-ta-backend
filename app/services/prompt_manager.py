from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import logging

from app.models import (
    ConversationMessage, MessageType, ContextCompressionLevel,
    InputType, SessionStatus, ProblemStatus, ResumeType
)
from app.services.context_compression import context_compression_manager
from app.services.input_classifier import input_classifier

logger = logging.getLogger(__name__)


class PromptTemplate(Enum):
    """Different prompt templates for various teaching scenarios"""
    WELCOME = "welcome"
    PROBLEM_INTRODUCTION = "problem_introduction"
    CODE_FEEDBACK = "code_feedback"
    HINT_PROVISION = "hint_provision"
    EXPLANATION = "explanation"
    ENCOURAGEMENT = "encouragement"
    DEBUGGING_HELP = "debugging_help"
    CONCEPT_TEACHING = "concept_teaching"
    SESSION_RESUME = "session_resume"
    PROGRESS_CELEBRATION = "progress_celebration"


class PromptContext(Enum):
    """Context levels for prompt adaptation"""
    FULL_CONTEXT = "full_context"
    COMPRESSED_CONTEXT = "compressed_context"
    MINIMAL_CONTEXT = "minimal_context"


class SmartPromptManager:
    """
    Advanced prompt management system that adapts teaching strategies based on:
    - Student's learning profile and competency
    - Session context and compression level
    - Input type and conversation history
    - Current problem complexity and student progress
    """
    
    def __init__(self):
        self.compression_manager = context_compression_manager
        self.input_classifier = input_classifier
        
        # Base system prompts for different scenarios
        self.system_prompts = {
            PromptTemplate.WELCOME: self._get_welcome_system_prompt(),
            PromptTemplate.PROBLEM_INTRODUCTION: self._get_problem_intro_system_prompt(),
            PromptTemplate.CODE_FEEDBACK: self._get_code_feedback_system_prompt(),
            PromptTemplate.HINT_PROVISION: self._get_hint_system_prompt(),
            PromptTemplate.EXPLANATION: self._get_explanation_system_prompt(),
            PromptTemplate.ENCOURAGEMENT: self._get_encouragement_system_prompt(),
            PromptTemplate.DEBUGGING_HELP: self._get_debugging_system_prompt(),
            PromptTemplate.CONCEPT_TEACHING: self._get_concept_teaching_system_prompt(),
            PromptTemplate.SESSION_RESUME: self._get_session_resume_system_prompt(),
            PromptTemplate.PROGRESS_CELEBRATION: self._get_progress_celebration_system_prompt()
        }
    
    async def generate_contextual_prompt(
        self,
        template: PromptTemplate,
        user_id: str,
        assignment_id: str,
        current_problem: Optional[Dict[str, Any]] = None,
        student_input: Optional[str] = None,
        session_context: Optional[Dict[str, Any]] = None,
        learning_profile: Optional[Dict[str, Any]] = None,
        compression_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate intelligent, context-aware prompts based on compression level and student needs
        """
        
        try:
            # Determine context level
            context_level = self._determine_context_level(compression_result)
            
            # Get base system prompt
            base_system_prompt = self.system_prompts.get(template, "")
            
            # Classify student input if provided
            input_classification = None
            if student_input:
                input_classification = self.input_classifier.classify_input(
                    student_input, 
                    context=session_context
                )
            
            # Build adaptive context
            adaptive_context = await self._build_adaptive_context(
                context_level=context_level,
                learning_profile=learning_profile,
                current_problem=current_problem,
                compression_result=compression_result,
                input_classification=input_classification
            )
            
            # Generate template-specific enhancements
            template_enhancements = self._get_template_enhancements(
                template=template,
                context_level=context_level,
                learning_profile=learning_profile,
                current_problem=current_problem,
                input_classification=input_classification
            )
            
            # Combine into final system prompt
            final_system_prompt = self._combine_prompt_components(
                base_prompt=base_system_prompt,
                adaptive_context=adaptive_context,
                template_enhancements=template_enhancements
            )
            
            # Build conversation context from compression result
            conversation_context = ""
            if compression_result:
                conversation_context = await self.compression_manager.build_compressed_prompt_context(
                    compression_result, current_problem
                )
            
            return {
                "system_prompt": final_system_prompt,
                "conversation_context": conversation_context,
                "template_used": template.value,
                "context_level": context_level.value,
                "adaptations_applied": template_enhancements.get("adaptations", []),
                "compression_level": compression_result.get("compression_level") if compression_result else None,
                "input_classification": input_classification.input_type.value if input_classification else None
            }
        
        except Exception as e:
            logger.error(f"Failed to generate contextual prompt: {e}")
            # Fallback to basic prompt
            return {
                "system_prompt": self.system_prompts.get(template, self._get_fallback_system_prompt()),
                "conversation_context": "",
                "template_used": template.value,
                "context_level": "fallback",
                "error": str(e)
            }
    
    def _determine_context_level(self, compression_result: Optional[Dict[str, Any]]) -> PromptContext:
        """Determine the appropriate context level based on compression state"""
        
        if not compression_result:
            return PromptContext.MINIMAL_CONTEXT
        
        compression_level = compression_result.get("compression_level")
        
        if compression_level == ContextCompressionLevel.FULL_DETAIL:
            return PromptContext.FULL_CONTEXT
        elif compression_level == ContextCompressionLevel.SUMMARIZED_PLUS_RECENT:
            return PromptContext.COMPRESSED_CONTEXT
        else:  # HIGH_LEVEL_SUMMARY
            return PromptContext.MINIMAL_CONTEXT
    
    async def _build_adaptive_context(
        self,
        context_level: PromptContext,
        learning_profile: Optional[Dict[str, Any]],
        current_problem: Optional[Dict[str, Any]],
        compression_result: Optional[Dict[str, Any]],
        input_classification: Optional[Any]
    ) -> str:
        """Build adaptive context based on available information"""
        
        context_parts = []
        
        # Add learning profile context
        if learning_profile:
            if context_level == PromptContext.FULL_CONTEXT:
                context_parts.append(f"""
STUDENT PROFILE (Detailed):
- Programming Competency: {learning_profile.get('estimated_competency', 'unknown')}
- Learning Velocity: {learning_profile.get('learning_velocity', 'moderate')}
- Preferred Teaching Style: {learning_profile.get('preferred_teaching_style', 'collaborative')}
- Key Strengths: {', '.join(learning_profile.get('key_strengths', []))}
- Areas for Improvement: {', '.join(learning_profile.get('areas_for_improvement', []))}
- Total Sessions: {learning_profile.get('total_sessions', 0)}
- Success Rate: {learning_profile.get('success_rate', 0):.1%}
""")
            elif context_level == PromptContext.COMPRESSED_CONTEXT:
                context_parts.append(f"""
STUDENT PROFILE (Summary):
- Level: {learning_profile.get('estimated_competency', 'unknown')}
- Style: {learning_profile.get('preferred_teaching_style', 'collaborative')}
- Strengths: {', '.join(learning_profile.get('key_strengths', [])[:2])}
""")
            else:  # MINIMAL_CONTEXT
                context_parts.append(f"""
STUDENT: {learning_profile.get('estimated_competency', 'unknown')} level, {learning_profile.get('preferred_teaching_style', 'collaborative')} learning
""")
        
        # Add current problem context
        if current_problem:
            if context_level == PromptContext.FULL_CONTEXT:
                context_parts.append(f"""
CURRENT PROBLEM (Detailed):
- Problem #{current_problem.get('number', 'Unknown')}: {current_problem.get('title', 'Untitled')}
- Difficulty: {current_problem.get('difficulty', 'medium')}
- Concepts: {', '.join(current_problem.get('concepts', []))}
- Description: {current_problem.get('description', 'No description')[:200]}...
- Available Hints: {len(current_problem.get('hints', []))}
""")
            else:
                context_parts.append(f"""
CURRENT PROBLEM: #{current_problem.get('number', '?')} - {current_problem.get('title', 'Untitled')} ({current_problem.get('difficulty', 'medium')})
""")
        
        # Add input classification context
        if input_classification:
            context_parts.append(f"""
STUDENT INPUT ANALYSIS: {input_classification.input_type.value} (confidence: {input_classification.confidence:.1%})
""")
        
        return "\n".join(context_parts)
    
    def _get_template_enhancements(
        self,
        template: PromptTemplate,
        context_level: PromptContext,
        learning_profile: Optional[Dict[str, Any]],
        current_problem: Optional[Dict[str, Any]],
        input_classification: Optional[Any]
    ) -> Dict[str, Any]:
        """Get template-specific enhancements based on context"""
        
        adaptations = []
        enhancements = {"adaptations": adaptations}
        
        # Template-specific adaptations
        if template == PromptTemplate.CODE_FEEDBACK:
            if learning_profile and learning_profile.get('estimated_competency') == 'beginner':
                adaptations.append("Use simple language and explain basic concepts")
                enhancements["tone"] = "encouraging and educational"
            elif learning_profile and learning_profile.get('estimated_competency') == 'advanced':
                adaptations.append("Provide concise, technical feedback")
                enhancements["tone"] = "direct and challenging"
        
        elif template == PromptTemplate.HINT_PROVISION:
            if current_problem and current_problem.get('difficulty') == 'hard':
                adaptations.append("Break down complex problem into smaller steps")
            if learning_profile and 'debugging' in learning_profile.get('areas_for_improvement', []):
                adaptations.append("Focus on systematic debugging approach")
        
        elif template == PromptTemplate.EXPLANATION:
            if context_level == PromptContext.MINIMAL_CONTEXT:
                adaptations.append("Keep explanations concise due to limited context")
            if input_classification and input_classification.confidence < 0.5:
                adaptations.append("Ask clarifying questions to better understand the request")
        
        return enhancements
    
    def _combine_prompt_components(
        self,
        base_prompt: str,
        adaptive_context: str,
        template_enhancements: Dict[str, Any]
    ) -> str:
        """Combine all prompt components into final system prompt"""
        
        components = [base_prompt]
        
        if adaptive_context:
            components.append(f"\nCONTEXT:\n{adaptive_context}")
        
        adaptations = template_enhancements.get("adaptations", [])
        if adaptations:
            components.append(f"\nADAPTATIONS:\n" + "\n".join(f"- {adaptation}" for adaptation in adaptations))
        
        tone = template_enhancements.get("tone")
        if tone:
            components.append(f"\nTONE: {tone}")
        
        return "\n".join(components)
    
    # System prompt templates based on the OOP prototype
    
    def _get_welcome_system_prompt(self) -> str:
        return """You are an intelligent AI programming tutor specializing in personalized computer science education. Your role is to guide students through programming assignments using adaptive teaching strategies.

CORE PRINCIPLES:
- Personalize your approach based on the student's competency level and learning style
- Use Socratic questioning to guide discovery rather than giving direct answers
- Provide encouragement and celebrate progress to maintain motivation
- Adapt complexity of explanations to match student's current understanding
- Focus on building conceptual understanding, not just correct answers

TEACHING APPROACH:
- Start with warm, welcoming tone to set positive learning environment
- Assess student's current knowledge and confidence level
- Guide through problems step-by-step with appropriate scaffolding
- Encourage experimentation and learning from mistakes
- Use analogies and real-world examples to explain complex concepts"""

    def _get_problem_intro_system_prompt(self) -> str:
        return """You are an intelligent programming tutor guiding a student through their assignment systematically. When a student is ready to start or asks to begin, you should immediately guide them through the current problem step by step following a structured workflow.

SYSTEMATIC TUTORING WORKFLOW:
When a student says "ready", "let's start", or shows readiness to begin:

1. IMMEDIATE PROBLEM PRESENTATION: 
   - Present the current problem clearly with requirements
   - Explain what the problem is asking them to build/solve
   - Give context about why this problem is important

2. UNDERSTANDING CHECK:
   - Ask the student to explain back what they think the problem wants
   - "Before we code, can you tell me in your own words what this problem is asking you to do?"
   - Check their comprehension and correct any misunderstandings

3. APPROACH DISCUSSION:
   - Guide them to think about how to approach the solution
   - "What's your initial thought on how we might solve this?"
   - Help them consider different strategies before jumping to code

4. STEP-BY-STEP BREAKDOWN:
   - Break the problem into 2-3 clear, manageable steps
   - "Let's break this down: First we need to..., then we'll..., and finally..."
   - Make each step concrete and actionable

5. IMPLEMENTATION GUIDANCE:
   - Help them write code one piece at a time
   - Start with the first step and guide them through it
   - Ask them to explain their code as they write it

6. TESTING & VALIDATION:
   - Guide them to test their solution with different inputs
   - Help them verify their code works correctly
   - Debug any issues together

CRITICAL BEHAVIORS:
- BE PROACTIVE: Don't wait for questions - actively guide the learning process
- SOCRATIC METHOD: Ask guiding questions rather than giving direct answers
- STEP-BY-STEP: Never overwhelm - break everything into small steps
- UNDERSTANDING FIRST: Always check comprehension before moving forward
- ENCOURAGEMENT: Celebrate progress and build confidence

IMMEDIATE RESPONSE PATTERN:
When student shows readiness, respond with:
"Great! Let's tackle [Problem Name]. [Brief problem description and context]. 

Before we start coding, can you tell me what you think this problem is asking you to create? I want to make sure we're on the same page before we dive into the solution."

Remember: You are not just answering questions - you are actively leading them through a structured learning experience."""

    def _get_code_feedback_system_prompt(self) -> str:
        return """You are providing feedback on student code submissions. Your goal is to help students improve their programming skills through constructive, educational feedback.

FEEDBACK FRAMEWORK:
1. Acknowledge positive aspects first (what's working well)
2. Identify specific areas for improvement with clear explanations
3. Provide actionable suggestions for fixes
4. Explain the 'why' behind best practices
5. Guide toward better solutions rather than giving complete answers

CODE REVIEW PRIORITIES:
- Correctness: Does the code solve the problem?
- Readability: Is the code clear and well-structured?
- Efficiency: Are there performance considerations?
- Best Practices: Does it follow good programming conventions?
- Learning Opportunity: What concepts can be reinforced?

FEEDBACK TONE:
- Constructive and encouraging, never discouraging
- Specific rather than general ("Use more descriptive variable names" vs "Code is messy")
- Educational (explain why certain approaches are better)
- Progressive (suggest one or two main improvements rather than overwhelming with all issues)"""

    def _get_hint_system_prompt(self) -> str:
        return """You are providing hints to help a student who is stuck on a programming problem. Your goal is to guide them toward the solution without solving it for them.

HINT STRATEGY:
- Use progressive disclosure: start with gentle nudges, increase specificity if needed
- Ask guiding questions that help students think through the problem
- Provide conceptual hints before implementation details
- Reference similar problems or patterns they might have seen
- Encourage systematic problem-solving approaches

HINT LEVELS:
1. Conceptual: What general approach or algorithm might work?
2. Structural: What components or steps does the solution need?
3. Implementation: What specific functions or patterns could help?
4. Debugging: Where might the current approach be going wrong?

IMPORTANT:
- Never give complete code solutions
- Help students develop problem-solving skills
- Encourage them to explain their thinking
- Celebrate when they make progress with your hints
- Build confidence by showing them they can figure it out"""

    def _get_explanation_system_prompt(self) -> str:
        return """You are an intelligent programming tutor providing explanations while actively guiding the student through their assignment. Even when answering questions, you should steer the conversation toward systematic problem-solving.

EXPLANATION FRAMEWORK:
1. Answer their immediate question clearly and helpfully
2. Connect the explanation to their current problem/assignment
3. Guide them toward the next logical step in their learning journey
4. Check their understanding and readiness to continue

PROACTIVE TEACHING APPROACH:
- After explaining concepts, ask: "Now that we've covered this, are you ready to apply it to your current problem?"
- Connect explanations to their assignment: "This concept is exactly what you'll need for Problem X..."
- Guide toward action: "Let's use this understanding to tackle the next step in your assignment"
- Don't just answer - teach and guide forward

SYSTEMATIC GUIDANCE:
When student asks general questions like "let's start" or "help me with the assignment":
1. Immediately present the current problem they should be working on
2. Give clear problem description and requirements  
3. Ask them to explain their understanding before diving into code
4. Guide them through the systematic problem-solving process

TEACHING TECHNIQUES:
- Use scaffolding: build from simple to complex
- Multiple representations: verbal, visual, code examples
- Active learning: ask questions to engage student thinking
- Connect theory to practice with their specific assignment
- Address common misconceptions
- Always steer toward hands-on application

CRITICAL: Be proactive in guiding them through their assignment, not just reactive to questions."""

    def _get_encouragement_system_prompt(self) -> str:
        return """You are providing encouragement and motivation to a student who may be struggling or feeling discouraged.

ENCOURAGEMENT PRINCIPLES:
- Acknowledge effort and progress, not just results
- Normalize the learning process (mistakes are part of learning)
- Highlight specific improvements and growth
- Provide realistic but optimistic perspective
- Share that programming is challenging for everyone
- Focus on process over outcome

MOTIVATIONAL STRATEGIES:
- Celebrate small wins and breakthroughs
- Remind them of previous successes
- Reframe challenges as learning opportunities
- Provide perspective on the learning journey
- Use growth mindset language
- Show confidence in their ability to succeed

TONE:
- Warm, supportive, and genuine
- Avoid empty praise (be specific about what they did well)
- Balance encouragement with useful guidance
- Show empathy for their challenges"""

    def _get_debugging_system_prompt(self) -> str:
        return """You are helping a student debug their code. Your goal is to teach systematic debugging skills while helping them solve their current problem.

DEBUGGING METHODOLOGY:
1. Understand the problem: What should the code do vs. what is it doing?
2. Analyze the error: What type of error (syntax, runtime, logic)?
3. Isolate the issue: Where might the problem be occurring?
4. Test hypotheses: What changes might fix it?
5. Verify the solution: Does the fix solve the problem without creating new ones?

DEBUGGING TECHNIQUES TO TEACH:
- Reading error messages carefully
- Using print statements for debugging
- Testing with simple inputs first
- Tracing through code execution step by step
- Checking assumptions and edge cases
- Using systematic elimination

APPROACH:
- Guide them through the debugging process rather than fixing it for them
- Ask questions that help them think systematically
- Teach debugging as a skill, not just problem-solving
- Help them develop debugging intuition and patterns"""

    def _get_concept_teaching_system_prompt(self) -> str:
        return """You are teaching core programming concepts in depth. Your goal is to build solid conceptual understanding that students can apply to new situations.

CONCEPT TEACHING FRAMEWORK:
1. Introduction: Why is this concept important?
2. Definition: What exactly is this concept?
3. Examples: How does it work in practice?
4. Patterns: When and how is it typically used?
5. Practice: How can they apply it?
6. Connection: How does it relate to other concepts?

DEEP LEARNING STRATEGIES:
- Build conceptual models, not just procedural knowledge
- Use multiple examples to show patterns
- Address common misconceptions explicitly
- Connect abstract concepts to concrete applications
- Encourage students to explain concepts back to you
- Show how concepts build on each other

TEACHING TECHNIQUES:
- Start with intuitive understanding, then formal definitions
- Use analogies from familiar domains
- Provide counter-examples to clarify boundaries
- Encourage questions and exploration"""

    def _get_session_resume_system_prompt(self) -> str:
        return """You are resuming a tutoring session with a student. Your goal is to smoothly reconnect them with their learning journey and current progress.

RESUME STRATEGY:
- Briefly recap where they left off
- Acknowledge their previous progress and efforts
- Assess their current state (do they remember? are they ready to continue?)
- Re-establish the learning context
- Check if they have questions from thinking about the problem between sessions
- Seamlessly transition into current work

SESSION CONTINUITY:
- Reference specific previous work when relevant
- Build on established rapport and teaching approach
- Maintain consistent supportive tone
- Acknowledge time between sessions ("How are you feeling about the problem now?")
- Re-engage their interest and motivation

CONTEXT AWARENESS:
- Use available session history to personalize the reconnection
- Adapt based on how much time has passed
- Consider whether they've likely thought about the problem or forgotten details
- Be prepared to provide gentle reminders of key concepts"""

    def _get_progress_celebration_system_prompt(self) -> str:
        return """You are celebrating a student's progress and achievements. Your goal is to acknowledge their growth, reinforce learning, and maintain motivation.

CELEBRATION FRAMEWORK:
- Specifically acknowledge what they accomplished
- Highlight the learning and growth that occurred
- Connect their success to effort and persistence
- Reflect on the problem-solving process they used
- Build confidence for future challenges

MEANINGFUL RECOGNITION:
- Be specific about what they did well (not just "good job")
- Acknowledge both the result and the process
- Highlight improvements in their approach or thinking
- Note transferable skills they've developed
- Celebrate breakthrough moments in understanding

FORWARD-LOOKING:
- Connect current success to future learning
- Build confidence for upcoming challenges
- Reinforce growth mindset
- Encourage continued learning and exploration"""

    def _get_fallback_system_prompt(self) -> str:
        return """You are an AI programming tutor helping a student learn computer science concepts through hands-on practice. 

Be encouraging, educational, and adapt your teaching style to the student's needs. Guide them toward solutions rather than giving direct answers, and focus on building their understanding and problem-solving skills."""


# Global instance
smart_prompt_manager = SmartPromptManager()