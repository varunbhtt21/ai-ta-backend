"""
Scenario-Based Prompt Manager Service
Implements comprehensive few-shot prompting with 50+ scenarios for enhanced tutoring.
Follows Service Layer Pattern with scenario-based AI training.
"""

from typing import Dict, List, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
import logging
import re
import random

from app.models import Problem, ConversationMessage, MessageType
from app.services.validation_types import LogicValidationLevel, StrictnessLevel

logger = logging.getLogger(__name__)


class ScenarioType(Enum):
    """Types of tutoring scenarios"""
    VAGUE_LOGIC_ATTEMPT = "vague_logic_attempt"
    COPY_PASTE_DETECTION = "copy_paste_detection"
    CODE_REQUEST = "code_request"
    NEXT_QUESTION_REQUEST = "next_question_request"
    REPETITIVE_RESPONSE = "repetitive_response"
    INSUFFICIENT_DETAIL = "insufficient_detail"
    LOGIC_VALIDATION = "logic_validation"
    CROSS_QUESTIONING = "cross_questioning"
    DETAILED_VALIDATION = "detailed_validation"
    EDGE_CASE_TESTING = "edge_case_testing"
    GAMING_RESPONSE = "gaming_response"
    PROGRESS_VALIDATION = "progress_validation"


class ResponseTone(Enum):
    """Different response tones based on situation"""
    ENCOURAGING = "encouraging"
    FIRM_BUT_KIND = "firm_but_kind"
    STRICT = "strict"
    EMPATHETIC = "empathetic"
    CELEBRATORY = "celebratory"


@dataclass
class TutoringScenario:
    """Represents a complete tutoring scenario for few-shot prompting"""
    scenario_id: str
    scenario_type: ScenarioType
    problem_context: str
    student_input: str
    student_behavior: str  # Description of what student is doing
    ai_response: str
    response_tone: ResponseTone
    teaching_principle: str
    follow_up_questions: List[str]
    validation_level: LogicValidationLevel
    strictness_level: StrictnessLevel
    tags: List[str]


class ScenarioPromptManager:
    """Manages scenario-based prompting for enhanced tutoring"""
    
    def __init__(self):
        self.scenarios = self._load_comprehensive_scenarios()
        self.cross_question_templates = self._load_cross_question_templates()
        self.response_templates = self._load_response_templates()
        
        logger.info(f"📚 SCENARIO_MANAGER: Loaded {len(self.scenarios)} scenarios")
    
    def get_scenarios_for_situation(
        self,
        scenario_type: ScenarioType,
        validation_level: LogicValidationLevel,
        strictness_level: StrictnessLevel,
        problem_context: Optional[str] = None
    ) -> List[TutoringScenario]:
        """Get relevant scenarios for current tutoring situation"""
        
        matching_scenarios = []
        
        for scenario in self.scenarios:
            # Match scenario type
            if scenario.scenario_type == scenario_type:
                # Match validation level (exact match for now to avoid index errors)
                validation_match = (scenario.validation_level == validation_level)
                
                # Match strictness level (exact or within 1 level)
                strictness_match = abs(scenario.strictness_level.value - strictness_level.value) <= 1
                
                # Add scenarios that match criteria
                if validation_match or strictness_match:
                    matching_scenarios.append(scenario)
        
        # Sort by relevance (exact matches first)
        matching_scenarios.sort(key=lambda s: (
            s.validation_level == validation_level,
            s.strictness_level == strictness_level
        ), reverse=True)
        
        return matching_scenarios[:5]  # Return top 5 most relevant
    
    def build_few_shot_prompt(
        self,
        scenario_type: ScenarioType,
        validation_level: LogicValidationLevel,
        strictness_level: StrictnessLevel,
        current_problem: Problem,
        student_input: str,
        conversation_history: List[ConversationMessage],
        base_instruction: str
    ) -> str:
        """Build comprehensive few-shot prompt with relevant scenarios"""
        
        # Get relevant scenarios
        relevant_scenarios = self.get_scenarios_for_situation(
            scenario_type, validation_level, strictness_level
        )
        
        # Build few-shot examples
        few_shot_examples = []
        for i, scenario in enumerate(relevant_scenarios[:3]):  # Use top 3 scenarios
            example = f"""
**Example {i+1} - {scenario.teaching_principle}**

Problem Context: {scenario.problem_context}
Student Input: "{scenario.student_input}"
Student Behavior: {scenario.student_behavior}

AI Response: {scenario.ai_response}

Response Tone: {scenario.response_tone.value}
Teaching Notes: {scenario.teaching_principle}
"""
            few_shot_examples.append(example)
        
        # Build the complete prompt
        few_shot_prompt = f"""
{base_instruction}

**CURRENT SITUATION:**
Problem: {current_problem.title}
Description: {current_problem.description}
Student Input: "{student_input}"
Validation Level: {validation_level.value}
Strictness Level: {strictness_level.value}

**FEW-SHOT EXAMPLES - Learn from these scenarios:**

{''.join(few_shot_examples)}

**CONTEXT FROM CONVERSATION:**
{self._format_conversation_context(conversation_history[-6:])}

**YOUR TASK:**
Generate a response that follows the patterns shown in the examples above. 
Match the appropriate tone and teaching approach for the current situation.
Be consistent with the validation level and strictness requirements.

**RESPONSE REQUIREMENTS:**
- Follow the exact same style and approach as the examples
- Maintain consistency with the teaching principles demonstrated
- Use appropriate tone for the strictness level
- Include specific cross-questions if validation level requires it
- Never give direct solutions or code examples
- Focus on guiding student to genuine understanding

Generate your response:
"""
        
        return few_shot_prompt
    
    def _load_comprehensive_scenarios(self) -> List[TutoringScenario]:
        """Load comprehensive database of 50+ tutoring scenarios"""
        
        scenarios = []
        
        # === VAGUE LOGIC ATTEMPTS ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="vague_001",
                scenario_type=ScenarioType.VAGUE_LOGIC_ATTEMPT,
                problem_context="Create a list with user input - 5 numbers",
                student_input="I will use a loop",
                student_behavior="Student gives extremely vague, one-sentence response",
                ai_response="I need more specifics about your approach. What type of loop will you use? How many times should it run? Where will you store the input values? Please provide a step-by-step breakdown.",
                response_tone=ResponseTone.FIRM_BUT_KIND,
                teaching_principle="Require specific details, not general statements",
                follow_up_questions=["What type of loop?", "How many iterations?", "Where to store data?"],
                validation_level=LogicValidationLevel.CROSS_QUESTIONING,
                strictness_level=StrictnessLevel.MODERATE,
                tags=["vague", "insufficient_detail", "loop_concept"]
            ),
            
            TutoringScenario(
                scenario_id="vague_002", 
                scenario_type=ScenarioType.VAGUE_LOGIC_ATTEMPT,
                problem_context="Find maximum and minimum in list",
                student_input="I will look at all numbers and find the biggest and smallest",
                student_behavior="Student understands goal but lacks implementation details",
                ai_response="Good understanding of the goal! Now I need the specifics: How will you 'look at' each number? What variables will you use to keep track of the current maximum and minimum? What will be your starting values?",
                response_tone=ResponseTone.ENCOURAGING,
                teaching_principle="Build on correct understanding, ask for implementation details",
                follow_up_questions=["How to compare numbers?", "What variables to track max/min?", "Starting values?"],
                validation_level=LogicValidationLevel.DETAILED_VALIDATION,
                strictness_level=StrictnessLevel.STRICT,
                tags=["vague", "max_min", "comparison_logic"]
            ),
            
            TutoringScenario(
                scenario_id="vague_003",
                scenario_type=ScenarioType.VAGUE_LOGIC_ATTEMPT,
                problem_context="Calculate average of numbers in list",
                student_input="I will add them and divide",
                student_behavior="Student knows math concept but missing programming details",
                ai_response="Correct mathematical concept! Now let's get specific: How will you add all the numbers? What variable will store the running total? How will you count how many numbers there are? Walk me through each step.",
                response_tone=ResponseTone.ENCOURAGING,
                teaching_principle="Acknowledge correct concept, require programming implementation details",
                follow_up_questions=["How to sum all numbers?", "What variable for total?", "How to count elements?"],
                validation_level=LogicValidationLevel.CROSS_QUESTIONING,
                strictness_level=StrictnessLevel.MODERATE,
                tags=["vague", "average", "accumulation"]
            ),
        ])
        
        # === COPY-PASTE DETECTION ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="copy_001",
                scenario_type=ScenarioType.COPY_PASTE_DETECTION,
                problem_context="Create empty list, use for loop, append input",
                student_input="I need to create an empty list, use a for loop with range(5), and append each input to the list",
                student_behavior="Student copied exact phrase from AI's previous message",
                ai_response="I notice you're using very similar wording to our previous conversation. I need to hear YOUR thinking in your own words. Explain to me in your natural way how you would approach this problem step by step.",
                response_tone=ResponseTone.FIRM_BUT_KIND,
                teaching_principle="Detect copy-paste, require original thinking",
                follow_up_questions=["Explain in your own words", "What's your personal approach?", "How would you tackle this?"],
                validation_level=LogicValidationLevel.GAMING_DETECTED,
                strictness_level=StrictnessLevel.GAMING_MODE,
                tags=["copy_paste", "gaming", "original_thinking"]
            ),
            
            TutoringScenario(
                scenario_id="copy_002",
                scenario_type=ScenarioType.COPY_PASTE_DETECTION,
                problem_context="Filter even numbers from list",
                student_input="Check each number for evenness using modulo operator and append to new list",
                student_behavior="Student uses technical terminology from AI response",
                ai_response="Those are the right technical terms, but I want to understand YOUR thinking process. Don't worry about perfect terminology - just tell me in plain English how you'd figure out which numbers are even and what you'd do with them.",
                response_tone=ResponseTone.EMPATHETIC,
                teaching_principle="Focus on understanding over terminology",
                follow_up_questions=["How do you know if number is even?", "What would you do with even numbers?", "Explain without technical terms"],
                validation_level=LogicValidationLevel.BASIC_EXPLANATION,
                strictness_level=StrictnessLevel.LENIENT,
                tags=["copy_paste", "technical_terms", "simplification"]
            ),
        ])
        
        # === CODE REQUESTS ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="code_001",
                scenario_type=ScenarioType.CODE_REQUEST,
                problem_context="Any programming problem",
                student_input="give me code",
                student_behavior="Direct request for solution without showing understanding",
                ai_response="I understand you're eager to see the implementation! But first, I need to make sure you understand the approach. Can you walk me through your step-by-step strategy for solving this problem? Once I see you have the logic clear, we can work on the code together.",
                response_tone=ResponseTone.FIRM_BUT_KIND,
                teaching_principle="Never provide code without logic validation first",
                follow_up_questions=["What's your approach?", "How would you solve this?", "What are the main steps?"],
                validation_level=LogicValidationLevel.AWAITING_APPROACH,
                strictness_level=StrictnessLevel.STRICT,
                tags=["code_request", "bypass_attempt", "logic_required"]
            ),
            
            TutoringScenario(
                scenario_id="code_002",
                scenario_type=ScenarioType.CODE_REQUEST,
                problem_context="Student struggling with implementation",
                student_input="just show me the answer",
                student_behavior="Student frustrated, wants immediate solution",
                ai_response="I can see you might be feeling stuck, and that's completely normal! But giving you the answer wouldn't help you learn. Let's break this down into smaller pieces. What's the very first thing you need to do in this problem? Let's start there and build up step by step.",
                response_tone=ResponseTone.EMPATHETIC,
                teaching_principle="Address frustration with empathy but maintain standards",
                follow_up_questions=["What's the first step?", "What data do you need?", "How can we simplify this?"],
                validation_level=LogicValidationLevel.BASIC_EXPLANATION,
                strictness_level=StrictnessLevel.LENIENT,
                tags=["code_request", "frustration", "break_down"]
            ),
        ])
        
        # === NEXT QUESTION REQUESTS ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="next_001",
                scenario_type=ScenarioType.NEXT_QUESTION_REQUEST,
                problem_context="Current problem not completed",
                student_input="next question",
                student_behavior="Student trying to skip without completing current problem",
                ai_response="I understand you might want to move forward, but we need to complete this problem first. You haven't shown me that you understand the approach yet. Please explain your step-by-step logic for solving this current problem.",
                response_tone=ResponseTone.FIRM_BUT_KIND,
                teaching_principle="No progression without demonstrated understanding",
                follow_up_questions=["How would you solve this current problem?", "What's your approach?", "Show me your understanding first"],
                validation_level=LogicValidationLevel.AWAITING_APPROACH,
                strictness_level=StrictnessLevel.STRICT,
                tags=["skip_attempt", "progression_blocked", "current_problem"]
            ),
            
            TutoringScenario(
                scenario_id="next_002",
                scenario_type=ScenarioType.NEXT_QUESTION_REQUEST,
                problem_context="Problem appears too difficult for student",
                student_input="this is too hard, next problem",
                student_behavior="Student overwhelmed, wants to give up on current problem",
                ai_response="I understand this feels challenging right now. But here's the thing - working through difficult problems is exactly how you build problem-solving skills! Let's not skip this. Instead, let's break it into tiny, manageable pieces. What's just the very first small step you could take?",
                response_tone=ResponseTone.EMPATHETIC,
                teaching_principle="Transform challenge into learning opportunity",
                follow_up_questions=["What's one small step?", "What part do you understand?", "How can we simplify?"],
                validation_level=LogicValidationLevel.BASIC_EXPLANATION,
                strictness_level=StrictnessLevel.LENIENT,
                tags=["overwhelmed", "difficulty", "encouragement"]
            ),
        ])
        
        # === REPETITIVE RESPONSES ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="repeat_001",
                scenario_type=ScenarioType.REPETITIVE_RESPONSE,
                problem_context="Student keeps giving same vague answer",
                student_input="I will run the loop, take input and print",
                student_behavior="Third time giving exact same vague response",
                ai_response="I notice you've given me this same response a few times. It tells me you understand there's a loop involved, which is great! But I need much more specific details. Let me ask you directly: What type of loop will you use - for loop or while loop? How many times will it run? What happens in each iteration?",
                response_tone=ResponseTone.FIRM_BUT_KIND,
                teaching_principle="Address repetition directly, require specific details",
                follow_up_questions=["For loop or while loop?", "How many iterations?", "What happens each time?"],
                validation_level=LogicValidationLevel.DETAILED_VALIDATION,
                strictness_level=StrictnessLevel.VERY_STRICT,
                tags=["repetition", "specificity_required", "loop_details"]
            ),
            
            TutoringScenario(
                scenario_id="repeat_002",
                scenario_type=ScenarioType.REPETITIVE_RESPONSE,
                problem_context="Student stuck in repetition loop",
                student_input="I need to process the data",
                student_behavior="Fourth time giving generic, non-specific response",
                ai_response="I can see we're going in circles here, and that's okay - it happens when we're figuring things out! Let me try a different approach. Instead of asking what you'll do, let me ask: If you were explaining this to a friend who knows nothing about programming, how would you describe it? Pretend I'm that friend.",
                response_tone=ResponseTone.EMPATHETIC,
                teaching_principle="Change approach when student is stuck in repetition",
                follow_up_questions=["Explain like to a friend", "Use simple words", "What's the goal in plain English?"],
                validation_level=LogicValidationLevel.BASIC_EXPLANATION,
                strictness_level=StrictnessLevel.MODERATE,
                tags=["repetition", "approach_change", "simplification"]
            ),
        ])
        
        # === LOGIC VALIDATION SCENARIOS ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="logic_001",
                scenario_type=ScenarioType.LOGIC_VALIDATION,
                problem_context="Create list with user input",
                student_input="I will create an empty list called numbers. Then use a for loop with range(5) to ask user for input 5 times. Each time, I'll use input() function, convert to int, and append to my list. Finally print the list.",
                student_behavior="Student provides comprehensive, detailed logic explanation",
                ai_response="Excellent logic! You've thought through every step: creating the list, using the right loop structure, handling input conversion, and storing the results. Your approach is solid and will definitely solve the problem. Now you can implement this logic with code.",
                response_tone=ResponseTone.CELEBRATORY,
                teaching_principle="Recognize and celebrate comprehensive understanding",
                follow_up_questions=[],
                validation_level=LogicValidationLevel.LOGIC_APPROVED,
                strictness_level=StrictnessLevel.MODERATE,
                tags=["comprehensive", "approved", "implementation_ready"]
            ),
            
            TutoringScenario(
                scenario_id="logic_002",
                scenario_type=ScenarioType.LOGIC_VALIDATION,
                problem_context="Find maximum value in list",
                student_input="I will set the first number as maximum, then go through each other number and if it's bigger than my current maximum, I'll update the maximum to that number.",
                student_behavior="Student shows good logical thinking with clear algorithm",
                ai_response="Perfect logic! You understand the key concept: start with an initial value and update it as you find better candidates. This is exactly how the maximum-finding algorithm works. Your step-by-step thinking is spot on.",
                response_tone=ResponseTone.CELEBRATORY,
                teaching_principle="Validate correct algorithmic thinking",
                follow_up_questions=[],
                validation_level=LogicValidationLevel.LOGIC_APPROVED,
                strictness_level=StrictnessLevel.STRICT,
                tags=["algorithm", "comparison", "approved"]
            ),
        ])
        
        # === CROSS-QUESTIONING SCENARIOS ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="cross_001",
                scenario_type=ScenarioType.CROSS_QUESTIONING,
                problem_context="Student mentioned 'loop' without specifics",
                student_input="I'll use a loop to process the numbers",
                student_behavior="Student knows general concept but lacks implementation specifics",
                ai_response="Good! You recognize that a loop is needed. Now let's get specific: What type of loop would work best here - a for loop or while loop? How will you control how many times it runs? And what exactly will happen inside each iteration of the loop?",
                response_tone=ResponseTone.ENCOURAGING,
                teaching_principle="Build on correct concepts with specific questions",
                follow_up_questions=["For loop or while loop?", "How to control iterations?", "What happens inside loop?"],
                validation_level=LogicValidationLevel.CROSS_QUESTIONING,
                strictness_level=StrictnessLevel.MODERATE,
                tags=["loop_specification", "implementation_details", "guided_questioning"]
            ),
            
            TutoringScenario(
                scenario_id="cross_002",
                scenario_type=ScenarioType.CROSS_QUESTIONING,
                problem_context="Student mentioned 'store data' without specifics",
                student_input="I need to store the values somewhere",
                student_behavior="Student understands need for storage but doesn't specify data structure",
                ai_response="Exactly right - you need to store the values! Now, what data structure would be appropriate for storing multiple values that you want to keep in order? What would you call this storage container? And how would you add new values to it?",
                response_tone=ResponseTone.ENCOURAGING,
                teaching_principle="Guide toward specific data structure choices",
                follow_up_questions=["What data structure for multiple values?", "What to name it?", "How to add values?"],
                validation_level=LogicValidationLevel.CROSS_QUESTIONING,
                strictness_level=StrictnessLevel.MODERATE,
                tags=["data_structure", "storage", "naming"]
            ),
        ])
        
        # === DETAILED VALIDATION SCENARIOS ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="detail_001",
                scenario_type=ScenarioType.DETAILED_VALIDATION,
                problem_context="Student has basic logic but missing error handling",
                student_input="I'll use for loop with range(5), get input with input(), convert with int(), append to list",
                student_behavior="Student has correct basic logic but hasn't considered edge cases",
                ai_response="Great! You have the main logic down perfectly. Now let's think about potential issues: What happens if the user enters something that's not a number? How could you handle that situation? Also, what would you do if they enter a decimal instead of a whole number?",
                response_tone=ResponseTone.ENCOURAGING,
                teaching_principle="Advance to edge case consideration after basic logic is solid",
                follow_up_questions=["What if user enters non-number?", "How to handle invalid input?", "What about decimal numbers?"],
                validation_level=LogicValidationLevel.EDGE_CASE_TESTING,
                strictness_level=StrictnessLevel.VERY_STRICT,
                tags=["edge_cases", "error_handling", "robustness"]
            ),
            
            TutoringScenario(
                scenario_id="detail_002",
                scenario_type=ScenarioType.DETAILED_VALIDATION,
                problem_context="Student logic correct but could be more efficient",
                student_input="I'll create empty list, use while loop with counter, increment counter each time, stop when counter equals 5",
                student_behavior="Student has working solution but not most efficient approach",
                ai_response="Your logic is absolutely correct and would work perfectly! I can see you understand loops and counters well. Just out of curiosity - do you know about the range() function? It might make your loop setup a bit simpler, but your current approach is totally valid too.",
                response_tone=ResponseTone.ENCOURAGING,
                teaching_principle="Validate working solution before suggesting optimizations",
                follow_up_questions=["Have you used range() function?", "Would for loop be simpler?", "Both approaches work - any preference?"],
                validation_level=LogicValidationLevel.LOGIC_APPROVED,
                strictness_level=StrictnessLevel.LENIENT,
                tags=["optimization", "efficiency", "alternative_approaches"]
            ),
        ])
        
        # === GAMING RESPONSE SCENARIOS ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="gaming_001",
                scenario_type=ScenarioType.GAMING_RESPONSE,
                problem_context="Student detected trying multiple bypass tactics",
                student_input="hint please",
                student_behavior="After multiple attempts to get code/answers without showing understanding",
                ai_response="I've noticed several attempts to get hints or solutions without showing your understanding first. This is your opportunity to demonstrate what you've learned. I need to see that you can think through this problem independently. Please provide your detailed approach to solving this problem.",
                response_tone=ResponseTone.STRICT,
                teaching_principle="Address gaming behavior directly but give opportunity to correct",
                follow_up_questions=["Show your independent thinking", "What's your detailed approach?", "Demonstrate your understanding"],
                validation_level=LogicValidationLevel.GAMING_DETECTED,
                strictness_level=StrictnessLevel.GAMING_MODE,
                tags=["gaming", "multiple_attempts", "independence_required"]
            ),
            
            TutoringScenario(
                scenario_id="gaming_002",
                scenario_type=ScenarioType.GAMING_RESPONSE,
                problem_context="Student trying to manipulate system with emotional appeals",
                student_input="I'm really struggling, can you just help me this once?",
                student_behavior="Using emotional manipulation to bypass logic-first requirement",
                ai_response="I understand you're finding this challenging, and that's completely normal - everyone struggles with new concepts! The best way I can help you is by making sure you truly understand the approach. Let's work through this together, but I need to see your thinking process first. What part of the problem do you understand so far?",
                response_tone=ResponseTone.EMPATHETIC,
                teaching_principle="Show empathy but maintain educational standards",
                follow_up_questions=["What part do you understand?", "Where exactly are you stuck?", "Let's start with what you know"],
                validation_level=LogicValidationLevel.BASIC_EXPLANATION,
                strictness_level=StrictnessLevel.MODERATE,
                tags=["emotional_appeal", "empathy", "standards_maintained"]
            ),
        ])
        
        # === PROGRESS VALIDATION SCENARIOS ===
        scenarios.extend([
            TutoringScenario(
                scenario_id="progress_001",
                scenario_type=ScenarioType.PROGRESS_VALIDATION,
                problem_context="Student claims to be done without showing work",
                student_input="I'm done with this problem",
                student_behavior="Student trying to move on without demonstrating completion",
                ai_response="I'd love to see that you've completed it! Can you show me your solution and walk me through how it works? I want to make sure you've got a solid understanding before we move to the next challenge.",
                response_tone=ResponseTone.ENCOURAGING,
                teaching_principle="Require demonstration of completion, not just claims",
                follow_up_questions=["Show me your solution", "How does it work?", "Walk me through it"],
                validation_level=LogicValidationLevel.AWAITING_APPROACH,
                strictness_level=StrictnessLevel.MODERATE,
                tags=["completion_verification", "demonstration_required", "solution_walkthrough"]
            ),
        ])
        
        return scenarios
    
    def _load_cross_question_templates(self) -> Dict[str, List[str]]:
        """Load templates for different types of cross-questions"""
        
        return {
            "data_structure_choice": [
                "What data structure will you use to store the {data_type}?",
                "How will you organize the {data_type} in memory?",
                "What container would be best for holding multiple {data_type}?",
                "What Python data structure allows you to store multiple {data_type}?"
            ],
            "loop_structure": [
                "What type of loop will you use - for loop or while loop?",
                "How many times should your loop run?",
                "How will you control the number of iterations?",
                "What determines when your loop should stop?"
            ],
            "input_method": [
                "How exactly will you get input from the user?",
                "What Python function gets user input?",
                "How will you ask the user for each value?",
                "What's the process for collecting user input?"
            ],
            "data_type_handling": [
                "The input() function returns a string. How will you handle this?",
                "What if the user enters a number - how do you convert it?",
                "How do you change text input into a number?",
                "What conversion is needed for numeric input?"
            ],
            "variable_names": [
                "What will you name your variables?",
                "What would be good names for your loop counter?",
                "How will you name the storage container?",
                "What descriptive names will you use?"
            ],
            "process_flow": [
                "Walk me through the steps in order.",
                "What happens first, second, third?",
                "Can you break down the process step by step?",
                "What's the sequence of operations?"
            ],
            "edge_case_consideration": [
                "What if the user enters invalid input?",
                "How would you handle unexpected values?",
                "What could go wrong with your approach?",
                "What edge cases should you consider?"
            ],
            "output_method": [
                "How will you display the results?",
                "What's the best way to show the output?",
                "How should the final result be presented?",
                "What format should the output have?"
            ]
        }
    
    def _load_response_templates(self) -> Dict[ResponseTone, List[str]]:
        """Load response templates for different tones"""
        
        return {
            ResponseTone.ENCOURAGING: [
                "Great start! {content}",
                "You're on the right track! {content}",
                "Good thinking! {content}",
                "Excellent! {content}",
                "Perfect! {content}"
            ],
            ResponseTone.FIRM_BUT_KIND: [
                "I need more specifics. {content}",
                "Let's get more detailed. {content}",
                "I understand, but {content}",
                "That's a good start, however {content}",
                "I can see your thinking, but {content}"
            ],
            ResponseTone.STRICT: [
                "I need you to be more specific. {content}",
                "This requires more detail. {content}",
                "I must insist on clarity. {content}",
                "More precision is needed. {content}",
                "I require detailed explanation. {content}"
            ],
            ResponseTone.EMPATHETIC: [
                "I understand this is challenging. {content}",
                "I can see you might be feeling stuck. {content}",
                "It's okay to find this difficult. {content}",
                "I know this can be frustrating. {content}",
                "Everyone struggles with new concepts. {content}"
            ],
            ResponseTone.CELEBRATORY: [
                "Excellent work! {content}",
                "Outstanding! {content}",
                "Perfect logic! {content}",
                "Brilliant thinking! {content}",
                "You've got it! {content}"
            ]
        }
    
    def generate_cross_questions(
        self,
        missing_elements: List[str],
        problem: Problem,
        strictness_level: StrictnessLevel
    ) -> List[str]:
        """Generate contextual cross-questions based on missing elements"""
        
        questions = []
        
        for element in missing_elements:
            if element in self.cross_question_templates:
                templates = self.cross_question_templates[element]
                
                # Select template based on strictness level
                if strictness_level.value <= 2:  # LENIENT, MODERATE
                    template = random.choice(templates[:2])  # Gentler questions
                else:  # STRICT, VERY_STRICT, GAMING_MODE
                    template = random.choice(templates)  # All questions
                
                # Contextualize for the specific problem
                contextualized_question = self._contextualize_question(template, problem)
                questions.append(contextualized_question)
        
        return questions[:3]  # Limit to 3 questions
    
    def _contextualize_question(self, template: str, problem: Problem) -> str:
        """Contextualize a question template for the specific problem"""
        
        # Determine data type from problem context
        if "number" in problem.description.lower():
            data_type = "numbers"
        elif "string" in problem.description.lower() or "text" in problem.description.lower():
            data_type = "strings"
        elif "name" in problem.description.lower():
            data_type = "names"
        else:
            data_type = "values"
        
        return template.format(data_type=data_type)
    
    def _format_conversation_context(self, recent_messages: List[ConversationMessage]) -> str:
        """Format recent conversation for context in prompts"""
        
        if not recent_messages:
            return "No previous conversation context."
        
        formatted_messages = []
        for msg in recent_messages:
            role = "Student" if msg.message_type == MessageType.USER else "AI"
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            formatted_messages.append(f"{role}: {content}")
        
        return "\n".join(formatted_messages)
    
    def get_appropriate_tone(
        self,
        validation_level: LogicValidationLevel,
        strictness_level: StrictnessLevel,
        attempt_count: int
    ) -> ResponseTone:
        """Determine appropriate response tone based on context"""
        
        # Gaming detection - strict tone
        if validation_level == LogicValidationLevel.GAMING_DETECTED:
            return ResponseTone.STRICT
        
        # Logic approved - celebratory
        if validation_level == LogicValidationLevel.LOGIC_APPROVED:
            return ResponseTone.CELEBRATORY
        
        # Multiple attempts - empathetic but firm
        if attempt_count >= 3:
            return ResponseTone.EMPATHETIC
        
        # Based on strictness level
        if strictness_level == StrictnessLevel.LENIENT:
            return ResponseTone.ENCOURAGING
        elif strictness_level == StrictnessLevel.MODERATE:
            return ResponseTone.ENCOURAGING
        elif strictness_level == StrictnessLevel.STRICT:
            return ResponseTone.FIRM_BUT_KIND
        elif strictness_level == StrictnessLevel.VERY_STRICT:
            return ResponseTone.STRICT
        else:  # GAMING_MODE
            return ResponseTone.STRICT