"""
Comprehensive logging configuration for SpaceX Launch Tracker.
Implements structured logging using structlog with proper formatting and filtering.
"""

import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

import structlog
from structlog.types import FilteringBoundLogger


class LogConfig:
    """Configuration class for logging setup."""
    
    def __init__(self):
        self.log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.log_dir = Path(os.getenv('LOG_DIR', 'logs'))
        self.log_format = os.getenv('LOG_FORMAT', 'json')  # json or console
        self.enable_file_logging = os.getenv('ENABLE_FILE_LOGGING', 'true').lower() == 'true'
        self.max_log_size = int(os.getenv('MAX_LOG_SIZE_MB', '100')) * 1024 * 1024  # 100MB default
        self.backup_count = int(os.getenv('LOG_BACKUP_COUNT', '5'))
        self.enable_sentry = os.getenv('ENABLE_SENTRY', 'false').lower() == 'true'
        self.sentry_dsn = os.getenv('SENTRY_DSN')
        self.environment = os.getenv('ENVIRONMENT', 'development')
        
        # Create log directory if it doesn't exist
        if self.enable_file_logging:
            self.log_dir.mkdir(exist_ok=True)


def add_timestamp(logger: FilteringBoundLogger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add timestamp to log events."""
    event_dict["timestamp"] = datetime.utcnow().isoformat() + "Z"
    return event_dict


def add_log_level(logger: FilteringBoundLogger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add log level to event dict."""
    event_dict["level"] = method_name.upper()
    return event_dict


def add_logger_name(logger: FilteringBoundLogger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add logger name to event dict."""
    if hasattr(logger, '_context') and 'logger' in logger._context:
        event_dict["logger"] = logger._context['logger']
    return event_dict


def add_service_context(logger: FilteringBoundLogger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add service context information."""
    event_dict["service"] = "spacex-launch-tracker"
    event_dict["component"] = event_dict.get("component", "unknown")
    return event_dict


def filter_sensitive_data(logger: FilteringBoundLogger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Filter out sensitive data from logs."""
    sensitive_keys = ['password', 'token', 'secret', 'key', 'authorization']
    
    def _filter_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        filtered = {}
        for k, v in d.items():
            if any(sensitive in k.lower() for sensitive in sensitive_keys):
                filtered[k] = "[REDACTED]"
            elif isinstance(v, dict):
                filtered[k] = _filter_dict(v)
            else:
                filtered[k] = v
        return filtered
    
    return _filter_dict(event_dict)


def setup_logging(config: Optional[LogConfig] = None) -> None:
    """
    Set up comprehensive logging configuration.
    
    Args:
        config: LogConfig instance, creates default if None
    """
    if config is None:
        config = LogConfig()
    
    # Configure standard library logging
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(message)s",
        stream=sys.stdout,
    )
    
    # Set up processors based on format
    processors = [
        add_timestamp,
        add_log_level,
        add_logger_name,
        add_service_context,
        filter_sensitive_data,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if config.log_format == 'json':
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True),
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Set up file logging if enabled
    if config.enable_file_logging:
        setup_file_logging(config)
    
    # Set up Sentry if enabled
    if config.enable_sentry and config.sentry_dsn:
        setup_sentry_logging(config)
    
    # Configure third-party loggers
    configure_third_party_loggers(config)


def setup_file_logging(config: LogConfig) -> None:
    """Set up file-based logging with rotation."""
    # Main application log
    app_log_file = config.log_dir / "spacex_tracker.log"
    app_handler = logging.handlers.RotatingFileHandler(
        app_log_file,
        maxBytes=config.max_log_size,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    app_handler.setLevel(getattr(logging, config.log_level))
    
    # Error log (only errors and above)
    error_log_file = config.log_dir / "errors.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=config.max_log_size,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    
    # Scraping log (for scraping-specific events)
    scraping_log_file = config.log_dir / "scraping.log"
    scraping_handler = logging.handlers.RotatingFileHandler(
        scraping_log_file,
        maxBytes=config.max_log_size,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    scraping_handler.setLevel(logging.INFO)
    
    # API log (for API-specific events)
    api_log_file = config.log_dir / "api.log"
    api_handler = logging.handlers.RotatingFileHandler(
        api_log_file,
        maxBytes=config.max_log_size,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    api_handler.setLevel(logging.INFO)
    
    # Add handlers to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    
    # Add specific handlers for component loggers
    scraping_logger = logging.getLogger('src.scraping')
    scraping_logger.addHandler(scraping_handler)
    
    api_logger = logging.getLogger('src.api')
    api_logger.addHandler(api_handler)


def setup_sentry_logging(config: LogConfig) -> None:
    """Set up Sentry error tracking integration."""
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        
        sentry_logging = LoggingIntegration(
            level=logging.INFO,        # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors and above as events
        )
        
        sentry_sdk.init(
            dsn=config.sentry_dsn,
            environment=config.environment,
            integrations=[
                sentry_logging,
                SqlalchemyIntegration(),
                FastApiIntegration(auto_enabling_integrations=False),
                CeleryIntegration(),
            ],
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            send_default_pii=False,  # Don't send personally identifiable information
            attach_stacktrace=True,
            before_send=filter_sentry_events,
        )
        
        logger = structlog.get_logger("logging_config")
        logger.info("Sentry error tracking initialized", environment=config.environment)
        
    except ImportError:
        logger = structlog.get_logger("logging_config")
        logger.warning("Sentry SDK not available, error tracking disabled")


def filter_sentry_events(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Filter Sentry events to reduce noise."""
    # Don't send certain types of errors to Sentry
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']
        
        # Skip common HTTP errors
        if exc_type.__name__ in ['HTTPException', 'ValidationError']:
            return None
        
        # Skip connection errors during scraping (expected)
        if 'connection' in str(exc_value).lower() or 'timeout' in str(exc_value).lower():
            return None
    
    return event


def configure_third_party_loggers(config: LogConfig) -> None:
    """Configure logging levels for third-party libraries."""
    # Reduce noise from third-party libraries
    third_party_loggers = {
        'urllib3': logging.WARNING,
        'requests': logging.WARNING,
        'aiohttp': logging.WARNING,
        'playwright': logging.WARNING,
        'celery': logging.INFO,
        'sqlalchemy.engine': logging.WARNING,
        'sqlalchemy.pool': logging.WARNING,
        'redis': logging.WARNING,
    }
    
    for logger_name, level in third_party_loggers.items():
        logging.getLogger(logger_name).setLevel(level)


def get_logger(name: str, component: Optional[str] = None) -> FilteringBoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        component: Component name for categorization
        
    Returns:
        Configured structlog logger
    """
    logger = structlog.get_logger(name)
    
    if component:
        logger = logger.bind(component=component)
    
    return logger


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = get_logger(
            self.__class__.__module__,
            component=self.__class__.__name__.lower()
        )


# Context managers for structured logging
class LogContext:
    """Context manager for adding structured context to logs."""
    
    def __init__(self, logger: FilteringBoundLogger, **context):
        self.logger = logger
        self.context = context
        self.bound_logger = None
    
    def __enter__(self) -> FilteringBoundLogger:
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.bound_logger.error(
                "Exception in log context",
                exc_type=exc_type.__name__,
                exc_value=str(exc_val)
            )


class TimedOperation:
    """Context manager for timing operations with logging."""
    
    def __init__(self, logger: FilteringBoundLogger, operation_name: str, **context):
        self.logger = logger
        self.operation_name = operation_name
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.utcnow()
        self.logger.info(
            f"Starting {self.operation_name}",
            operation=self.operation_name,
            **self.context
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        
        if exc_type:
            self.logger.error(
                f"Failed {self.operation_name}",
                operation=self.operation_name,
                duration_seconds=duration,
                exc_type=exc_type.__name__,
                exc_value=str(exc_val),
                **self.context
            )
        else:
            self.logger.info(
                f"Completed {self.operation_name}",
                operation=self.operation_name,
                duration_seconds=duration,
                **self.context
            )


# Utility functions for common logging patterns
def log_function_call(logger: FilteringBoundLogger):
    """Decorator to log function calls with parameters and results."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.debug(
                f"Calling {func_name}",
                function=func_name,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )
            
            try:
                result = func(*args, **kwargs)
                logger.debug(
                    f"Completed {func_name}",
                    function=func_name,
                    success=True
                )
                return result
            except Exception as e:
                logger.error(
                    f"Failed {func_name}",
                    function=func_name,
                    error=str(e),
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


def log_async_function_call(logger: FilteringBoundLogger):
    """Decorator to log async function calls with parameters and results."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            func_name = func.__name__
            logger.debug(
                f"Calling async {func_name}",
                function=func_name,
                args_count=len(args),
                kwargs_keys=list(kwargs.keys())
            )
            
            try:
                result = await func(*args, **kwargs)
                logger.debug(
                    f"Completed async {func_name}",
                    function=func_name,
                    success=True
                )
                return result
            except Exception as e:
                logger.error(
                    f"Failed async {func_name}",
                    function=func_name,
                    error=str(e),
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


# Initialize logging on module import
if not os.getenv('SKIP_LOGGING_INIT'):
    setup_logging()