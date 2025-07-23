from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.base import BaseDocument, TimestampMixin, MetadataMixin
from app.models.enums import (
    MessageType, ContextCompressionLevel, LearningVelocity, 
    SessionStatus, ProblemStatus, UserRole, CompressionReason,
    TeachingStyle, CodeCompetencyLevel
)


class ConversationMessage(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_type: MessageType
    content: str
    tokens_used: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class CodeSubmission(BaseModel):
    submission_number: int
    code: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    result: Optional[str] = None
    feedback: Optional[str] = None
    is_correct: Optional[bool] = None


class StudentProgress(BaseModel):
    problem_number: int
    status: ProblemStatus = ProblemStatus.NOT_STARTED
    attempts: int = 0
    hints_used: int = 0
    code_submissions: List[CodeSubmission] = Field(default_factory=list)
    time_spent_minutes: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Problem(BaseModel):
    number: int
    title: str
    description: str
    difficulty: str = "medium"  # easy, medium, hard
    concepts: List[str] = Field(default_factory=list)
    starter_code: Optional[str] = None
    solution_template: Optional[str] = None
    test_cases: List[Dict[str, Any]] = Field(default_factory=list)
    hints: List[str] = Field(default_factory=list)


class Assignment(BaseDocument, MetadataMixin):
    title: str
    description: Optional[str] = None
    curriculum_content: str
    problems: List[Problem] = Field(default_factory=list)
    total_problems: int = 0
    estimated_duration_minutes: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    is_active: bool = True


class LearningProfile(BaseDocument):
    user_id: str
    current_problem: int = 0
    mastered_concepts: List[str] = Field(default_factory=list)
    active_struggles: List[str] = Field(default_factory=list)
    learning_velocity: LearningVelocity = LearningVelocity.MODERATE
    preferred_teaching_style: TeachingStyle = TeachingStyle.COLLABORATIVE
    code_competency: Dict[str, CodeCompetencyLevel] = Field(default_factory=dict)
    session_pattern: Dict[str, Any] = Field(default_factory=dict)
    total_sessions: int = 0
    total_time_spent_minutes: float = 0.0
    average_session_duration_minutes: float = 0.0
    problems_completed: int = 0
    problems_attempted: int = 0
    success_rate: float = 0.0


class CompressedSummary(BaseDocument):
    user_id: str
    sessions_range: str  # "1-5"
    key_learning_milestones: List[str] = Field(default_factory=list)
    persistent_struggles: List[str] = Field(default_factory=list)
    successful_code_patterns: List[str] = Field(default_factory=list)
    teaching_strategies_that_worked: List[str] = Field(default_factory=list)
    total_attempts: int = 0
    problems_completed: int = 0
    problems_attempted: List[int] = Field(default_factory=list)
    compression_metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextMetadata(BaseModel):
    compression_triggered: bool = False
    compression_reason: Optional[CompressionReason] = None
    original_token_count: Optional[int] = None
    compressed_token_count: Optional[int] = None
    compression_timestamp: Optional[datetime] = None
    compression_quality_score: Optional[float] = None


class LearningMetrics(BaseModel):
    problems_attempted: List[int] = Field(default_factory=list)
    problems_completed: List[int] = Field(default_factory=list)
    hints_requested: int = 0
    code_submissions: int = 0
    total_time_active_minutes: float = 0.0
    breakthrough_moments: List[str] = Field(default_factory=list)
    struggle_points: List[str] = Field(default_factory=list)


class User(BaseDocument):
    username: str = Field(..., min_length=3, max_length=50)
    email: str
    full_name: Optional[str] = None
    hashed_password: str
    role: UserRole = UserRole.STUDENT
    is_active: bool = True
    preferences: Dict[str, Any] = Field(default_factory=dict)
    last_login: Optional[datetime] = None