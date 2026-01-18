-- Migration: Add channel_candidates table for Search & Filter node
-- Created: 2026-01-18

CREATE TABLE IF NOT EXISTS channel_candidates (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    
    -- Telegram identifiers
    peer_id BIGINT NOT NULL,
    access_hash BIGINT NOT NULL,
    username VARCHAR(255),
    title VARCHAR(255),
    
    -- Classification
    type VARCHAR(20),  -- CHANNEL, MEGAGROUP
    language VARCHAR(5),  -- RU, EN
    origin VARCHAR(20),  -- SEARCH, LINK
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'VISITED',  -- VISITED, JOINED, REJECTED
    last_visit_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Validation data
    participants_count INTEGER,
    last_post_date TIMESTAMP,
    can_send_messages BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT _account_peer_uc UNIQUE (account_id, peer_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_channel_candidates_peer_id ON channel_candidates(peer_id);
CREATE INDEX IF NOT EXISTS idx_channel_candidates_username ON channel_candidates(username);
CREATE INDEX IF NOT EXISTS idx_channel_candidates_account_status ON channel_candidates(account_id, status);
CREATE INDEX IF NOT EXISTS idx_channel_candidates_last_visit ON channel_candidates(last_visit_ts DESC);

-- Comments
COMMENT ON TABLE channel_candidates IS 'Discovered Telegram channels/groups from Search & Filter node';
COMMENT ON COLUMN channel_candidates.access_hash IS 'Telethon access key for direct entity resolution';
COMMENT ON COLUMN channel_candidates.origin IS 'How this channel was discovered: SEARCH (contacts.Search) or LINK (direct username)';
COMMENT ON COLUMN channel_candidates.status IS 'Lifecycle: VISITED (discovered), JOINED (subscribed), REJECTED (filtered out)';
