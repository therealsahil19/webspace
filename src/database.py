"""
Database connection utilities and session management for SpaceX Launch Tracker.
"""
import os
import logging
from typing import Generator, Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from src.models.database import Base

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration class."""
    
    def __init__(self):
        """Initialize database configuration from environment variables."""
        self.database_url = self._get_database_url()
        self.echo = os.getenv("DB_ECHO", "false").lower() == "true"
        self.pool_size = int(os.getenv("DB_POOL_SIZE", "10"))
        self.max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "3600"))
        self.pool_pre_ping = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
    
    def _get_database_url(self) -> str:
        """Construct database URL from environment variables."""
        # Check for full DATABASE_URL first (common in production)
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Handle postgres:// vs postgresql:// scheme
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            return database_url
        
        # Construct from individual components
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "spacex_tracker")
        db_user = os.getenv("DB_USER", "postgres")
        db_password = os.getenv("DB_PASSWORD", "postgres")
        
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


class DatabaseManager:
    """Database connection and session manager."""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        """Initialize database manager with configuration."""
        self.config = config or DatabaseConfig()
        self._engine: Optional[Engine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._setup_engine()
        self._setup_session_factory()
    
    def _setup_engine(self) -> None:
        """Set up SQLAlchemy engine with connection pooling."""
        self._engine = create_engine(
            self.config.database_url,
            echo=self.config.echo,
            poolclass=QueuePool,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_recycle=self.config.pool_recycle,
            pool_pre_ping=self.config.pool_pre_ping,
            # Additional connection arguments for PostgreSQL
            connect_args={
                "options": "-c timezone=utc",
                "application_name": "spacex_launch_tracker"
            }
        )
        
        # Add event listeners for connection management
        self._setup_engine_events()
        
        logger.info(f"Database engine created with pool_size={self.config.pool_size}")
    
    def _setup_engine_events(self) -> None:
        """Set up SQLAlchemy engine event listeners."""
        
        @event.listens_for(self._engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set connection-level settings for PostgreSQL."""
            # This is primarily for PostgreSQL, but we keep it generic
            pass
        
        @event.listens_for(self._engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log when a connection is checked out from the pool."""
            logger.debug("Connection checked out from pool")
        
        @event.listens_for(self._engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Log when a connection is returned to the pool."""
            logger.debug("Connection returned to pool")
    
    def _setup_session_factory(self) -> None:
        """Set up SQLAlchemy session factory."""
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        logger.info("Database session factory created")
    
    @property
    def engine(self) -> Engine:
        """Get the SQLAlchemy engine."""
        if self._engine is None:
            raise RuntimeError("Database engine not initialized")
        return self._engine
    
    def get_session(self) -> Session:
        """Get a new database session."""
        if self._session_factory is None:
            raise RuntimeError("Session factory not initialized")
        return self._session_factory()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def create_tables(self) -> None:
        """Create all database tables."""
        try:
            Base.metadata.create_all(bind=self._engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def drop_tables(self) -> None:
        """Drop all database tables (use with caution)."""
        try:
            Base.metadata.drop_all(bind=self._engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Error dropping database tables: {e}")
            raise
    
    def check_connection(self) -> bool:
        """Check if database connection is working."""
        try:
            with self.session_scope() as session:
                session.execute("SELECT 1")
            logger.info("Database connection check successful")
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    def get_pool_status(self) -> dict:
        """Get connection pool status information."""
        if self._engine is None:
            return {"error": "Engine not initialized"}
        
        pool = self._engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.invalid()
        }
    
    def close(self) -> None:
        """Close all database connections and dispose of the engine."""
        if self._engine:
            self._engine.dispose()
            logger.info("Database engine disposed")


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db_session() -> Session:
    """Get a database session."""
    db_manager = get_database_manager()
    return db_manager.get_session()


def init_database() -> None:
    """Initialize the database with tables."""
    db_manager = get_database_manager()
    db_manager.create_tables()


def close_database() -> None:
    """Close database connections."""
    global _db_manager
    if _db_manager:
        _db_manager.close()
        _db_manager = None


def close_database_connections() -> None:
    """Alias for close_database for compatibility."""
    close_database()