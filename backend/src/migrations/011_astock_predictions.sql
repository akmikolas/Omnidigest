-- A股趋势预测表
CREATE TABLE IF NOT EXISTS astock_predictions (
    id UUID PRIMARY KEY,
    prediction_date DATE NOT NULL,
    index_type VARCHAR(20) NOT NULL,  -- 'shanghai' 或 'shenzhen'
    prediction_type VARCHAR(20) NOT NULL,  -- 'pre_market' 或 'intraday'
    prediction_direction VARCHAR(10) NOT NULL,  -- 'up' / 'down' / 'neutral'
    confidence_score INT DEFAULT 50,  -- 0-100 置信度
    news_summary TEXT,  -- 基于的主要新闻摘要
    actual_close_change NUMERIC(10,4),  -- 实际收盘涨跌幅（收盘后填写）
    is_correct BOOLEAN,  -- 预测是否正确
    "created_at" TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_astock_pred_date ON astock_predictions(prediction_date);
CREATE INDEX IF NOT EXISTS idx_astock_pred_index ON astock_predictions(index_type);
CREATE INDEX IF NOT EXISTS idx_astock_pred_type ON astock_predictions(prediction_type);
