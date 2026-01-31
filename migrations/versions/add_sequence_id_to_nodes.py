"""
Database migration: Add sequence_id to warmup_schedule_nodes
Per-account sequential ID for nodes (not global database ID)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = 'add_sequence_id_to_nodes'
down_revision = 'create_warmup_scheduler'
branch_labels = None
depends_on = None


def upgrade():
    # Add sequence_id column
    op.add_column('warmup_schedule_nodes', sa.Column('sequence_id', sa.Integer(), nullable=True))
    
    # Backfill existing nodes with sequence_id based on creation order within each schedule
    connection = op.get_bind()
    
    # Get all schedules
    schedules = connection.execute(text("SELECT DISTINCT schedule_id FROM warmup_schedule_nodes")).fetchall()
    
    for (schedule_id,) in schedules:
        # Get all nodes for this schedule ordered by created_at
        nodes = connection.execute(text("""
            SELECT id FROM warmup_schedule_nodes 
            WHERE schedule_id = :schedule_id 
            ORDER BY created_at ASC
        """), {"schedule_id": schedule_id}).fetchall()
        
        # Assign sequence_id
        for idx, (node_id,) in enumerate(nodes, 1):
            connection.execute(text("""
                UPDATE warmup_schedule_nodes 
                SET sequence_id = :seq_id 
                WHERE id = :node_id
            """), {"seq_id": idx, "node_id": node_id})
    
    # Create index for faster lookups
    op.create_index('ix_warmup_schedule_nodes_sequence_id', 'warmup_schedule_nodes', ['sequence_id'])


def downgrade():
    op.drop_index('ix_warmup_schedule_nodes_sequence_id', table_name='warmup_schedule_nodes')
    op.drop_column('warmup_schedule_nodes', 'sequence_id')
