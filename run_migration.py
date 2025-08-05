#!/usr/bin/env python3
"""
Database Migration Runner
Execute this script to clean up duplicate sessions and apply constraints
"""

import asyncio
import logging
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

async def main():
    """Run the database migration to clean up duplicate sessions"""
    
    logger.info("🚀 Starting database cleanup and constraint migration...")
    
    try:
        # Import the migration
        from app.database.migrations.add_session_constraints import upgrade, cleanup_duplicate_sessions
        from app.database.connection import get_database
        
        # Get database connection
        db = await get_database()
        logger.info("✅ Database connection established")
        
        # First, let's check current state
        logger.info("📊 Checking current database state...")
        
        # Count total sessions
        total_sessions = await db.sessions.count_documents({})
        active_sessions = await db.sessions.count_documents({"status": "active"})
        
        logger.info(f"📊 Current state: {total_sessions} total sessions, {active_sessions} active sessions")
        
        # Check for duplicates
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
        
        if duplicates:
            logger.warning(f"🚨 Found {len(duplicates)} sets of duplicate active sessions")
            
            total_duplicate_sessions = sum(dup["count"] - 1 for dup in duplicates)  # -1 because we keep one
            logger.warning(f"🚨 Total duplicate sessions to clean: {total_duplicate_sessions}")
            
            # Show details
            for i, dup in enumerate(duplicates[:5]):  # Show first 5
                user_id = dup["_id"]["user_id"]
                assignment_id = dup["_id"]["assignment_id"] 
                count = dup["count"]
                logger.warning(f"   {i+1}. User {user_id[:8]}..., Assignment {assignment_id[:8]}...: {count} sessions")
            
            if len(duplicates) > 5:
                logger.warning(f"   ... and {len(duplicates) - 5} more sets")
        else:
            logger.info("✅ No duplicate active sessions found")
        
        # Ask for confirmation
        print("\n" + "="*60)
        print("🚨 DATABASE CLEANUP CONFIRMATION")
        print("="*60)
        print(f"Total sessions: {total_sessions}")
        print(f"Active sessions: {active_sessions}")
        print(f"Duplicate sets found: {len(duplicates)}")
        
        if duplicates:
            total_to_clean = sum(dup["count"] - 1 for dup in duplicates)
            print(f"Sessions to be cleaned up: {total_to_clean}")
            print("\nThis will:")
            print("1. End duplicate active sessions (keeping the most recent)")
            print("2. Add database constraints to prevent future duplicates")
            print("3. Add performance indexes")
        else:
            print("\nThis will:")
            print("1. Add database constraints to prevent future duplicates") 
            print("2. Add performance indexes")
        
        print("\n⚠️  This operation cannot be undone!")
        
        response = input("\nProceed with database cleanup? (yes/no): ").lower().strip()
        
        if response not in ['yes', 'y']:
            logger.info("❌ Database cleanup cancelled by user")
            return
        
        logger.info("🚀 Starting database cleanup and migration...")
        
        # Run the migration
        await upgrade()
        
        # Check results
        logger.info("📊 Checking results...")
        
        final_active_sessions = await db.sessions.count_documents({"status": "active"})
        final_duplicates = await db.sessions.aggregate(pipeline).to_list(None)
        
        logger.info(f"✅ Cleanup complete!")
        logger.info(f"📊 Final state: {final_active_sessions} active sessions, {len(final_duplicates)} duplicate sets")
        
        if len(final_duplicates) == 0:
            logger.info("🎉 All duplicate sessions cleaned up successfully!")
        else:
            logger.warning(f"⚠️  {len(final_duplicates)} duplicate sets still remain")
        
        # Check constraints
        try:
            indexes = await db.sessions.list_indexes().to_list(None)
            constraint_found = any("unique_active_session" in idx.get("name", "") for idx in indexes)
            
            if constraint_found:
                logger.info("✅ Unique constraint successfully applied")
            else:
                logger.warning("⚠️  Unique constraint may not have been applied")
        except Exception as e:
            logger.warning(f"⚠️  Could not verify constraints: {e}")
        
        logger.info("🎉 Database migration completed successfully!")
        
    except Exception as e:
        logger.error(f"💥 Migration failed: {e}")
        logger.error("Please check the error above and try again")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())