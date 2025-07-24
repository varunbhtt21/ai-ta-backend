from enum import Enum


class MessageType(str, Enum):
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"


class ContextCompressionLevel(str, Enum):
    FULL_DETAIL = "full_detail"              # Sessions 1-5
    SUMMARIZED_PLUS_RECENT = "summarized_plus_recent"  # Sessions 6-10
    HIGH_LEVEL_SUMMARY = "high_level_summary"  # Sessions 11+


class LearningVelocity(str, Enum):
    FAST = "fast"
    MODERATE = "moderate"  
    SLOW = "slow"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    TERMINATED = "terminated"


class ProblemStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STUCK = "stuck"


class InputType(str, Enum):
    CODE_SUBMISSION = "code_submission"
    QUESTION = "question"
    NEXT_PROBLEM = "next_problem"
    READY_TO_START = "ready_to_start"
    GENERAL_CHAT = "general_chat"


class UserRole(str, Enum):
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


class CompressionReason(str, Enum):
    TOKEN_LIMIT = "token_limit"
    SESSION_COUNT = "session_count"
    MANUAL = "manual"
    PERFORMANCE = "performance"


class TeachingStyle(str, Enum):
    SOCRATIC = "socratic"           # Ask leading questions
    DIRECT = "direct"               # Provide direct answers
    COLLABORATIVE = "collaborative" # Work through problems together
    SUPPORTIVE = "supportive"       # Lots of encouragement
    CHALLENGING = "challenging"     # Push boundaries


class CodeCompetencyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ResumeType(str, Enum):
    FRESH_START = "fresh_start"
    MID_CONVERSATION = "mid_conversation"
    BETWEEN_PROBLEMS = "between_problems"
    COMPLETED_ASSIGNMENT = "completed_assignment"