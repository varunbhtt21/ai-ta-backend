from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database.connection import get_database
from app.models import (
    Session, SessionStatus, ContextCompressionLevel, 
    SessionRequest, SessionResponse, MessageRequest,
    ConversationDocument, StudentProgressDocument
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class SessionService:
    def __init__(self):
        self.db = None
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    async def create_session(self, user_id: str, assignment_id: str) -> Session:
        """Create a new tutoring session"""
        db = await self._get_db()
        
        # Get user's session count for this assignment
        session_count = await db.sessions.count_documents({
            "user_id": user_id,
            "assignment_id": assignment_id
        })
        
        # Determine compression level based on session count
        if session_count < 5:
            compression_level = ContextCompressionLevel.FULL_DETAIL
        elif session_count < 10:
            compression_level = ContextCompressionLevel.SUMMARIZED_PLUS_RECENT
        else:
            compression_level = ContextCompressionLevel.HIGH_LEVEL_SUMMARY
        
        # Create new session
        session = Session(
            user_id=user_id,
            assignment_id=assignment_id,
            session_number=session_count + 1,
            compression_level=compression_level,
            status=SessionStatus.ACTIVE
        )
        
        # Save to database
        result = await db.sessions.insert_one(session.dict(by_alias=True))
        session.id = result.inserted_id
        
        logger.info(f"Created session {result.inserted_id} for user {user_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve session by ID"""
        db = await self._get_db()
        
        session_data = await db.sessions.find_one({"_id": ObjectId(session_id)})
        if not session_data:
            return None
        
        return Session.model_validate(session_data)
    
    async def get_active_session(self, user_id: str, assignment_id: str) -> Optional[Session]:
        """Get user's active session for an assignment"""
        db = await self._get_db()
        
        session_data = await db.sessions.find_one({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "status": SessionStatus.ACTIVE
        })
        
        if not session_data:
            return None
        
        return Session.model_validate(session_data)
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data"""
        db = await self._get_db()
        
        updates["updated_at"] = datetime.utcnow()
        
        result = await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": updates}
        )
        
        return result.modified_count > 0
    
    async def end_session(self, session_id: str) -> bool:
        """End a session"""
        db = await self._get_db()
        
        updates = {
            "status": SessionStatus.COMPLETED,
            "ended_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            logger.info(f"Ended session {session_id}")
            return True
        
        return False
    
    async def get_user_sessions(
        self, 
        user_id: str, 
        assignment_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Session]:
        """Get user's session history"""
        db = await self._get_db()
        
        query = {"user_id": user_id}
        if assignment_id:
            query["assignment_id"] = assignment_id
        
        cursor = db.sessions.find(query).sort("started_at", -1).limit(limit)
        sessions = []
        
        async for session_data in cursor:
            sessions.append(Session.model_validate(session_data))
        
        return sessions
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        db = await self._get_db()
        
        expiry_time = datetime.utcnow() - timedelta(minutes=settings.SESSION_TIMEOUT_MINUTES)
        
        result = await db.sessions.update_many(
            {
                "status": SessionStatus.ACTIVE,
                "started_at": {"$lt": expiry_time}
            },
            {
                "$set": {
                    "status": SessionStatus.TERMINATED,
                    "ended_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Cleaned up {result.modified_count} expired sessions")
        
        return result.modified_count
    
    async def get_session_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get session statistics for a user"""
        db = await self._get_db()
        
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": None,
                    "total_sessions": {"$sum": 1},
                    "completed_sessions": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", SessionStatus.COMPLETED]}, 1, 0]
                        }
                    },
                    "active_sessions": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", SessionStatus.ACTIVE]}, 1, 0]
                        }
                    },
                    "total_messages": {"$sum": "$total_messages"},
                    "total_tokens": {"$sum": "$total_tokens"},
                    "avg_session_duration": {
                        "$avg": {
                            "$subtract": [
                                {"$ifNull": ["$ended_at", datetime.utcnow()]},
                                "$started_at"
                            ]
                        }
                    }
                }
            }
        ]
        
        result = await db.sessions.aggregate(pipeline).to_list(1)
        
        if result:
            stats = result[0]
            # Convert duration from milliseconds to minutes
            if stats.get("avg_session_duration"):
                stats["avg_session_duration_minutes"] = stats["avg_session_duration"] / (1000 * 60)
            return stats
        
        return {
            "total_sessions": 0,
            "completed_sessions": 0,
            "active_sessions": 0,
            "total_messages": 0,
            "total_tokens": 0,
            "avg_session_duration_minutes": 0
        }


session_service = SessionService()