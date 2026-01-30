#!/bin/bash
# Migration script for warmup scheduler tables
# Run this on the server to create new database tables

echo "🔄 Applying warmup scheduler migration..."

# Create SQL migration file
cat > /tmp/warmup_scheduler_migration.sql << 'EOF'
-- Create warmup_schedules table
CREATE TABLE IF NOT EXISTS warmup_schedules (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    name VARCHAR(200) NOT NULL DEFAULT 'Warmup Schedule',
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_warmup_schedules_account_id ON warmup_schedules(account_id);
CREATE INDEX IF NOT EXISTS ix_warmup_schedules_status ON warmup_schedules(status);

-- Create warmup_schedule_nodes table
CREATE TABLE IF NOT EXISTS warmup_schedule_nodes (
    id SERIAL PRIMARY KEY,
    schedule_id INTEGER NOT NULL REFERENCES warmup_schedules(id) ON DELETE CASCADE,
    node_type VARCHAR(50) NOT NULL,
    day_number INTEGER NOT NULL,
    execution_time VARCHAR(20),
    is_random_time BOOLEAN NOT NULL DEFAULT FALSE,
    config JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    executed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_warmup_schedule_nodes_schedule_id ON warmup_schedule_nodes(schedule_id);
CREATE INDEX IF NOT EXISTS ix_warmup_schedule_nodes_day_number ON warmup_schedule_nodes(day_number);
CREATE INDEX IF NOT EXISTS ix_warmup_schedule_nodes_status ON warmup_schedule_nodes(status);
EOF

# Apply migration
echo "📊 Creating tables..."
sudo -u postgres psql -p 5434 -d telegram_system -f /tmp/warmup_scheduler_migration.sql

# Verify tables created
echo "✅ Verifying tables..."
sudo -u postgres psql -p 5434 -d telegram_system -c "\dt warmup_*"

# Restart web server
echo "🔄 Restarting web server..."
systemctl restart mrktguru-web

echo "✅ Migration completed!"
