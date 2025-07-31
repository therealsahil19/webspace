"""
SQLAlchemy database models for the SpaceX Launch Tracker.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Numeric, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Launch(Base):
    """SQLAlchemy model for launches table."""
    __tablename__ = 'launches'
    
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    mission_name = Column(String(255), nullable=False, index=True)
    launch_date = Column(DateTime(timezone=True), nullable=True, index=True)
    vehicle_type = Column(String(100), nullable=True, index=True)
    payload_mass = Column(Numeric(10, 2), nullable=True)
    orbit = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, index=True)
    details = Column(Text, nullable=True)
    mission_patch_url = Column(String(500), nullable=True)
    webcast_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    sources = relationship("LaunchSource", back_populates="launch", cascade="all, delete-orphan")
    conflicts = relationship("DataConflict", back_populates="launch", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_launch_date_status', 'launch_date', 'status'),
        Index('idx_vehicle_status', 'vehicle_type', 'status'),
    )
    
    def __repr__(self):
        return f"<Launch(id={self.id}, slug='{self.slug}', mission_name='{self.mission_name}')>"


class LaunchSource(Base):
    """SQLAlchemy model for launch_sources table."""
    __tablename__ = 'launch_sources'
    
    id = Column(Integer, primary_key=True, index=True)
    launch_id = Column(Integer, ForeignKey('launches.id', ondelete='CASCADE'), nullable=False, index=True)
    source_name = Column(String(100), nullable=False, index=True)
    source_url = Column(Text, nullable=False)
    scraped_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    data_quality_score = Column(Numeric(3, 2), nullable=False, default=0.0)
    
    # Relationships
    launch = relationship("Launch", back_populates="sources")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_launch_source', 'launch_id', 'source_name'),
        Index('idx_scraped_at', 'scraped_at'),
    )
    
    def __repr__(self):
        return f"<LaunchSource(id={self.id}, launch_id={self.launch_id}, source_name='{self.source_name}')>"


class DataConflict(Base):
    """SQLAlchemy model for data_conflicts table."""
    __tablename__ = 'data_conflicts'
    
    id = Column(Integer, primary_key=True, index=True)
    launch_id = Column(Integer, ForeignKey('launches.id', ondelete='CASCADE'), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    source1_value = Column(Text, nullable=False)
    source2_value = Column(Text, nullable=False)
    confidence_score = Column(Numeric(3, 2), nullable=False, default=0.0)
    resolved = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    launch = relationship("Launch", back_populates="conflicts")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_launch_field_conflict', 'launch_id', 'field_name'),
        Index('idx_unresolved_conflicts', 'resolved', 'created_at'),
    )
    
    def __repr__(self):
        return f"<DataConflict(id={self.id}, launch_id={self.launch_id}, field_name='{self.field_name}', resolved={self.resolved})>"


class User(Base):
    """SQLAlchemy model for users table."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='viewer', index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class APIKey(Base):
    """SQLAlchemy model for api_keys table."""
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_api_key_active_expires', 'is_active', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<APIKey(id={self.id}, name='{self.name}', is_active={self.is_active})>"