-- Migration Script for 1.3.0 Breaking News Features
-- Adds tables to support the decoupled stream processing architecture and dynamic RSS sources

-- 1. Breaking News RSS Sources Table
CREATE TABLE IF NOT EXISTS breaking_rss_sources (
    id UUID PRIMARY KEY,
    url VARCHAR(512) UNIQUE NOT NULL,
    name VARCHAR(100),
    platform VARCHAR(50) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    fail_count INT DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_brss_url ON breaking_rss_sources(url);
CREATE INDEX IF NOT EXISTS idx_brss_enabled ON breaking_rss_sources(enabled);

-- Seed initial fast-lane sources
INSERT INTO breaking_rss_sources (id, url, name, platform)
VALUES 
    (gen_random_uuid(), 'http://feeds.bbci.co.uk/news/world/rss.xml', 'BBC World Breaking', 'BBC'),
    (gen_random_uuid(), 'https://rss.nytimes.com/services/xml/rss/nyt/World.xml', 'NYT World Breaking', 'NYT'),
    (gen_random_uuid(), 'https://www.aljazeera.com/xml/rss/all.xml', 'Al Jazeera Breaking', 'Al_Jazeera')
ON CONFLICT (url) DO NOTHING;


-- 2. Stream Raw Ingestion Table
-- This table is the unified interface for ALL scrapers (Douyin, X, RSS).
CREATE TABLE IF NOT EXISTS breaking_stream_raw (
    id UUID PRIMARY KEY,
    source_platform VARCHAR(100) NOT NULL, -- e.g., 'X', 'Douyin', 'BBC_Breaking'
    source_url TEXT UNIQUE NOT NULL,       -- To prevent duplicate ingestion of the exact same post
    raw_text TEXT NOT NULL,                -- The actual content/tweet/caption
    author VARCHAR(255),                   -- Author or account name
    publish_time TIMESTAMP,                -- Original publish time of the content
    status SMALLINT DEFAULT 0,             -- 0 = unprocessed, 1 = processed, 2 = error/ignored
    created_at TIMESTAMP DEFAULT NOW()     -- Our ingestion time
);

CREATE INDEX IF NOT EXISTS idx_bsr_status ON breaking_stream_raw(status);
CREATE INDEX IF NOT EXISTS idx_bsr_platform ON breaking_stream_raw(source_platform);
CREATE INDEX IF NOT EXISTS idx_bsr_pub_time ON breaking_stream_raw(publish_time);


-- 3. Consolidated Breaking Events Table
-- This table holds the finalized, LLM-curated explosive events.
CREATE TABLE IF NOT EXISTS breaking_events (
    id UUID PRIMARY KEY,
    event_title VARCHAR(512) NOT NULL,
    summary TEXT,
    category VARCHAR(100),
    impact_score INT DEFAULT 0,
    ragflow_id VARCHAR(100),
    pushed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_be_score ON breaking_events(impact_score);
CREATE INDEX IF NOT EXISTS idx_be_cat ON breaking_events(category);
CREATE INDEX IF NOT EXISTS idx_be_created ON breaking_events(created_at);

-- 4. Mapping Table (Many-to-One: Stream Items -> Event)
-- Links raw posts to the consolidated event they describe.
CREATE TABLE IF NOT EXISTS event_stream_mapping (
    id UUID PRIMARY KEY,
    event_id UUID REFERENCES breaking_events(id) ON DELETE CASCADE,
    stream_id UUID REFERENCES breaking_stream_raw(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_esm_event ON event_stream_mapping(event_id);
CREATE INDEX IF NOT EXISTS idx_esm_stream ON event_stream_mapping(stream_id);
