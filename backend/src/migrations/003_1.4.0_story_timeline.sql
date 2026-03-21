-- Migration Script for 1.4.0 Story Timeline & Cross-Verification
-- 故事线时间线与交叉验证迁移脚本
-- Adds the breaking_stories table and links events to stories for better clustering,
-- cross-source verification, and smart alert deduplication.

-- 1. Breaking Stories Table (故事线表)
-- A Story groups related Events that belong to the same news narrative/topic.
-- 一个 Story 将属于同一新闻叙事/主题的相关事件分组。
CREATE TABLE IF NOT EXISTS breaking_stories (
    id UUID PRIMARY KEY,
    story_title VARCHAR(512) NOT NULL,
    story_summary TEXT,
    category VARCHAR(100),
    peak_score INT DEFAULT 0,                    -- Highest impact score among child events / 子事件中的最高影响力分数
    source_count INT DEFAULT 0,                  -- Number of distinct source platforms / 独立信息源平台数量
    status VARCHAR(20) DEFAULT 'developing',     -- developing / verified / resolved / 状态: 发展中/已验证/已结束
    pushed BOOLEAN DEFAULT FALSE,                -- Whether this story has been pushed at least once / 是否已推送过
    push_count INT DEFAULT 0,                    -- Total number of pushes for this story / 该故事线的总推送次数
    last_pushed_at TIMESTAMP,                    -- Last push timestamp / 上次推送时间
    last_pushed_score INT DEFAULT 0,             -- Score at the time of last push / 上次推送时的分数
    "created_at" TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bs_status ON breaking_stories(status);
CREATE INDEX IF NOT EXISTS idx_bs_score ON breaking_stories(peak_score);
CREATE INDEX IF NOT EXISTS idx_bs_created ON breaking_stories("created_at");
CREATE INDEX IF NOT EXISTS idx_bs_updated ON breaking_stories(updated_at);

-- 2. Add story_id foreign key to breaking_events
-- 为 breaking_events 表添加 story_id 外键
ALTER TABLE breaking_events ADD COLUMN IF NOT EXISTS story_id UUID REFERENCES breaking_stories(id);
CREATE INDEX IF NOT EXISTS idx_be_story ON breaking_events(story_id);

-- 3. Add success_count to breaking_rss_sources if not exists
-- 为 breaking_rss_sources 添加 success_count 列（如不存在）
ALTER TABLE breaking_rss_sources ADD COLUMN IF NOT EXISTS success_count INT DEFAULT 0;
