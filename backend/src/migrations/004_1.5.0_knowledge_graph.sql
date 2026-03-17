-- Migration: 004_1.5.0_knowledge_graph.sql
-- Adds Knowledge Graph tracking fields to breaking_stream_raw.
-- 为突发事件原始流表添加知识图谱处理跟踪字段。

ALTER TABLE breaking_stream_raw ADD COLUMN IF NOT EXISTS kg_processed BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_bsr_kg ON breaking_stream_raw (kg_processed);
