import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging

from app.models import InputType

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    """Result of input classification with confidence and details"""
    input_type: InputType
    confidence: float  # 0.0 to 1.0
    indicators: List[str]  # What patterns led to this classification
    code_detected: bool = False
    question_detected: bool = False
    navigation_detected: bool = False


class InputClassifier:
    """Enhanced input classification system with pattern matching and confidence scoring"""
    
    def __init__(self):
        # Code detection patterns with weights
        self.code_patterns = [
            (r'\bdef\s+\w+\s*\(', 0.9, "function_definition"),
            (r'\bclass\s+\w+', 0.9, "class_definition"),
            (r'\bfor\s+\w+\s+in\s+', 0.8, "for_loop"),
            (r'\bwhile\s+.+:', 0.8, "while_loop"),
            (r'\bif\s+.+:', 0.7, "if_statement"),
            (r'\belif\s+.+:', 0.7, "elif_statement"),
            (r'\belse\s*:', 0.6, "else_statement"),
            (r'\btry\s*:', 0.8, "try_block"),
            (r'\bexcept\s+', 0.8, "except_block"),
            (r'\bfinally\s*:', 0.8, "finally_block"),
            (r'\bwith\s+\w+', 0.7, "with_statement"),
            (r'\breturn\s+', 0.7, "return_statement"),
            (r'\bprint\s*\(', 0.6, "print_function"),
            (r'\bimport\s+\w+', 0.8, "import_statement"),
            (r'\bfrom\s+\w+\s+import', 0.8, "from_import"),
            (r'=\s*\[.*\]', 0.6, "list_assignment"),
            (r'=\s*\{.*\}', 0.6, "dict_assignment"),
            (r'=\s*\(.*\)', 0.5, "tuple_assignment"),
            (r'\.append\s*\(', 0.7, "list_method"),
            (r'\.split\s*\(', 0.6, "string_method"),
            (r'\.join\s*\(', 0.6, "string_method"),
            (r'\blen\s*\(', 0.5, "builtin_function"),
            (r'\brange\s*\(', 0.6, "range_function"),
            (r'```python', 0.9, "code_block_markdown"),
            (r'```\s*\n', 0.7, "code_block_generic"),
            (r'^\s{4,}', 0.4, "indented_code"),  # 4+ spaces indentation
            (r'#.*', 0.3, "python_comment"),
            (r'""".*?"""', 0.6, "docstring"),
            (r"'''.*?'''", 0.6, "docstring"),
        ]
        
        # Question detection patterns
        self.question_patterns = [
            (r'\?', 0.9, "question_mark"),
            (r'\bhow\b', 0.7, "how_question"),
            (r'\bwhat\b', 0.6, "what_question"),
            (r'\bwhy\b', 0.7, "why_question"),
            (r'\bwhen\b', 0.6, "when_question"),
            (r'\bwhere\b', 0.6, "where_question"),
            (r'\bwhich\b', 0.5, "which_question"),
            (r'\bwho\b', 0.5, "who_question"),
            (r'\bcan\s+you', 0.6, "can_you_question"),
            (r'\bwould\s+you', 0.6, "would_you_question"),
            (r'\bcould\s+you', 0.6, "could_you_question"),
            (r'\bhelp\b', 0.7, "help_request"),
            (r'\bexplain\b', 0.8, "explanation_request"),
            (r'\bconfused\b', 0.8, "confusion_indicator"),
            (r'\bdont?\s+understand', 0.9, "understanding_issue"),
            (r'\bstuck\b', 0.8, "stuck_indicator"),
            (r'\berror\b', 0.6, "error_mention"),
            (r'\bissue\b', 0.5, "issue_mention"),
            (r'\bproblem\b', 0.5, "problem_mention"),
        ]
        
        # Navigation/control patterns
        self.navigation_patterns = [
            (r'\bnext\b', 0.8, "next_request"),
            (r'\bmove\s+on\b', 0.9, "move_on_request"),
            (r'\bcontinue\b', 0.7, "continue_request"),
            (r'\bdone\b', 0.6, "done_indicator"),
            (r'\bfinished\b', 0.8, "finished_indicator"),
            (r'\bskip\b', 0.8, "skip_request"),
            (r'\bgo\s+to\b', 0.7, "goto_request"),
            (r'\bback\b', 0.5, "back_request"),
            (r'\breturn\s+to\b', 0.6, "return_request"),
        ]
        
        # Ready/start patterns
        self.ready_patterns = [
            (r'\bready\b', 0.9, "ready_indicator"),
            (r'\bstart\b', 0.8, "start_request"),
            (r'\bbegin\b', 0.8, "begin_request"),
            (r'\blet\'?s\s+go\b', 0.9, "lets_go"),
            (r'\bok\b', 0.4, "ok_response"),
            (r'\byes\b', 0.4, "yes_response"),
            (r'\bi\'?m\s+ready\b', 0.9, "im_ready"),
            (r'\bshow\s+me\b', 0.7, "show_me"),
        ]
        
        # Greeting/social patterns
        self.social_patterns = [
            (r'\bhello\b', 0.8, "greeting"),
            (r'\bhi\b', 0.7, "greeting"),
            (r'\bthanks?\b', 0.6, "thanks"),
            (r'\bthank\s+you\b', 0.8, "thank_you"),
            (r'\bplease\b', 0.3, "polite_request"),
            (r'\bsorry\b', 0.5, "apology"),
        ]
    
    def _apply_patterns(
        self, 
        text: str, 
        patterns: List[Tuple[str, float, str]]
    ) -> Tuple[float, List[str]]:
        """Apply pattern list to text and return total score and matched indicators"""
        
        total_score = 0.0
        indicators = []
        text_lower = text.lower()
        
        for pattern, weight, indicator in patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
            if matches:
                # Multiple matches increase confidence but with diminishing returns
                match_count = len(matches)
                score_contribution = weight * min(match_count * 0.5, 1.0)
                total_score += score_contribution
                indicators.append(f"{indicator}({match_count})")
        
        return total_score, indicators
    
    def _detect_code_quality(self, text: str) -> float:
        """Assess code quality indicators beyond just syntax detection"""
        
        quality_score = 0.0
        
        # Check for proper Python structure
        lines = text.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if len(non_empty_lines) > 1:
            quality_score += 0.2  # Multi-line suggests more complete code
        
        # Check for consistent indentation
        indented_lines = [line for line in lines if line.startswith('    ') or line.startswith('\t')]
        if indented_lines and len(indented_lines) >= len(non_empty_lines) * 0.3:
            quality_score += 0.3  # Good indentation ratio
        
        # Check for variable assignments
        if re.search(r'\w+\s*=\s*', text):
            quality_score += 0.2
        
        # Check for function calls
        if re.search(r'\w+\s*\(', text):
            quality_score += 0.2
        
        # Check for complete functions
        if re.search(r'def\s+\w+.*?:\s*\n', text, re.MULTILINE):
            quality_score += 0.3
        
        return min(quality_score, 1.0)
    
    def classify_input(self, text: str, context: Optional[Dict] = None) -> ClassificationResult:
        """Classify user input with confidence scoring"""
        
        if not text or not text.strip():
            return ClassificationResult(
                input_type=InputType.GENERAL_CHAT,
                confidence=0.5,
                indicators=["empty_input"]
            )
        
        text = text.strip()
        
        # Apply all pattern sets
        code_score, code_indicators = self._apply_patterns(text, self.code_patterns)
        question_score, question_indicators = self._apply_patterns(text, self.question_patterns)
        nav_score, nav_indicators = self._apply_patterns(text, self.navigation_patterns)
        ready_score, ready_indicators = self._apply_patterns(text, self.ready_patterns)
        social_score, social_indicators = self._apply_patterns(text, self.social_patterns)
        
        # Additional code quality assessment
        if code_score > 0:
            code_quality = self._detect_code_quality(text)
            code_score = code_score * 0.7 + code_quality * 0.3
        
        # Context-based adjustments
        if context:
            session_context = context.get('session', {})
            recent_messages = context.get('recent_messages', [])
            
            # If recent conversation was about code, boost code classification
            if recent_messages:
                recent_text = ' '.join([msg.get('content', '') for msg in recent_messages[-3:]])
                if 'code' in recent_text.lower() or 'function' in recent_text.lower():
                    code_score *= 1.2
        
        # Determine primary classification
        scores = {
            InputType.CODE_SUBMISSION: code_score,
            InputType.QUESTION: question_score,
            InputType.NEXT_PROBLEM: nav_score,
            InputType.READY_TO_START: ready_score,
            InputType.GENERAL_CHAT: social_score + 0.1  # Slight baseline for general chat
        }
        
        # Find highest scoring type
        primary_type = max(scores, key=scores.get)
        primary_score = scores[primary_type]
        
        # Normalize confidence to 0-1 range
        confidence = min(primary_score / 2.0, 1.0)  # Divide by 2 since scores can exceed 1
        
        # If confidence is too low, default to general chat
        if confidence < 0.3:
            primary_type = InputType.GENERAL_CHAT
            confidence = 0.5
        
        # Collect all relevant indicators
        all_indicators = []
        if code_indicators:
            all_indicators.extend([f"code:{ind}" for ind in code_indicators])
        if question_indicators:
            all_indicators.extend([f"question:{ind}" for ind in question_indicators])
        if nav_indicators:
            all_indicators.extend([f"nav:{ind}" for ind in nav_indicators])
        if ready_indicators:
            all_indicators.extend([f"ready:{ind}" for ind in ready_indicators])
        if social_indicators:
            all_indicators.extend([f"social:{ind}" for ind in social_indicators])
        
        return ClassificationResult(
            input_type=primary_type,
            confidence=confidence,
            indicators=all_indicators[:10],  # Limit to prevent overflow
            code_detected=code_score > 0.3,
            question_detected=question_score > 0.3,
            navigation_detected=nav_score > 0.3
        )
    
    def get_classification_explanation(self, result: ClassificationResult) -> str:
        """Get human-readable explanation of classification"""
        
        explanations = {
            InputType.CODE_SUBMISSION: "Detected as code submission due to programming syntax and structure",
            InputType.QUESTION: "Detected as question due to question words and help-seeking patterns",
            InputType.NEXT_PROBLEM: "Detected as navigation request to move forward",
            InputType.READY_TO_START: "Detected as readiness signal to begin or continue",
            InputType.GENERAL_CHAT: "Classified as general conversation"
        }
        
        base_explanation = explanations.get(result.input_type, "Unknown classification")
        
        if result.indicators:
            main_indicators = [ind.split(':')[-1] for ind in result.indicators[:3]]
            base_explanation += f" (key indicators: {', '.join(main_indicators)})"
        
        return base_explanation
    
    def analyze_input_patterns(self, inputs: List[str]) -> Dict[str, Any]:
        """Analyze patterns across multiple inputs for insights"""
        
        classifications = [self.classify_input(inp) for inp in inputs]
        
        type_counts = {}
        confidence_sum = 0.0
        indicator_frequency = {}
        
        for result in classifications:
            # Count types
            type_name = result.input_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
            
            # Sum confidence
            confidence_sum += result.confidence
            
            # Count indicators
            for indicator in result.indicators:
                indicator_frequency[indicator] = indicator_frequency.get(indicator, 0) + 1
        
        # Find most common indicators
        top_indicators = sorted(indicator_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "total_inputs": len(inputs),
            "type_distribution": type_counts,
            "average_confidence": confidence_sum / len(classifications) if classifications else 0,
            "most_common_indicators": top_indicators,
            "classification_accuracy": confidence_sum / len(classifications) if classifications else 0
        }


# Global instance
input_classifier = InputClassifier()