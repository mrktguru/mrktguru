"""
Add supernode_id and supernode_order columns to warmup_schedule_nodes table
for grouping nodes that execute in sequence (supernode feature)
"""

def upgrade_sql():
    """SQL commands to add supernode columns"""
    return """
        ALTER TABLE warmup_schedule_nodes 
        ADD COLUMN IF NOT EXISTS supernode_id INTEGER DEFAULT NULL;
        
        ALTER TABLE warmup_schedule_nodes 
        ADD COLUMN IF NOT EXISTS supernode_order INTEGER DEFAULT NULL;
        
        -- Add index for faster supernode queries
        CREATE INDEX IF NOT EXISTS idx_warmup_nodes_supernode 
        ON warmup_schedule_nodes(supernode_id) 
        WHERE supernode_id IS NOT NULL;
    """

def downgrade_sql():
    """SQL commands to remove supernode columns"""
    return """
        DROP INDEX IF EXISTS idx_warmup_nodes_supernode;
        ALTER TABLE warmup_schedule_nodes DROP COLUMN IF EXISTS supernode_order;
        ALTER TABLE warmup_schedule_nodes DROP COLUMN IF EXISTS supernode_id;
    """

if __name__ == "__main__":
    print("Run this migration on the server:")
    print(upgrade_sql())
