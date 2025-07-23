from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # FastAPI Configuration
    APP_NAME: str = "AI-TA Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    HOST: str = "localhost"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    
    # Security
    SECRET_KEY: str = Field(..., description="Secret key for JWT tokens")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # MongoDB Configuration
    MONGODB_URL: str = Field(..., description="MongoDB connection URL")
    MONGODB_DB_NAME: str = "ai_tutor_db"
    MONGODB_TEST_DB_NAME: str = "ai_tutor_test_db"
    MONGODB_MIN_POOL_SIZE: int = 10
    MONGODB_MAX_POOL_SIZE: int = 50
    
    # Redis Configuration
    REDIS_URL: str = Field(..., description="Redis connection URL")
    REDIS_TTL: int = 3600
    CACHE_TTL: int = 1800
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 4000
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_REQUEST_TIMEOUT: int = 30
    
    # Context Compression Settings
    MAX_TOKENS_TIER_1: int = 30000
    MAX_TOKENS_TIER_2: int = 60000
    MAX_TOKENS_TIER_3: int = 100000
    COMPRESSION_TRIGGER_THRESHOLD: float = 0.8
    
    # Session Management
    SESSION_TIMEOUT_MINUTES: int = 60
    MAX_CONCURRENT_SESSIONS: int = 100
    
    # File Upload Settings
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    UPLOAD_PATH: str = "./uploads"
    ALLOWED_EXTENSIONS: str = ".md,.txt,.json,.yaml,.yml"
    
    # Analytics & Monitoring
    ENABLE_ANALYTICS: bool = True
    LOG_LEVEL: str = "INFO"
    STRUCTURED_LOGGING: bool = True
    
    # CORS Settings
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="Comma-separated allowed CORS origins"
    )
    CORS_ALLOW_CREDENTIALS: bool = True
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to a list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10
    
    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]


def get_settings() -> Settings:
    return Settings()


settings = get_settings()