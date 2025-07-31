"""
Log management utilities for SpaceX Launch Tracker.
Handles log rotation, retention, and cleanup policies.
"""

import os
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LogRetentionPolicy:
    """Configuration for log retention policy."""
    max_age_days: int = 30
    max_size_mb: int = 1000  # Total size limit for all logs
    compress_after_days: int = 7
    delete_after_days: int = 30
    keep_minimum_files: int = 5


class LogManager:
    """Manages log files, rotation, and retention policies."""
    
    def __init__(self, log_dir: Path, retention_policy: Optional[LogRetentionPolicy] = None):
        """
        Initialize log manager.
        
        Args:
            log_dir: Directory containing log files
            retention_policy: Retention policy configuration
        """
        self.log_dir = Path(log_dir)
        self.retention_policy = retention_policy or LogRetentionPolicy()
        
        # Ensure log directory exists
        self.log_dir.mkdir(exist_ok=True)
        
        logger.info("Log manager initialized", log_dir=str(self.log_dir))
    
    def get_log_files(self) -> List[Path]:
        """Get all log files in the log directory."""
        log_files = []
        
        # Find all .log files and their rotated versions
        for pattern in ['*.log', '*.log.*']:
            log_files.extend(self.log_dir.glob(pattern))
        
        return sorted(log_files, key=lambda f: f.stat().st_mtime, reverse=True)
    
    def get_log_file_info(self, log_file: Path) -> Dict[str, Any]:
        """Get information about a log file."""
        try:
            stat = log_file.stat()
            return {
                'path': str(log_file),
                'size_bytes': stat.st_size,
                'size_mb': stat.st_size / (1024 * 1024),
                'modified_time': datetime.fromtimestamp(stat.st_mtime),
                'age_days': (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days,
                'is_compressed': log_file.suffix == '.gz',
            }
        except OSError as e:
            logger.error(f"Error getting info for {log_file}", error=str(e))
            return {}
    
    def compress_log_file(self, log_file: Path) -> Optional[Path]:
        """
        Compress a log file using gzip.
        
        Args:
            log_file: Path to log file to compress
            
        Returns:
            Path to compressed file, or None if compression failed
        """
        if log_file.suffix == '.gz':
            logger.debug(f"File already compressed: {log_file}")
            return log_file
        
        compressed_path = log_file.with_suffix(log_file.suffix + '.gz')
        
        try:
            with open(log_file, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove original file after successful compression
            log_file.unlink()
            
            logger.info(f"Compressed log file: {log_file} -> {compressed_path}")
            return compressed_path
            
        except Exception as e:
            logger.error(f"Failed to compress {log_file}", error=str(e))
            # Clean up partial compressed file
            if compressed_path.exists():
                compressed_path.unlink()
            return None
    
    def delete_log_file(self, log_file: Path) -> bool:
        """
        Delete a log file.
        
        Args:
            log_file: Path to log file to delete
            
        Returns:
            True if deletion was successful
        """
        try:
            log_file.unlink()
            logger.info(f"Deleted log file: {log_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {log_file}", error=str(e))
            return False
    
    def apply_retention_policy(self) -> Dict[str, Any]:
        """
        Apply retention policy to log files.
        
        Returns:
            Dictionary with results of retention policy application
        """
        logger.info("Applying log retention policy")
        
        log_files = self.get_log_files()
        results = {
            'total_files': len(log_files),
            'compressed_files': 0,
            'deleted_files': 0,
            'total_size_before_mb': 0,
            'total_size_after_mb': 0,
            'errors': [],
        }
        
        # Calculate total size before cleanup
        total_size_bytes = 0
        file_info_list = []
        
        for log_file in log_files:
            info = self.get_log_file_info(log_file)
            if info:
                file_info_list.append((log_file, info))
                total_size_bytes += info['size_bytes']
        
        results['total_size_before_mb'] = total_size_bytes / (1024 * 1024)
        
        # Group files by base name (e.g., 'spacex_tracker.log')
        file_groups = {}
        for log_file, info in file_info_list:
            base_name = log_file.name.split('.')[0] + '.log'
            if base_name not in file_groups:
                file_groups[base_name] = []
            file_groups[base_name].append((log_file, info))
        
        # Apply retention policy to each group
        for base_name, files in file_groups.items():
            # Sort by modification time (newest first)
            files.sort(key=lambda x: x[1]['modified_time'], reverse=True)
            
            logger.debug(f"Processing {len(files)} files for {base_name}")
            
            for i, (log_file, info) in enumerate(files):
                # Skip the most recent files (keep minimum)
                if i < self.retention_policy.keep_minimum_files:
                    continue
                
                # Compress old files
                if (info['age_days'] >= self.retention_policy.compress_after_days and 
                    not info['is_compressed']):
                    compressed_file = self.compress_log_file(log_file)
                    if compressed_file:
                        results['compressed_files'] += 1
                        # Update file info for further processing
                        log_file = compressed_file
                        info = self.get_log_file_info(log_file)
                
                # Delete very old files
                if info['age_days'] >= self.retention_policy.delete_after_days:
                    if self.delete_log_file(log_file):
                        results['deleted_files'] += 1
                        total_size_bytes -= info['size_bytes']
        
        # Check total size limit
        if total_size_bytes > self.retention_policy.max_size_mb * 1024 * 1024:
            logger.warning(
                "Log directory exceeds size limit",
                current_size_mb=total_size_bytes / (1024 * 1024),
                limit_mb=self.retention_policy.max_size_mb
            )
            
            # Delete oldest files until under limit
            remaining_files = []
            for log_file in self.get_log_files():
                info = self.get_log_file_info(log_file)
                if info:
                    remaining_files.append((log_file, info))
            
            # Sort by age (oldest first)
            remaining_files.sort(key=lambda x: x[1]['modified_time'])
            
            for log_file, info in remaining_files:
                if total_size_bytes <= self.retention_policy.max_size_mb * 1024 * 1024:
                    break
                
                # Don't delete the most recent file of each type
                base_name = log_file.name.split('.')[0] + '.log'
                most_recent = max(
                    (f for f, i in remaining_files if f.name.startswith(base_name.split('.')[0])),
                    key=lambda f: f.stat().st_mtime,
                    default=None
                )
                
                if log_file != most_recent:
                    if self.delete_log_file(log_file):
                        results['deleted_files'] += 1
                        total_size_bytes -= info['size_bytes']
        
        results['total_size_after_mb'] = total_size_bytes / (1024 * 1024)
        
        logger.info(
            "Log retention policy applied",
            **{k: v for k, v in results.items() if k != 'errors'}
        )
        
        return results
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """Get statistics about log files."""
        log_files = self.get_log_files()
        
        total_size = 0
        compressed_count = 0
        file_types = {}
        oldest_file = None
        newest_file = None
        
        for log_file in log_files:
            info = self.get_log_file_info(log_file)
            if not info:
                continue
            
            total_size += info['size_bytes']
            
            if info['is_compressed']:
                compressed_count += 1
            
            # Count file types
            base_name = log_file.name.split('.')[0]
            file_types[base_name] = file_types.get(base_name, 0) + 1
            
            # Track oldest and newest files
            if oldest_file is None or info['modified_time'] < oldest_file[1]:
                oldest_file = (log_file, info['modified_time'])
            
            if newest_file is None or info['modified_time'] > newest_file[1]:
                newest_file = (log_file, info['modified_time'])
        
        return {
            'total_files': len(log_files),
            'total_size_mb': total_size / (1024 * 1024),
            'compressed_files': compressed_count,
            'uncompressed_files': len(log_files) - compressed_count,
            'file_types': file_types,
            'oldest_file': {
                'path': str(oldest_file[0]) if oldest_file else None,
                'modified_time': oldest_file[1].isoformat() if oldest_file else None,
            },
            'newest_file': {
                'path': str(newest_file[0]) if newest_file else None,
                'modified_time': newest_file[1].isoformat() if newest_file else None,
            },
            'retention_policy': {
                'max_age_days': self.retention_policy.max_age_days,
                'max_size_mb': self.retention_policy.max_size_mb,
                'compress_after_days': self.retention_policy.compress_after_days,
                'delete_after_days': self.retention_policy.delete_after_days,
            }
        }
    
    def cleanup_logs(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Perform log cleanup with optional dry run.
        
        Args:
            dry_run: If True, only simulate cleanup without making changes
            
        Returns:
            Dictionary with cleanup results
        """
        if dry_run:
            logger.info("Performing dry run log cleanup")
            # TODO: Implement dry run logic
            return {'dry_run': True, 'message': 'Dry run not implemented yet'}
        else:
            return self.apply_retention_policy()


# Global log manager instance
_log_manager: Optional[LogManager] = None


def get_log_manager(log_dir: Optional[Path] = None) -> LogManager:
    """Get the global log manager instance."""
    global _log_manager
    if _log_manager is None:
        if log_dir is None:
            log_dir = Path(os.getenv('LOG_DIR', 'logs'))
        _log_manager = LogManager(log_dir)
    return _log_manager


def setup_log_rotation_task():
    """Set up periodic log rotation task."""
    from ..celery_app import celery_app
    
    @celery_app.task(name='src.monitoring.log_management.rotate_logs')
    def rotate_logs_task():
        """Celery task to rotate and clean up logs."""
        try:
            log_manager = get_log_manager()
            results = log_manager.apply_retention_policy()
            
            logger.info("Log rotation completed", **results)
            return results
            
        except Exception as e:
            logger.error("Log rotation failed", error=str(e), exc_info=True)
            raise
    
    return rotate_logs_task