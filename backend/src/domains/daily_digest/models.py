"""
Daily News Domain — Pydantic Models for Structured Output.
每日新闻领域 — 用于结构化输出的 Pydantic 模型。
"""
from pydantic import BaseModel, Field
from typing import List


class DailyArticleResult(BaseModel):
    """
    Result for a single article classification.
    单篇文章分类结果。
    """
    article_id: str = Field(description="Original article ID from database")
    category: str = Field(description="Category: [AI & LLMs, Software Engineering, Hardware & Semiconductors, Cybersecurity, Frontier Tech & Startups, Web3, Other]")
    score: int = Field(description="Relevance score 0-100")
    summary: str = Field(description="One-sentence summary (max 50 words)")


class DailyBatchResult(BaseModel):
    """
    Batch result for daily news classification.
    每日新闻分类批次结果。
    """
    results: List[DailyArticleResult] = Field(description="List of article classification results")
