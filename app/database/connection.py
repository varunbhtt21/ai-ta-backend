from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    client: Optional[AsyncIOMotorClient] = None
    database: Optional[AsyncIOMotorDatabase] = None


db_manager = DatabaseManager()


async def connect_to_mongo():
    """Create database connection"""
    try:
        db_manager.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            minPoolSize=settings.MONGODB_MIN_POOL_SIZE,
            maxPoolSize=settings.MONGODB_MAX_POOL_SIZE,
        )
        
        db_manager.database = db_manager.client[settings.MONGODB_DB_NAME]
        
        # Test the connection
        await db_manager.client.admin.command("ping")
        logger.info(f"Connected to MongoDB: {settings.MONGODB_DB_NAME}")
        
        # Create indexes
        await create_indexes()
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close database connection"""
    if db_manager.client:
        db_manager.client.close()
        logger.info("Disconnected from MongoDB")


async def get_database() -> AsyncIOMotorDatabase:
    """Get database instance"""
    if db_manager.database is None:
        await connect_to_mongo()
    return db_manager.database


async def create_indexes():
    """Create database indexes for optimal performance"""
    if db_manager.database is None:
        return
    
    try:
        # Users collection indexes
        await db_manager.database.users.create_index("username", unique=True)
        await db_manager.database.users.create_index("email", unique=True)
        
        # Sessions collection indexes
        await db_manager.database.sessions.create_index([("user_id", 1), ("session_number", -1)])
        await db_manager.database.sessions.create_index([("user_id", 1), ("assignment_id", 1)])
        await db_manager.database.sessions.create_index("started_at")
        
        # Conversations collection indexes
        await db_manager.database.conversations.create_index([("session_id", 1), ("timestamp", 1)])
        await db_manager.database.conversations.create_index([("user_id", 1), ("timestamp", -1)])
        await db_manager.database.conversations.create_index("archived")
        
        # Student progress collection indexes
        await db_manager.database.student_progress.create_index([("user_id", 1), ("assignment_id", 1), ("problem_number", 1)], unique=True)
        await db_manager.database.student_progress.create_index([("user_id", 1), ("session_id", 1)])
        
        # Learning profiles collection indexes
        await db_manager.database.learning_profiles.create_index("user_id", unique=True)
        
        # Compressed summaries collection indexes
        await db_manager.database.compressed_summaries.create_index([("user_id", 1), ("sessions_range", 1)])
        
        # Assignments collection indexes
        await db_manager.database.assignments.create_index("title")
        await db_manager.database.assignments.create_index("created_at")
        
        logger.info("Database indexes created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        # Don't raise - indexes are not critical for basic functionality