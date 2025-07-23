from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from bson import ObjectId
import logging
import tiktoken

from app.database.connection import get_database
from app.models import (
    ConversationMessage, MessageType, ContextCompressionLevel,
    CompressedSummary, LearningProfile, CompressionReason, SessionContext
)
from app.services.openai_client import openai_client
from app.core.config import settings

logger = logging.getLogger(__name__)


class ContextCompressionManager:
    """
    Advanced 3-tier context compression system for managing long-term tutoring conversations
    
    Tier 1 (Sessions 1-5): Full Detail - Complete conversation history ≤30K tokens
    Tier 2 (Sessions 6-10): Summarized + Recent - AI summaries + recent context ≤60K tokens  
    Tier 3 (Sessions 11+): High-Level Summary - Learning profile + minimal context ≤100K tokens
    """
    
    def __init__(self):
        self.db = None
        self.tokenizer = tiktoken.encoding_for_model(settings.OPENAI_MODEL)
        self.openai_client = openai_client
    
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
            return len(text) // 4  # Fallback estimate
    
    def _count_message_tokens(self, messages: List[ConversationMessage]) -> int:
        """Count total tokens in a list of messages"""
        total_tokens = 0
        for msg in messages:
            total_tokens += self._count_tokens(msg.content)
        return total_tokens
    
    async def determine_compression_level(
        self, 
        user_id: str, 
        assignment_id: str,
        session_count: int,
        total_tokens: int
    ) -> Tuple[ContextCompressionLevel, CompressionReason]:
        """
        Determine appropriate compression level based on session count and token usage
        """
        
        # Check token limits first (override session-based rules)
        if total_tokens >= settings.MAX_TOKENS_TIER_3:
            return ContextCompressionLevel.HIGH_LEVEL_SUMMARY, CompressionReason.TOKEN_LIMIT
        elif total_tokens >= settings.MAX_TOKENS_TIER_2:
            return ContextCompressionLevel.SUMMARIZED_PLUS_RECENT, CompressionReason.TOKEN_LIMIT
        elif total_tokens >= settings.MAX_TOKENS_TIER_1:
            return ContextCompressionLevel.SUMMARIZED_PLUS_RECENT, CompressionReason.TOKEN_LIMIT
        
        # Session-based compression levels
        if session_count <= 5:
            return ContextCompressionLevel.FULL_DETAIL, CompressionReason.SESSION_COUNT
        elif session_count <= 10:
            return ContextCompressionLevel.SUMMARIZED_PLUS_RECENT, CompressionReason.SESSION_COUNT
        else:
            return ContextCompressionLevel.HIGH_LEVEL_SUMMARY, CompressionReason.SESSION_COUNT
    
    async def should_trigger_compression(
        self,
        user_id: str,
        current_tokens: int,
        compression_level: ContextCompressionLevel
    ) -> bool:
        """Check if compression should be triggered based on current state"""
        
        thresholds = {
            ContextCompressionLevel.FULL_DETAIL: settings.MAX_TOKENS_TIER_1,
            ContextCompressionLevel.SUMMARIZED_PLUS_RECENT: settings.MAX_TOKENS_TIER_2, 
            ContextCompressionLevel.HIGH_LEVEL_SUMMARY: settings.MAX_TOKENS_TIER_3
        }
        
        max_tokens = thresholds.get(compression_level, settings.MAX_TOKENS_TIER_1)
        trigger_threshold = max_tokens * settings.COMPRESSION_TRIGGER_THRESHOLD
        
        return current_tokens >= trigger_threshold
    
    async def compress_context_tier_1(
        self,
        user_id: str,
        assignment_id: str,
        conversations: List[ConversationMessage]
    ) -> Dict[str, Any]:
        """
        Tier 1: Full Detail - Maintain complete conversation history
        Simply return full context with token counting
        """
        
        total_tokens = self._count_message_tokens(conversations)
        
        # If over limit, prepare for transition to Tier 2
        needs_upgrade = total_tokens > settings.MAX_TOKENS_TIER_1
        
        context_data = {
            "compression_level": ContextCompressionLevel.FULL_DETAIL,
            "full_conversations": [msg.dict() for msg in conversations],
            "total_tokens": total_tokens,
            "message_count": len(conversations),
            "needs_upgrade": needs_upgrade,
            "compressed_summary": None,
            "learning_profile_summary": None
        }
        
        return context_data
    
    async def compress_context_tier_2(
        self,
        user_id: str,
        assignment_id: str,
        conversations: List[ConversationMessage],
        recent_message_count: int = 50
    ) -> Dict[str, Any]:
        """
        Tier 2: Summarized + Recent - AI-generated summaries of early sessions + recent messages
        """
        
        if len(conversations) <= recent_message_count:
            # Not enough messages to compress, return as Tier 1
            return await self.compress_context_tier_1(user_id, assignment_id, conversations)
        
        # Split conversations: older (to summarize) vs recent (keep full)
        older_messages = conversations[:-recent_message_count]
        recent_messages = conversations[-recent_message_count:]
        
        # Check if we already have a summary for the older messages
        existing_summary = await self._get_existing_summary(
            user_id, assignment_id, len(older_messages)
        )
        
        if existing_summary:
            compressed_summary = existing_summary
        else:
            # Generate new AI summary of older conversations
            compressed_summary = await self._generate_conversation_summary(
                user_id, assignment_id, older_messages, summary_type="detailed"
            )
            
            # Save the summary for future use
            await self._save_compressed_summary(user_id, assignment_id, compressed_summary)
        
        # Count tokens in compressed context
        summary_tokens = self._count_tokens(compressed_summary.get("summary_text", ""))
        recent_tokens = self._count_message_tokens(recent_messages)
        total_tokens = summary_tokens + recent_tokens
        
        # Check if we need to upgrade to Tier 3
        needs_upgrade = total_tokens > settings.MAX_TOKENS_TIER_2
        
        context_data = {
            "compression_level": ContextCompressionLevel.SUMMARIZED_PLUS_RECENT,
            "compressed_summary": compressed_summary,
            "recent_conversations": [msg.dict() for msg in recent_messages],
            "summary_tokens": summary_tokens,
            "recent_tokens": recent_tokens,
            "total_tokens": total_tokens,
            "summarized_message_count": len(older_messages),
            "recent_message_count": len(recent_messages),
            "needs_upgrade": needs_upgrade,
            "learning_profile_summary": None
        }
        
        return context_data
    
    async def compress_context_tier_3(
        self,
        user_id: str,
        assignment_id: str,
        conversations: List[ConversationMessage],
        recent_message_count: int = 20
    ) -> Dict[str, Any]:
        """
        Tier 3: High-Level Summary - Minimal learning profile + essential recent context
        """
        
        # Get or generate learning profile summary
        learning_profile = await self._generate_learning_profile_summary(
            user_id, assignment_id, conversations
        )
        
        # Keep only most recent essential messages
        recent_messages = conversations[-recent_message_count:] if conversations else []
        
        # Generate high-level session summary if needed
        if len(conversations) > recent_message_count:
            older_messages = conversations[:-recent_message_count]
            high_level_summary = await self._generate_conversation_summary(
                user_id, assignment_id, older_messages, summary_type="high_level"
            )
        else:
            high_level_summary = {"summary_text": "Early session - full context available"}
        
        # Count tokens
        profile_tokens = self._count_tokens(str(learning_profile))
        summary_tokens = self._count_tokens(high_level_summary.get("summary_text", ""))
        recent_tokens = self._count_message_tokens(recent_messages)
        total_tokens = profile_tokens + summary_tokens + recent_tokens
        
        context_data = {
            "compression_level": ContextCompressionLevel.HIGH_LEVEL_SUMMARY,
            "learning_profile_summary": learning_profile,
            "high_level_summary": high_level_summary,
            "recent_conversations": [msg.dict() for msg in recent_messages],
            "profile_tokens": profile_tokens,
            "summary_tokens": summary_tokens,
            "recent_tokens": recent_tokens,
            "total_tokens": total_tokens,
            "summarized_message_count": len(conversations) - len(recent_messages),
            "recent_message_count": len(recent_messages),
            "needs_upgrade": False  # Tier 3 is the highest compression
        }
        
        return context_data
    
    async def compress_context(
        self,
        user_id: str,
        assignment_id: str,
        conversations: List[ConversationMessage],
        target_level: ContextCompressionLevel
    ) -> Dict[str, Any]:
        """
        Main compression method that routes to appropriate tier
        """
        
        start_time = datetime.utcnow()
        original_tokens = self._count_message_tokens(conversations)
        
        try:
            if target_level == ContextCompressionLevel.FULL_DETAIL:
                result = await self.compress_context_tier_1(user_id, assignment_id, conversations)
            
            elif target_level == ContextCompressionLevel.SUMMARIZED_PLUS_RECENT:
                result = await self.compress_context_tier_2(user_id, assignment_id, conversations)
            
            elif target_level == ContextCompressionLevel.HIGH_LEVEL_SUMMARY:
                result = await self.compress_context_tier_3(user_id, assignment_id, conversations)
            
            else:
                raise ValueError(f"Unknown compression level: {target_level}")
            
            # Add compression metadata
            compression_time = (datetime.utcnow() - start_time).total_seconds()
            compressed_tokens = result.get("total_tokens", original_tokens)
            compression_ratio = original_tokens / compressed_tokens if compressed_tokens > 0 else 1.0
            
            result["compression_metadata"] = {
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "compression_ratio": compression_ratio,
                "compression_time_seconds": compression_time,
                "compression_timestamp": start_time,
                "compression_quality": self._assess_compression_quality(result)
            }
            
            logger.info(f"Context compressed: {original_tokens} → {compressed_tokens} tokens "
                       f"(ratio: {compression_ratio:.2f}x) in {compression_time:.2f}s")
            
            return result
        
        except Exception as e:
            logger.error(f"Context compression failed: {e}")
            # Fallback to Tier 1 (no compression)
            return await self.compress_context_tier_1(user_id, assignment_id, conversations)
    
    async def _generate_conversation_summary(
        self,
        user_id: str,
        assignment_id: str,
        conversations: List[ConversationMessage],
        summary_type: str = "detailed"
    ) -> Dict[str, Any]:
        """Generate AI-powered summary of conversations"""
        
        if not conversations:
            return {"summary_text": "No conversations to summarize", "summary_type": summary_type}
        
        # Prepare conversation text for summarization
        conversation_text = "\n\n".join([
            f"{msg.message_type.value.upper()}: {msg.content}"
            for msg in conversations
        ])
        
        if summary_type == "detailed":
            system_prompt = """You are an AI tutor assistant analyzing student learning conversations. Create a detailed summary that preserves:

1. Key learning milestones and breakthroughs
2. Persistent struggles and misconceptions
3. Successful code patterns and solutions
4. Effective teaching strategies that worked
5. Programming concepts covered and mastered
6. Student's problem-solving approach evolution

Focus on educational progress rather than conversational details. Be concise but comprehensive."""

        else:  # high_level
            system_prompt = """You are an AI tutor assistant creating a high-level learning profile summary. Extract:

1. Overall programming competency level
2. Key strengths and persistent challenges
3. Learning velocity and preferred teaching style
4. Major conceptual breakthroughs
5. Current skill level and readiness

Provide a concise profile suitable for long-term student tracking."""

        user_prompt = f"""Summarize these tutoring conversations between an AI programming tutor and a student:

{conversation_text[:8000]}  

Provide a {summary_type} summary focusing on learning progress and educational insights."""

        messages = [
            ConversationMessage(
                message_type=MessageType.USER,
                content=user_prompt,
                timestamp=datetime.utcnow()
            )
        ]
        
        result = await self.openai_client.generate_response_with_retry(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=1000 if summary_type == "detailed" else 500
        )
        
        if result["success"]:
            return {
                "summary_text": result["content"],
                "summary_type": summary_type,
                "original_message_count": len(conversations),
                "generated_at": datetime.utcnow(),
                "token_usage": result.get("usage", {})
            }
        
        # Fallback summary
        return {
            "summary_text": f"Session summary: {len(conversations)} messages exchanged covering programming topics.",
            "summary_type": summary_type,
            "original_message_count": len(conversations),
            "generated_at": datetime.utcnow(),
            "fallback": True
        }
    
    async def _generate_learning_profile_summary(
        self,
        user_id: str,
        assignment_id: str,
        conversations: List[ConversationMessage]
    ) -> Dict[str, Any]:
        """Generate high-level learning profile for Tier 3 compression"""
        
        # TODO: Integrate with actual learning profile service
        # For now, generate from conversations
        
        total_messages = len(conversations)
        user_messages = [msg for msg in conversations if msg.message_type == MessageType.USER]
        code_messages = [msg for msg in user_messages if "def " in msg.content or "for " in msg.content]
        
        profile = {
            "user_id": user_id,
            "assignment_id": assignment_id,
            "total_interactions": total_messages,
            "user_messages": len(user_messages),
            "code_submissions_detected": len(code_messages),
            "estimated_competency": "intermediate" if len(code_messages) > 10 else "beginner",
            "learning_velocity": "moderate",  # TODO: Calculate from actual data
            "preferred_teaching_style": "collaborative",
            "key_strengths": ["problem-solving approach", "code syntax"],
            "areas_for_improvement": ["debugging", "optimization"],
            "last_updated": datetime.utcnow()
        }
        
        return profile
    
    async def _get_existing_summary(
        self,
        user_id: str,
        assignment_id: str,
        message_count: int
    ) -> Optional[Dict[str, Any]]:
        """Check for existing summary covering the specified message range"""
        
        db = await self._get_db()
        
        summary = await db.compressed_summaries.find_one({
            "user_id": user_id,
            "assignment_id": assignment_id,
            "original_message_count": {"$gte": message_count}
        })
        
        if summary:
            return {
                "summary_text": summary.get("summary_text", ""),
                "summary_type": summary.get("summary_type", "detailed"),
                "original_message_count": summary.get("original_message_count", 0),
                "generated_at": summary.get("generated_at"),
                "cached": True
            }
        
        return None
    
    async def _save_compressed_summary(
        self,
        user_id: str,
        assignment_id: str,
        summary_data: Dict[str, Any]
    ):
        """Save compressed summary for future reuse"""
        
        db = await self._get_db()
        
        summary_doc = {
            "user_id": user_id,
            "assignment_id": assignment_id,
            "summary_text": summary_data.get("summary_text", ""),
            "summary_type": summary_data.get("summary_type", "detailed"),
            "original_message_count": summary_data.get("original_message_count", 0),
            "generated_at": summary_data.get("generated_at", datetime.utcnow()),
            "token_usage": summary_data.get("token_usage", {}),
            "created_at": datetime.utcnow()
        }
        
        await db.compressed_summaries.insert_one(summary_doc)
        logger.info(f"Saved compressed summary for user {user_id}")
    
    def _assess_compression_quality(self, compression_result: Dict[str, Any]) -> float:
        """Assess the quality of compression (0.0 to 1.0)"""
        
        quality_score = 1.0
        
        # Check if compression actually reduced tokens
        original_tokens = compression_result.get("compression_metadata", {}).get("original_tokens", 1)
        compressed_tokens = compression_result.get("total_tokens", original_tokens)
        
        if compressed_tokens >= original_tokens:
            quality_score -= 0.3  # No compression achieved
        
        # Check for fallback usage
        if compression_result.get("compressed_summary", {}).get("fallback"):
            quality_score -= 0.2
        
        # Check if upgrade is needed immediately
        if compression_result.get("needs_upgrade"):
            quality_score -= 0.1
        
        return max(0.0, quality_score)
    
    async def build_compressed_prompt_context(
        self,
        compression_result: Dict[str, Any],
        current_problem: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build final prompt context from compressed data"""
        
        context_parts = []
        level = compression_result.get("compression_level")
        
        if level == ContextCompressionLevel.FULL_DETAIL:
            # Include full conversation history
            conversations = compression_result.get("full_conversations", [])
            for conv in conversations[-20:]:  # Last 20 messages for context
                role = conv.get("message_type", "user")
                content = conv.get("content", "")
                context_parts.append(f"{role.upper()}: {content}")
        
        elif level == ContextCompressionLevel.SUMMARIZED_PLUS_RECENT:
            # Include summary + recent conversations
            summary = compression_result.get("compressed_summary", {})
            if summary:
                context_parts.append("PREVIOUS SESSION SUMMARY:")
                context_parts.append(summary.get("summary_text", ""))
                context_parts.append("\nRECENT CONVERSATION:")
            
            recent_convs = compression_result.get("recent_conversations", [])
            for conv in recent_convs[-15:]:  # Last 15 recent messages
                role = conv.get("message_type", "user")
                content = conv.get("content", "")
                context_parts.append(f"{role.upper()}: {content}")
        
        elif level == ContextCompressionLevel.HIGH_LEVEL_SUMMARY:
            # Include learning profile + minimal recent context
            profile = compression_result.get("learning_profile_summary", {})
            if profile:
                context_parts.append("STUDENT LEARNING PROFILE:")
                context_parts.append(f"Competency: {profile.get('estimated_competency', 'unknown')}")
                context_parts.append(f"Learning Style: {profile.get('preferred_teaching_style', 'collaborative')}")
                context_parts.append(f"Strengths: {', '.join(profile.get('key_strengths', []))}")
                context_parts.append(f"Areas for Improvement: {', '.join(profile.get('areas_for_improvement', []))}")
            
            high_level = compression_result.get("high_level_summary", {})
            if high_level:
                context_parts.append("\nSESSION OVERVIEW:")
                context_parts.append(high_level.get("summary_text", ""))
            
            context_parts.append("\nRECENT INTERACTION:")
            recent_convs = compression_result.get("recent_conversations", [])
            for conv in recent_convs[-10:]:  # Last 10 messages only
                role = conv.get("message_type", "user")
                content = conv.get("content", "")
                context_parts.append(f"{role.upper()}: {content}")
        
        # Add current problem context if available
        if current_problem:
            context_parts.append(f"\nCURRENT PROBLEM: {current_problem.get('title', 'Unknown')}")
            context_parts.append(f"Description: {current_problem.get('description', 'No description')}")
        
        return "\n".join(context_parts)


# Global instance
context_compression_manager = ContextCompressionManager()