"""
Database migration: Create warmup scheduler tables
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'create_warmup_scheduler'
down_revision = None  # Update this with your latest migration
branch_labels = None
depends_on = None


def upgrade():
    # Create warmup_schedules table
    op.create_table(
        'warmup_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_warmup_schedules_account_id', 'warmup_schedules', ['account_id'])
    op.create_index('ix_warmup_schedules_status', 'warmup_schedules', ['status'])
    
    # Create warmup_schedule_nodes table
    op.create_table(
        'warmup_schedule_nodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=False),
        sa.Column('node_type', sa.String(length=50), nullable=False),
        sa.Column('day_number', sa.Integer(), nullable=False),
        sa.Column('execution_time', sa.String(length=20), nullable=True),
        sa.Column('is_random_time', sa.Boolean(), nullable=False),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['schedule_id'], ['warmup_schedules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_warmup_schedule_nodes_schedule_id', 'warmup_schedule_nodes', ['schedule_id'])
    op.create_index('ix_warmup_schedule_nodes_day_number', 'warmup_schedule_nodes', ['day_number'])
    op.create_index('ix_warmup_schedule_nodes_status', 'warmup_schedule_nodes', ['status'])


def downgrade():
    op.drop_index('ix_warmup_schedule_nodes_status', table_name='warmup_schedule_nodes')
    op.drop_index('ix_warmup_schedule_nodes_day_number', table_name='warmup_schedule_nodes')
    op.drop_index('ix_warmup_schedule_nodes_schedule_id', table_name='warmup_schedule_nodes')
    op.drop_table('warmup_schedule_nodes')
    
    op.drop_index('ix_warmup_schedules_status', table_name='warmup_schedules')
    op.drop_index('ix_warmup_schedules_account_id', table_name='warmup_schedules')
    op.drop_table('warmup_schedules')
