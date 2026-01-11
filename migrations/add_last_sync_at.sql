-- Migration: Add last_sync_at column to accounts table
-- Date: 2026-01-12

ALTER TABLE accounts ADD COLUMN last_sync_at DATETIME;
