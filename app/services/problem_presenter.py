from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import logging

from app.models import (
    Problem, ConversationMessage, MessageType, ContextCompressionLevel,
    ProblemStatus, LearningVelocity, CodeCompetencyLevel
)
from app.services.prompt_manager import smart_prompt_manager, PromptTemplate
from app.services.smart_response_generator import smart_response_generator, ResponseGenerationContext

logger = logging.getLogger(__name__)


class PresentationStyle(Enum):
    """Different ways to present problems based on student needs"""
    DETAILED = "detailed"  # Full problem with context and examples
    FOCUSED = "focused"   # Core problem with minimal context
    SCAFFOLDED = "scaffolded"  # Problem broken into sub-steps
    CHALLENGING = "challenging"  # Problem with extensions and edge cases


class ProblemComplexity(Enum):
    """Problem complexity assessment"""
    SIMPLE = "simple"      # Single concept, straightforward implementation
    MODERATE = "moderate"  # Multiple concepts, some complexity
    COMPLEX = "complex"    # Advanced concepts, significant implementation


class StructuredProblemPresenter:
    """
    Advanced problem presentation system that adapts problem delivery based on:
    - Student's competency level and learning profile
    - Context compression level and session history
    - Problem complexity and pedagogical requirements
    - Previous problem performance and current confidence
    """
    
    def __init__(self):
        self.prompt_manager = smart_prompt_manager
        self.response_generator = smart_response_generator
    
    async def present_problem(
        self,
        problem: Problem,
        user_id: str,
        session_id: str,
        assignment_id: str,
        learning_profile: Optional[Dict[str, Any]] = None,
        session_context: Optional[Dict[str, Any]] = None,
        compression_result: Optional[Dict[str, Any]] = None,
        previous_problem_performance: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Present a problem using intelligent adaptation based on student context and needs
        """
        
        try:
            # Step 1: Analyze problem complexity
            problem_analysis = self._analyze_problem_complexity(problem)
            
            # Step 2: Determine optimal presentation style
            presentation_style = await self._determine_presentation_style(
                problem=problem,
                problem_analysis=problem_analysis,
                learning_profile=learning_profile,
                session_context=session_context,
                previous_performance=previous_problem_performance
            )
            
            # Step 3: Build adaptive problem context
            problem_context = await self._build_problem_context(
                problem=problem,
                presentation_style=presentation_style,
                problem_analysis=problem_analysis,
                learning_profile=learning_profile,
                compression_result=compression_result
            )
            
            # Step 4: Generate structured presentation
            presentation = await self._generate_structured_presentation(
                problem=problem,
                problem_context=problem_context,
                presentation_style=presentation_style,
                user_id=user_id,
                session_id=session_id,
                assignment_id=assignment_id,
                compression_result=compression_result
            )
            
            # Step 5: Add pedagogical enhancements
            enhanced_presentation = self._add_pedagogical_enhancements(
                presentation=presentation,
                problem=problem,
                style=presentation_style,
                learning_profile=learning_profile
            )
            
            return {
                "success": True,
                "presentation": enhanced_presentation,
                "problem_id": problem.number,
                "presentation_style": presentation_style.value,
                "problem_complexity": problem_analysis["complexity"].value,
                "adaptations_applied": problem_context.get("adaptations", []),
                "learning_objectives": problem_analysis.get("learning_objectives", []),
                "estimated_difficulty": self._estimate_difficulty_for_student(
                    problem, learning_profile
                ),
                "metadata": {
                    "presentation_timestamp": datetime.utcnow(),
                    "concepts_covered": problem.concepts,
                    "prerequisite_check": problem_analysis.get("prerequisites_met", True),
                    "scaffolding_level": problem_context.get("scaffolding_level", "moderate")
                }
            }
        
        except Exception as e:
            logger.error(f"Problem presentation failed: {e}")
            return await self._generate_fallback_presentation(problem, str(e))
    
    def _analyze_problem_complexity(self, problem: Problem) -> Dict[str, Any]:
        """Analyze problem to determine complexity and teaching requirements"""
        
        analysis = {
            "complexity": ProblemComplexity.MODERATE,
            "learning_objectives": [],
            "prerequisites": [],
            "implementation_steps": [],
            "potential_challenges": [],
            "extension_opportunities": []
        }
        
        # Assess complexity based on multiple factors
        complexity_score = 0
        
        # Concept count (more concepts = higher complexity)
        concept_count = len(problem.concepts)
        if concept_count <= 2:
            complexity_score += 1
        elif concept_count <= 4:
            complexity_score += 2
        else:
            complexity_score += 3
        
        # Description complexity (longer, more detailed = more complex)
        description_words = len(problem.description.split())
        if description_words > 100:
            complexity_score += 1
        if description_words > 200:
            complexity_score += 1
        
        # Difficulty level
        difficulty_scores = {"easy": 1, "medium": 2, "hard": 3}
        complexity_score += difficulty_scores.get(problem.difficulty.lower(), 2)
        
        # Test cases (more test cases might indicate edge cases)
        if len(problem.test_cases) > 5:
            complexity_score += 1
        
        # Determine final complexity
        if complexity_score <= 3:
            analysis["complexity"] = ProblemComplexity.SIMPLE
        elif complexity_score <= 6:
            analysis["complexity"] = ProblemComplexity.MODERATE
        else:
            analysis["complexity"] = ProblemComplexity.COMPLEX
        
        # Extract learning objectives from concepts
        analysis["learning_objectives"] = problem.concepts.copy()
        
        # Identify potential implementation steps
        if "loops" in problem.concepts:
            analysis["implementation_steps"].append("Design loop structure")
        if "functions" in problem.concepts:
            analysis["implementation_steps"].append("Define function signature")
        if "data structures" in problem.concepts:
            analysis["implementation_steps"].append("Choose appropriate data structure")
        
        # Common challenges based on concepts
        challenge_mapping = {
            "loops": "Off-by-one errors and loop conditions",
            "recursion": "Base case identification and recursive logic",
            "data structures": "Choosing the right data structure",
            "algorithms": "Time and space complexity considerations",
            "debugging": "Systematic error identification and fixing"
        }
        
        for concept in problem.concepts:
            if concept in challenge_mapping:
                analysis["potential_challenges"].append(challenge_mapping[concept])
        
        return analysis
    
    async def _determine_presentation_style(
        self,
        problem: Problem,
        problem_analysis: Dict[str, Any],
        learning_profile: Optional[Dict[str, Any]],
        session_context: Optional[Dict[str, Any]],
        previous_performance: Optional[Dict[str, Any]]
    ) -> PresentationStyle:
        """Determine the optimal way to present this problem to this student"""
        
        # Start with default style
        style = PresentationStyle.FOCUSED
        
        # Analyze student competency
        if learning_profile:
            competency = learning_profile.get("estimated_competency", "intermediate")
            learning_velocity = learning_profile.get("learning_velocity", "moderate")
            
            # Beginner students need more scaffolding
            if competency == "beginner":
                style = PresentationStyle.SCAFFOLDED
            
            # Advanced students can handle more challenging presentations
            elif competency == "advanced":
                style = PresentationStyle.CHALLENGING
            
            # Adjust based on learning velocity
            if learning_velocity == "slow" and style != PresentationStyle.SCAFFOLDED:
                style = PresentationStyle.DETAILED
        
        # Consider problem complexity
        complexity = problem_analysis["complexity"]
        
        if complexity == ProblemComplexity.COMPLEX:
            # Complex problems usually need scaffolding unless student is advanced
            if style != PresentationStyle.CHALLENGING:
                style = PresentationStyle.SCAFFOLDED
        
        elif complexity == ProblemComplexity.SIMPLE:
            # Simple problems can be more focused unless student needs support
            if style not in [PresentationStyle.SCAFFOLDED, PresentationStyle.DETAILED]:
                style = PresentationStyle.FOCUSED
        
        # Consider previous performance
        if previous_performance:
            success_rate = previous_performance.get("success_rate", 0.5)
            avg_attempts = previous_performance.get("average_attempts", 3)
            
            # Struggling students need more support
            if success_rate < 0.4 or avg_attempts > 5:
                style = PresentationStyle.SCAFFOLDED
            
            # High-performing students can handle challenges
            elif success_rate > 0.8 and avg_attempts < 2:
                style = PresentationStyle.CHALLENGING
        
        # Consider session context
        if session_context:
            # If student has been struggling recently, provide more support
            recent_struggles = session_context.get("recent_struggles", False)
            if recent_struggles:
                style = PresentationStyle.DETAILED
        
        return style
    
    async def _build_problem_context(
        self,
        problem: Problem,
        presentation_style: PresentationStyle,
        problem_analysis: Dict[str, Any],
        learning_profile: Optional[Dict[str, Any]],
        compression_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build comprehensive context for problem presentation"""
        
        context = {
            "adaptations": [],
            "scaffolding_level": "moderate",
            "focus_areas": [],
            "support_elements": [],
            "challenge_elements": []
        }
        
        # Style-specific adaptations
        if presentation_style == PresentationStyle.SCAFFOLDED:
            context["scaffolding_level"] = "high"
            context["adaptations"].extend([
                "Break problem into sub-steps",
                "Provide guided implementation approach",
                "Include intermediate checkpoints"
            ])
            context["support_elements"].extend([
                "Step-by-step guidance",
                "Conceptual explanations",
                "Implementation hints"
            ])
        
        elif presentation_style == PresentationStyle.CHALLENGING:
            context["scaffolding_level"] = "low"
            context["adaptations"].extend([
                "Include advanced considerations",
                "Suggest optimization opportunities",
                "Present edge cases to consider"
            ])
            context["challenge_elements"].extend([
                "Performance optimization",
                "Edge case handling",
                "Alternative approaches"
            ])
        
        elif presentation_style == PresentationStyle.DETAILED:
            context["adaptations"].extend([
                "Provide comprehensive context",
                "Include multiple examples",
                "Explain underlying concepts"
            ])
            context["support_elements"].extend([
                "Detailed explanations",
                "Multiple examples",
                "Concept reinforcement"
            ])
        
        else:  # FOCUSED
            context["adaptations"].append("Present core problem clearly and concisely")
        
        # Learning profile adaptations
        if learning_profile:
            competency = learning_profile.get("estimated_competency", "intermediate")
            teaching_style = learning_profile.get("preferred_teaching_style", "collaborative")
            
            if competency == "beginner":
                context["focus_areas"].extend(["foundational_concepts", "basic_syntax"])
            elif competency == "advanced":
                context["focus_areas"].extend(["best_practices", "optimization"])
            
            if teaching_style == "visual":
                context["support_elements"].append("visual_examples")
            elif teaching_style == "hands_on":
                context["support_elements"].append("interactive_elements")
        
        # Compression level adaptations
        if compression_result:
            compression_level = compression_result.get("compression_level")
            if compression_level == ContextCompressionLevel.HIGH_LEVEL_SUMMARY:
                context["adaptations"].append("Minimize context references due to compression")
                context["focus_areas"].append("self_contained_presentation")
        
        return context
    
    async def _generate_structured_presentation(
        self,
        problem: Problem,
        problem_context: Dict[str, Any],
        presentation_style: PresentationStyle,
        user_id: str,
        session_id: str,
        assignment_id: str,
        compression_result: Optional[Dict[str, Any]]
    ) -> str:
        """Generate the actual problem presentation text"""
        
        # Create a simulated "ready to start" input to trigger problem introduction
        context = ResponseGenerationContext(
            user_id=user_id,
            session_id=session_id,
            assignment_id=assignment_id,
            user_input="I'm ready to start the next problem",
            current_problem=problem.dict(),
            compression_result=compression_result
        )
        
        # Use the smart response generator with problem introduction template
        response_result = await self.response_generator.generate_intelligent_response(context)
        
        if response_result["success"]:
            base_presentation = response_result["response"]
        else:
            # Fallback to manual presentation
            base_presentation = self._create_manual_presentation(problem, presentation_style)
        
        # Enhance with style-specific elements
        enhanced_presentation = self._enhance_with_style_elements(
            base_presentation, problem, presentation_style, problem_context
        )
        
        return enhanced_presentation
    
    def _create_manual_presentation(self, problem: Problem, style: PresentationStyle) -> str:
        """Manual fallback for problem presentation"""
        
        presentation_parts = []
        
        # Problem header
        presentation_parts.append(f"## Problem {problem.number}: {problem.title}")
        
        # Difficulty indicator
        presentation_parts.append(f"**Difficulty:** {problem.difficulty.title()}")
        
        # Style-specific content
        if style == PresentationStyle.SCAFFOLDED:
            presentation_parts.append("Let's approach this step by step:")
            presentation_parts.append(f"**Description:** {problem.description}")
            presentation_parts.append("**Implementation Approach:**")
            presentation_parts.append("1. Start by understanding the requirements")
            presentation_parts.append("2. Plan your solution structure")
            presentation_parts.append("3. Implement incrementally")
            presentation_parts.append("4. Test with the provided examples")
        
        elif style == PresentationStyle.CHALLENGING:
            presentation_parts.append(f"**Challenge:** {problem.description}")
            presentation_parts.append("**Advanced Considerations:**")
            presentation_parts.append("- Consider edge cases and error handling")
            presentation_parts.append("- Think about performance optimization")
            presentation_parts.append("- Explore alternative solution approaches")
        
        elif style == PresentationStyle.DETAILED:
            presentation_parts.append(f"**Overview:** {problem.description}")
            if problem.concepts:
                presentation_parts.append(f"**Key Concepts:** {', '.join(problem.concepts)}")
            presentation_parts.append("**What you'll learn:**")
            for concept in problem.concepts:
                presentation_parts.append(f"- {concept.title()}")
        
        else:  # FOCUSED
            presentation_parts.append(f"{problem.description}")
        
        # Add starter code if available
        if problem.starter_code:
            presentation_parts.append("**Starter Code:**")
            presentation_parts.append(f"```python\n{problem.starter_code}\n```")
        
        return "\n\n".join(presentation_parts)
    
    def _enhance_with_style_elements(
        self,
        base_presentation: str,
        problem: Problem,
        style: PresentationStyle,
        context: Dict[str, Any]
    ) -> str:
        """Add style-specific enhancements to the presentation"""
        
        enhanced_parts = [base_presentation]
        
        # Add support elements
        support_elements = context.get("support_elements", [])
        if "step_by_step_guidance" in support_elements:
            enhanced_parts.append("\n**Getting Started:**")
            enhanced_parts.append("1. Read through the problem carefully")
            enhanced_parts.append("2. Identify the key requirements")
            enhanced_parts.append("3. Plan your approach before coding")
        
        if "implementation_hints" in support_elements and problem.hints:
            enhanced_parts.append(f"\n**Available Hints:** {len(problem.hints)} hints available (ask if you need help!)")
        
        # Add challenge elements
        challenge_elements = context.get("challenge_elements", [])
        if "edge_case_handling" in challenge_elements:
            enhanced_parts.append("\n**Challenge Extension:**")
            enhanced_parts.append("Once you have a working solution, consider:")
            enhanced_parts.append("- How would you handle invalid inputs?")
            enhanced_parts.append("- What edge cases might exist?")
        
        return "\n".join(enhanced_parts)
    
    def _add_pedagogical_enhancements(
        self,
        presentation: str,
        problem: Problem,
        style: PresentationStyle,
        learning_profile: Optional[Dict[str, Any]]
    ) -> str:
        """Add pedagogical enhancements based on educational best practices"""
        
        enhanced_parts = [presentation]
        
        # Add motivational elements
        if learning_profile and learning_profile.get("needs_encouragement", False):
            enhanced_parts.append("\n💪 **You've got this!** Take your time and remember that every expert was once a beginner.")
        
        # Add learning objectives if appropriate
        if style in [PresentationStyle.DETAILED, PresentationStyle.SCAFFOLDED]:
            if problem.concepts:
                enhanced_parts.append(f"\n**Learning Objectives:**")
                for concept in problem.concepts:
                    enhanced_parts.append(f"- Master {concept} concepts and application")
        
        # Add success criteria
        enhanced_parts.append("\n**Success Criteria:**")
        enhanced_parts.append("- Your solution solves the problem correctly")
        enhanced_parts.append("- Your code is readable and well-structured")
        enhanced_parts.append("- You understand the concepts involved")
        
        return "\n".join(enhanced_parts)
    
    def _estimate_difficulty_for_student(
        self,
        problem: Problem,
        learning_profile: Optional[Dict[str, Any]]
    ) -> str:
        """Estimate how difficult this problem will be for this specific student"""
        
        base_difficulty = problem.difficulty.lower()
        
        if not learning_profile:
            return base_difficulty
        
        competency = learning_profile.get("estimated_competency", "intermediate")
        mastered_concepts = learning_profile.get("mastered_concepts", [])
        
        # Check how many problem concepts the student has mastered
        problem_concepts = set(problem.concepts)
        mastered_set = set(mastered_concepts)
        mastery_ratio = len(problem_concepts.intersection(mastered_set)) / len(problem_concepts) if problem_concepts else 1.0
        
        # Adjust difficulty based on competency and concept mastery
        if competency == "beginner":
            if mastery_ratio > 0.7:
                return base_difficulty  # Keep as-is
            else:
                # Increase perceived difficulty for beginners with unfamiliar concepts
                difficulty_map = {"easy": "medium", "medium": "hard", "hard": "very hard"}
                return difficulty_map.get(base_difficulty, "hard")
        
        elif competency == "advanced":
            if mastery_ratio > 0.8:
                # Decrease perceived difficulty for advanced students with familiar concepts
                difficulty_map = {"hard": "medium", "medium": "easy", "easy": "very easy"}
                return difficulty_map.get(base_difficulty, "easy")
            else:
                return base_difficulty
        
        return base_difficulty
    
    async def _generate_fallback_presentation(self, problem: Problem, error: str) -> Dict[str, Any]:
        """Generate fallback presentation when main generation fails"""
        
        logger.warning(f"Using fallback problem presentation due to error: {error}")
        
        fallback_presentation = f"""## Problem {problem.number}: {problem.title}

**Difficulty:** {problem.difficulty.title()}

{problem.description}

Let's work through this problem together. I'm here to help guide you through the solution!

"""
        
        if problem.starter_code:
            fallback_presentation += f"**Starter Code:**\n```python\n{problem.starter_code}\n```\n"
        
        fallback_presentation += "\nFeel free to ask questions or submit your code when you're ready!"
        
        return {
            "success": True,
            "presentation": fallback_presentation,
            "problem_id": problem.number,
            "presentation_style": "fallback",
            "fallback": True,
            "error": error,
            "metadata": {
                "presentation_timestamp": datetime.utcnow(),
                "is_fallback": True
            }
        }


# Global instance
structured_problem_presenter = StructuredProblemPresenter()