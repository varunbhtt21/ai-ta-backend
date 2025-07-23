from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging
import uvicorn

from app.core.config import settings
from app.database.connection import connect_to_mongo, close_mongo_connection
from app.routers import auth, sessions, assignments, progress, analytics, context, learning_profiles, file_uploads, instructor_dashboard

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Python Tutoring System Backend API",
    debug=settings.DEBUG,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"] if settings.DEBUG else [settings.HOST]
)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # Connect to MongoDB
    await connect_to_mongo()
    
    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("Shutting down application...")
    
    # Close MongoDB connection
    await close_mongo_connection()
    
    logger.info("Application shutdown complete")


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(sessions.router, prefix="/sessions", tags=["Sessions"])
app.include_router(assignments.router, prefix="/assignments", tags=["Assignments"])
app.include_router(progress.router, prefix="/progress", tags=["Progress"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(context.router, prefix="/context", tags=["Context Compression"])
app.include_router(learning_profiles.router, prefix="/learning-profiles", tags=["Learning Profiles"])
app.include_router(file_uploads.router, prefix="/uploads", tags=["File Uploads"])
app.include_router(instructor_dashboard.router, prefix="/dashboard", tags=["Instructor Dashboard"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if settings.DEBUG else "Disabled in production"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )