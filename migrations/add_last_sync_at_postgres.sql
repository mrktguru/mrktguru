-- Migration: Add last_sync_at column to accounts table (PostgreSQL)
-- Date: 2026-01-12

-- Check if column exists and add if not
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name='accounts' AND column_name='last_sync_at'
    ) THEN
        ALTER TABLE accounts ADD COLUMN last_sync_at TIMESTAMP;
        RAISE NOTICE 'Column last_sync_at added successfully';
    ELSE
        RAISE NOTICE 'Column last_sync_at already exists';
    END IF;
END $$;
