"""
Content processing service. Uses LLMs to classify and score newly fetched articles, prioritizing them for summaries.
内容处理服务。使用 LLM 对新抓取的文章进行分类和评分，为总结生成提供优先级。

Uses the generic OnePass framework for unified AI analysis.
使用通用 OnePass 框架进行统一的 AI 分析。
"""
import logging
import asyncio
import json
from typing import List
from ...config import settings
from ..core.onepass import OnePassProcessor, OnePassConfig
from .models import DailyArticleResult, DailyBatchResult
from ..ingestion.rss.standard_crawler import NewsCrawler  # Import purely for type hinting if needed

logger = logging.getLogger(__name__)


class ContentProcessor:
    """
    Processes and classifies news content using LLM via OnePass framework.
    使用 OnePass 框架通过 LLM 处理和分类新闻内容。
    """

    def __init__(self, db, llm_manager):
        """
        Initializes the ContentProcessor with required connections.
        使用所需的连接初始化 ContentProcessor。

        Args:
            db (DatabaseManager): The database manager. / 数据库管理器。
            llm_manager (LLMManager): The LLM management service for dynamic model selection. / LLM 管理服务，用于动态模型选择。
        """
        self.db = db
        self.llm = llm_manager

        # Initialize generic OnePass processor for daily news
        self.onepass_config = OnePassConfig(
            name="daily_news",
            prompt_template=settings.prompt_daily_onepass,
            response_model=DailyBatchResult,
            context_providers=[],  # No external context needed for classification
            temperature=0.1,
            max_context_items=0
        )

        self.onepass = OnePassProcessor(
            config=self.onepass_config,
            llm_manager=llm_manager,
            db=db,
            rag_client=None
        )

    def _format_articles(self, articles: List[dict]) -> str:
        """
        Format articles for OnePass input.
        将文章格式化为 OnePass 输入。
        """
        formatted = ""
        for article in articles:
            formatted += f"--- ARTICLE_ID: {article['id']} ---\n"
            formatted += f"Title: {article['title']}\n"
            formatted += f"Content: {article['content'][:1000]}...\n\n"
        return formatted

    async def _classify_batch(self, articles: List[dict]) -> List[DailyArticleResult]:
        """
        Classify a batch of articles using OnePass.
        使用 OnePass 分类一批文章。
        """
        if not articles:
            return []

        # Format articles as input
        input_text = self._format_articles(articles)

        try:
            # Use OnePass processor
            batch_result = await self.onepass.process(
                input_data=input_text,
                context_params={}
            )

            if batch_result and hasattr(batch_result, 'results'):
                return batch_result.results
            return []

        except Exception as e:
            logger.error(f"Error in batch classification: {e}")
            return []

    async def classify_article(self, title: str, content: str) -> tuple[str, int, str]:
        """
        Uses the configured external LLM to classify an article's category, assign a relevance score, and generate a concise one-sentence summary.
        使用配置的外部 LLM 对文章的类别进行分类，分配相关性得分，并生成简洁的一句话摘要。

        Args:
            title (str): The original title of the article. / 文章的原始标题。
            content (str): The full text content of the article. / 文章的全文内容。

        Returns:
            tuple[str, int, str]: A tuple containing (category, score, summary). / 包含 (category, score, summary) 的元组。
        """
        if not self.llm:
            logger.warning("LLM client not available for classification.")
            return "Other", 0, None

        # Format single article
        articles = [{"id": "single", "title": title, "content": content}]
        results = await self._classify_batch(articles)

        if results:
            result = results[0]
            return result.category, result.score, result.summary

        return "Other", 0, None

    async def run_processing_cycle(self) -> int:
        """
        Continuously fetches batches of unclassified articles from the database, classifies them concurrently using the OnePass LLM, and updates their records. Stops when no more unclassified articles are found.
        持续从数据库中分批获取未分类的文章，使用 OnePass LLM 并发地对它们进行分类，并更新它们的记录。当没有找到更多未分类的文章时停止。

        Returns:
            int: The total number of articles processed in this cycle. / 此周期处理的文章总数。
        """
        total_processed = 0
        batch_size = 10
        # Limit the number of concurrent LLM API calls to avoid hitting rate limits
        # 限制并发的 LLM API 调用数以避免触发速率限制
        max_concurrent_calls = 5
        semaphore = asyncio.Semaphore(max_concurrent_calls)

        async def process_batch(articles: list):
            async with semaphore:
                try:
                    # Use OnePass batch classification
                    results = await self._classify_batch(articles)
                    if not results:
                        return 0

                    # Create lookup by article_id
                    result_map = {r.article_id: r for r in results}

                    processed = 0
                    for article in articles:
                        result = result_map.get(article['id'])
                        if result:
                            # Validate category
                            valid_categories = [
                                "AI & LLMs", "Software Engineering", "Hardware & Semiconductors",
                                "Cybersecurity", "Frontier Tech & Startups", "Web3", "Other"
                            ]
                            category = result.category if result.category in valid_categories else "Other"

                            await asyncio.to_thread(
                                self.db.update_classification,
                                article['id'],
                                category,
                                result.score,
                                result.summary
                            )
                            logger.info(f"Classified '{article['title'][:30]}...' -> {category} ({result.score})")
                            processed += 1
                    return processed

                except Exception as e:
                    logger.error(f"Failed to process batch: {e}")
                    return 0

        while True:
            articles = await asyncio.to_thread(self.db.get_unclassified_articles, limit=batch_size)
            if not articles:
                break

            logger.info(f"Processing batch of {len(articles)} articles using OnePass...")

            # Fire batch classification
            processed = await process_batch(articles)
            total_processed += processed

            # Small delay before the next batch if there are multiple batches
            # 如果有多个批次，在下一个批次之前稍作延迟
            await asyncio.sleep(1)

        return total_processed
