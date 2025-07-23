from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.models.base import BaseDocument
from app.models.enums import SessionStatus, ContextCompressionLevel, InputType
from app.models.core import ContextMetadata, LearningMetrics, ConversationMessage


class Session(BaseDocument):
    user_id: str
    assignment_id: str
    session_number: int
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    status: SessionStatus = SessionStatus.ACTIVE
    compression_level: ContextCompressionLevel = ContextCompressionLevel.FULL_DETAIL
    total_tokens: int = 0
    total_messages: int = 0
    current_problem: int = 0
    context_metadata: ContextMetadata = Field(default_factory=ContextMetadata)
    learning_metrics: LearningMetrics = Field(default_factory=LearningMetrics)
    session_notes: Optional[str] = None


class ConversationDocument(BaseDocument):
    session_id: str
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_type: str  # MessageType as string for MongoDB
    content: str
    tokens_used: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    archived: bool = False
    input_type: Optional[InputType] = None


class StudentProgressDocument(BaseDocument):
    user_id: str
    assignment_id: str
    session_id: str
    problem_number: int
    status: str  # ProblemStatus as string
    attempts: int = 0
    hints_used: int = 0
    time_spent_minutes: float = 0.0
    code_submissions: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    final_solution: Optional[str] = None


class SessionContext(BaseModel):
    session: Session
    recent_messages: List[ConversationMessage] = Field(default_factory=list)
    compressed_summary: Optional[str] = None
    current_problem_data: Optional[Dict[str, Any]] = None
    learning_profile_data: Optional[Dict[str, Any]] = None
    total_context_tokens: int = 0
    compression_metadata: Optional[Dict[str, Any]] = None


class SessionRequest(BaseModel):
    assignment_id: str
    resume_session: bool = False
    session_id: Optional[str] = None


class MessageRequest(BaseModel):
    content: str
    message_type: Optional[str] = "user"


class SessionResponse(BaseModel):
    session_id: str
    status: str
    message: Optional[str] = None
    current_problem: Optional[int] = None
    total_problems: Optional[int] = None
    session_number: int
    compression_level: str