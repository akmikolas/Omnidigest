"""
Core Processing Engine for Breaking News.
Takes raw streams from the database, runs LLM triage, clusters them into events,
and assigns impact scores.
突发新闻的核心处理引擎。
从数据库获取原始信息流，运行 LLM 过滤，将它们聚合为事件，并分配影响力评分。
"""
import asyncio
import logging
import re
from pydantic import BaseModel, Field
from ...core.database import DatabaseManager
from ..knowledge_base.rag_client import RAGClient
from ..core.onepass import OnePassProcessor, OnePassConfig
from ...config import settings

logger = logging.getLogger(__name__)


# ==========================
# 辅助函数
# ==========================

def _extract_content_from_raw_text(raw_text: str) -> str:
    """
    从 raw_text 中提取 Content 部分。
    raw_text 格式为: "Title: xxx\nContent: xxx"
    """
    if "Content:" in raw_text:
        return raw_text.split("Content:", 1)[1].strip()
    return raw_text


def _extract_title_from_raw_text(raw_text: str) -> str:
    """
    从 raw_text 中提取 Title 部分。
    """
    if "Title:" in raw_text:
        parts = raw_text.split("Content:", 1)
        title = parts[0]
        if title.startswith("Title:"):
            title = title[6:].strip()
        return title
    return ""


def _is_english_content(text: str) -> bool:
    """
    检测内容是否为纯英文（英文字符占比超过 90%）。
    用于判断是否需要使用翻译专用 prompt。
    """
    # 提取纯字母字符
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return False
    # 计算英文字符占比
    english_count = sum(1 for c in alpha_chars if ord(c) < 128)
    english_ratio = english_count / len(alpha_chars)
    return english_ratio > 0.9


class OnePassBreakingResult(BaseModel):
    """
    Schema for the one-pass structured response from the LLM for breaking news triage.
    用于突发新闻过滤的 LLM 单通结构化响应模式。

    Attributes:
        is_breaking (bool): True if the content is confirmed as breaking news. / 如果内容被确认为突发新闻，则为 True。
        event_title (str): Headline for the event in Chinese. / 事件的中文标题。
        summary (str): Concise 1-2 sentence summary in Chinese. / 事件的 1-2 句核心中文摘要。
        category (str): Predefined category name. / 预定义的类别名称。
        impact_score (int): Normalized impact score (0-100). / 归一化后的影响力评分（0-100）。
        matched_event_id (str): UUID of an existing similar event if found. / 如果找到，则为现有相似事件的 UUID。
        matched_story_id (str): UUID of the broader story arc this belongs to. / 该事件所属的更广泛故事线的 UUID。
    """
    is_breaking: bool = Field(description="True if this is an explosive/breaking event, False if it is noise or routine chatter.")
    event_title: str | None = Field(None, description="A short, punchy headline in CHINESE. (Required if is_breaking is True)")
    summary: str | None = Field(None, description="A concise 1-2 sentence summary in CHINESE. (Required if is_breaking is True)")
    category: str | None = Field(None, description="Category of the event.")
    impact_score: int | None = Field(None, description="Impact score from 0 to 100.")
    matched_event_id: str | None = Field(None, description="UUID of the exact same event if duplicated from Recent Events list, else null.")
    matched_story_id: str | None = Field(None, description="UUID of the broader story arc this belongs to from Active Stories list, else null.")


class BreakingProcessor:
    """
    Main processor for the breaking news pipeline.
    突发新闻管线的主处理器。

    Uses the generic OnePass framework for unified AI analysis.
    使用通用 OnePass 框架进行统一的 AI 分析。
    """
    def __init__(self, db: DatabaseManager, llm_manager, rag: RAGClient):
        """
        Initializes the BreakingProcessor with necessary clients.
        使用必要的客户端初始化 BreakingProcessor。

        Args:
            db (DatabaseManager): Relational database manager. / 关系数据库管理器。
            llm_manager (LLMManager): LLM service manager. / LLM 服务管理器。
            rag (RAGClient): RAG client for context retrieval. / 用于上下文检索的 RAG 客户端。
        """
        self.db = db
        self.llm = llm_manager
        self.rag = rag

        # Initialize generic OnePass processor
        # Determine context providers based on RAG settings
        context_providers = ["recent_events", "active_stories"]
        if settings.breaking_rag_enabled and settings.breaking_rag_dataset_id:
            context_providers.append("rag")

        self.onepass_config = OnePassConfig(
            name="breaking_news",
            prompt_template=settings.prompt_breaking_onepass,
            response_model=OnePassBreakingResult,
            context_providers=context_providers,
            temperature=0.1,
            max_context_items=settings.breaking_context_recent_events
        )

        # Initialize RAG provider with config if enabled
        rag_client = None
        rag_config = {}
        if settings.breaking_rag_enabled and settings.breaking_rag_dataset_id:
            rag_client = self.rag
            rag_config = {
                "dataset_id": settings.breaking_rag_dataset_id,
                "top_k": 3,
                "similarity_threshold": 0.65
            }

        self.onepass = OnePassProcessor(
            config=self.onepass_config,
            llm_manager=llm_manager,
            db=db,
            rag_client=rag_client,
            rag_config=rag_config
        )

    async def _analyze_and_route_stream(self, raw_text: str) -> OnePassBreakingResult | None:
        """
        Uses the generic OnePass processor to analyze and route the stream.
        使用通用 OnePass 处理器分析和路由信息流。

        根据内容语言自动选择合适的 prompt。
        """
        # 检测内容语言
        content = _extract_content_from_raw_text(raw_text)
        is_english = _is_english_content(content)

        # 根据语言选择 prompt
        if is_english:
            prompt_template = settings.prompt_breaking_onepass_english
            logger.debug(f"Detected English content, using translation prompt")
        else:
            prompt_template = settings.prompt_breaking_onepass

        try:
            # Pass event_type to get correct events from DB
            result = await self.onepass.process_with_custom_prompt(
                input_data=raw_text,
                custom_prompt_template=prompt_template,
                context_params={
                    "event_type": "breaking",
                    "hours": 48,
                    "limit": settings.breaking_context_recent_events,
                    "stories_hours": settings.breaking_story_lookback_days * 24,
                    "stories_limit": settings.breaking_context_active_stories,
                    "rag_dataset_id": settings.breaking_rag_dataset_id if settings.breaking_rag_enabled else None,
                    "rag_top_k": 3,
                    "rag_threshold": 0.65
                }
            )
            return result
        except Exception as e:
            logger.error(f"One-Pass processing failed: {e}")
            return None

    async def _retry_with_fallback_prompt(self, raw_text: str) -> OnePassBreakingResult | None:
        """
        使用更简洁的翻译 prompt 重试。
        当第一次调用返回空标题时调用此方法。
        """
        try:
            logger.info(f"Retrying with fallback translation prompt...")
            result = await self.onepass.process_with_custom_prompt(
                input_data=raw_text,
                custom_prompt_template=settings.prompt_breaking_onepass_retry,
                context_params={
                    "event_type": "breaking",
                    "hours": 48,
                    "limit": settings.breaking_context_recent_events,
                    "stories_hours": settings.breaking_story_lookback_days * 24,
                    "stories_limit": settings.breaking_context_active_stories,
                }
            )
            return result
        except Exception as e:
            logger.error(f"Fallback prompt retry failed: {e}")
            return None

    async def process_single_stream(self, stream) -> bool:
        """
        Processes a single raw stream using One-Pass logic.
        使用 One-Pass 逻辑从头到尾处理单个原始信息流。

        质量控制:
        1. Content 长度门槛检查
        2. 空标题自动重试
        """
        stream_id = stream['id']
        raw_text = stream['raw_text']

        # ========== 方案1: Content 长度门槛 ==========
        content = _extract_content_from_raw_text(raw_text)
        if len(content) < settings.breaking_min_content_length:
            logger.warning(f"Stream {stream_id} content too short ({len(content)} chars < {settings.breaking_min_content_length}), skipping")
            await asyncio.to_thread(self.db.update_breaking_stream_status, stream_id, 2)
            return False

        # ========== 1. Mega LLM Call ==========
        result = await self._analyze_and_route_stream(raw_text)
        if not result:
            logger.error(f"Failed to process stream {stream_id}")
            await asyncio.to_thread(self.db.update_breaking_stream_status, stream_id, 2)
            return False

        # ========== 方案2: 空标题重试机制 ==========
        if not result.event_title and settings.breaking_max_title_retries > 0:
            logger.info(f"Stream {stream_id} returned empty title, retrying with fallback prompt...")
            result_retry = await self._retry_with_fallback_prompt(raw_text)
            if result_retry and result_retry.event_title:
                logger.info(f"Retry successful for stream {stream_id}")
                result = result_retry
            else:
                logger.warning(f"Retry also failed for stream {stream_id}")

        # ========== 2. Extract Response ==========
        if not result.is_breaking:
            logger.debug(f"Stream {stream_id} triaged as NOISE. Ignoring.")
            await asyncio.to_thread(self.db.update_breaking_stream_status, stream_id, 2)
            return False

        logger.info(f"Stream {stream_id} validated as BREAKING NEWS. Final Score: {result.impact_score}")

        # ========== 3. 处理标题为空的情况 ==========
        # 如果重试后仍然没有有效标题，跳过此 stream
        if not result.event_title:
            logger.warning(f"Stream {stream_id} has no valid title after retry, skipping")
            await asyncio.to_thread(self.db.update_breaking_stream_status, stream_id, 2)
            return False

        # Pydantic safely guarantees these are typed
        title = result.event_title
        summary = result.summary or ''
        category = result.category or 'Other'
        score = result.impact_score or 0

        # Clean up string "null"s from LLM hallucinations
        event_id = result.matched_event_id
        if event_id and event_id.lower() == "null":
            event_id = None

        # 4. Save / Update Event
        is_new_event = False
        if event_id:
            await asyncio.to_thread(self.db.update_breaking_event, event_id, title, summary, score)
        else:
            event_id = await asyncio.to_thread(self.db.create_breaking_event, title, summary, category, score)
            is_new_event = True

        # 5. Auto-Ingest to RAGFlow
        if is_new_event and settings.breaking_rag_enabled and settings.breaking_rag_dataset_id:
            try:
                content_to_upload = f"Event ID: {event_id}\n\nTitle: {title}\nSummary: {summary}\nCategory: {category}\nImpact Score: {score}"
                doc_id = await asyncio.to_thread(
                    self.rag.upload_document,
                    title=f"Breaking_{event_id}",
                    content=content_to_upload,
                    metadata={"event_id": event_id, "category": category},
                    dataset_id=settings.breaking_rag_dataset_id
                )
                if doc_id:
                     await asyncio.to_thread(self.rag.trigger_parsing, [doc_id], settings.breaking_rag_dataset_id)
                     logger.info(f"Auto-ingested new breaking event into RAGFlow KB: {event_id}")
            except Exception as e:
                logger.error(f"Failed to auto-ingest to RAGFlow: {e}")

        # 6. Link Mapping
        if event_id:
            await asyncio.to_thread(self.db.link_stream_to_event, stream_id, event_id)
            await asyncio.to_thread(self.db.update_breaking_stream_status, stream_id, 1)

            # 7. Story Matching
            story_id = result.matched_story_id
            if story_id and story_id.lower() == "null":
                story_id = None

            if story_id:
                await asyncio.to_thread(self.db.link_event_to_story, event_id, story_id)
                source_count = await asyncio.to_thread(self.db.get_story_source_count, story_id)
                await asyncio.to_thread(self.db.update_story, story_id, title, summary, score, source_count)
                await asyncio.to_thread(self.db.update_story_verification, story_id, source_count)
                logger.info(f"Event '{title}' linked to Story [{story_id}] (sources: {source_count})")
            else:
                story_id = await asyncio.to_thread(self.db.create_story, title, summary, category, score)
                if story_id:
                    await asyncio.to_thread(self.db.link_event_to_story, event_id, story_id)
                    logger.info(f"Created NEW Story [{story_id}] for event '{title}'")

            logger.info(f"Successfully processed breaking event: '{title}' (Score: {score})")
            return True
        return False


    async def run_processing_cycle(self):
        """
        Pulls unclassified raw streams and processes them concurrently.
        Single batch per invocation - scheduler handles continuous triggering.
        提取未分类的原始流并并发处理。每次调用只处理一个批次，调度器负责持续触发。
        """
        batch_size = settings.breaking_processor_batch_size
        max_concurrent = settings.breaking_processor_concurrency
        semaphore = asyncio.Semaphore(max_concurrent)

        async def sem_process(stream):
            async with semaphore:
                return await self.process_single_stream(stream)

        # Single batch processing - no infinite loop
        # 每次调度只处理一个批次，不使用 while True 循环
        streams = await asyncio.to_thread(self.db.get_unprocessed_breaking_streams, limit=batch_size)
        if not streams:
            return  # No pending work, exit cleanly

        logger.info(f"Processing batch of {len(streams)} raw breaking streams...")

        tasks = [sem_process(stream) for stream in streams]
        await asyncio.gather(*tasks, return_exceptions=True)
