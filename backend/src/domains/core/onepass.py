"""
Generic One-Pass Processor Framework.
通用单次 LLM 调用处理器框架。

Provides a configurable framework for unified AI analysis tasks like triage, scoring,
and clustering in a single LLM call.
提供可配置的统一 AI 分析任务框架，如单次 LLM 调用中的分类、打分和聚类。

Usage:
    from src.omnidigest.domains.core.onepass import OnePassProcessor, OnePassConfig

    config = OnePassConfig(
        name="my_processor",
        prompt_template=MY_PROMPT,
        response_model=MyOutputModel,
        context_providers=["recent_events"],
        temperature=0.1
    )
    processor = OnePassProcessor(config, llm_manager)
    result = await processor.process(input_data)
"""
import logging
from typing import Type, Optional, Any, Dict, List, Callable
from pydantic import BaseModel, Field
from ...core.llm_manager import LLMManager

logger = logging.getLogger(__name__)


class OnePassConfig(BaseModel):
    """
    Configuration for a One-Pass processor.
    One-Pass 处理器的配置。

    Attributes:
        name (str): Unique identifier for this processor. / 处理器的唯一标识。
        prompt_template (str): Prompt template with placeholders. / 带占位符的提示词模板。
        response_model (Type[BaseModel]): Pydantic model for structured output. / 结构化输出的 Pydantic 模型。
        context_providers (list[str]): List of context providers to use. / 使用的上下文提供者列表。
        temperature (float): LLM temperature setting. / LLM 温度设置。
    """
    name: str = Field(description="Unique identifier for this processor / 处理器的唯一标识")
    prompt_template: str = Field(description="Prompt template with placeholders / 带占位符的提示词模板")
    response_model: Type[BaseModel] = Field(description="Pydantic model for structured output / 结构化输出的 Pydantic 模型")
    context_providers: List[str] = Field(
        default_factory=list,
        description="Context providers: recent_events, active_stories, rag, custom / 上下文提供者"
    )
    temperature: float = Field(default=0.1, description="LLM temperature / LLM 温度")
    max_context_items: int = Field(default=10, description="Max items to include in context / 上下文包含的最大条目数")


class ContextProvider:
    """
    Base class for context providers.
    上下文提供者的基类。

    Context providers fetch additional data to include in the LLM prompt.
    上下文提供者获取额外数据以包含在 LLM 提示词中。
    """

    def get_context(self, **kwargs) -> str:
        """
        Get context text for the prompt.
        获取提示词的上下文文本。

        Args:
            **kwargs: Provider-specific parameters. / 提供者特定参数。

        Returns:
            Formatted context string. / 格式化的上下文字符串。
        """
        raise NotImplementedError


class RecentEventsProvider(ContextProvider):
    """
    Provides recent events context.
    提供最近事件上下文。

    Retrieves recent events from database for clustering/matching.
    从数据库检索最近事件用于聚类/匹配。
    """

    def __init__(self, db, event_type: str = "twitter", hours: int = 24, limit: int = 10):
        """
        Initialize the provider.
        初始化提供者。

        Args:
            db: Database manager. / 数据库管理器。
            event_type: Type of events (twitter, breaking, etc.). / 事件类型。
            hours: Lookback hours. / 回溯小时数。
            limit: Max events to return. / 返回的最大事件数。
        """
        self.db = db
        self.event_type = event_type
        self.hours = hours
        self.limit = limit

    def get_context(self, **kwargs) -> str:
        """
        Get recent events as context text.
        将最近事件作为上下文文本获取。
        """
        # Allow override from kwargs
        event_type = kwargs.get("event_type", self.event_type)
        hours = kwargs.get("hours", self.hours)
        limit = kwargs.get("limit", self.limit)

        try:
            if event_type == "twitter":
                events = self.db.get_recent_twitter_events(hours=hours)
            elif event_type == "breaking":
                events = self.db.get_recent_breaking_events(hours=hours)
            else:
                return "No events."

            if not events:
                return "No recent events."

            # Apply limit
            events = events[:limit]

            context = ""
            for event in events:
                context += f"---\n"
                context += f"ID: {event.get('id')}\n"
                context += f"Title: {event.get('event_title', event.get('title', 'N/A'))}\n"
                context += f"Category: {event.get('category', 'N/A')}\n"
                if event.get('source_count'):
                    context += f"Source Count: {event['source_count']}\n"
            return context
        except Exception as e:
            logger.warning(f"Failed to get recent events: {e}")
            return "No recent events."


class ActiveStoriesProvider(ContextProvider):
    """
    Provides active stories context.
    提供活跃故事上下文。

    Retrieves active story narratives for broader context.
    检索活跃故事线以获取更广泛的上下文。
    """

    def __init__(self, db, hours: int = 24 * 10, limit: int = 10):
        """
        Initialize the provider.
        初始化提供者。
        """
        self.db = db
        self.hours = hours
        self.limit = limit

    def get_context(self, **kwargs) -> str:
        """
        Get active stories as context text.
        将活跃故事作为上下文文本获取。
        """
        # Allow override from kwargs
        hours = kwargs.get("stories_hours", self.hours)
        limit = kwargs.get("stories_limit", self.limit)

        try:
            stories = self.db.get_active_stories(hours=hours)
            if not stories:
                return "No active stories."

            stories = stories[:limit]

            context = ""
            for story in stories:
                context += f"---\n"
                context += f"Story ID: {story.get('id')}\n"
                context += f"Title: {story.get('story_title', story.get('title', 'N/A'))}\n"
                context += f"Category: {story.get('category', 'N/A')}\n"
            return context
        except Exception as e:
            logger.warning(f"Failed to get active stories: {e}")
            return "No active stories."


class RAGProvider(ContextProvider):
    """
    Provides RAG (Retrieval-Augmented Generation) context.
    提供 RAG（检索增强生成）上下文。

    Uses vector similarity search to find relevant context.
    使用向量相似度搜索查找相关上下文。
    """

    def __init__(self, rag_client, dataset_id: str, top_k: int = 3, similarity_threshold: float = 0.65):
        """
        Initialize the provider.
        初始化提供者。
        """
        self.rag_client = rag_client
        self.dataset_id = dataset_id
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def get_context(self, query: str = None, **kwargs) -> str:
        """
        Get RAG context for the query.
        获取查询的 RAG 上下文。
        """
        if not self.rag_client or not query:
            return ""

        try:
            chunks = self.rag_client.search_chunks(
                question=query,
                dataset_id=self.dataset_id,
                top_k=self.top_k,
                similarity_threshold=self.similarity_threshold
            )
            if not chunks:
                return ""

            context = ""
            for chunk in chunks:
                context += f"---\n{chunk.content}\n"
            return context
        except Exception as e:
            logger.warning(f"RAG lookup failed: {e}")
            return ""


class OnePassProcessor:
    """
    Generic One-Pass processor for unified AI analysis.
    通用单次 LLM 调用处理器，用于统一 AI 分析。

    This framework enables single-LLM-call processing for tasks that traditionally
    required multiple steps (e.g., triage + scoring + clustering).
    此框架支持单次 LLM 调用处理传统上需要多步骤的任务（如分类 + 打分 + 聚类）。

    Example:
        config = OnePassConfig(
            name="custom_processor",
            prompt_template=CUSTOM_PROMPT,
            response_model=CustomOutputModel,
            context_providers=["recent_events", "rag"]
        )
        processor = OnePassProcessor(config, llm_manager)
        result = await processor.process(input_data)
    """

    def __init__(
        self,
        config: OnePassConfig,
        llm_manager: LLMManager,
        db=None,
        rag_client=None,
        rag_config: Dict[str, any] = None,
        custom_providers: Dict[str, ContextProvider] = None
    ):
        """
        Initialize the One-Pass processor.
        初始化 One-Pass 处理器。

        Args:
            config (OnePassConfig): Processor configuration. / 处理器配置。
            llm_manager (LLMManager): LLM service manager. / LLM 服务管理器。
            db: Database manager for context providers. / 上下文提供者的数据库管理器。
            rag_client: RAG client for vector search. / 向量搜索的 RAG 客户端。
            rag_config (dict): RAG provider config (dataset_id, top_k, similarity_threshold). / RAG 提供者配置。
            custom_providers (dict): Custom context providers. / 自定义上下文提供者。
        """
        self.config = config
        self.llm = llm_manager
        self.db = db
        self.rag_client = rag_client
        self.rag_config = rag_config or {}

        # Initialize built-in providers
        self.providers: Dict[str, ContextProvider] = {}

        if db:
            # Add built-in providers that need DB
            if "recent_events" in config.context_providers:
                self.providers["recent_events"] = RecentEventsProvider(db)
            if "active_stories" in config.context_providers:
                self.providers["active_stories"] = ActiveStoriesProvider(db)

        if rag_client and "rag" in config.context_providers:
            # RAGProvider requires dataset_id
            dataset_id = self.rag_config.get("dataset_id")
            if dataset_id:
                self.providers["rag"] = RAGProvider(
                    rag_client,
                    dataset_id=dataset_id,
                    top_k=self.rag_config.get("top_k", 3),
                    similarity_threshold=self.rag_config.get("similarity_threshold", 0.65)
                )

        # Add custom providers
        if custom_providers:
            self.providers.update(custom_providers)

    def _gather_context(self, input_data: str, **kwargs) -> Dict[str, str]:
        """
        Gather context from all configured providers.
        从所有配置的提供者收集上下文。

        Args:
            input_data: The main input data. / 主输入数据。
            **kwargs: Additional parameters for providers. / 提供者的额外参数。

        Returns:
            Dict mapping provider name to context text. / 提供者名称到上下文文本的映射。
        """
        context = {}

        # Add query for RAG provider
        if "rag" in self.providers and isinstance(self.providers["rag"], RAGProvider):
            context["rag"] = self.providers["rag"].get_context(query=input_data)

        # Add other providers
        for name in self.config.context_providers:
            if name in self.providers and name != "rag":
                try:
                    context[name] = self.providers[name].get_context(**kwargs)
                except Exception as e:
                    logger.warning(f"Provider {name} failed: {e}")
                    context[name] = ""

        return context

    def _format_prompt(self, input_data: str, context: Dict[str, str]) -> str:
        """
        Format the prompt template with input and context.
        使用输入和上下文格式化提示词模板。

        Args:
            input_data: The main input data. / 主输入数据。
            context: Gathered context from providers. / 从提供者收集的上下文。

        Returns:
            Formatted prompt string. / 格式化的提示词字符串。
        """
        # Build context text for prompt
        context_parts = []
        for name, text in context.items():
            if text:
                context_parts.append(f"【{name.upper()}】:\n{text}")

        full_context = "\n\n".join(context_parts) if context_parts else "No additional context."

        # Format the prompt
        prompt = self.config.prompt_template.format(
            input_data=input_data,
            context=full_context,
            **context  # Also pass individual context items
        )

        return prompt

    async def process(self, input_data: str, context_params: Dict[str, Any] = None) -> Optional[BaseModel]:
        """
        Execute One-Pass analysis.
        执行单次分析。

        Args:
            input_data: The main input data to analyze. / 要分析的主输入数据。
            context_params (dict): Additional parameters for context providers. / 上下文提供者的额外参数。

        Returns:
            Validated Pydantic model result, or None on failure. / 验证后的 Pydantic 模型结果，失败返回 None。
        """
        try:
            # Gather context from providers
            params = context_params or {}
            context = self._gather_context(input_data, **params)

            # Format prompt
            prompt = self._format_prompt(input_data, context)

            # Call LLM with structured output
            result = await self.llm.chat_completion_structured(
                response_model=self.config.response_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                service_name=f"onepass_{self.config.name}"
            )

            logger.info(f"OnePass processor '{self.config.name}' completed successfully")
            return result

        except Exception as e:
            logger.error(f"OnePass processor '{self.config.name}' failed: {e}")
            return None

    async def process_batch(self, inputs: List[str], context_params: Dict[str, Any] = None) -> List[Optional[BaseModel]]:
        """
        Execute One-Pass analysis for multiple inputs.
        对多个输入执行单次分析。

        Args:
            inputs (list): List of input data to analyze. / 要分析的输入数据列表。
            context_params (dict): Additional parameters for context providers. / 上下文提供者的额外参数。

        Returns:
            List of results. / 结果列表。
        """
        results = []
        for input_data in inputs:
            result = await self.process(input_data, context_params)
            results.append(result)
        return results
