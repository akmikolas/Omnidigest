"""
Scheduled and background jobs for OmniDigest. Contains tasks for fetching news, processing content, generating summaries, and handling webhooks.
OmniDigest 的定时和后台任务。包含抓取新闻、处理内容、生成总结和处理 Webhook 的任务。
"""
import logging
import asyncio
import datetime
from datetime import timedelta
from ..config import settings
from ..api.deps import get_db, get_rag, get_pusher, get_processor, get_analyzer, get_breaking_crawler, get_breaking_processor, get_breaking_alerter, get_llm_manager, get_astock_analyzer
from .scheduler import scheduler
from ..domains.ingestion.rss.standard_crawler import NewsCrawler
from ..domains.knowledge_base.sync_service import RAGService
from ..domains.knowledge_graph.extractor import KGExtractor
from ..domains.knowledge_graph.dgraph_client import DgraphClient
from .twitter import job_twitter_crawl, job_twitter_triage

import instructor
from pydantic import BaseModel, Field

# --- Pydantic Models for One-Pass Daily Summary ---
class ArticleTranslation(BaseModel):
    """
    Schema for a single article translation within the one-pass result.
    单通结果中单篇文章翻译的模式。
    
    Attributes:
        id (int): Original database ID of the article. / 文章的原始数据库 ID。
        chinese_title (str): Translated or improved Chinese title. / 翻译或改进后的中文标题。
        summary (str): Translated or improved Chinese summary. / 翻译或改进后的中文摘要。
        original_url (str): The exact original source_url of this article. / 文章的准确原始源 URL。
    """
    id: int
    chinese_title: str = Field(description="Translated or improved Chinese title.")
    summary: str = Field(description="Translated or improved Chinese summary (max 300 chars).")
    original_url: str = Field(description="The exact original source_url of this article to maintain mapping.")

class CategorySummary(BaseModel):
    """
    Schema for a category group within the daily summary.
    每日总结中类组的模式。
    
    Attributes:
        category (str): The English category name (e.g. 'AI & LLMs'). / 英语类别名称（例如 'AI & LLMs'）。
        overview (str): Concise summary of the trends in this category. / 该类别趋势的简明总结。
        critique (str): Sharp, spicy one-liner critique of the news. / 对新闻的犀利、刻薄的一句话锐评。
        articles (list[ArticleTranslation]): The processed articles for this category. / 该类别下处理后的文章列表。
    """
    category: str = Field(description="The English category name (e.g. 'AI & LLMs').")
    overview: str = Field(description="Concise summary of the trends in this category.")
    critique: str = Field(description="A professional editorial critique/intro for this entire category's news today.")
    articles: list[ArticleTranslation] = Field(description="The processed articles for this category.")

class DailySummaryResult(BaseModel):
    """
    The final one-pass result containing all translations and category summaries.
    最终的单通结果，包含所有翻译和类别总结。
    
    Attributes:
        overview (str): The executive overview of today's tech news. / 今日科技新闻的执行概览。
        categories (list[CategorySummary]): The summarized categories. / 汇总的类别列表。
    """
    overview: str = Field(description="The executive overview of today's tech news as a whole.")
    categories: list[CategorySummary] = Field(description="The summarized categories.")
# --------------------------------------------------

# Lazy load singletons for background tasks
db = get_db()
rag = get_rag()
pusher = get_pusher()
processor = get_processor()
breaking_crawler = get_breaking_crawler()
breaking_processor = get_breaking_processor()
breaking_alerter = get_breaking_alerter()

logger = logging.getLogger(__name__)

async def job_fetch_news():
    """
    Scheduled background job to fetch news articles from configured RSS feeds.
    定时后台任务，从配置的 RSS 订阅源中抓取新闻文章。
    
    Instantiates the NewsCrawler, runs its blocking IO operations in a separate thread, and then triggers content processing immediately.
    实例化 NewsCrawler，在单独的线程中运行其阻塞 IO 操作，然后立即触发内容处理。
    """
    logger.info("Starting scheduled news fetch...")
    crawler = NewsCrawler(db, rag)
    # Run loop-blocking IO in a separate thread
    # 在单独的线程中运行阻塞 IO
    await asyncio.to_thread(crawler.run)
    logger.info("News fetch completed.")
    
    # Trigger processing immediately after fetch
    # 抓取完成后立即触发处理
    await job_process_content()

async def job_process_content():
    """
    Background job to classify and score newly fetched articles.
    后台任务，用于分类和评估新抓取的文章。
    
    Delegates to the ContentProcessor to run a complete processing cycle using the LLM.
    委托给 ContentProcessor() 使用 LLM 运行一个完整的处理周期。
    
    Returns:
        None: / 无返回值。
    """
    logger.info("Starting content processing...")
    # Updated to handle loop processing logic internally in processor.run_processing_cycle
    count = await processor.run_processing_cycle()
    if count > 0:
        logger.info(f"Processed {count} articles.")

def _get_daily_context() -> str:
    """
    Helper function to retrieve and format the daily high-scoring articles context from the database.
    辅助方法，用于从数据库中检索并格式化每日高分文章的内容。
    
    This context is injected into prompts for generating daily summaries.
    此内容将被注入到用于生成每日总结的提示词中。
    
    Returns:
        str: A formatted markdown-like string containing grouped article summaries, or an empty string if none found. / 包含分组文章摘要的格式化类 markdown 字符串，如果没有找到则返回空字符串。
    """
    # 1. Retrieve High-Scoring Articles from DB (past 24h, score > 60)
    # 1. 从数据库检索高分文章（过去 24 小时，分数 > 60）
    articles = db.get_high_score_articles(hours=24, min_score=60)
    
    if not articles:
        return ""

    # 2. Group by Category
    # 2. 按类别分组
    categorized_content = {}
    for art in articles:
        cat = art.get('category', 'Other') or 'Other'
        if cat not in categorized_content:
            categorized_content[cat] = []
        categorized_content[cat].append(art)
    
    # 3. Construct Prompt with Categorized Sections
    # 3. 构建包含分类部分的提示词
    context_parts = []
    # Define preferred order
    # 定义首选顺序
    category_order = ["AI & LLMs", "Software Engineering", "Hardware & Semiconductors", "Cybersecurity", "Frontier Tech & Startups", "Web3", "Other"]
    
    for cat in category_order:
        if cat in categorized_content:
            items = categorized_content[cat]
            section = f"## {cat}\n"
            for item in items:
                # Use summary_raw if available, else first 200 chars of content
                # 如果有 summary_raw 则使用，否则使用内容的前 200 个字符
                desc = item.get('summary_raw') or item['content'][:200].replace('\n', ' ') + "..."
                section += f"- **{item['title']}** (Score: {item['score']})\n  {desc}\n  Source URL: {item['source_url']}\n"
            context_parts.append(section)
            
    # Add any remaining categories not in the ordered list
    # 添加任何不在排序列表中的剩余类别
    for cat, items in categorized_content.items():
        if cat not in category_order:
            section = f"## {cat}\n"
            for item in items:
                desc = item.get('summary_raw') or item['content'][:200].replace('\n', ' ') + "..."
                section += f"- **{item['title']}** (Score: {item['score']})\n  {desc}\n  Source URL: {item['source_url']}\n"
            context_parts.append(section)

    return "\n".join(context_parts)

UNIFIED_DAILY_SUMMARY_PROMPT = """
You are a senior tech editor compiling a daily news digest for professionals. 
Your task is to review all today's high-scoring articles, summarize them, and generate a cohesive, structured report in ONE PASS.

### INSTRUCTIONS:
1. **Overview**: Write an executive overview (`overview`) of today's tech news as a whole (in Chinese).
2. **Category Critiques**: For each category provided, write a professional editorial critique (`critique`) summarizing the major trends of that specific category today (in Chinese).
3. **Article Translation/Polishing**: For EVERY article provided in the input:
   - Provide a translated or polished Chinese title (`title`).
   - Provide a concise Chinese summary (`summary`).
   - YOU MUST include the exact `original_url` for every article so we can link them back to the database.

### INPUT ARTICLES (Categorized):
{context}

Respond STRICTLY with the requested Structured Output based on the schema mapping.
"""

async def job_daily_summary(push_telegram: bool = True, push_dingtalk: bool = True, custom_title_prefix: str = ""):
    """
    Generates the daily news summary using parallel LLM fragment generation. Constructs the target dictionary natively in Python and dispatches to Telegram and DingTalk.
    使用并行的 LLM 片段生成来生成每日新闻总结。在 Python 中原生构建目标字典，并分发到 Telegram 和钉钉。
    
    Args:
        push_telegram (bool, optional): Whether to push to Telegram. Defaults to True. / 是否推送到 Telegram。默认为 True。
        push_dingtalk (bool, optional): Whether to push to DingTalk. Defaults to True. / 是否推送到钉钉。默认为 True。
    """
    logger.info(f"Starting unified daily summary generation... (TG: {push_telegram}, DingTalk: {push_dingtalk})")
    
    articles = db.get_high_score_articles(hours=24, min_score=60)
    if not articles:
        logger.warning("No high-scoring articles found for daily summary.")
        return

    # Categorize articles
    categorized_content = {}
    for art in articles:
        cat = art.get('category', 'Other') or 'Other'
        if cat not in categorized_content:
            categorized_content[cat] = []
        categorized_content[cat].append(art)
        
    # Cap each category at 5 articles to keep the summary concise
    for cat in categorized_content:
        categorized_content[cat] = categorized_content[cat][:5]
    
    # Construct Context for One-Pass LLM
    context_parts = []
    category_order = ["AI & LLMs", "Software Engineering", "Hardware & Semiconductors", "Cybersecurity", "Frontier Tech & Startups", "Web3", "Other"]
    
    for cat in category_order:
        if cat in categorized_content:
            items = categorized_content[cat]
            section = f"## Category: {cat}\n"
            for item in items:
                desc = item.get('summary_raw') or item['content'][:200].replace('\n', ' ') + "..."
                section += f"- Title: {item['title']}\n  URL: {item['source_url']}\n  Summary: {desc}\n"
            context_parts.append(section)
    
    # Add unmapped
    for cat, items in categorized_content.items():
        if cat not in category_order:
            section = f"## Category: {cat}\n"
            for item in items:
                desc = item.get('summary_raw') or item['content'][:200].replace('\n', ' ') + "..."
                section += f"- Title: {item['title']}\n  URL: {item['source_url']}\n  Summary: {desc}\n"
            context_parts.append(section)
            
    prompt = UNIFIED_DAILY_SUMMARY_PROMPT.format(context="\n".join(context_parts))
    
    logger.info("Dispatching ONE-PASS LLM Daily Summary Generation...")
    llm_manager = get_llm_manager()
    try:
        result: DailySummaryResult = await llm_manager.chat_completion_structured(
            response_model=DailySummaryResult,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            service_name="daily_summary_generation"
        )
    except Exception as e:
        logger.error(f"Failed to generate structured daily summary: {e}")
        return

    # Python predefined mapping
    CATEGORY_MAPPING = {
        "AI & LLMs": ("人工智能与大模型", "🤖"),
        "Software Engineering": ("软件工程", "💻"),
        "Hardware & Semiconductors": ("硬件与半导体", "⚙️"),
        "Cybersecurity": ("网络安全", "🛡️"),
        "Frontier Tech & Startups": ("前沿科技与初创企业", "🚀"),
        "Web3": ("Web3", "⛓️"),
        "Other": ("综合", "📰")
    }
    
    # Construct final dictionary for UI / Notifications
    summary_data = {
        "overview": result.overview or "今日科技界动态汇编。",
        "custom_title_prefix": custom_title_prefix,
        "categories": []
    }
    
    # Iterate over the LLM generated structured categories
    for cat_data in result.categories:
        cat_name_en = cat_data.category
        cat_name_zh, emoji = CATEGORY_MAPPING.get(cat_name_en, ("综合", "📰"))
        
        formatted_articles = []
        for art in cat_data.articles:
            formatted_articles.append({
                "chinese_title": art.chinese_title,
                "original_url": art.original_url,
                "summary": art.summary
            })
            
        summary_data["categories"].append({
            "category_name": cat_name_zh,
            "emoji": emoji,
            "critique": cat_data.critique,
            "articles": formatted_articles
        })

    # === Dispatch ===
    if push_telegram:
        try:
            # Use per-robot routing: each TG robot renders its own daily_template
            for robot in settings.tg_robots:
                if robot.enable_daily:
                    html_text = pusher.render_template(robot.daily_template, summary_data)
                    reply_markup = {
                        "inline_keyboard": [
                            [
                                {"text": "📊 分析AI趋势 (7天)", "callback_data": "analyze_ai_7"},
                                {"text": "📈 综合周报 (7天)", "callback_data": "analyze_general_7"}
                            ],
                            [
                                {"text": "🌐 综合月报 (30天)", "callback_data": "analyze_general_30"}
                            ]
                        ]
                    }
                    pusher.send_telegram(html_text, reply_markup=reply_markup, chat_id=robot.chat_id)
            logger.info("Daily summary pushed to Telegram.")
        except Exception as e:
            logger.error(f"Failed pushing summary to Telegram: {e}")

    if push_dingtalk and settings.ding_robots:
        try:
            title = f"{custom_title_prefix}每日科技新闻"
            pusher.push_to_dingtalk(title, summary_data, event_type="daily")
            logger.info("Daily summary pushed to DingTalk.")
        except Exception as e:
            logger.error(f"Failed pushing summary to DingTalk: {e}")

    return summary_data

async def job_cleanup_low_quality():
    """
    Background job to permanently delete articles from the database and RAGFlow if their relevance score is strictly below a defined threshold.
    后台任务，用于从数据库和 RAGFlow 中永久删除相关性得分严格低于设定阈值的文章。
    
    Returns:
        None: / 无返回值。
    """
    logger.info("Starting low-quality article cleanup...")
    threshold = 45
    articles = db.get_low_score_articles(threshold=threshold)
    
    if not articles:
        logger.info("No low-score articles found for cleanup.")
        return

    logger.info(f"Found {len(articles)} articles to delete (score < {threshold}).")
    deleted_count = 0
    
    for art in articles:
        try:
            # First attempt to delete from RAGFlow knowledge base if it was synced
            # 首先尝试从 RAGFlow 知识库中删除（如果已同步）
            rag_id = art.get('ragflow_id')
            if rag_id:
                rag.delete_document(rag_id)
            
            # Then delete from local database
            # 然后从本地数据库中删除
            db.delete_article(art['id'])
            deleted_count += 1
        except Exception as e:
            logger.error(f"Error cleaning up article {art.get('id')}: {e}")
            
    logger.info(f"Cleanup completed. Deleted {deleted_count} articles.")

async def job_sync_rag():
    """
    Background job to incrementally synchronize historical, un-synced database articles to RAGFlow.
    后台任务，用于将未同步的历史数据库文章增量同步到 RAGFlow。
    
    Instantiates RAGService and runs its synchronous sync loop in a separate thread to prevent blocking.
    实例化 RAGService，并在单独的线程中运行其同步同步循环，以防止后台阻塞。
    
    Returns:
        None: / 无返回值。
    """
    logger.info("Starting historical RAGFlow sync...")
    sync_service = RAGService(db, rag)
    # Run sync in thread as it might be IO bound and we don't want to block loop too much if it was synchronous
    # 在线程中运行同步，因为它可能是 IO 密集型的，我们不想阻塞循环
    count = await asyncio.to_thread(sync_service.sync_articles_to_rag)
    logger.info(f"RAGFlow sync completed. Synced {count} articles.")

async def job_handle_telegram_callback(chat_id: int, callback_data: str):
    """
    Background job to handle inline keyboard button callbacks originating from Telegram. Parses the requested time window and topic, triggers an LLM analysis via AnalysisService, and replies to the specific chat with an HTML-formatted trend report.
    处理源自 Telegram 的内联键盘按钮回调的后台任务。解析请求的时间窗口和主题，通过 AnalysisService 触发 LLM 分析，并回复特定聊天，发送 HTML 格式的趋势报告。
    
    Args:
        chat_id (int): The Telegram chat ID where the button was clicked. / 点击按钮所在的 Telegram 聊天 ID。
        callback_data (str): The payload embedded in the button (e.g., "analyze_ai_7"). / 按钮中嵌入的有效负载（例如，“analyze_ai_7”）。
        
    Returns:
        None: / 无返回值。
    """
    logger.info(f"Handling Telegram callback: {callback_data} for chat {chat_id}")
    
    # Parse callback_data to determine query and days
    # 解析 callback_data 以确定查询和天数
    if callback_data == "analyze_ai_7":
        query = "过去 7 天内关于人工智能 (AI)、大模型 (LLMs) 和相关技术突破的核心趋势是什么？"
        days = 7
    elif callback_data == "analyze_general_7":
        query = "过去 7 天内科技圈发生了哪些重大事件？主要趋势是什么？"
        days = 7
    elif callback_data == "analyze_general_30":
        query = "总结过去 30 天内科技行业的重大发展和宏观趋势。"
        days = 30
    else:
        logger.warning(f"Unknown callback data: {callback_data}")
        return

    # Notify user that analysis started (optional if we ack'd the callback already, but good UX)
    # 通知用户分析已开始（如果我们已经确认了回调，这是可选的，但是很好的体验）
    
    try:
        # 1. Start Analysis using analyzer singleton
        # 1. 使用 analyzer 单例开始分析
        analyzer = get_analyzer()
        result = await analyzer.analyze_trends(query, days=days)
        
        # 2. Format Result into generic HTML structure with Telegram-compatible tags
        # 2. 将结果格式化为带有兼容 Telegram 标签的通用 HTML 结构
        final_text = f"<b>📉 深度趋势分析报告</b>\n<i>关键词: {query[:20]}... ({days}天)</i>\n\n{result}"
        
        # 3. Send back to the user/group using the robust pusher service
        # 3. 使用健壮的推送服务将其发回给用户/群组
        pusher.send_telegram(final_text, chat_id=str(chat_id))
        logger.info(f"Sent analysis result to chat {chat_id}")
        
    except Exception as e:
        logger.error(f"Error handling callback {callback_data}: {e}")
        # Try to notify user of failure
        # 尝试通知用户发生故障
        try:
            pusher.send_telegram("⚠️ 抱歉，生成分析报告时发生了错误。", chat_id=str(chat_id))
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")


import threading

_kg_extract_lock = threading.Lock()
_is_kg_extracting = False

def is_kg_extraction_running() -> bool:
    """
    Thread-safe check to see if KG extraction is currently active.
    线程安全地检查 KG 提取是否当前处于活跃状态。
    
    Returns:
        bool: True if running, False otherwise. / 如果正在运行则为 True，否则为 False。
    """
    with _kg_extract_lock:
        return _is_kg_extracting

def job_kg_extract():
    """
    Background job to incrementally extract entities and relations into Dgraph.
    Runs reliably using a fresh event loop so it doesn't conflict with APScheduler.
    增量提取实体和关系到 Dgraph 的后台任务。
    """
    if not getattr(settings, 'kg_enabled', False):
        return

    global _is_kg_extracting
    with _kg_extract_lock:
        if _is_kg_extracting:
            logger.warning("[Scheduled] Knowledge Graph Extraction skipped because it is already running.")
            return
        _is_kg_extracting = True

    try:
        logger.info("[Scheduled] Starting Knowledge Graph Extraction (last 168 hours)...")
        from ..api.deps import get_llm_manager
        dgraph = DgraphClient()
        extractor = KGExtractor(db, dgraph, get_llm_manager())

        async def wrapper():
            try:
                dgraph.init_schema()
                # hours=168 is just a fallback limit; kg_processed=FALSE ensures only new/failed ones run
                await extractor.run(hours=168)
            except Exception as e:
                logger.error(f"[Scheduled KG Extraction] Failed: {e}", exc_info=True)
            finally:
                dgraph.close()

        try:
            asyncio.run(wrapper())
        except Exception as e:
            logger.error(f"Critical error in job_kg_extract: {e}", exc_info=True)
    finally:
        with _kg_extract_lock:
            _is_kg_extracting = False


def job_kg_resolve():
    """
    Background job to run LLM-based entity deduplication across the graph.
    Runs periodically to maintain graph quality.
    基于 LLM 的实体去重后台任务。定期运行以维护图谱质量。
    """
    if not getattr(settings, 'kg_enabled', False):
        return

    logger.info("[Scheduled] Starting Knowledge Graph Entity Resolution...")
    from ..api.deps import get_llm_manager
    dgraph = DgraphClient()
    extractor = KGExtractor(db, dgraph, get_llm_manager())

    async def wrapper():
        try:
            await extractor.resolve_entities()
        except Exception as e:
            logger.error(f"[Scheduled KG Resolution] Failed: {e}", exc_info=True)
        finally:
            dgraph.close()

    try:
        asyncio.run(wrapper())
    except Exception as e:
        logger.error(f"Critical error in job_kg_resolve: {e}", exc_info=True)


def setup_scheduler():
    """
    Configures and starts the apscheduler instance with initial cron and interval jobs. Sets up news fetching, daily summaries, and automated cleanup routines.
    配置并使用初始的 cron 和间隔任务启动 apscheduler 实例。设置新闻抓取、每日总结和自动清理例程。
    
    Returns:
        None: / 无返回值。
    """
    scheduler.add_job(
        job_fetch_news, 
        'interval', 
        hours=settings.fetch_interval_hours, 
        id='fetch_news'
    )
    
    scheduler.add_job(
        job_daily_summary, 
        'cron', 
        hour=settings.summary_hour, 
        minute=settings.summary_minute, 
        id='daily_summary'
    )

    scheduler.add_job(
        job_cleanup_low_quality,
        'cron',
        hour=5,
        minute=0,
        id='cleanup_low_quality'
    )
    
    # ----------------------------------------------------
    # Breaking News Subsystem Tasks
    # 突发新闻子系统任务
    # ----------------------------------------------------
    if getattr(settings, 'enable_breaking_news', True):
        # 1. MVP Fast Lane Crawler (Runs every 10 minutes)
        # 快车道爬虫（每 10 分钟运行一次）
        async def run_crawler_job():
            await asyncio.to_thread(breaking_crawler.run)
            
        scheduler.add_job(
            run_crawler_job,
            'interval',
            minutes=settings.breaking_fetch_interval_minutes,
            id='breaking_fetch',
            next_run_time=datetime.datetime.now()
        )
        
        # 2. Breaking News Processor (Runs every 30 seconds for near real-time processing)
        # 突发新闻处理器（每30秒运行一次，实现近实时处理）
        async def run_processor_loop():
            try:
                await breaking_processor.run_processing_cycle()
            except Exception as e:
                logger.error(f"Breaking processor loop error: {e}", exc_info=True)
                raise

        scheduler.add_job(
            run_processor_loop,
            'interval',
            seconds=60,  # 60 seconds to allow enough time for LLM processing
            id='breaking_processor_loop',
            max_instances=2,  # Allow 2 concurrent instances in case processing takes longer than interval
            next_run_time=datetime.datetime.now() + datetime.timedelta(seconds=5)
        )

        # 3. Breaking Alerter (Runs every 60 seconds)
        # 突发新闻告警（每60秒运行一次）
        async def run_alerter_loop():
            try:
                await breaking_alerter.run_alerter_loop(interval_seconds=60)
            except Exception as e:
                logger.error(f"Breaking alerter loop error: {e}", exc_info=True)
                raise

        scheduler.add_job(
            run_alerter_loop,
            'interval',
            seconds=60,  # 60 seconds interval
            id='breaking_alerter_loop',
            max_instances=1,  # Prevent duplicate pushes from concurrent instances
            next_run_time=datetime.datetime.now() + timedelta(seconds=10)
        )

        # 4. Knowledge Graph Tasks
        # 知识图谱任务
        if getattr(settings, 'kg_enabled', False):
            # Extract triples every 15 minutes / 每 15 分钟提取三元组
            scheduler.add_job(
                job_kg_extract,
                'interval',
                minutes=15,
                id='kg_extract_interval',
                # Start first run 1 minute after boot
                next_run_time=datetime.datetime.now() + timedelta(minutes=1)
            )

            # Resolve duplicates every 6 hours / 每 6 小时合并重复实体
            scheduler.add_job(
                job_kg_resolve,
                'cron',
                hour='0,6,12,18',  # 00:00, 06:00, 12:00, 18:00
                minute=15,         # Wait 15 mins after extract runs / 等提取跑完 15 分钟后再跑消歧
                id='kg_resolve_cron'
            )
            logger.info("Knowledge Graph tasks (Extract 15m, Resolve 6h) scheduled.")
        
        # 5. Twitter Ingestion (Runs every 10 minutes) / 推特摄取（每 10 分钟一次）
        async def run_twitter_job():
            await asyncio.to_thread(job_twitter_crawl)
            
        scheduler.add_job(
            run_twitter_job,
            'interval',
            minutes=10,
            id='twitter_crawl',
            next_run_time=datetime.datetime.now() + timedelta(seconds=30)
        )
        
        # 6. Twitter AI Triage (Runs every 10 minutes, offset by 5 mins)
        scheduler.add_job(
            job_twitter_triage,
            'interval',
            minutes=10,
            id='twitter_triage',
            next_run_time=datetime.datetime.now() + timedelta(minutes=5)
        )
        
        logger.info("Breaking News Subsystem tasks scheduled.")

    # ==========================
    # A股分析定时任务
    # ==========================
    if getattr(settings, 'enable_astock_analysis', True):
        async def job_astock_pre_market():
            """
            A股盘前分析任务 - 每日开盘前执行。
            A-share market pre-market analysis job - runs before market open each day.
            """
            # Skip on weekends / 周末不执行
            from datetime import datetime
            if datetime.now().weekday() >= 5:
                logger.info("Skipping A股 pre-market analysis - weekend")
                return

            logger.info("Starting A股 pre-market analysis...")

            try:
                astock_analyzer = get_astock_analyzer()
                result = await astock_analyzer.pre_market_analysis(index_type="both")

                if result:
                    # 发送通知 - 使用 enable_astock 开关，模板根据配置和类型自动选择
                    prediction_type = result.get('prediction_type', 'pre_market')

                    # Telegram 模板映射
                    tg_template_suffix = {
                        'pre_market': '_pre_market',
                        'intraday': '_intraday',
                        'post_market': '_post_market',
                    }

                    for robot in settings.tg_robots:
                        if getattr(robot, 'enable_astock', True):
                            # 使用配置的 astock_template 作为基础，替换后缀
                            base_template = getattr(robot, 'astock_template', 'telegram_astock_pre_market.html.j2')
                            suffix = tg_template_suffix.get(prediction_type, '_pre_market')
                            # 替换后缀: telegram_astock_pre_market → telegram_astock_intraday
                            template = base_template.replace('_pre_market', suffix).replace('_intraday', suffix).replace('_post_market', suffix)
                            html_text = pusher.render_template(template, result)
                            pusher.send_telegram(html_text, chat_id=robot.chat_id)
                    logger.info("A-stock pre-market analysis pushed to Telegram.")

                    # DingTalk 模板映射
                    ding_template_suffix = {
                        'pre_market': '_pre_market',
                        'intraday': '_intraday',
                        'post_market': '_post_market',
                    }

                    for robot in settings.ding_robots:
                        if getattr(robot, 'enable_astock', True):
                            base_template = getattr(robot, 'astock_template', 'dingtalk_astock_pre_market.md.j2')
                            suffix = ding_template_suffix.get(prediction_type, '_pre_market')
                            ding_template = base_template.replace('_pre_market', suffix).replace('_intraday', suffix).replace('_post_market', suffix)
                            title = f"A股{'盘前' if prediction_type == 'pre_market' else '盘中' if prediction_type == 'intraday' else '盘后'}分析 / 新闻"
                            pusher.push_astock_to_dingtalk(title, result, ding_template)
                    logger.info("A-stock pre-market analysis pushed to DingTalk.")
                else:
                    logger.warning("No result from A股 pre-market analysis")

            except Exception as e:
                logger.error(f"Error in A股 pre-market analysis: {e}")

        async def job_astock_intraday():
            """
            A股盘中分析任务 - 每日盘中执行。
            A-share market intraday analysis job - runs during market hours each day.
            """
            # Skip on weekends / 周末不执行
            from datetime import datetime
            if datetime.now().weekday() >= 5:
                logger.info("Skipping A股 intraday analysis - weekend")
                return

            logger.info("Starting A股 intraday analysis...")

            try:
                astock_analyzer = get_astock_analyzer()
                result = await astock_analyzer.intraday_analysis(index_type="both")

                if result:
                    # 发送通知 - 使用 enable_astock 开关，模板根据配置和类型自动选择
                    prediction_type = result.get('prediction_type', 'intraday')

                    tg_template_suffix = {
                        'pre_market': '_pre_market',
                        'intraday': '_intraday',
                        'post_market': '_post_market',
                    }

                    for robot in settings.tg_robots:
                        if getattr(robot, 'enable_astock', True):
                            base_template = getattr(robot, 'astock_template', 'telegram_astock_pre_market.html.j2')
                            suffix = tg_template_suffix.get(prediction_type, '_intraday')
                            template = base_template.replace('_pre_market', suffix).replace('_intraday', suffix).replace('_post_market', suffix)
                            html_text = pusher.render_template(template, result)
                            pusher.send_telegram(html_text, chat_id=robot.chat_id)
                    logger.info("A-stock intraday analysis pushed to Telegram.")

                    ding_template_suffix = {
                        'pre_market': '_pre_market',
                        'intraday': '_intraday',
                        'post_market': '_post_market',
                    }

                    for robot in settings.ding_robots:
                        if getattr(robot, 'enable_astock', True):
                            base_template = getattr(robot, 'astock_template', 'dingtalk_astock_pre_market.md.j2')
                            suffix = ding_template_suffix.get(prediction_type, '_intraday')
                            ding_template = base_template.replace('_pre_market', suffix).replace('_intraday', suffix).replace('_post_market', suffix)
                            title = f"A股{'盘前' if prediction_type == 'pre_market' else '盘中' if prediction_type == 'intraday' else '盘后'}分析 / 新闻"
                            pusher.push_astock_to_dingtalk(title, result, ding_template)
                    logger.info("A-stock intraday analysis pushed to DingTalk.")
                else:
                    logger.warning("No result from A股 intraday analysis")

            except Exception as e:
                logger.error(f"Error in A股 intraday analysis: {e}")

        # 盘前分析 - 每天 8:30 执行
        scheduler.add_job(
            job_astock_pre_market,
            'cron',
            hour=settings.astock_pre_market_hour,
            minute=settings.astock_pre_market_minute,
            id='astock_pre_market'
        )
        logger.info(f"A股盘前分析 scheduled at {settings.astock_pre_market_hour}:{settings.astock_pre_market_minute}")

        # 盘中分析 - 每天 14:30 执行
        scheduler.add_job(
            job_astock_intraday,
            'cron',
            hour=settings.astock_intraday_hour,
            minute=settings.astock_intraday_minute,
            id='astock_intraday'
        )
        logger.info(f"A股盘中分析 scheduled at {settings.astock_intraday_hour}:{settings.astock_intraday_minute}")

        # 盘后分析 - 每天 15:30 执行（收盘后对比预测与实际）
        async def job_astock_post_market():
            """
            A股盘后分析任务 - 每日收盘后执行。
            A-share market post-market analysis job - runs after market close each day.
            """
            # Skip on weekends / 周末不执行
            from datetime import datetime
            if datetime.now().weekday() >= 5:
                logger.info("Skipping A股 post-market analysis - weekend")
                return

            logger.info("Starting A股 post-market analysis...")

            try:
                astock_analyzer = get_astock_analyzer()
                result = await astock_analyzer.post_market_analysis(index_type="both")

                if result:
                    # 发送通知 - 使用 enable_astock 开关，模板根据配置和类型自动选择
                    prediction_type = result.get('prediction_type', 'post_market')

                    tg_template_suffix = {
                        'pre_market': '_pre_market',
                        'intraday': '_intraday',
                        'post_market': '_post_market',
                    }

                    for robot in settings.tg_robots:
                        if getattr(robot, 'enable_astock', True):
                            base_template = getattr(robot, 'astock_template', 'telegram_astock_pre_market.html.j2')
                            suffix = tg_template_suffix.get(prediction_type, '_post_market')
                            template = base_template.replace('_pre_market', suffix).replace('_intraday', suffix).replace('_post_market', suffix)
                            html_text = pusher.render_template(template, result)
                            pusher.send_telegram(html_text, chat_id=robot.chat_id)
                    logger.info("A-stock post-market analysis pushed to Telegram.")

                    ding_template_suffix = {
                        'pre_market': '_pre_market',
                        'intraday': '_intraday',
                        'post_market': '_post_market',
                    }

                    for robot in settings.ding_robots:
                        if getattr(robot, 'enable_astock', True):
                            base_template = getattr(robot, 'astock_template', 'dingtalk_astock_pre_market.md.j2')
                            suffix = ding_template_suffix.get(prediction_type, '_post_market')
                            ding_template = base_template.replace('_pre_market', suffix).replace('_intraday', suffix).replace('_post_market', suffix)
                            title = f"A股{'盘前' if prediction_type == 'pre_market' else '盘中' if prediction_type == 'intraday' else '盘后'}分析 / 新闻"
                            pusher.push_astock_to_dingtalk(title, result, ding_template)
                    logger.info("A-stock post-market analysis pushed to DingTalk.")
                else:
                    logger.warning("No result from A股 post-market analysis")

            except Exception as e:
                logger.error(f"Error in A股 post-market analysis: {e}")

        scheduler.add_job(
            job_astock_post_market,
            'cron',
            hour=settings.astock_post_market_hour,
            minute=settings.astock_post_market_minute,
            id='astock_post_market'
        )
        logger.info(f"A股盘后分析 scheduled at {settings.astock_post_market_hour}:{settings.astock_post_market_minute}")

    # A股异常波动检测任务
    if getattr(settings, 'enable_astock_alert', True):
        async def job_astock_alert():
            """A股异常波动检测任务"""
            try:
                from ..domains.analysis.alert_service import get_alert_service
                alert_service = get_alert_service()
                result = await alert_service.run_check()
                logger.info(f"A股异常波动检测完成: {result.get('total_anomalies', 0)} 项异常")
            except Exception as e:
                logger.error(f"Error in A股异常波动检测: {e}")

        # 添加定时任务 - 每30分钟执行一次（交易时段）
        check_interval = getattr(settings, 'astock_alert_check_interval', 30)
        scheduler.add_job(
            job_astock_alert,
            'interval',
            minutes=check_interval,
            id='astock_alert'
        )
        logger.info(f"A股异常波动检测 scheduled every {check_interval} minutes")

    scheduler.start()
