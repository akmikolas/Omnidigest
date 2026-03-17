-- Add cooling timestamp to twitter_accounts
ALTER TABLE twitter_accounts ADD COLUMN IF NOT EXISTS cooled_until TIMESTAMP;
