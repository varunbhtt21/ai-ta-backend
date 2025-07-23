from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging
import tiktoken

from app.database.connection import get_database
from app.models import (
    ConversationDocument, ConversationMessage, MessageType, InputType
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(self):
        self.db = None
        self.tokenizer = tiktoken.encoding_for_model(settings.OPENAI_MODEL)
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken"""
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.warning(f"Failed to count tokens: {e}")
            # Fallback: rough estimate (4 characters per token)
            return len(text) // 4
    
    def _detect_input_type(self, content: str) -> InputType:
        """Detect the type of user input"""
        content_lower = content.lower().strip()
        
        # Code detection patterns
        code_patterns = [
            r'def\s+\w+\s*\(',  # function definitions
            r'for\s+\w+\s+in\s+',  # for loops
            r'if\s+.+:',  # if statements
            r'print\s*\(',  # print statements
            r'=\s*\[.*\]',  # list assignments
            r'import\s+\w+',  # imports
            r'from\s+\w+\s+import',  # from imports
            r'while\s+.+:',  # while loops
            r'class\s+\w+',  # class definitions
            r'return\s+',  # return statements
        ]
        
        import re
        for pattern in code_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return InputType.CODE_SUBMISSION
        
        # Next problem requests
        next_patterns = ['next', 'move on', 'continue', 'done', 'finished', 'skip']
        if any(pattern in content_lower for pattern in next_patterns):
            return InputType.NEXT_PROBLEM
        
        # Ready signals
        ready_patterns = ['ready', 'start', 'begin', "let's go", 'lets go', 'ok', 'yes']
        if any(pattern in content_lower for pattern in ready_patterns):
            return InputType.READY_TO_START
        
        # Question indicators
        question_patterns = ['?', 'how', 'what', 'why', 'help', 'explain', 'confused']
        if any(pattern in content_lower for pattern in question_patterns):
            return InputType.QUESTION
        
        return InputType.GENERAL_CHAT
    
    async def add_message(
        self,
        session_id: str,
        user_id: str,
        message_type: MessageType,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationDocument:
        """Add a new message to the conversation"""
        db = await self._get_db()
        
        # Count tokens
        token_count = self._count_tokens(content)
        
        # Detect input type for user messages
        input_type = None
        if message_type == MessageType.USER:
            input_type = self._detect_input_type(content)
        
        # Create conversation document
        conversation = ConversationDocument(
            session_id=session_id,
            user_id=user_id,
            message_type=message_type.value,
            content=content,
            tokens_used=token_count,
            metadata=metadata or {},
            input_type=input_type
        )
        
        # Save to database
        result = await db.conversations.insert_one(conversation.dict(by_alias=True))
        conversation.id = result.inserted_id
        
        # Update session token count
        await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {
                "$inc": {
                    "total_tokens": token_count,
                    "total_messages": 1
                },
                "$set": {"updated_at": datetime.utcnow()}
            }
        )
        
        logger.debug(f"Added {message_type.value} message to session {session_id}")
        return conversation
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
        include_archived: bool = False
    ) -> List[ConversationMessage]:
        """Get conversation history for a session"""
        db = await self._get_db()
        
        query = {"session_id": session_id}
        if not include_archived:
            query["archived"] = {"$ne": True}
        
        cursor = db.conversations.find(query).sort("timestamp", 1)
        if limit:
            cursor = cursor.limit(limit)
        
        messages = []
        async for doc in cursor:
            message = ConversationMessage(
                timestamp=doc["timestamp"],
                message_type=MessageType(doc["message_type"]),
                content=doc["content"],
                metadata=doc.get("metadata")
            )
            messages.append(message)
        
        return messages
    
    async def get_recent_messages(
        self,
        session_id: str,
        count: int = 10
    ) -> List[ConversationMessage]:
        """Get recent messages from a session"""
        db = await self._get_db()
        
        cursor = db.conversations.find({
            "session_id": session_id,
            "archived": {"$ne": True}
        }).sort("timestamp", -1).limit(count)
        
        messages = []
        async for doc in cursor:
            message = ConversationMessage(
                timestamp=doc["timestamp"],
                message_type=MessageType(doc["message_type"]),
                content=doc["content"],
                metadata=doc.get("metadata")
            )
            messages.append(message)
        
        # Reverse to get chronological order
        return list(reversed(messages))
    
    async def archive_messages(
        self,
        session_id: str,
        before_timestamp: Optional[datetime] = None
    ) -> int:
        """Archive old messages to reduce context size"""
        db = await self._get_db()
        
        query = {"session_id": session_id}
        if before_timestamp:
            query["timestamp"] = {"$lt": before_timestamp}
        
        result = await db.conversations.update_many(
            query,
            {"$set": {"archived": True, "updated_at": datetime.utcnow()}}
        )
        
        if result.modified_count > 0:
            logger.info(f"Archived {result.modified_count} messages for session {session_id}")
        
        return result.modified_count
    
    async def get_conversation_tokens(self, session_id: str) -> int:
        """Get total token count for a session's conversation"""
        db = await self._get_db()
        
        pipeline = [
            {
                "$match": {
                    "session_id": session_id,
                    "archived": {"$ne": True}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_tokens": {"$sum": "$tokens_used"}
                }
            }
        ]
        
        result = await db.conversations.aggregate(pipeline).to_list(1)
        return result[0]["total_tokens"] if result else 0
    
    async def search_conversations(
        self,
        user_id: str,
        query: str,
        assignment_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search through user's conversations"""
        db = await self._get_db()
        
        # Build search query
        search_query = {
            "user_id": user_id,
            "content": {"$regex": query, "$options": "i"},
            "archived": {"$ne": True}
        }
        
        # If assignment_id provided, join with sessions to filter
        if assignment_id:
            pipeline = [
                {"$match": search_query},
                {
                    "$lookup": {
                        "from": "sessions",
                        "localField": "session_id",
                        "foreignField": "_id",
                        "as": "session"
                    }
                },
                {"$match": {"session.assignment_id": assignment_id}},
                {"$sort": {"timestamp": -1}},
                {"$limit": limit}
            ]
            
            cursor = db.conversations.aggregate(pipeline)
        else:
            cursor = db.conversations.find(search_query).sort("timestamp", -1).limit(limit)
        
        results = []
        async for doc in cursor:
            results.append({
                "session_id": doc["session_id"],
                "content": doc["content"],
                "timestamp": doc["timestamp"],
                "message_type": doc["message_type"]
            })
        
        return results
    
    async def get_user_message_stats(self, user_id: str) -> Dict[str, Any]:
        """Get message statistics for a user"""
        db = await self._get_db()
        
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": "$message_type",
                    "count": {"$sum": 1},
                    "total_tokens": {"$sum": "$tokens_used"}
                }
            }
        ]
        
        result = await db.conversations.aggregate(pipeline).to_list(10)
        
        stats = {}
        total_messages = 0
        total_tokens = 0
        
        for item in result:
            message_type = item["_id"]
            count = item["count"]
            tokens = item["total_tokens"] or 0
            
            stats[message_type] = {
                "count": count,
                "tokens": tokens
            }
            total_messages += count
            total_tokens += tokens
        
        stats["total_messages"] = total_messages
        stats["total_tokens"] = total_tokens
        
        return stats


conversation_service = ConversationService()