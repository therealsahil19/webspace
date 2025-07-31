"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    # Create launches table
    op.create_table('launches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('mission_name', sa.String(length=255), nullable=False),
        sa.Column('launch_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('vehicle_type', sa.String(length=100), nullable=True),
        sa.Column('payload_mass', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('orbit', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('mission_patch_url', sa.String(length=500), nullable=True),
        sa.Column('webcast_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for launches table
    op.create_index('ix_launches_id', 'launches', ['id'], unique=False)
    op.create_index('ix_launches_slug', 'launches', ['slug'], unique=True)
    op.create_index('ix_launches_mission_name', 'launches', ['mission_name'], unique=False)
    op.create_index('ix_launches_launch_date', 'launches', ['launch_date'], unique=False)
    op.create_index('ix_launches_vehicle_type', 'launches', ['vehicle_type'], unique=False)
    op.create_index('ix_launches_status', 'launches', ['status'], unique=False)
    op.create_index('idx_launch_date_status', 'launches', ['launch_date', 'status'], unique=False)
    op.create_index('idx_vehicle_status', 'launches', ['vehicle_type', 'status'], unique=False)
    
    # Create launch_sources table
    op.create_table('launch_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('launch_id', sa.Integer(), nullable=False),
        sa.Column('source_name', sa.String(length=100), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('data_quality_score', sa.Numeric(precision=3, scale=2), nullable=False),
        sa.ForeignKeyConstraint(['launch_id'], ['launches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for launch_sources table
    op.create_index('ix_launch_sources_id', 'launch_sources', ['id'], unique=False)
    op.create_index('ix_launch_sources_launch_id', 'launch_sources', ['launch_id'], unique=False)
    op.create_index('ix_launch_sources_source_name', 'launch_sources', ['source_name'], unique=False)
    op.create_index('idx_launch_source', 'launch_sources', ['launch_id', 'source_name'], unique=False)
    op.create_index('idx_scraped_at', 'launch_sources', ['scraped_at'], unique=False)
    
    # Create data_conflicts table
    op.create_table('data_conflicts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('launch_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('source1_value', sa.Text(), nullable=False),
        sa.Column('source2_value', sa.Text(), nullable=False),
        sa.Column('confidence_score', sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['launch_id'], ['launches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for data_conflicts table
    op.create_index('ix_data_conflicts_id', 'data_conflicts', ['id'], unique=False)
    op.create_index('ix_data_conflicts_launch_id', 'data_conflicts', ['launch_id'], unique=False)
    op.create_index('ix_data_conflicts_field_name', 'data_conflicts', ['field_name'], unique=False)
    op.create_index('ix_data_conflicts_resolved', 'data_conflicts', ['resolved'], unique=False)
    op.create_index('idx_launch_field_conflict', 'data_conflicts', ['launch_id', 'field_name'], unique=False)
    op.create_index('idx_unresolved_conflicts', 'data_conflicts', ['resolved', 'created_at'], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('data_conflicts')
    op.drop_table('launch_sources')
    op.drop_table('launches')