"""
FastAPI main application for SpaceX Launch Tracker.
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from src.api.launches import router as launches_router
from src.api.auth import router as auth_router
from src.api.admin import router as admin_router
from src.api.health import router as health_router
from src.api.responses import ErrorResponse
from src.api.middleware import RateLimitMiddleware, CacheHeadersMiddleware
from src.database import init_database, close_database_connections
from src.cache.redis_client import close_redis_client
from src.logging_config import setup_logging, get_logger

# Initialize structured logging
setup_logging()
logger = get_logger(__name__, component="main_app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting SpaceX Launch Tracker API")
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down SpaceX Launch Tracker API")
    try:
        close_database_connections()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")
    
    try:
        close_redis_client()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.error(f"Error closing Redis connections: {e}")


app = FastAPI(
    title="SpaceX Launch Tracker API",
    description="API for tracking SpaceX launches with data from multiple sources",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    default_limit=100,  # 100 requests per hour by default
    default_window=3600,  # 1 hour window
    enabled=True
)

# Add cache headers middleware
app.add_middleware(
    CacheHeadersMiddleware,
    enabled=True
)

# Include routers
app.include_router(launches_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(health_router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Custom HTTP exception handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            code=str(exc.status_code)
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """General exception handler for unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail="An unexpected error occurred",
            code="500"
        ).model_dump()
    )


@app.get("/", summary="Root endpoint", description="Welcome message for the API")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SpaceX Launch Tracker API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "launches": "/api/launches",
            "upcoming": "/api/launches/upcoming",
            "historical": "/api/launches/historical",
            "auth": "/api/auth",
            "admin": "/api/admin",
            "health": "/health"
        }
    }


@app.get("/health", summary="Health check", description="Check API health status")
async def health_check():
    """Health check endpoint."""
    try:
        # You could add database connectivity check here
        return {
            "status": "healthy",
            "service": "SpaceX Launch Tracker API",
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )