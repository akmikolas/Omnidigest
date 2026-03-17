-- Twitter Event Aggregation & Deduplication
-- -------------------------------------------
-- Tables for clustering similar tweets into events

-- Twitter Events: Stores aggregated news events from multiple tweet sources
CREATE TABLE IF NOT EXISTS twitter_events (
    id UUID PRIMARY KEY,
    event_title VARCHAR(512) NOT NULL,
    summary TEXT,
    category VARCHAR(50),
    peak_score INT DEFAULT 0,
    source_count INT DEFAULT 0,
    first_tweet_id VARCHAR(50),
    pushed BOOLEAN DEFAULT FALSE,
    push_count INT DEFAULT 0,
    last_pushed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Twitter Event Tweet Mapping: Links tweets to events
CREATE TABLE IF NOT EXISTS twitter_event_tweet_mapping (
    id UUID PRIMARY KEY,
    event_id UUID REFERENCES twitter_events(id) ON DELETE CASCADE,
    tweet_id VARCHAR(50) REFERENCES twitter_stream_raw(tweet_id) ON DELETE CASCADE,
    author_screen_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for efficient event lookups
CREATE INDEX IF NOT EXISTS idx_twitter_events_created_at ON twitter_events(created_at);
CREATE INDEX IF NOT EXISTS idx_twitter_events_category ON twitter_events(category);
CREATE INDEX IF NOT EXISTS idx_twitter_event_mapping_event_id ON twitter_event_tweet_mapping(event_id);
CREATE INDEX IF NOT EXISTS idx_twitter_event_mapping_tweet_id ON twitter_event_tweet_mapping(tweet_id);
