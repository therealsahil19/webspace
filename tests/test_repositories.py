"""
Integration tests for repository operations.
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.models.database import Base, Launch, LaunchSource, DataConflict
from src.models.schemas import LaunchData, SourceData, ConflictData, LaunchStatus
from src.repositories import (
    LaunchRepository, 
    SourceRepository, 
    ConflictRepository,
    RepositoryManager
)
from src.database import DatabaseManager, DatabaseConfig


class TestDatabaseConfig:
    """Test database configuration for in-memory SQLite."""
    
    def __init__(self):
        self.database_url = "sqlite:///:memory:"
        self.echo = False
        self.pool_size = 1
        self.max_overflow = 0
        self.pool_timeout = 30
        self.pool_recycle = 3600
        self.pool_pre_ping = False


@pytest.fixture
def test_engine():
    """Create test database engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_db_manager(test_engine):
    """Create test database manager."""
    config = TestDatabaseConfig()
    db_manager = DatabaseManager(config)
    db_manager._engine = test_engine
    db_manager._setup_session_factory()
    return db_manager


@pytest.fixture
def sample_launch_data():
    """Create sample launch data for testing."""
    return LaunchData(
        slug="falcon-heavy-demo",
        mission_name="Falcon Heavy Demo",
        launch_date=datetime(2024, 6, 15, 14, 30, 0, tzinfo=timezone.utc),
        vehicle_type="Falcon Heavy",
        payload_mass=1420.0,
        orbit="Heliocentric",
        status=LaunchStatus.SUCCESS,
        details="Demonstration flight of Falcon Heavy rocket",
        mission_patch_url="https://example.com/patch.png",
        webcast_url="https://example.com/webcast"
    )


@pytest.fixture
def sample_source_data():
    """Create sample source data for testing."""
    return [
        SourceData(
            source_name="spacex_website",
            source_url="https://spacex.com/launches",
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.95
        ),
        SourceData(
            source_name="nasa_website",
            source_url="https://nasa.gov/launches",
            scraped_at=datetime.now(timezone.utc),
            data_quality_score=0.85
        )
    ]


@pytest.fixture
def sample_conflict_data():
    """Create sample conflict data for testing."""
    return [
        ConflictData(
            field_name="payload_mass",
            source1_value="1420.0",
            source2_value="1400.0",
            confidence_score=0.8
        ),
        ConflictData(
            field_name="launch_date",
            source1_value="2024-06-15T14:30:00Z",
            source2_value="2024-06-15T14:35:00Z",
            confidence_score=0.9
        )
    ]


class TestLaunchRepository:
    """Test cases for LaunchRepository."""
    
    def test_create_launch(self, test_session, sample_launch_data):
        """Test creating a new launch."""
        repo = LaunchRepository(test_session)
        
        launch = repo.create(sample_launch_data)
        
        assert launch.id is not None
        assert launch.slug == sample_launch_data.slug
        assert launch.mission_name == sample_launch_data.mission_name
        assert launch.status == sample_launch_data.status
    
    def test_get_launch_by_slug(self, test_session, sample_launch_data):
        """Test retrieving launch by slug."""
        repo = LaunchRepository(test_session)
        
        # Create launch
        created_launch = repo.create(sample_launch_data)
        test_session.commit()
        
        # Retrieve by slug
        retrieved_launch = repo.get_by_slug(sample_launch_data.slug)
        
        assert retrieved_launch is not None
        assert retrieved_launch.id == created_launch.id
        assert retrieved_launch.slug == sample_launch_data.slug
    
    def test_upsert_launch_create(self, test_session, sample_launch_data):
        """Test upsert operation creating new launch."""
        repo = LaunchRepository(test_session)
        
        launch, was_created = repo.upsert_launch(sample_launch_data)
        test_session.commit()
        
        assert was_created is True
        assert launch.slug == sample_launch_data.slug
        assert launch.mission_name == sample_launch_data.mission_name
    
    def test_upsert_launch_update(self, test_session, sample_launch_data):
        """Test upsert operation updating existing launch."""
        repo = LaunchRepository(test_session)
        
        # Create initial launch
        repo.create(sample_launch_data)
        test_session.commit()
        
        # Update with upsert
        updated_data = sample_launch_data.copy()
        updated_data.mission_name = "Updated Mission Name"
        
        launch, was_created = repo.upsert_launch(updated_data)
        test_session.commit()
        
        assert was_created is False
        assert launch.mission_name == "Updated Mission Name"
    
    def test_get_upcoming_launches(self, test_session):
        """Test retrieving upcoming launches."""
        repo = LaunchRepository(test_session)
        
        # Create upcoming launch
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        upcoming_launch = LaunchData(
            slug="upcoming-mission",
            mission_name="Upcoming Mission",
            launch_date=future_date,
            vehicle_type="Falcon 9",
            status=LaunchStatus.UPCOMING
        )
        repo.create(upcoming_launch)
        
        # Create past launch
        past_date = datetime.now(timezone.utc) - timedelta(days=30)
        past_launch = LaunchData(
            slug="past-mission",
            mission_name="Past Mission",
            launch_date=past_date,
            vehicle_type="Falcon 9",
            status=LaunchStatus.SUCCESS
        )
        repo.create(past_launch)
        
        test_session.commit()
        
        upcoming = repo.get_upcoming_launches()
        
        assert len(upcoming) == 1
        assert upcoming[0].slug == "upcoming-mission"
    
    def test_search_launches(self, test_session, sample_launch_data):
        """Test searching launches by mission name."""
        repo = LaunchRepository(test_session)
        
        repo.create(sample_launch_data)
        test_session.commit()
        
        results = repo.search_launches("Falcon Heavy")
        
        assert len(results) == 1
        assert results[0].slug == sample_launch_data.slug
    
    def test_batch_upsert_launches(self, test_session):
        """Test batch upsert of multiple launches."""
        repo = LaunchRepository(test_session)
        
        launches = [
            LaunchData(
                slug=f"mission-{i}",
                mission_name=f"Mission {i}",
                vehicle_type="Falcon 9",
                status=LaunchStatus.UPCOMING
            )
            for i in range(3)
        ]
        
        result = repo.batch_upsert_launches(launches)
        test_session.commit()
        
        assert result['created'] == 3
        assert result['updated'] == 0
        assert result['total'] == 3
    
    def test_get_launch_statistics(self, test_session):
        """Test getting launch statistics."""
        repo = LaunchRepository(test_session)
        
        # Create test launches
        launches = [
            LaunchData(slug="success-1", mission_name="Success 1", vehicle_type="Falcon 9", status=LaunchStatus.SUCCESS),
            LaunchData(slug="success-2", mission_name="Success 2", vehicle_type="Falcon 9", status=LaunchStatus.SUCCESS),
            LaunchData(slug="failure-1", mission_name="Failure 1", vehicle_type="Falcon 9", status=LaunchStatus.FAILURE),
            LaunchData(slug="upcoming-1", mission_name="Upcoming 1", vehicle_type="Falcon Heavy", status=LaunchStatus.UPCOMING),
        ]
        
        for launch in launches:
            repo.create(launch)
        test_session.commit()
        
        stats = repo.get_launch_statistics()
        
        assert stats['total_launches'] == 4
        assert stats['successful_launches'] == 2
        assert stats['failed_launches'] == 1
        assert stats['upcoming_launches'] == 1
        assert 'Falcon 9' in stats['vehicle_distribution']
        assert 'Falcon Heavy' in stats['vehicle_distribution']


class TestSourceRepository:
    """Test cases for SourceRepository."""
    
    def test_create_source_for_launch(self, test_session, sample_launch_data, sample_source_data):
        """Test creating source for a launch."""
        launch_repo = LaunchRepository(test_session)
        source_repo = SourceRepository(test_session)
        
        # Create launch first
        launch = launch_repo.create(sample_launch_data)
        test_session.flush()
        
        # Create source
        source = source_repo.create_source_for_launch(launch.id, sample_source_data[0])
        test_session.commit()
        
        assert source.id is not None
        assert source.launch_id == launch.id
        assert source.source_name == sample_source_data[0].source_name
    
    def test_get_sources_for_launch(self, test_session, sample_launch_data, sample_source_data):
        """Test retrieving sources for a launch."""
        launch_repo = LaunchRepository(test_session)
        source_repo = SourceRepository(test_session)
        
        # Create launch
        launch = launch_repo.create(sample_launch_data)
        test_session.flush()
        
        # Create sources
        for source_data in sample_source_data:
            source_repo.create_source_for_launch(launch.id, source_data)
        test_session.commit()
        
        sources = source_repo.get_sources_for_launch(launch.id)
        
        assert len(sources) == 2
        assert all(s.launch_id == launch.id for s in sources)
    
    def test_batch_create_sources(self, test_session, sample_launch_data, sample_source_data):
        """Test batch creation of sources."""
        launch_repo = LaunchRepository(test_session)
        source_repo = SourceRepository(test_session)
        
        # Create launch
        launch = launch_repo.create(sample_launch_data)
        test_session.flush()
        
        # Batch create sources
        sources = source_repo.batch_create_sources(launch.id, sample_source_data)
        test_session.commit()
        
        assert len(sources) == 2
        assert all(s.launch_id == launch.id for s in sources)
    
    def test_get_source_quality_stats(self, test_session, sample_launch_data, sample_source_data):
        """Test getting source quality statistics."""
        launch_repo = LaunchRepository(test_session)
        source_repo = SourceRepository(test_session)
        
        # Create launch and sources
        launch = launch_repo.create(sample_launch_data)
        test_session.flush()
        
        source_repo.batch_create_sources(launch.id, sample_source_data)
        test_session.commit()
        
        stats = source_repo.get_source_quality_stats()
        
        assert 'overall' in stats
        assert 'by_source' in stats
        assert stats['overall']['total_sources'] == 2
        assert 'spacex_website' in stats['by_source']
        assert 'nasa_website' in stats['by_source']


class TestConflictRepository:
    """Test cases for ConflictRepository."""
    
    def test_create_conflict_for_launch(self, test_session, sample_launch_data, sample_conflict_data):
        """Test creating conflict for a launch."""
        launch_repo = LaunchRepository(test_session)
        conflict_repo = ConflictRepository(test_session)
        
        # Create launch first
        launch = launch_repo.create(sample_launch_data)
        test_session.flush()
        
        # Create conflict
        conflict = conflict_repo.create_conflict_for_launch(launch.id, sample_conflict_data[0])
        test_session.commit()
        
        assert conflict.id is not None
        assert conflict.launch_id == launch.id
        assert conflict.field_name == sample_conflict_data[0].field_name
        assert conflict.resolved is False
    
    def test_get_conflicts_for_launch(self, test_session, sample_launch_data, sample_conflict_data):
        """Test retrieving conflicts for a launch."""
        launch_repo = LaunchRepository(test_session)
        conflict_repo = ConflictRepository(test_session)
        
        # Create launch
        launch = launch_repo.create(sample_launch_data)
        test_session.flush()
        
        # Create conflicts
        for conflict_data in sample_conflict_data:
            conflict_repo.create_conflict_for_launch(launch.id, conflict_data)
        test_session.commit()
        
        conflicts = conflict_repo.get_conflicts_for_launch(launch.id)
        
        assert len(conflicts) == 2
        assert all(c.launch_id == launch.id for c in conflicts)
    
    def test_resolve_conflict(self, test_session, sample_launch_data, sample_conflict_data):
        """Test resolving a conflict."""
        launch_repo = LaunchRepository(test_session)
        conflict_repo = ConflictRepository(test_session)
        
        # Create launch and conflict
        launch = launch_repo.create(sample_launch_data)
        test_session.flush()
        
        conflict = conflict_repo.create_conflict_for_launch(launch.id, sample_conflict_data[0])
        test_session.commit()
        
        # Resolve conflict
        resolved_conflict = conflict_repo.resolve_conflict(conflict.id)
        test_session.commit()
        
        assert resolved_conflict.resolved is True
        assert resolved_conflict.resolved_at is not None
    
    def test_batch_create_conflicts(self, test_session, sample_launch_data, sample_conflict_data):
        """Test batch creation of conflicts."""
        launch_repo = LaunchRepository(test_session)
        conflict_repo = ConflictRepository(test_session)
        
        # Create launch
        launch = launch_repo.create(sample_launch_data)
        test_session.flush()
        
        # Batch create conflicts
        conflicts = conflict_repo.batch_create_conflicts(launch.id, sample_conflict_data)
        test_session.commit()
        
        assert len(conflicts) == 2
        assert all(c.launch_id == launch.id for c in conflicts)
    
    def test_get_conflict_statistics(self, test_session, sample_launch_data, sample_conflict_data):
        """Test getting conflict statistics."""
        launch_repo = LaunchRepository(test_session)
        conflict_repo = ConflictRepository(test_session)
        
        # Create launch and conflicts
        launch = launch_repo.create(sample_launch_data)
        test_session.flush()
        
        conflict_repo.batch_create_conflicts(launch.id, sample_conflict_data)
        test_session.commit()
        
        stats = conflict_repo.get_conflict_statistics()
        
        assert stats['total_conflicts'] == 2
        assert stats['unresolved_conflicts'] == 2
        assert stats['resolved_conflicts'] == 0
        assert 'by_field' in stats


class TestRepositoryManager:
    """Test cases for RepositoryManager."""
    
    def test_process_launch_with_sources_and_conflicts(
        self, 
        test_db_manager, 
        sample_launch_data, 
        sample_source_data, 
        sample_conflict_data
    ):
        """Test processing complete launch with sources and conflicts."""
        repo_manager = RepositoryManager(test_db_manager)
        
        result = repo_manager.process_launch_with_sources_and_conflicts(
            sample_launch_data,
            sample_source_data,
            sample_conflict_data
        )
        
        assert result['launch']['slug'] == sample_launch_data.slug
        assert result['launch']['was_created'] is True
        assert result['sources_created'] == 2
        assert result['conflicts_created'] == 2
    
    def test_batch_process_launches(
        self, 
        test_db_manager, 
        sample_source_data
    ):
        """Test batch processing of multiple launches."""
        repo_manager = RepositoryManager(test_db_manager)
        
        # Create multiple launch data sets
        launch_data_list = []
        for i in range(3):
            launch_data = LaunchData(
                slug=f"batch-mission-{i}",
                mission_name=f"Batch Mission {i}",
                vehicle_type="Falcon 9",
                status=LaunchStatus.UPCOMING
            )
            launch_data_list.append((launch_data, sample_source_data, None))
        
        result = repo_manager.batch_process_launches(launch_data_list)
        
        assert result['launches_created'] == 3
        assert result['launches_updated'] == 0
        assert result['total_sources_created'] == 6  # 3 launches * 2 sources each
        assert len(result['processed_launches']) == 3
    
    def test_get_system_health_stats(self, test_db_manager, sample_launch_data):
        """Test getting system health statistics."""
        repo_manager = RepositoryManager(test_db_manager)
        
        # Create some test data
        with repo_manager.transaction():
            repo_manager.launches.create(sample_launch_data)
        
        stats = repo_manager.get_system_health_stats()
        
        assert 'launches' in stats
        assert 'sources' in stats
        assert 'conflicts' in stats
        assert 'database_pool' in stats
    
    def test_transaction_rollback_on_error(self, test_db_manager):
        """Test that transactions are rolled back on errors."""
        repo_manager = RepositoryManager(test_db_manager)
        
        with pytest.raises(Exception):
            with repo_manager.transaction():
                # Create a launch
                launch_data = LaunchData(
                    slug="test-rollback",
                    mission_name="Test Rollback",
                    vehicle_type="Falcon 9",
                    status=LaunchStatus.UPCOMING
                )
                repo_manager.launches.create(launch_data)
                
                # Force an error
                raise Exception("Test error")
        
        # Verify the launch was not saved due to rollback
        with repo_manager.transaction():
            launch = repo_manager.launches.get_by_slug("test-rollback")
            assert launch is None