"""
Shared validation types and enums for the logic validation system
Prevents circular imports between services
"""

from enum import Enum


class LogicValidationLevel(Enum):
    """Multi-level validation system for logic explanations"""
    INITIAL_REQUEST = "initial_request"           # First logic request
    AWAITING_APPROACH = "awaiting_approach"       # Waiting for student's approach
    BASIC_EXPLANATION = "basic_explanation"       # Student provided basic logic
    CROSS_QUESTIONING = "cross_questioning"       # Need more details - ask cross questions
    DETAILED_VALIDATION = "detailed_validation"   # Validate specific implementation details
    EDGE_CASE_TESTING = "edge_case_testing"      # Test understanding of edge cases
    LOGIC_APPROVED = "logic_approved"            # Logic is comprehensive and approved
    GAMING_DETECTED = "gaming_detected"          # Student trying to game the system


class StrictnessLevel(Enum):
    """Escalating strictness levels based on student behavior"""
    LENIENT = 1          # First attempt, encouraging
    MODERATE = 2         # Second attempt, more specific requirements
    STRICT = 3           # Third attempt, detailed cross-questioning
    VERY_STRICT = 4      # Multiple attempts, edge case testing required
    GAMING_MODE = 5      # Gaming detected, maximum strictness