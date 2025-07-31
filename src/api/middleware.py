"""
FastAPI middleware for rate limiting and caching.
"""
import time
import logging
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.cache.rate_limiter import get_rate_limiter
from src.api.responses import ErrorResponse

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for API rate limiting."""
    
    def __init__(
        self,
        app,
        default_limit: int = 100,
        default_window: int = 3600,
        enabled: bool = True
    ):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: FastAPI application
            default_limit: Default requests per window
            default_window: Default window size in seconds
            enabled: Whether rate limiting is enabled
        """
        super().__init__(app)
        self.default_limit = default_limit
        self.default_window = default_window
        self.enabled = enabled
        self.rate_limiter = get_rate_limiter()
        
        # Endpoint-specific rate limits
        self.endpoint_limits = {
            "/api/launches": {"limit": 200, "window": 3600},
            "/api/launches/upcoming": {"limit": 300, "window": 3600},
            "/api/launches/historical": {"limit": 150, "window": 3600},
            "/api/admin/refresh": {"limit": 10, "window": 3600},
            "/api/admin/system/stats": {"limit": 60, "window": 3600},
            "/api/admin/system/health": {"limit": 120, "window": 3600},
        }
        
        # Paths to exclude from rate limiting
        self.excluded_paths = {
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/"
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        if not self.enabled:
            return await call_next(request)
        
        # Skip rate limiting for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Get client identifier (IP address or API key)
        client_id = self._get_client_identifier(request)
        endpoint = self._normalize_endpoint(request.url.path)
        
        # Get rate limit configuration for endpoint
        limit_config = self.endpoint_limits.get(endpoint, {
            "limit": self.default_limit,
            "window": self.default_window
        })
        
        # Check rate limit
        allowed, rate_info = self.rate_limiter.check_rate_limit(
            identifier=client_id,
            endpoint=endpoint,
            limit=limit_config["limit"],
            window_seconds=limit_config["window"]
        )
        
        if not allowed:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded for {client_id} on {endpoint}: "
                f"{rate_info.get('retry_after', 'unknown')}s retry after"
            )
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=ErrorResponse(
                    error="Rate limit exceeded",
                    detail=f"Too many requests. Try again in {rate_info.get('retry_after', 60)} seconds.",
                    code="429"
                ).model_dump(),
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": str(rate_info["remaining"]),
                    "X-RateLimit-Reset": str(rate_info["reset_time"]),
                    "Retry-After": str(rate_info.get("retry_after", 60))
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset_time"])
        
        return response
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Check for API key in headers
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key[:8]}..."  # Use first 8 chars for privacy
        
        # Check for Authorization header (JWT)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return f"jwt:{token[:8]}..."  # Use first 8 chars for privacy
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        
        # Check for forwarded IP (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            client_ip = real_ip
        
        return f"ip:{client_ip}"
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for rate limiting."""
        # Remove query parameters
        if "?" in path:
            path = path.split("?")[0]
        
        # Handle parameterized routes
        if path.startswith("/api/launches/") and len(path.split("/")) > 3:
            # Individual launch detail endpoint
            return "/api/launches/{slug}"
        
        if path.startswith("/api/admin/conflicts/") and path.endswith("/resolve"):
            return "/api/admin/conflicts/{id}/resolve"
        
        if path.startswith("/api/admin/refresh/status/"):
            return "/api/admin/refresh/status/{task_id}"
        
        return path


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding cache-related headers."""
    
    def __init__(self, app, enabled: bool = True):
        """Initialize cache headers middleware."""
        super().__init__(app)
        self.enabled = enabled
        
        # Cache control settings for different endpoints
        self.cache_settings = {
            "/api/launches": {"max_age": 1800, "public": True},  # 30 minutes
            "/api/launches/upcoming": {"max_age": 900, "public": True},  # 15 minutes
            "/api/launches/historical": {"max_age": 3600, "public": True},  # 1 hour
            "/api/launches/{slug}": {"max_age": 3600, "public": True},  # 1 hour
            "/health": {"max_age": 300, "public": True},  # 5 minutes
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add cache headers to response."""
        response = await call_next(request)
        
        if not self.enabled:
            return response
        
        # Only add cache headers for GET requests
        if request.method != "GET":
            return response
        
        # Get cache settings for endpoint
        endpoint = self._normalize_endpoint(request.url.path)
        cache_config = self.cache_settings.get(endpoint)
        
        if cache_config:
            max_age = cache_config["max_age"]
            is_public = cache_config["public"]
            
            # Set cache control header
            cache_control = f"max-age={max_age}"
            if is_public:
                cache_control += ", public"
            else:
                cache_control += ", private"
            
            response.headers["Cache-Control"] = cache_control
            
            # Add ETag for better caching
            if hasattr(response, 'body') and response.body:
                etag = f'"{hash(response.body)}"'
                response.headers["ETag"] = etag
            
            # Add Last-Modified header
            response.headers["Last-Modified"] = time.strftime(
                "%a, %d %b %Y %H:%M:%S GMT", 
                time.gmtime()
            )
        
        return response
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for cache settings."""
        if "?" in path:
            path = path.split("?")[0]
        
        if path.startswith("/api/launches/") and len(path.split("/")) > 3:
            return "/api/launches/{slug}"
        
        return path