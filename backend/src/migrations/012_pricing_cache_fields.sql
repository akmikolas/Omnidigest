-- Migration: Add pricing and cached_tokens fields
-- Run this SQL to update existing database

-- 1. Add price fields to llm_models table
ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS input_price_per_m DECIMAL(10, 2) DEFAULT 7.0;
ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS output_price_per_m DECIMAL(10, 2) DEFAULT 7.0;

-- 2. Add cached_tokens field to token_usage table
ALTER TABLE token_usage ADD COLUMN IF NOT EXISTS cached_tokens INT DEFAULT 0;

-- 3. Update existing models with actual pricing (example for DashScope models)
-- You can adjust prices based on actual model pricing

-- Example: Update specific models with correct prices
-- UPDATE llm_models SET input_price_per_m = 1.0, output_price_per_m = 4.0 WHERE model_name = 'qwen-plus';
-- UPDATE llm_models SET input_price_per_m = 0.2, output_price_per_m = 0.8 WHERE model_name = 'qwen-turbo';
-- UPDATE llm_models SET input_price_per_m = 60.0, output_price_per_m = 120.0 WHERE model_name = 'qwen-max';

-- Verify the changes
SELECT 'llm_models columns:' as info;
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'llm_models' AND column_name IN ('input_price_per_m', 'output_price_per_m');

SELECT 'token_usage columns:' as info;
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'token_usage' AND column_name = 'cached_tokens';
