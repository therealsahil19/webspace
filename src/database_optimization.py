"""
Database optimization utilities for performance improvements.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy import text, Index
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database import get_database_manager
from src.models.database import Launch, LaunchSource, DataConflict

logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """Database optimization utilities."""
    
    def __init__(self):
        """Initialize database optimizer."""
        self.db_manager = get_database_manager()
    
    def create_performance_indexes(self) -> Dict[str, bool]:
        """Create additional performance indexes."""
        results = {}
        
        with self.db_manager.session_scope() as session:
            try:
                # Index for launch date range queries
                session.execute(text("""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_launches_date_range 
                    ON launches (launch_date) 
                    WHERE launch_date IS NOT NULL
                """))
                results["idx_launches_date_range"] = True
                logger.info("Created launch date range index")
                
                # Index for upcoming launches (most common query)
                session.execute(text("""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_launches_upcoming 
                    ON launches (launch_date, status) 
                    WHERE launch_date > NOW() AND status = 'upcoming'
                """))
                results["idx_launches_upcoming"] = True
                logger.info("Created upcoming launches index")
                
                # Index for historical launches with status
                session.execute(text("""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_launches_historical 
                    ON launches (launch_date DESC, status) 
                    WHERE launch_date <= NOW()
                """))
                results["idx_launches_historical"] = True
                logger.info("Created historical launches index")
                
                # Composite index for filtered searches
                session.execute(text("""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_launches_search 
                    ON launches (status, vehicle_type, launch_date) 
                    WHERE status IS NOT NULL
                """))
                results["idx_launches_search"] = True
                logger.info("Created search filter index")
                
                # Full-text search index for mission names and details
                session.execute(text("""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_launches_fulltext 
                    ON launches USING gin(to_tsvector('english', mission_name || ' ' || COALESCE(details, '')))
                """))
                results["idx_launches_fulltext"] = True
                logger.info("Created full-text search index")
                
                # Index for source data quality queries
                session.execute(text("""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sources_quality 
                    ON launch_sources (launch_id, data_quality_score DESC, scraped_at DESC)
                """))
                results["idx_sources_quality"] = True
                logger.info("Created source quality index")
                
                # Index for unresolved conflicts
                session.execute(text("""
                    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conflicts_unresolved 
                    ON data_conflicts (resolved, created_at DESC) 
                    WHERE resolved = false
                """))
                results["idx_conflicts_unresolved"] = True
                logger.info("Created unresolved conflicts index")
                
                session.commit()
                logger.info("All performance indexes created successfully")
                
            except SQLAlchemyError as e:
                logger.error(f"Error creating performance indexes: {e}")
                session.rollback()
                results["error"] = str(e)
        
        return results
    
    def analyze_query_performance(self) -> Dict[str, Any]:
        """Analyze query performance and suggest optimizations."""
        analysis = {
            "timestamp": "2024-01-01T00:00:00Z",
            "table_stats": {},
            "index_usage": {},
            "slow_queries": [],
            "recommendations": []
        }
        
        with self.db_manager.session_scope() as session:
            try:
                # Get table statistics
                tables = ['launches', 'launch_sources', 'data_conflicts', 'users', 'api_keys']
                for table in tables:
                    result = session.execute(text(f"""
                        SELECT 
                            schemaname,
                            tablename,
                            attname,
                            n_distinct,
                            correlation
                        FROM pg_stats 
                        WHERE tablename = '{table}'
                        ORDER BY n_distinct DESC
                        LIMIT 5
                    """)).fetchall()
                    
                    analysis["table_stats"][table] = [
                        {
                            "column": row.attname,
                            "distinct_values": row.n_distinct,
                            "correlation": row.correlation
                        }
                        for row in result
                    ]
                
                # Get index usage statistics
                index_stats = session.execute(text("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname,
                        idx_tup_read,
                        idx_tup_fetch
                    FROM pg_stat_user_indexes 
                    WHERE schemaname = 'public'
                    ORDER BY idx_tup_read DESC
                """)).fetchall()
                
                analysis["index_usage"] = [
                    {
                        "table": row.tablename,
                        "index": row.indexname,
                        "tuples_read": row.idx_tup_read,
                        "tuples_fetched": row.idx_tup_fetch,
                        "efficiency": (row.idx_tup_fetch / max(row.idx_tup_read, 1)) * 100
                    }
                    for row in index_stats
                ]
                
                # Check for unused indexes
                unused_indexes = session.execute(text("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname
                    FROM pg_stat_user_indexes 
                    WHERE idx_tup_read = 0 
                    AND schemaname = 'public'
                """)).fetchall()
                
                if unused_indexes:
                    analysis["recommendations"].append({
                        "type": "unused_indexes",
                        "message": "Consider dropping unused indexes",
                        "indexes": [f"{row.tablename}.{row.indexname}" for row in unused_indexes]
                    })
                
                # Check table sizes
                table_sizes = session.execute(text("""
                    SELECT 
                        tablename,
                        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                        pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                    FROM pg_tables 
                    WHERE schemaname = 'public'
                    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                """)).fetchall()
                
                analysis["table_sizes"] = [
                    {
                        "table": row.tablename,
                        "size": row.size,
                        "size_bytes": row.size_bytes
                    }
                    for row in table_sizes
                ]
                
                # Performance recommendations
                if any(stats["size_bytes"] > 100 * 1024 * 1024 for stats in analysis["table_sizes"]):  # 100MB
                    analysis["recommendations"].append({
                        "type": "large_tables",
                        "message": "Consider partitioning large tables or archiving old data"
                    })
                
                logger.info("Query performance analysis completed")
                
            except SQLAlchemyError as e:
                logger.error(f"Error analyzing query performance: {e}")
                analysis["error"] = str(e)
        
        return analysis
    
    def optimize_database_settings(self) -> Dict[str, Any]:
        """Suggest database configuration optimizations."""
        recommendations = {
            "timestamp": "2024-01-01T00:00:00Z",
            "current_settings": {},
            "recommendations": []
        }
        
        with self.db_manager.session_scope() as session:
            try:
                # Get current PostgreSQL settings
                settings_query = """
                    SELECT name, setting, unit, short_desc 
                    FROM pg_settings 
                    WHERE name IN (
                        'shared_buffers',
                        'effective_cache_size',
                        'maintenance_work_mem',
                        'checkpoint_completion_target',
                        'wal_buffers',
                        'default_statistics_target',
                        'random_page_cost',
                        'effective_io_concurrency'
                    )
                """
                
                settings = session.execute(text(settings_query)).fetchall()
                
                for setting in settings:
                    recommendations["current_settings"][setting.name] = {
                        "value": setting.setting,
                        "unit": setting.unit,
                        "description": setting.short_desc
                    }
                
                # Add optimization recommendations
                recommendations["recommendations"] = [
                    {
                        "setting": "shared_buffers",
                        "recommended": "25% of RAM",
                        "reason": "Improves cache hit ratio for frequently accessed data"
                    },
                    {
                        "setting": "effective_cache_size",
                        "recommended": "75% of RAM",
                        "reason": "Helps query planner make better decisions"
                    },
                    {
                        "setting": "maintenance_work_mem",
                        "recommended": "256MB - 1GB",
                        "reason": "Speeds up VACUUM, CREATE INDEX, and other maintenance operations"
                    },
                    {
                        "setting": "checkpoint_completion_target",
                        "recommended": "0.9",
                        "reason": "Spreads checkpoint I/O over more time"
                    },
                    {
                        "setting": "default_statistics_target",
                        "recommended": "100-500",
                        "reason": "Improves query planning for complex queries"
                    }
                ]
                
                logger.info("Database optimization recommendations generated")
                
            except SQLAlchemyError as e:
                logger.error(f"Error getting database settings: {e}")
                recommendations["error"] = str(e)
        
        return recommendations
    
    def vacuum_analyze_tables(self) -> Dict[str, bool]:
        """Run VACUUM ANALYZE on all tables for better performance."""
        results = {}
        tables = ['launches', 'launch_sources', 'data_conflicts', 'users', 'api_keys']
        
        with self.db_manager.session_scope() as session:
            for table in tables:
                try:
                    session.execute(text(f"VACUUM ANALYZE {table}"))
                    results[table] = True
                    logger.info(f"VACUUM ANALYZE completed for {table}")
                except SQLAlchemyError as e:
                    logger.error(f"Error running VACUUM ANALYZE on {table}: {e}")
                    results[table] = False
        
        return results


# Global optimizer instance
_db_optimizer: Optional[DatabaseOptimizer] = None


def get_database_optimizer() -> DatabaseOptimizer:
    """Get global database optimizer instance."""
    global _db_optimizer
    if _db_optimizer is None:
        _db_optimizer = DatabaseOptimizer()
    return _db_optimizer