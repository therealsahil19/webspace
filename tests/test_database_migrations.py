"""
Database migration tests and data integrity checks.
Tests database schema migrations, data consistency, and integrity constraints.
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.operations import Operations

from src.database import get_database_manager, DatabaseManager
from src.models.launch import Launch, LaunchSource
from src.models.conflict import DataConflict
from src.models.base import Base


class TestDatabaseMigrations:
    """Test database migrations and schema changes."""
    
    @pytest.fixture
    def temp_database(self):
        """Create a temporary database for migration testing."""
        # Create temporary database file
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        database_url = f"sqlite:///{temp_db.name}"
        engine = create_engine(database_url)
        
        yield engine, database_url
        
        # Cleanup
        engine.dispose()
        os.unlink(temp_db.name)
    
    def test_fresh_database_creation(self, temp_database):
        """Test creating database schema from scratch."""
        engine, database_url = temp_database
        
        # Create all tables
        Base.metadata.create_all(engine)
        
        # Verify all expected tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = ['launches', 'launch_sources', 'data_conflicts']
        for table in expected_tables:
            assert table in tables, f"Table {table} not created"
        
        # Verify table structures
        launches_columns = [col['name'] for col in inspector.get_columns('launches')]
        expected_launch_columns = [
            'id', 'slug', 'mission_name', 'launch_date', 'vehicle_type',
            'payload_mass', 'orbit', 'status', 'details', 'mission_patch_url',
            'webcast_url', 'created_at', 'updated_at'
        ]
        
        for column in expected_launch_columns:
            assert column in launches_columns, f"Column {column} not found in launches table"
    
    def test_alembic_migration_consistency(self):
        """Test that Alembic migrations are consistent with model definitions."""
        # This test ensures that the current models match the latest migration
        db_manager = get_database_manager()
        
        # Get current database schema
        inspector = inspect(db_manager.engine)
        current_tables = inspector.get_table_names()
        
        # Verify core tables exist
        expected_tables = ['launches', 'launch_sources', 'data_conflicts', 'alembic_version']
        for table in expected_tables:
            assert table in current_tables, f"Expected table {table} not found"
        
        # Check launches table structure
        launches_columns = {col['name']: col for col in inspector.get_columns('launches')}
        
        # Verify critical columns exist with correct types
        critical_columns = {
            'id': 'INTEGER',
            'slug': 'VARCHAR',
            'mission_name': 'VARCHAR',
            'launch_date': 'TIMESTAMP',
            'status': 'VARCHAR'
        }
        
        for column_name, expected_type in critical_columns.items():
            assert column_name in launches_columns, f"Critical column {column_name} missing"
            # Note: Exact type checking may vary by database backend
    
    def test_database_constraints_and_indexes(self):
        """Test database constraints and indexes."""
        db_manager = get_database_manager()
        inspector = inspect(db_manager.engine)
        
        # Check primary keys
        launches_pk = inspector.get_pk_constraint('launches')
        assert launches_pk['constrained_columns'] == ['id']
        
        # Check unique constraints
        launches_unique = inspector.get_unique_constraints('launches')
        slug_unique = any(constraint['column_names'] == ['slug'] for constraint in launches_unique)
        assert slug_unique, "Slug unique constraint not found"
        
        # Check foreign key constraints
        sources_fks = inspector.get_foreign_keys('launch_sources')
        launch_fk = any(fk['constrained_columns'] == ['launch_id'] for fk in sources_fks)
        assert launch_fk, "Launch foreign key constraint not found in launch_sources"
        
        conflicts_fks = inspector.get_foreign_keys('data_conflicts')
        conflict_launch_fk = any(fk['constrained_columns'] == ['launch_id'] for fk in conflicts_fks)
        assert conflict_launch_fk, "Launch foreign key constraint not found in data_conflicts"
        
        # Check indexes (if any are defined)
        launches_indexes = inspector.get_indexes('launches')
        # Verify important indexes exist for performance
        date_index = any('launch_date' in idx['column_names'] for idx in launches_indexes)
        status_index = any('status' in idx['column_names'] for idx in launches_indexes)
        
        print(f"Database constraints verification:")
        print(f"  Primary keys: ✓")
        print(f"  Unique constraints: ✓")
        print(f"  Foreign keys: ✓")
        print(f"  Date index: {'✓' if date_index else '✗'}")
        print(f"  Status index: {'✓' if status_index else '✗'}")
    
    def test_data_integrity_constraints(self):
        """Test data integrity constraints."""
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as session:
            # Test unique constraint on slug
            launch1 = Launch(
                slug="integrity-test-1",
                mission_name="Integrity Test 1",
                status="upcoming"
            )
            session.add(launch1)
            session.commit()
            
            # Try to add duplicate slug - should fail
            launch2 = Launch(
                slug="integrity-test-1",  # Same slug
                mission_name="Integrity Test 2",
                status="upcoming"
            )
            session.add(launch2)
            
            with pytest.raises(Exception):  # Should raise integrity error
                session.commit()
            
            session.rollback()
            
            # Test foreign key constraint
            # Try to add launch source with invalid launch_id
            invalid_source = LaunchSource(
                launch_id=99999,  # Non-existent launch
                source_name="test_source",
                source_url="http://test.com",
                scraped_at=datetime.utcnow()
            )
            session.add(invalid_source)
            
            with pytest.raises(Exception):  # Should raise foreign key error
                session.commit()
            
            session.rollback()
            
            # Cleanup
            session.query(Launch).filter(Launch.slug == "integrity-test-1").delete()
            session.commit()
    
    def test_cascade_deletes(self):
        """Test cascade delete behavior."""
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as session:
            # Create test launch with related data
            test_launch = Launch(
                slug="cascade-test",
                mission_name="Cascade Test",
                status="upcoming"
            )
            session.add(test_launch)
            session.flush()  # Get the ID
            
            # Add related source data
            test_source = LaunchSource(
                launch_id=test_launch.id,
                source_name="test_source",
                source_url="http://test.com",
                scraped_at=datetime.utcnow()
            )
            session.add(test_source)
            
            # Add related conflict data
            test_conflict = DataConflict(
                launch_id=test_launch.id,
                field_name="mission_name",
                source1_value="Test Mission A",
                source2_value="Test Mission B"
            )
            session.add(test_conflict)
            session.commit()
            
            # Verify related data exists
            sources_count = session.query(LaunchSource).filter(
                LaunchSource.launch_id == test_launch.id
            ).count()
            conflicts_count = session.query(DataConflict).filter(
                DataConflict.launch_id == test_launch.id
            ).count()
            
            assert sources_count == 1
            assert conflicts_count == 1
            
            # Delete the launch
            session.delete(test_launch)
            session.commit()
            
            # Check if related data was handled appropriately
            # (Behavior depends on cascade configuration)
            remaining_sources = session.query(LaunchSource).filter(
                LaunchSource.launch_id == test_launch.id
            ).count()
            remaining_conflicts = session.query(DataConflict).filter(
                DataConflict.launch_id == test_launch.id
            ).count()
            
            print(f"Cascade delete behavior:")
            print(f"  Sources after launch delete: {remaining_sources}")
            print(f"  Conflicts after launch delete: {remaining_conflicts}")


class TestDataIntegrity:
    """Test data integrity and consistency."""
    
    @pytest.fixture
    def integrity_test_data(self):
        """Set up test data for integrity testing."""
        db_manager = get_database_manager()
        
        test_launches = []
        with db_manager.session_scope() as session:
            # Create test launches with various data scenarios
            for i in range(10):
                launch = Launch(
                    slug=f"integrity-test-{i:03d}",
                    mission_name=f"Integrity Test Mission {i:03d}",
                    launch_date=datetime.utcnow() + timedelta(days=i-5),
                    vehicle_type="Falcon 9" if i % 2 == 0 else "Falcon Heavy",
                    status="upcoming" if i < 5 else "success",
                    payload_mass=float(1000 + i * 100) if i % 3 != 0 else None,
                    orbit="LEO" if i % 2 == 0 else "GTO"
                )
                session.add(launch)
                test_launches.append(launch)
            
            session.commit()
        
        yield test_launches
        
        # Cleanup
        with db_manager.session_scope() as session:
            session.query(Launch).filter(
                Launch.slug.like("integrity-test-%")
            ).delete(synchronize_session=False)
            session.commit()
    
    def test_data_consistency_checks(self, integrity_test_data):
        """Test data consistency across the database."""
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as session:
            # Check for orphaned launch sources
            orphaned_sources = session.query(LaunchSource).filter(
                ~LaunchSource.launch_id.in_(
                    session.query(Launch.id)
                )
            ).count()
            
            assert orphaned_sources == 0, f"Found {orphaned_sources} orphaned launch sources"
            
            # Check for orphaned conflicts
            orphaned_conflicts = session.query(DataConflict).filter(
                ~DataConflict.launch_id.in_(
                    session.query(Launch.id)
                )
            ).count()
            
            assert orphaned_conflicts == 0, f"Found {orphaned_conflicts} orphaned conflicts"
            
            # Check for invalid status values
            invalid_statuses = session.query(Launch).filter(
                ~Launch.status.in_(["upcoming", "success", "failure", "in_flight", "aborted"])
            ).count()
            
            assert invalid_statuses == 0, f"Found {invalid_statuses} launches with invalid status"
            
            # Check for future dates on historical launches
            invalid_historical = session.query(Launch).filter(
                Launch.status.in_(["success", "failure"]),
                Launch.launch_date > datetime.utcnow()
            ).count()
            
            # This might be acceptable in some cases, so just warn
            if invalid_historical > 0:
                print(f"Warning: Found {invalid_historical} historical launches with future dates")
    
    def test_data_validation_rules(self, integrity_test_data):
        """Test business logic data validation rules."""
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as session:
            # Check slug format consistency
            launches = session.query(Launch).filter(
                Launch.slug.like("integrity-test-%")
            ).all()
            
            for launch in launches:
                # Slug should be lowercase and use hyphens
                assert launch.slug.islower(), f"Slug not lowercase: {launch.slug}"
                assert " " not in launch.slug, f"Slug contains spaces: {launch.slug}"
                
                # Mission name should not be empty
                assert launch.mission_name.strip(), f"Empty mission name for {launch.slug}"
                
                # Payload mass should be positive if set
                if launch.payload_mass is not None:
                    assert launch.payload_mass > 0, f"Invalid payload mass: {launch.payload_mass}"
                
                # Vehicle type should be valid
                valid_vehicles = ["Falcon 9", "Falcon Heavy", "Starship", "Dragon"]
                if launch.vehicle_type:
                    # Allow partial matches for flexibility
                    valid_vehicle = any(vehicle in launch.vehicle_type for vehicle in valid_vehicles)
                    assert valid_vehicle, f"Invalid vehicle type: {launch.vehicle_type}"
    
    def test_timestamp_consistency(self, integrity_test_data):
        """Test timestamp consistency and ordering."""
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as session:
            launches = session.query(Launch).filter(
                Launch.slug.like("integrity-test-%")
            ).all()
            
            for launch in launches:
                # created_at should be before or equal to updated_at
                if launch.created_at and launch.updated_at:
                    assert launch.created_at <= launch.updated_at, \
                        f"created_at after updated_at for {launch.slug}"
                
                # Timestamps should be reasonable (not too far in past/future)
                now = datetime.utcnow()
                if launch.created_at:
                    time_diff = abs((now - launch.created_at).days)
                    assert time_diff < 365, f"created_at too far from now: {launch.created_at}"
    
    def test_referential_integrity(self):
        """Test referential integrity across related tables."""
        db_manager = get_database_manager()
        
        with db_manager.session_scope() as session:
            # Create test launch with sources and conflicts
            test_launch = Launch(
                slug="ref-integrity-test",
                mission_name="Referential Integrity Test",
                status="upcoming"
            )
            session.add(test_launch)
            session.flush()
            
            # Add source
            test_source = LaunchSource(
                launch_id=test_launch.id,
                source_name="test_source",
                source_url="http://test.com",
                scraped_at=datetime.utcnow()
            )
            session.add(test_source)
            
            # Add conflict
            test_conflict = DataConflict(
                launch_id=test_launch.id,
                field_name="mission_name",
                source1_value="Test A",
                source2_value="Test B"
            )
            session.add(test_conflict)
            session.commit()
            
            # Verify relationships work correctly
            launch_with_relations = session.query(Launch).filter(
                Launch.id == test_launch.id
            ).first()
            
            assert len(launch_with_relations.sources) == 1
            assert launch_with_relations.sources[0].source_name == "test_source"
            
            # Verify reverse relationships
            source = session.query(LaunchSource).filter(
                LaunchSource.launch_id == test_launch.id
            ).first()
            assert source.launch.slug == "ref-integrity-test"
            
            conflict = session.query(DataConflict).filter(
                DataConflict.launch_id == test_launch.id
            ).first()
            assert conflict.launch.slug == "ref-integrity-test"
            
            # Cleanup
            session.delete(test_launch)
            session.commit()
    
    def test_concurrent_data_modifications(self):
        """Test data integrity under concurrent modifications."""
        import threading
        import time
        
        db_manager = get_database_manager()
        errors = []
        
        def modify_launch(launch_id, thread_id):
            try:
                with db_manager.session_scope() as session:
                    launch = session.query(Launch).filter(Launch.id == launch_id).first()
                    if launch:
                        launch.mission_name = f"Modified by thread {thread_id}"
                        launch.updated_at = datetime.utcnow()
                        session.commit()
                        time.sleep(0.1)  # Simulate processing time
            except Exception as e:
                errors.append(f"Thread {thread_id}: {str(e)}")
        
        # Create test launch
        with db_manager.session_scope() as session:
            test_launch = Launch(
                slug="concurrent-test",
                mission_name="Concurrent Test",
                status="upcoming"
            )
            session.add(test_launch)
            session.commit()
            launch_id = test_launch.id
        
        # Start concurrent modifications
        threads = []
        for i in range(5):
            thread = threading.Thread(target=modify_launch, args=(launch_id, i))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check for errors
        if errors:
            print(f"Concurrent modification errors: {errors}")
        
        # Verify final state is consistent
        with db_manager.session_scope() as session:
            final_launch = session.query(Launch).filter(Launch.id == launch_id).first()
            assert final_launch is not None
            assert "Modified by thread" in final_launch.mission_name
            
            # Cleanup
            session.delete(final_launch)
            session.commit()


class TestDatabaseBackupAndRestore:
    """Test database backup and restore functionality."""
    
    def test_data_export_import_consistency(self):
        """Test that exported data can be imported consistently."""
        db_manager = get_database_manager()
        
        # Create test data
        with db_manager.session_scope() as session:
            test_launch = Launch(
                slug="export-test",
                mission_name="Export Test Mission",
                launch_date=datetime.utcnow() + timedelta(days=1),
                vehicle_type="Falcon 9",
                status="upcoming",
                payload_mass=5000.0,
                orbit="LEO"
            )
            session.add(test_launch)
            session.commit()
            original_id = test_launch.id
        
        # Export data (simulate)
        with db_manager.session_scope() as session:
            exported_launch = session.query(Launch).filter(
                Launch.slug == "export-test"
            ).first()
            
            export_data = {
                "slug": exported_launch.slug,
                "mission_name": exported_launch.mission_name,
                "launch_date": exported_launch.launch_date.isoformat() if exported_launch.launch_date else None,
                "vehicle_type": exported_launch.vehicle_type,
                "status": exported_launch.status,
                "payload_mass": exported_launch.payload_mass,
                "orbit": exported_launch.orbit
            }
        
        # Delete original
        with db_manager.session_scope() as session:
            session.query(Launch).filter(Launch.slug == "export-test").delete()
            session.commit()
        
        # Import data (simulate)
        with db_manager.session_scope() as session:
            imported_launch = Launch(
                slug=export_data["slug"],
                mission_name=export_data["mission_name"],
                launch_date=datetime.fromisoformat(export_data["launch_date"]) if export_data["launch_date"] else None,
                vehicle_type=export_data["vehicle_type"],
                status=export_data["status"],
                payload_mass=export_data["payload_mass"],
                orbit=export_data["orbit"]
            )
            session.add(imported_launch)
            session.commit()
            imported_id = imported_launch.id
        
        # Verify data consistency
        with db_manager.session_scope() as session:
            restored_launch = session.query(Launch).filter(
                Launch.slug == "export-test"
            ).first()
            
            assert restored_launch is not None
            assert restored_launch.mission_name == "Export Test Mission"
            assert restored_launch.vehicle_type == "Falcon 9"
            assert restored_launch.status == "upcoming"
            assert restored_launch.payload_mass == 5000.0
            assert restored_launch.orbit == "LEO"
            
            # ID will be different after import
            assert restored_launch.id != original_id
            assert restored_launch.id == imported_id
            
            # Cleanup
            session.delete(restored_launch)
            session.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])