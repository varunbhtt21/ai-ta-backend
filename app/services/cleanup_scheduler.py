"""
Cleanup Scheduler Service
Handles scheduled cleanup tasks for session management
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from app.services.session_monitoring import session_monitoring_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class CleanupScheduler:
    """Scheduler for running periodic cleanup tasks"""
    
    def __init__(self):
        self.running = False
        self.tasks = {}
        self.stats = {
            "cleanup_runs": 0,
            "total_sessions_cleaned": 0,
            "total_conversations_archived": 0,
            "last_cleanup": None,
            "last_health_check": None
        }
    
    async def start(self):
        """Start the cleanup scheduler"""
        if self.running:
            logger.warning("🔄 [SCHEDULER] Cleanup scheduler is already running")
            return
        
        self.running = True
        logger.info("🚀 [SCHEDULER] Starting cleanup scheduler...")
        
        # Start cleanup tasks
        self.tasks = {
            "unused_sessions": asyncio.create_task(self._unused_sessions_cleanup_loop()),
            "old_conversations": asyncio.create_task(self._old_conversations_cleanup_loop()),
            "health_monitoring": asyncio.create_task(self._health_monitoring_loop()),
            "duplicate_detection": asyncio.create_task(self._duplicate_detection_loop())
        }
        
        logger.info("✅ [SCHEDULER] Cleanup scheduler started successfully")
    
    async def stop(self):
        """Stop the cleanup scheduler"""
        if not self.running:
            logger.warning("⚠️ [SCHEDULER] Cleanup scheduler is not running")
            return
        
        logger.info("🛑 [SCHEDULER] Stopping cleanup scheduler...")
        self.running = False
        
        # Cancel all tasks
        for task_name, task in self.tasks.items():
            if not task.done():
                logger.info(f"🛑 [SCHEDULER] Cancelling task: {task_name}")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.tasks.clear()
        logger.info("✅ [SCHEDULER] Cleanup scheduler stopped")
    
    async def _unused_sessions_cleanup_loop(self):
        """Loop for cleaning up unused sessions"""
        logger.info("🧹 [SCHEDULER] Starting unused sessions cleanup loop")
        
        while self.running:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                if not self.running:
                    break
                
                logger.info("🧹 [SCHEDULER] Running unused sessions cleanup...")
                
                # Clean up sessions older than 2 hours with no activity
                cleaned_count = await session_monitoring_service.cleanup_unused_sessions(
                    hours_threshold=2,
                    dry_run=False
                )
                
                if cleaned_count > 0:
                    self.stats["total_sessions_cleaned"] += cleaned_count
                    self.stats["cleanup_runs"] += 1
                    self.stats["last_cleanup"] = datetime.utcnow()
                    
                    logger.info(f"✅ [SCHEDULER] Cleaned up {cleaned_count} unused sessions")
                else:
                    logger.info("✅ [SCHEDULER] No unused sessions to clean up")
                
            except asyncio.CancelledError:
                logger.info("🛑 [SCHEDULER] Unused sessions cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"💥 [SCHEDULER] Error in unused sessions cleanup: {e}")
                # Continue running despite errors
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    async def _old_conversations_cleanup_loop(self):
        """Loop for archiving old conversation data"""
        logger.info("🗃️ [SCHEDULER] Starting old conversations cleanup loop")
        
        while self.running:
            try:
                await asyncio.sleep(86400)  # Run daily
                
                if not self.running:
                    break
                
                logger.info("🗃️ [SCHEDULER] Running old conversations cleanup...")
                
                # Archive conversations from sessions completed > 30 days ago
                archived_count = await session_monitoring_service.cleanup_old_completed_sessions(
                    days_threshold=30,
                    dry_run=False
                )
                
                if archived_count > 0:
                    self.stats["total_conversations_archived"] += archived_count
                    logger.info(f"✅ [SCHEDULER] Archived conversations for {archived_count} old sessions")
                else:
                    logger.info("✅ [SCHEDULER] No old conversations to archive")
                
            except asyncio.CancelledError:
                logger.info("🛑 [SCHEDULER] Old conversations cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"💥 [SCHEDULER] Error in old conversations cleanup: {e}")
                # Continue running despite errors
                await asyncio.sleep(3600)  # Wait 1 hour before retrying
    
    async def _health_monitoring_loop(self):
        """Loop for monitoring session health"""
        logger.info("🏥 [SCHEDULER] Starting health monitoring loop")
        
        while self.running:
            try:
                await asyncio.sleep(1800)  # Run every 30 minutes
                
                if not self.running:
                    break
                
                logger.info("🏥 [SCHEDULER] Running session health check...")
                
                # Generate health report
                health_report = await session_monitoring_service.generate_health_report()
                
                self.stats["last_health_check"] = datetime.utcnow()
                
                # Log health status
                health_score = health_report["health_score"]
                health_status = health_report["health_status"]
                
                if health_score >= 90:
                    logger.info(f"✅ [HEALTH] System health: {health_status} ({health_score}/100)")
                elif health_score >= 75:
                    logger.info(f"⚠️ [HEALTH] System health: {health_status} ({health_score}/100)")
                else:
                    logger.warning(f"🚨 [HEALTH] System health: {health_status} ({health_score}/100)")
                
                # Log issues if any
                if health_report["issues"]:
                    logger.warning("🚨 [HEALTH] Issues detected:")
                    for issue in health_report["issues"]:
                        logger.warning(f"   - {issue}")
                
                # Log recommendations
                if health_report["recommendations"]:
                    logger.info("💡 [HEALTH] Recommendations:")
                    for rec in health_report["recommendations"]:
                        logger.info(f"   - {rec}")
                
            except asyncio.CancelledError:
                logger.info("🛑 [SCHEDULER] Health monitoring loop cancelled")
                break
            except Exception as e:
                logger.error(f"💥 [SCHEDULER] Error in health monitoring: {e}")
                # Continue running despite errors
                await asyncio.sleep(600)  # Wait 10 minutes before retrying
    
    async def _duplicate_detection_loop(self):
        """Loop for detecting duplicate sessions"""
        logger.info("🔍 [SCHEDULER] Starting duplicate detection loop")
        
        while self.running:
            try:
                await asyncio.sleep(900)  # Run every 15 minutes
                
                if not self.running:
                    break
                
                logger.info("🔍 [SCHEDULER] Running duplicate session detection...")
                
                # Detect duplicate sessions
                duplicates = await session_monitoring_service.detect_duplicate_sessions()
                
                if duplicates:
                    logger.warning(f"🚨 [SCHEDULER] Found {len(duplicates)} sets of duplicate active sessions")
                    
                    # Log details for investigation
                    for dup in duplicates:
                        user_id = dup["_id"]["user_id"]
                        assignment_id = dup["_id"]["assignment_id"]
                        count = dup["count"]
                        logger.warning(f"🚨 [DUPLICATE] User {user_id}, Assignment {assignment_id}: {count} sessions")
                else:
                    logger.debug("✅ [SCHEDULER] No duplicate sessions detected")
                
            except asyncio.CancelledError:
                logger.info("🛑 [SCHEDULER] Duplicate detection loop cancelled")
                break
            except Exception as e:
                logger.error(f"💥 [SCHEDULER] Error in duplicate detection: {e}")
                # Continue running despite errors
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    async def force_cleanup(self, cleanup_type: str = "all") -> Dict[str, Any]:
        """Force immediate cleanup (for manual triggers)"""
        logger.info(f"🔧 [SCHEDULER] Force cleanup requested: {cleanup_type}")
        
        results = {}
        
        try:
            if cleanup_type in ["all", "unused"]:
                logger.info("🧹 [FORCE_CLEANUP] Running unused sessions cleanup...")
                cleaned = await session_monitoring_service.cleanup_unused_sessions(
                    hours_threshold=1,
                    dry_run=False
                )
                results["unused_sessions_cleaned"] = cleaned
                self.stats["total_sessions_cleaned"] += cleaned
            
            if cleanup_type in ["all", "conversations"]:
                logger.info("🗃️ [FORCE_CLEANUP] Running old conversations cleanup...")
                archived = await session_monitoring_service.cleanup_old_completed_sessions(
                    days_threshold=30,
                    dry_run=False
                )
                results["conversations_archived"] = archived
                self.stats["total_conversations_archived"] += archived
            
            if cleanup_type in ["all", "duplicates"]:
                logger.info("🔍 [FORCE_CLEANUP] Detecting duplicate sessions...")
                duplicates = await session_monitoring_service.detect_duplicate_sessions()
                results["duplicates_detected"] = len(duplicates)
            
            results["cleanup_completed_at"] = datetime.utcnow()
            self.stats["last_cleanup"] = datetime.utcnow()
            
            logger.info(f"✅ [FORCE_CLEANUP] Force cleanup completed: {results}")
            
        except Exception as e:
            logger.error(f"💥 [FORCE_CLEANUP] Force cleanup failed: {e}")
            results["error"] = str(e)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cleanup scheduler statistics"""
        return {
            **self.stats,
            "running": self.running,
            "active_tasks": list(self.tasks.keys()),
            "uptime_seconds": (datetime.utcnow() - self.stats.get("started_at", datetime.utcnow())).total_seconds() if self.running else 0
        }
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        try:
            health_report = await session_monitoring_service.generate_health_report()
            return {
                "health_score": health_report["health_score"],
                "health_status": health_report["health_status"],
                "issues_count": len(health_report["issues"]),
                "duplicates_detected": health_report["duplicates_detected"],
                "unused_sessions_detected": health_report["unused_sessions_detected"],
                "last_check": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"💥 [HEALTH] Failed to get health status: {e}")
            return {
                "health_score": 0,
                "health_status": "unknown",
                "error": str(e),
                "last_check": datetime.utcnow()
            }


# Create service instance
cleanup_scheduler = CleanupScheduler()