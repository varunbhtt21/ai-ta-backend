"""
Session Monitoring Service
Provides monitoring, analytics, and cleanup for session management
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from bson import ObjectId
import logging

from app.database.connection import get_database
from app.models import SessionStatus
from app.core.config import settings

logger = logging.getLogger(__name__)


class SessionMonitoringService:
    """Service for monitoring session health and detecting issues"""
    
    def __init__(self):
        self.db = None
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    async def detect_duplicate_sessions(self) -> List[Dict[str, Any]]:
        """Detect and report duplicate active sessions"""
        db = await self._get_db()
        
        logger.info("🔍 [MONITORING] Scanning for duplicate active sessions...")
        
        pipeline = [
            {"$match": {"status": SessionStatus.ACTIVE}},
            {
                "$group": {
                    "_id": {"user_id": "$user_id", "assignment_id": "$assignment_id"},
                    "count": {"$sum": 1},
                    "sessions": {
                        "$push": {
                            "session_id": "$_id",
                            "created_at": "$created_at",
                            "total_tokens": "$total_tokens",
                            "total_messages": "$total_messages"
                        }
                    }
                }
            },
            {"$match": {"count": {"$gt": 1}}},
            {"$sort": {"count": -1}}
        ]
        
        duplicates = await db.sessions.aggregate(pipeline).to_list(None)
        
        if duplicates:
            logger.warning(f"🚨 [MONITORING] Found {len(duplicates)} sets of duplicate active sessions")
            
            for dup in duplicates:
                user_id = dup["_id"]["user_id"]
                assignment_id = dup["_id"]["assignment_id"]
                count = dup["count"]
                
                logger.warning(f"🚨 [MONITORING] User {user_id}, Assignment {assignment_id}: {count} active sessions")
                
                for session in dup["sessions"]:
                    logger.warning(f"   📊 Session {session['session_id']}: created {session['created_at']}, tokens: {session['total_tokens']}, messages: {session['total_messages']}")
        else:
            logger.info("✅ [MONITORING] No duplicate active sessions found")
        
        return duplicates
    
    async def detect_unused_sessions(self, hours_threshold: int = 1) -> List[Dict[str, Any]]:
        """Detect sessions that were created but never used"""
        db = await self._get_db()
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_threshold)
        
        logger.info(f"🔍 [MONITORING] Scanning for unused sessions older than {hours_threshold} hours...")
        
        unused_sessions = await db.sessions.find({
            "created_at": {"$lt": cutoff_time},
            "total_tokens": 0,
            "total_messages": 0,
            "status": SessionStatus.ACTIVE
        }).to_list(None)
        
        if unused_sessions:
            logger.warning(f"🚨 [MONITORING] Found {len(unused_sessions)} unused sessions")
            
            for session in unused_sessions:
                age_hours = (datetime.utcnow() - session["created_at"]).total_seconds() / 3600
                logger.warning(f"   📊 Session {session['_id']}: age {age_hours:.1f}h, user {session['user_id']}")
        else:
            logger.info("✅ [MONITORING] No unused sessions found")
        
        return unused_sessions
    
    async def get_session_statistics(self) -> Dict[str, Any]:
        """Get comprehensive session statistics"""
        db = await self._get_db()
        
        logger.info("📊 [MONITORING] Generating session statistics...")
        
        # Total sessions by status
        status_pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        status_stats = await db.sessions.aggregate(status_pipeline).to_list(None)
        
        # Sessions created in last 24 hours
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_sessions = await db.sessions.count_documents({
            "created_at": {"$gte": last_24h}
        })
        
        # Average session duration
        duration_pipeline = [
            {
                "$match": {
                    "status": SessionStatus.COMPLETED,
                    "ended_at": {"$exists": True}
                }
            },
            {
                "$addFields": {
                    "duration_minutes": {
                        "$divide": [
                            {"$subtract": ["$ended_at", "$started_at"]},
                            1000 * 60
                        ]
                    }
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_duration": {"$avg": "$duration_minutes"},
                    "max_duration": {"$max": "$duration_minutes"},
                    "min_duration": {"$min": "$duration_minutes"}
                }
            }
        ]
        duration_stats = await db.sessions.aggregate(duration_pipeline).to_list(1)
        
        # Token usage statistics
        token_pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_tokens": {"$sum": "$total_tokens"},
                    "avg_tokens": {"$avg": "$total_tokens"},
                    "max_tokens": {"$max": "$total_tokens"},
                    "sessions_with_tokens": {
                        "$sum": {"$cond": [{"$gt": ["$total_tokens", 0]}, 1, 0]}
                    }
                }
            }
        ]
        token_stats = await db.sessions.aggregate(token_pipeline).to_list(1)
        
        # Message statistics
        message_pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_messages": {"$sum": "$total_messages"},
                    "avg_messages": {"$avg": "$total_messages"},
                    "max_messages": {"$max": "$total_messages"},
                    "sessions_with_messages": {
                        "$sum": {"$cond": [{"$gt": ["$total_messages", 0]}, 1, 0]}
                    }
                }
            }
        ]
        message_stats = await db.sessions.aggregate(message_pipeline).to_list(1)
        
        # Compression level distribution
        compression_pipeline = [
            {"$group": {"_id": "$compression_level", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        compression_stats = await db.sessions.aggregate(compression_pipeline).to_list(None)
        
        stats = {
            "total_sessions": await db.sessions.count_documents({}),
            "sessions_by_status": {stat["_id"]: stat["count"] for stat in status_stats},
            "sessions_last_24h": recent_sessions,
            "duration_stats": duration_stats[0] if duration_stats else None,
            "token_stats": token_stats[0] if token_stats else None,
            "message_stats": message_stats[0] if message_stats else None,
            "compression_distribution": {stat["_id"]: stat["count"] for stat in compression_stats},
            "generated_at": datetime.utcnow()
        }
        
        logger.info("✅ [MONITORING] Session statistics generated successfully")
        return stats
    
    async def cleanup_unused_sessions(self, hours_threshold: int = 1, dry_run: bool = False) -> int:
        """Clean up sessions that were created but never used"""
        db = await self._get_db()
        
        unused_sessions = await self.detect_unused_sessions(hours_threshold)
        
        if not unused_sessions:
            logger.info("✅ [CLEANUP] No unused sessions to clean up")
            return 0
        
        if dry_run:
            logger.info(f"🔍 [CLEANUP] DRY RUN: Would clean up {len(unused_sessions)} unused sessions")
            return len(unused_sessions)
        
        logger.info(f"🧹 [CLEANUP] Cleaning up {len(unused_sessions)} unused sessions...")
        
        session_ids = [session["_id"] for session in unused_sessions]
        
        result = await db.sessions.update_many(
            {"_id": {"$in": session_ids}},
            {
                "$set": {
                    "status": SessionStatus.TERMINATED,
                    "ended_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "session_notes": f"Auto-terminated: unused session (cleanup threshold: {hours_threshold}h)"
                }
            }
        )
        
        logger.info(f"✅ [CLEANUP] Cleaned up {result.modified_count} unused sessions")
        return result.modified_count
    
    async def cleanup_old_completed_sessions(self, days_threshold: int = 30, dry_run: bool = False) -> int:
        """Clean up old completed sessions by archiving conversation data"""
        db = await self._get_db()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)
        
        logger.info(f"🔍 [CLEANUP] Scanning for completed sessions older than {days_threshold} days...")
        
        old_sessions = await db.sessions.find({
            "status": SessionStatus.COMPLETED,
            "ended_at": {"$lt": cutoff_date}
        }).to_list(None)
        
        if not old_sessions:
            logger.info("✅ [CLEANUP] No old completed sessions to clean up")
            return 0
        
        if dry_run:
            logger.info(f"🔍 [CLEANUP] DRY RUN: Would archive {len(old_sessions)} old completed sessions")
            return len(old_sessions)
        
        logger.info(f"🗃️ [CLEANUP] Archiving conversations for {len(old_sessions)} old completed sessions...")
        
        archived_count = 0
        for session in old_sessions:
            session_id = str(session["_id"])
            
            # Archive conversation messages for this session
            archive_result = await db.conversations.update_many(
                {"session_id": session_id, "archived": {"$ne": True}},
                {
                    "$set": {
                        "archived": True,
                        "archived_at": datetime.utcnow(),
                        "archive_reason": f"Session completed > {days_threshold} days ago"
                    }
                }
            )
            
            if archive_result.modified_count > 0:
                logger.info(f"🗃️ [CLEANUP] Archived {archive_result.modified_count} messages for session {session_id}")
                archived_count += 1
        
        logger.info(f"✅ [CLEANUP] Archived conversations for {archived_count} old sessions")
        return archived_count
    
    async def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive session health report"""
        logger.info("🏥 [HEALTH_CHECK] Generating session health report...")
        
        # Get basic statistics
        stats = await self.get_session_statistics()
        
        # Check for issues
        duplicates = await self.detect_duplicate_sessions()
        unused_sessions = await self.detect_unused_sessions(hours_threshold=1)
        
        # Calculate health scores
        total_sessions = stats["total_sessions"]
        active_sessions = stats["sessions_by_status"].get("active", 0)
        sessions_with_tokens = stats["token_stats"]["sessions_with_tokens"] if stats["token_stats"] else 0
        
        # Health metrics
        health_metrics = {
            "duplicate_sessions_count": len(duplicates),
            "unused_sessions_count": len(unused_sessions),
            "session_utilization_rate": (sessions_with_tokens / total_sessions * 100) if total_sessions > 0 else 0,
            "active_session_ratio": (active_sessions / total_sessions * 100) if total_sessions > 0 else 0
        }
        
        # Determine overall health
        health_score = 100
        issues = []
        
        if duplicates:
            health_score -= len(duplicates) * 10
            issues.append(f"Found {len(duplicates)} sets of duplicate active sessions")
        
        if unused_sessions:
            health_score -= len(unused_sessions) * 5
            issues.append(f"Found {len(unused_sessions)} unused sessions")
        
        if health_metrics["session_utilization_rate"] < 50:
            health_score -= 20
            issues.append(f"Low session utilization rate: {health_metrics['session_utilization_rate']:.1f}%")
        
        if health_metrics["active_session_ratio"] > 20:
            health_score -= 15
            issues.append(f"High active session ratio: {health_metrics['active_session_ratio']:.1f}%")
        
        health_score = max(0, health_score)
        
        # Health status
        if health_score >= 90:
            health_status = "excellent"
        elif health_score >= 75:
            health_status = "good"
        elif health_score >= 50:
            health_status = "fair"
        else:
            health_status = "poor"
        
        report = {
            "health_score": health_score,
            "health_status": health_status,
            "issues": issues,
            "recommendations": self._generate_recommendations(health_metrics, duplicates, unused_sessions),
            "statistics": stats,
            "health_metrics": health_metrics,
            "duplicates_detected": len(duplicates),
            "unused_sessions_detected": len(unused_sessions),
            "report_generated_at": datetime.utcnow()
        }
        
        logger.info(f"✅ [HEALTH_CHECK] Health report generated - Score: {health_score}/100 ({health_status})")
        return report
    
    def _generate_recommendations(self, metrics: Dict[str, Any], duplicates: List, unused_sessions: List) -> List[str]:
        """Generate recommendations based on health metrics"""
        recommendations = []
        
        if duplicates:
            recommendations.append("Run cleanup to remove duplicate active sessions")
            recommendations.append("Investigate frontend race conditions causing multiple session creation")
        
        if unused_sessions:
            recommendations.append("Clean up unused sessions to free resources")
            recommendations.append("Investigate why sessions are created but not used")
        
        if metrics["session_utilization_rate"] < 50:
            recommendations.append("Investigate low session utilization - check frontend flow")
            recommendations.append("Consider adding session timeout to auto-cleanup unused sessions")
        
        if metrics["active_session_ratio"] > 20:
            recommendations.append("High number of active sessions - consider session timeout")
            recommendations.append("Monitor for sessions that should have been ended")
        
        if not recommendations:
            recommendations.append("System health looks good - continue monitoring")
        
        return recommendations


# Create service instance
session_monitoring_service = SessionMonitoringService()