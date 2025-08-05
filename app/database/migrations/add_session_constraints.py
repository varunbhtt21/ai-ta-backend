"""
Database migration to add session constraints and performance indexes
This migration adds constraints to prevent duplicate active sessions
and improves query performance for session-related operations.
"""

from datetime import datetime
from app.database.connection import get_database
import logging

logger = logging.getLogger(__name__)


async def upgrade():
    """Add constraints and indexes to prevent duplicate active sessions"""
    db = await get_database()
    
    logger.info("🏗️ [MIGRATION] Starting session constraints migration")
    
    try:
        # Create compound index for performance on common queries
        logger.info("📊 [MIGRATION] Creating performance indexes...")
        await db.sessions.create_index([
            ("user_id", 1),
            ("assignment_id", 1),
            ("status", 1),
            ("created_at", -1)
        ], name="idx_sessions_user_assignment_status_created")
        
        # Create partial unique index to prevent multiple active sessions
        # This will prevent two active sessions for the same user+assignment
        logger.info("🚫 [MIGRATION] Creating unique constraint for active sessions...")
        try:
            await db.sessions.create_index([
                ("user_id", 1),
                ("assignment_id", 1)
            ], {
                "unique": True,
                "partialFilterExpression": {"status": "active"},
                "name": "unique_active_session_per_user_assignment"
            })
            logger.info("✅ [MIGRATION] Unique constraint created successfully")
        except Exception as e:
            if "duplicate key" in str(e).lower():
                logger.warning("⚠️ [MIGRATION] Duplicate active sessions detected - cleaning up first")
                await cleanup_duplicate_sessions(db)
                # Retry after cleanup
                await db.sessions.create_index([
                    ("user_id", 1),
                    ("assignment_id", 1)
                ], {
                    "unique": True,
                    "partialFilterExpression": {"status": "active"},
                    "name": "unique_active_session_per_user_assignment"
                })
                logger.info("✅ [MIGRATION] Unique constraint created after cleanup")
            else:
                raise
        
        # Create additional performance indexes
        logger.info("📈 [MIGRATION] Creating additional performance indexes...")
        
        # Index for session lookup by user
        await db.sessions.create_index([
            ("user_id", 1),
            ("created_at", -1)
        ], name="idx_sessions_user_created")
        
        # Index for session cleanup operations
        await db.sessions.create_index([
            ("status", 1),
            ("created_at", 1)
        ], name="idx_sessions_status_created")
        
        # Index for session token tracking
        await db.sessions.create_index([
            ("total_tokens", 1),
            ("total_messages", 1),
            ("created_at", 1)
        ], name="idx_sessions_usage_tracking")
        
        logger.info("✅ [MIGRATION] Session constraints migration completed successfully")
        
    except Exception as e:
        logger.error(f"💥 [MIGRATION] Migration failed: {e}")
        raise


async def cleanup_duplicate_sessions(db):
    """Clean up duplicate active sessions before applying constraints"""
    logger.info("🧹 [CLEANUP] Starting duplicate session cleanup")
    
    # Find all duplicate active sessions
    pipeline = [
        {"$match": {"status": "active"}},
        {
            "$group": {
                "_id": {"user_id": "$user_id", "assignment_id": "$assignment_id"},
                "count": {"$sum": 1},
                "sessions": {"$push": {"id": "$_id", "created_at": "$created_at"}}
            }
        },
        {"$match": {"count": {"$gt": 1}}}
    ]
    
    duplicates = await db.sessions.aggregate(pipeline).to_list(None)
    
    if not duplicates:
        logger.info("✅ [CLEANUP] No duplicate sessions found")
        return
    
    logger.info(f"🚨 [CLEANUP] Found {len(duplicates)} sets of duplicate active sessions")
    
    total_cleaned = 0
    for dup in duplicates:
        sessions = dup["sessions"]
        user_id = dup["_id"]["user_id"]
        assignment_id = dup["_id"]["assignment_id"]
        
        logger.info(f"🧹 [CLEANUP] Processing {len(sessions)} duplicate sessions for user {user_id}")
        
        # Sort by created_at to keep the most recent
        sessions.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Keep the first (most recent), end the others
        sessions_to_end = [s["id"] for s in sessions[1:]]
        
        if sessions_to_end:
            result = await db.sessions.update_many(
                {"_id": {"$in": sessions_to_end}},
                {
                    "$set": {
                        "status": "completed",
                        "ended_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow(),
                        "session_notes": "Auto-ended during migration cleanup"
                    }
                }
            )
            
            total_cleaned += result.modified_count
            logger.info(f"🧹 [CLEANUP] Ended {result.modified_count} duplicate sessions for user {user_id}")
    
    logger.info(f"✅ [CLEANUP] Cleaned up {total_cleaned} duplicate sessions total")


async def downgrade():
    """Remove constraints and indexes (rollback)"""
    db = await get_database()
    
    logger.info("🔄 [ROLLBACK] Starting session constraints rollback")
    
    try:
        # Drop the unique constraint index
        await db.sessions.drop_index("unique_active_session_per_user_assignment")
        
        # Drop performance indexes
        await db.sessions.drop_index("idx_sessions_user_assignment_status_created")
        await db.sessions.drop_index("idx_sessions_user_created")
        await db.sessions.drop_index("idx_sessions_status_created")
        await db.sessions.drop_index("idx_sessions_usage_tracking")
        
        logger.info("✅ [ROLLBACK] Session constraints rollback completed")
        
    except Exception as e:
        logger.error(f"💥 [ROLLBACK] Rollback failed: {e}")
        raise


if __name__ == "__main__":
    import asyncio
    
    async def main():
        await upgrade()
    
    asyncio.run(main())