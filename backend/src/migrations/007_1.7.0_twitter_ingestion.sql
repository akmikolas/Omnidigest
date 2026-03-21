-- Twitter Ingestion Module Schema (v1.7.0)
-- -----------------------------------------

-- Twitter Account Pool for rotating sessions
CREATE TABLE IF NOT EXISTS twitter_accounts (
    id UUID PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    auth_token TEXT NOT NULL,
    ct0 TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active', -- active, cooling, disabled
    last_error TEXT,
    last_used_at TIMESTAMP,
    fail_count INT DEFAULT 0,
    "created_at" TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_twitter_accounts_status ON twitter_accounts(status);

-- Monitored Influencer List (名单)
CREATE TABLE IF NOT EXISTS twitter_monitored_users (
    rest_id VARCHAR(50) PRIMARY KEY, -- Twitter Numeric ID
    screen_name VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    category VARCHAR(50),
    last_seen_tweet_id VARCHAR(50) DEFAULT '0',
    "created_at" TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_twitter_monitored_active ON twitter_monitored_users(is_active);

-- Standardized Twitter Stream for raw ingestion
CREATE TABLE IF NOT EXISTS twitter_stream_raw (
    id UUID PRIMARY KEY,
    tweet_id VARCHAR(50) UNIQUE NOT NULL,
    author_screen_name VARCHAR(100),
    raw_text TEXT NOT NULL,
    is_reply BOOLEAN DEFAULT FALSE,
    reply_to_tweet_id VARCHAR(50),
    metadata JSONB, -- likes, retweets, images, etc.
    status SMALLINT DEFAULT 0, -- 0: raw, 1: processed
    "created_at" TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_twitter_stream_id ON twitter_stream_raw(tweet_id);
CREATE INDEX IF NOT EXISTS idx_twitter_stream_status ON twitter_stream_raw(status);
CREATE INDEX IF NOT EXISTS idx_twitter_stream_author ON twitter_stream_raw(author_screen_name);
