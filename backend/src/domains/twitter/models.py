"""
Twitter Ingestion Domain — Pydantic Models for Structured Output.
推特摄取领域 — 用于结构化输出的 Pydantic 模型。
"""
from pydantic import BaseModel, Field

class TwitterTriageResult(BaseModel):
    """
    Schema for a single tweet triage result within a batch.
    单条推文分类结果的模式定义。
    """
    tweet_id: str = Field(description="The original Twitter status ID (e.g. '123456') to ensure mapping.")
    is_significant: bool = Field(description="True if this is high-value intelligence, False if it is noise.")
    impact_score: int = Field(0, description="Score from 0 to 100.")
    summary_zh: str | None = Field(None, description="Concise summary in Chinese.")
    category: str | None = Field(None, description="Category: [Politics, Macro Economy, Tech, Finance, Crisis, Other]")
    is_thread_start: bool = Field(False, description="True if this tweet starts a thread.")
    reasoning: str | None = Field(None, description="Internal reasoning for the score.")

class TwitterBatchTriageResult(BaseModel):
    """
    The final one-pass batch result containing multiple tweet triage results.
    包含多个推文分类结果的一轮批次最终结果。
    """
    results: list[TwitterTriageResult] = Field(description="List of triage results for the provided batch of tweets.")


class OnePassTwitterResult(BaseModel):
    """
    One-Pass Twitter triage result with event clustering.
    单次 LLM 调用完成推文分类和事件匹配。

    Combines triage, scoring, and event matching in a single LLM call.
    将分类、打分和事件匹配合并到单次 LLM 调用中。
    """
    tweet_id: str = Field(description="The original Twitter status ID for mapping.")
    is_significant: bool = Field(description="True if this is high-value intelligence, False if it is noise.")
    impact_score: int = Field(0, description="Score from 0 to 100.")
    summary_zh: str | None = Field(None, description="Concise summary in Chinese.")
    category: str | None = Field(None, description="Category: [Politics, Macro Economy, Tech, Finance, Crisis, Other]")
    is_thread_start: bool = Field(False, description="True if this tweet starts a thread.")
    matched_event_id: str | None = Field(
        None,
        description="UUID of existing event to link to. Null if no match or should create new."
    )
    should_create_event: bool = Field(
        False,
        description="True if this is significant and should create a new event (no matching existing event)."
    )
    reasoning: str | None = Field(None, description="Internal reasoning for the triage decision.")


class OnePassTwitterBatchResult(BaseModel):
    """
    One-Pass batch result for Twitter triage with event matching.
    推特 One-Pass 批次分类结果（含事件匹配）。

    Each result includes both triage decision and event matching in one LLM call.
    每个结果在单次 LLM 调用中包含分类决策和事件匹配。
    """
    results: list[OnePassTwitterResult] = Field(
        description="List of One-Pass triage results with event matching."
    )
