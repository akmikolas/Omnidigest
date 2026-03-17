-- Twitter Triage columns for Phase 2
-- ---------------------------------

ALTER TABLE twitter_stream_raw ADD COLUMN IF NOT EXISTS impact_score INT DEFAULT 0;
ALTER TABLE twitter_stream_raw ADD COLUMN IF NOT EXISTS category VARCHAR(50);
ALTER TABLE twitter_stream_raw ADD COLUMN IF NOT EXISTS summary_zh TEXT;
ALTER TABLE twitter_stream_raw ADD COLUMN IF NOT EXISTS is_thread_start BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_twitter_stream_impact ON twitter_stream_raw(impact_score);
