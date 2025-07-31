"""
Unit tests for database connection utilities and session management.
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from src.database import (
    DatabaseConfig, 
    DatabaseManager, 
    get_database_manager, 
    get_db_session,
    init_database,
    close_database
)


class TestDatabaseConfig:
    """Test cases for DatabaseConfig class."""
    
    def test_init_with_database_url(self):
        """Test initialization with DATABASE_URL environment variable."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@host:5432/db'}):
            config = DatabaseConfig()
            assert config.database_url == 'postgresql://user:pass@host:5432/db'
    
    def test_init_with_postgres_scheme_conversion(self):
        """Test conversion of postgres:// to postgresql:// scheme."""
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://user:pass@host:5432/db'}):
            config = DatabaseConfig()
            assert config.database_url == 'postgresql://user:pass@host:5432/db'
    
    def test_init_with_individual_components(self):
        """Test initialization with individual database components."""
        env_vars = {
            'DB_HOST': 'testhost',
            'DB_PORT': '5433',
            'DB_NAME': 'testdb',
            'DB_USER': 'testuser',
            'DB_PASSWORD': 'testpass'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            config = DatabaseConfig()
            expected_url = 'postgresql://testuser:testpass@testhost:5433/testdb'
            assert config.database_url == expected_url
    
    def test_init_with_defaults(self):
        """Test initialization with default values."""
        with patch.dict(os.environ, {}, clear=True):
            config = DatabaseConfig()
            expected_url = 'postgresql://postgres:postgres@localhost:5432/spacex_tracker'
            assert config.database_url == expected_url
            assert config.echo is False
            assert config.pool_size == 10
            assert config.max_overflow == 20
            assert config.pool_timeout == 30
            assert config.pool_recycle == 3600
            assert config.pool_pre_ping is True
    
    def test_init_with_custom_pool_settings(self):
        """Test initialization with custom pool settings."""
        env_vars = {
            'DB_ECHO': 'true',
            'DB_POOL_SIZE': '5',
            'DB_MAX_OVERFLOW': '10',
            'DB_POOL_TIMEOUT': '60',
            'DB_POOL_RECYCLE': '7200',
            'DB_POOL_PRE_PING': 'false'
        }
        with patch.dict(os.environ, env_vars):
            config = DatabaseConfig()
            assert config.echo is True
            assert config.pool_size == 5
            assert config.max_overflow == 10
            assert config.pool_timeout == 60
            assert config.pool_recycle == 7200
            assert config.pool_pre_ping is False


class TestDatabaseManager:
    """Test cases for DatabaseManager class."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock database configuration."""
        config = Mock(spec=DatabaseConfig)
        config.database_url = 'sqlite:///:memory:'
        config.echo = False
        config.pool_size = 5
        config.max_overflow = 10
        config.pool_timeout = 30
        config.pool_recycle = 3600
        config.pool_pre_ping = True
        return config
    
    @pytest.fixture
    def db_manager(self, mock_config):
        """Create a DatabaseManager instance with mock config."""
        with patch('src.database.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            with patch('src.database.sessionmaker') as mock_sessionmaker:
                mock_session_factory = Mock()
                mock_sessionmaker.return_value = mock_session_factory
                
                with patch('src.database.event'):
                    manager = DatabaseManager(mock_config)
                    manager._engine = mock_engine
                    manager._session_factory = mock_session_factory
                    return manager
    
    def test_init_creates_engine_and_session_factory(self, mock_config):
        """Test that initialization creates engine and session factory."""
        with patch('src.database.create_engine') as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine
            
            with patch('src.database.sessionmaker') as mock_sessionmaker:
                mock_session_factory = Mock()
                mock_sessionmaker.return_value = mock_session_factory
                
                with patch('src.database.event'):
                    manager = DatabaseManager(mock_config)
                    
                    # Verify engine creation
                    mock_create_engine.assert_called_once()
                    args, kwargs = mock_create_engine.call_args
                    assert args[0] == mock_config.database_url
                    assert kwargs['echo'] == mock_config.echo
                    assert kwargs['pool_size'] == mock_config.pool_size
                    
                    # Verify session factory creation
                    mock_sessionmaker.assert_called_once()
                    session_kwargs = mock_sessionmaker.call_args[1]
                    assert session_kwargs['bind'] == mock_engine
                    assert session_kwargs['autocommit'] is False
                    assert session_kwargs['autoflush'] is False
                    assert session_kwargs['expire_on_commit'] is False
    
    def test_engine_property(self, db_manager):
        """Test engine property returns the engine."""
        assert db_manager.engine == db_manager._engine
    
    def test_engine_property_raises_when_not_initialized(self):
        """Test engine property raises when engine is not initialized."""
        manager = DatabaseManager.__new__(DatabaseManager)
        manager._engine = None
        
        with pytest.raises(RuntimeError, match="Database engine not initialized"):
            _ = manager.engine
    
    def test_get_session(self, db_manager):
        """Test get_session returns a new session."""
        mock_session = Mock(spec=Session)
        db_manager._session_factory.return_value = mock_session
        
        session = db_manager.get_session()
        
        assert session == mock_session
        db_manager._session_factory.assert_called_once()
    
    def test_get_session_raises_when_factory_not_initialized(self):
        """Test get_session raises when session factory is not initialized."""
        manager = DatabaseManager.__new__(DatabaseManager)
        manager._session_factory = None
        
        with pytest.raises(RuntimeError, match="Session factory not initialized"):
            manager.get_session()
    
    def test_session_scope_success(self, db_manager):
        """Test session_scope context manager with successful transaction."""
        mock_session = Mock(spec=Session)
        db_manager._session_factory.return_value = mock_session
        
        with db_manager.session_scope() as session:
            assert session == mock_session
        
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()
    
    def test_session_scope_with_exception(self, db_manager):
        """Test session_scope context manager with exception."""
        mock_session = Mock(spec=Session)
        db_manager._session_factory.return_value = mock_session
        
        with pytest.raises(ValueError):
            with db_manager.session_scope() as session:
                assert session == mock_session
                raise ValueError("Test exception")
        
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.commit.assert_not_called()
    
    def test_create_tables(self, db_manager):
        """Test create_tables method."""
        with patch('src.database.Base') as mock_base:
            mock_metadata = Mock()
            mock_base.metadata = mock_metadata
            
            db_manager.create_tables()
            
            mock_metadata.create_all.assert_called_once_with(bind=db_manager._engine)
    
    def test_create_tables_with_exception(self, db_manager):
        """Test create_tables method with exception."""
        with patch('src.database.Base') as mock_base:
            mock_metadata = Mock()
            mock_base.metadata = mock_metadata
            mock_metadata.create_all.side_effect = Exception("Database error")
            
            with pytest.raises(Exception, match="Database error"):
                db_manager.create_tables()
    
    def test_drop_tables(self, db_manager):
        """Test drop_tables method."""
        with patch('src.database.Base') as mock_base:
            mock_metadata = Mock()
            mock_base.metadata = mock_metadata
            
            db_manager.drop_tables()
            
            mock_metadata.drop_all.assert_called_once_with(bind=db_manager._engine)
    
    def test_check_connection_success(self, db_manager):
        """Test check_connection method with successful connection."""
        mock_session = Mock(spec=Session)
        db_manager._session_factory.return_value = mock_session
        
        result = db_manager.check_connection()
        
        assert result is True
        mock_session.execute.assert_called_once_with("SELECT 1")
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()
    
    def test_check_connection_failure(self, db_manager):
        """Test check_connection method with connection failure."""
        mock_session = Mock(spec=Session)
        mock_session.execute.side_effect = OperationalError("Connection failed", None, None)
        db_manager._session_factory.return_value = mock_session
        
        result = db_manager.check_connection()
        
        assert result is False
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
    
    def test_get_pool_status(self, db_manager):
        """Test get_pool_status method."""
        mock_pool = Mock()
        mock_pool.size.return_value = 10
        mock_pool.checkedin.return_value = 8
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 0
        mock_pool.invalid.return_value = 0
        db_manager._engine.pool = mock_pool
        
        status = db_manager.get_pool_status()
        
        expected_status = {
            'pool_size': 10,
            'checked_in': 8,
            'checked_out': 2,
            'overflow': 0,
            'invalid': 0
        }
        assert status == expected_status
    
    def test_get_pool_status_no_engine(self):
        """Test get_pool_status method when engine is not initialized."""
        manager = DatabaseManager.__new__(DatabaseManager)
        manager._engine = None
        
        status = manager.get_pool_status()
        
        assert status == {"error": "Engine not initialized"}
    
    def test_close(self, db_manager):
        """Test close method."""
        db_manager.close()
        
        db_manager._engine.dispose.assert_called_once()


class TestGlobalFunctions:
    """Test cases for global database functions."""
    
    def test_get_database_manager_singleton(self):
        """Test that get_database_manager returns singleton instance."""
        with patch('src.database.DatabaseManager') as mock_manager_class:
            mock_instance = Mock()
            mock_manager_class.return_value = mock_instance
            
            # Clear the global variable
            import src.database
            src.database._db_manager = None
            
            # First call should create instance
            manager1 = get_database_manager()
            assert manager1 == mock_instance
            mock_manager_class.assert_called_once()
            
            # Second call should return same instance
            manager2 = get_database_manager()
            assert manager2 == mock_instance
            assert manager1 is manager2
            # Should not create another instance
            mock_manager_class.assert_called_once()
    
    def test_get_db_session(self):
        """Test get_db_session dependency function."""
        with patch('src.database.get_database_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_session = Mock(spec=Session)
            
            # Create a proper context manager mock
            mock_context_manager = MagicMock()
            mock_context_manager.__enter__.return_value = mock_session
            mock_context_manager.__exit__.return_value = None
            mock_manager.session_scope.return_value = mock_context_manager
            mock_get_manager.return_value = mock_manager
            
            # Test the generator
            session_gen = get_db_session()
            session = next(session_gen)
            
            assert session == mock_session
            mock_get_manager.assert_called_once()
            mock_manager.session_scope.assert_called_once()
    
    def test_init_database(self):
        """Test init_database function."""
        with patch('src.database.get_database_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            
            init_database()
            
            mock_get_manager.assert_called_once()
            mock_manager.create_tables.assert_called_once()
    
    def test_close_database(self):
        """Test close_database function."""
        with patch('src.database.get_database_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_get_manager.return_value = mock_manager
            
            # Set up global manager
            import src.database
            src.database._db_manager = mock_manager
            
            close_database()
            
            mock_manager.close.assert_called_once()
            assert src.database._db_manager is None