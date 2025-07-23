from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
from passlib.context import CryptContext
from jose import JWTError, jwt
import logging

from app.database.connection import get_database
from app.models import User, UserRole
from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and user management service"""
    
    def __init__(self):
        self.db = None
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    async def _get_db(self):
        if self.db is None:
            self.db = await get_database()
        return self.db
    
    def _hash_password(self, password: str) -> str:
        """Hash a password for storing"""
        return self.pwd_context.hash(password)
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def _create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    def _verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"Token verification failed: {e}")
            return None
    
    async def register_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: UserRole = UserRole.STUDENT
    ) -> User:
        """Register a new user"""
        
        db = await self._get_db()
        
        # Check if username already exists
        existing_user = await db.users.find_one({"username": username})
        if existing_user:
            raise ValueError("Username already exists")
        
        # Check if email already exists
        existing_email = await db.users.find_one({"email": email})
        if existing_email:
            raise ValueError("Email already exists")
        
        # Validate password strength
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        # Create new user
        hashed_password = self._hash_password(password)
        
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role,
            is_active=True,
            preferences={}
        )
        
        result = await db.users.insert_one(user.dict(by_alias=True))
        user.id = result.inserted_id
        
        logger.info(f"Registered new user: {username} ({role.value})")
        return user
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username/password"""
        
        db = await self._get_db()
        
        user_data = await db.users.find_one({"username": username, "is_active": True})
        if not user_data:
            return None
        
        user = User.model_validate(user_data)
        
        if not self._verify_password(password, user.hashed_password):
            return None
        
        # Update last login
        await db.users.update_one(
            {"_id": user.id},
            {"$set": {"last_login": datetime.utcnow()}}
        )
        
        logger.info(f"User authenticated: {username}")
        return user
    
    async def create_access_token_for_user(self, user: User) -> str:
        """Create access token for authenticated user"""
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = self._create_access_token(
            data={
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value
            },
            expires_delta=access_token_expires
        )
        
        return access_token
    
    async def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from JWT token"""
        
        payload = self._verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        try:
            db = await self._get_db()
            user_data = await db.users.find_one({"_id": ObjectId(user_id), "is_active": True})
            
            if user_data:
                return User.model_validate(user_data)
        
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
        
        return None
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        
        db = await self._get_db()
        user_data = await db.users.find_one({"username": username, "is_active": True})
        
        if user_data:
            return User.model_validate(user_data)
        return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        
        db = await self._get_db()
        try:
            user_data = await db.users.find_one({"_id": ObjectId(user_id), "is_active": True})
            
            if user_data:
                return User.model_validate(user_data)
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
        
        return None
    
    async def update_user_profile(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update user profile"""
        
        db = await self._get_db()
        
        # Remove sensitive fields that shouldn't be updated directly
        safe_updates = {k: v for k, v in updates.items() 
                       if k not in ["id", "_id", "username", "hashed_password", "created_at"]}
        
        safe_updates["updated_at"] = datetime.utcnow()
        
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": safe_updates}
        )
        
        return result.modified_count > 0
    
    async def update_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """Update user preferences"""
        
        db = await self._get_db()
        
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "preferences": preferences,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> bool:
        """Change user password"""
        
        db = await self._get_db()
        
        # Get current user
        user_data = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user_data:
            return False
        
        user = User.model_validate(user_data)
        
        # Verify current password
        if not self._verify_password(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect")
        
        # Validate new password
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters long")
        
        # Update password
        new_hashed_password = self._hash_password(new_password)
        
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "hashed_password": new_hashed_password,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Password changed for user: {user.username}")
            return True
        
        return False
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate user account"""
        
        db = await self._get_db()
        
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_active": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
    
    async def list_users(
        self,
        role: Optional[UserRole] = None,
        active_only: bool = True,
        limit: int = 50,
        skip: int = 0
    ) -> List[User]:
        """List users with optional filtering"""
        
        db = await self._get_db()
        
        query = {}
        if active_only:
            query["is_active"] = True
        if role:
            query["role"] = role.value
        
        cursor = db.users.find(
            query,
            {"hashed_password": 0}  # Exclude password hash
        ).skip(skip).limit(limit).sort("created_at", -1)
        
        users = []
        async for user_data in cursor:
            # Don't include password hash in user object
            user_data.pop("hashed_password", None)
            users.append(User.model_validate(user_data))
        
        return users
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user activity statistics"""
        
        db = await self._get_db()
        
        # Get session count
        session_count = await db.sessions.count_documents({"user_id": user_id})
        
        # Get progress statistics
        progress_pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": None,
                    "total_problems_attempted": {"$sum": 1},
                    "problems_completed": {
                        "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                    },
                    "total_attempts": {"$sum": "$attempts"},
                    "total_time_spent": {"$sum": "$time_spent_minutes"}
                }
            }
        ]
        
        progress_stats = await db.student_progress.aggregate(progress_pipeline).to_list(1)
        
        stats = {
            "user_id": user_id,
            "total_sessions": session_count,
            "total_problems_attempted": progress_stats[0]["total_problems_attempted"] if progress_stats else 0,
            "problems_completed": progress_stats[0]["problems_completed"] if progress_stats else 0,
            "total_attempts": progress_stats[0]["total_attempts"] if progress_stats else 0,
            "total_time_spent_minutes": progress_stats[0]["total_time_spent"] if progress_stats else 0,
            "completion_rate": 0
        }
        
        if stats["total_problems_attempted"] > 0:
            stats["completion_rate"] = (stats["problems_completed"] / stats["total_problems_attempted"]) * 100
        
        return stats
    
    def is_instructor(self, user: User) -> bool:
        """Check if user has instructor role"""
        return user.role in [UserRole.INSTRUCTOR, UserRole.ADMIN]
    
    def is_admin(self, user: User) -> bool:
        """Check if user has admin role"""
        return user.role == UserRole.ADMIN


# Global instance
auth_service = AuthService()