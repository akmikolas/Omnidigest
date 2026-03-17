"""
API router definitions for the OmniDigest backend. Provides endpoints for manual job triggering, health checks, and webhooks.
OmniDigest 后端 API 路由定义。提供手动触发任务、健康检查和 Webhook 的服务端点。
"""
import logging
from functools import wraps
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, BackgroundTasks, Request
from ..jobs import (
    job_fetch_news,
    job_process_content,
    job_daily_summary,
    job_handle_telegram_callback,
    job_kg_extract,
    is_kg_extraction_running
)
from ..jobs.scheduler import scheduler
from ..core.cache import cache
from .auth import verify_api_key
from .deps import get_analyzer
from fastapi import Depends

router = APIRouter(prefix="/api")


def cached_endpoint(key_prefix: str, ttl: int = 60):
    """
    Decorator for caching endpoint responses.
    缓存端点响应的装饰器。

    Args:
        key_prefix: Cache key prefix / 缓存键前缀
        ttl: Time to live in seconds / 过期时间（秒）
    """
    # Inner decorator function that wraps the original function with caching logic.
    # 内部装饰器函数，使用缓存逻辑包装原始函数。

    # Args:
    #     func: The function to be wrapped. / 要包装的函数。

    # Returns:
    #     Wrapped function with caching. / 带缓存的包装函数。
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            cache_key = f"omnidigest:{key_prefix}"
            # Add query params to key if present
            if kwargs:
                params = "_".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None)
                if params:
                    cache_key = f"{cache_key}:{params}"

            # Try to get from cache
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            if result is not None:
                cache.set(cache_key, result, ttl=ttl)

            return result
        return wrapper
    return decorator

@router.post("/trigger/fetch", dependencies=[Depends(verify_api_key)])
async def trigger_fetch(background_tasks: BackgroundTasks):
    """
    Manually triggers the news fetching background job.
    手动在后台触发新闻抓取任务。
    
    Args:
        background_tasks (BackgroundTasks): FastAPI utility for scheduling background operations. / FastAPI 用于调度后台操作的工具。
        
    Returns:
        dict: A status confirmation message. / 状态确认消息。
    """
    # Enqueue the job_fetch_news function to run asynchronously
    # 将 job_fetch_news 函数排队以异步运行
    background_tasks.add_task(job_fetch_news)
    return {"status": "accepted", "message": "News fetch started in background"}

@router.post("/trigger/process", dependencies=[Depends(verify_api_key)])
async def trigger_process(background_tasks: BackgroundTasks):
    """
    Manually triggers the content processing and LLM classification job.
    手动触发内容处理和 LLM 分类任务。
    
    Args:
        background_tasks (BackgroundTasks): FastAPI utility. / FastAPI 工具。
        
    Returns:
        dict: A status confirmation message. / 状态确认消息。
    """
    # Enqueue the job_process_content function
    # 将 job_process_content 函数排队
    background_tasks.add_task(job_process_content)
    return {"status": "accepted", "message": "Content processing started in background"}

@router.post("/trigger/kg_extract", dependencies=[Depends(verify_api_key)])
async def trigger_kg_extract(background_tasks: BackgroundTasks):
    """
    Manually triggers the Knowledge Graph extraction job.
    手动触发知识图谱抽取任务。
    """
    if is_kg_extraction_running():
        return {"status": "already_running", "message": "Knowledge Graph extraction is currently running."}
        
    background_tasks.add_task(job_kg_extract)
    return {"status": "accepted", "message": "Knowledge Graph extraction started in background."}

@router.post("/trigger/summary", dependencies=[Depends(verify_api_key)])
async def trigger_summary(background_tasks: BackgroundTasks):
    """
    Manually triggers ALL summary generation jobs (Telegram, DingTalk, etc.).
    手动在后台触发所有总结生成任务（Telegram、钉钉等）。
    
    Args:
        background_tasks (BackgroundTasks): FastAPI utility. / FastAPI 工具。
        
    Returns:
        dict: A status confirmation message. / 状态确认消息。
    """
    # Enqueue the master job_daily_summary function
    # 将主总结生成函数 job_daily_summary 排队
    background_tasks.add_task(job_daily_summary)
    return {"status": "accepted", "message": "All summary generations started."}

@router.post("/trigger/summary/telegram", dependencies=[Depends(verify_api_key)])
async def trigger_summary_telegram(background_tasks: BackgroundTasks):
    """
    Manually triggers only the Telegram summary generation job.
    手动触发仅 Telegram 总结生成任务。
    
    Args:
        background_tasks (BackgroundTasks): FastAPI utility. / FastAPI 工具。
        
    Returns:
        dict: A status confirmation message. / 状态确认消息。
    """
    background_tasks.add_task(job_daily_summary, push_telegram=True, push_dingtalk=False)
    return {"status": "accepted", "message": "Telegram summary generation started."}

@router.post("/trigger/summary/dingtalk", dependencies=[Depends(verify_api_key)])
async def trigger_summary_dingtalk(background_tasks: BackgroundTasks):
    """
    Manually triggers only the DingTalk summary generation job.
    手动触发仅钉钉总结生成任务。
    
    Args:
        background_tasks (BackgroundTasks): FastAPI utility. / FastAPI 工具。
        
    Returns:
        dict: A status confirmation message. / 状态确认消息。
    """
    background_tasks.add_task(job_daily_summary, push_telegram=False, push_dingtalk=True)
    return {"status": "accepted", "message": "DingTalk summary generation started."}

@router.post("/trigger/sync/rag", dependencies=[Depends(verify_api_key)])
async def trigger_sync_rag(background_tasks: BackgroundTasks):
    """
    Manually triggers the background job to synchronize historical articles to RAGFlow.
    Useful for populating the knowledge base after initial setup.
    手动触发后台任务，将历史文章同步到 RAGFlow。在初始设置后用于填充知识库很有用。
    
    Args:
        background_tasks (BackgroundTasks): FastAPI utility. / FastAPI 工具。
        
    Returns:
        dict: A status confirmation message. / 状态确认消息。
    """
    # Import locally to avoid circular dependencies if any
    # 局部导入以避免潜在的循环依赖
    from ..jobs import job_sync_rag
    background_tasks.add_task(job_sync_rag)
    return {"status": "accepted", "message": "RAGFlow sync started in background."}

@router.get("/health")
async def health_check():
    """
    Health check endpoint to verify the API is running and check scheduler status.
    健康检查接口，用于验证 API 是否正在运行并检查调度器状态。
    
    Returns:
        dict: The health status and scheduler running state. / 健康状态和调度器运行状态。
    """
    return {"status": "ok", "scheduler_running": scheduler.running}

@router.get("/token-stats", dependencies=[Depends(verify_api_key)])
async def get_token_stats(days: int = 30):
    """
    Endpoint for querying aggregated token usage statistics by service and model.
    用于按服务和模型查询聚合的令牌使用统计信息的端点。

    Args:
        days (int, optional): Number of days to look back. Defaults to 30.

    Returns:
        dict: Token usage statistics.
    """
    import asyncio
    from .deps import get_db

    if days < 1 or days > 365:
        return {"error": "Days must be between 1 and 365"}

    db = get_db()
    stats = await asyncio.to_thread(db.get_token_usage_stats, days=days)
    return {"status": "ok", "days": days, "stats": stats}


@router.get("/token-stats/range", dependencies=[Depends(verify_api_key)])
async def get_token_stats_by_range(start_date: str = None, end_date: str = None, hours: int = None):
    """
    Endpoint for querying token usage by custom date range.
    按自定义日期范围查询 Token 使用情况。

    Args:
        start_date (str): Start date in ISO format (YYYY-MM-DD)
        end_date (str): End date in ISO format (YYYY-MM-DD)
        hours (int): Alternative to dates - last N hours

    Returns:
        dict: Token usage statistics.
    """
    import asyncio
    from datetime import datetime, timedelta
    from .deps import get_db
    from psycopg2.extras import RealDictCursor

    db = get_db()

    def get_stats():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if hours:
                    # Use hours directly
                    cur.execute("""
                        SELECT
                            service_name,
                            model_name,
                            COUNT(*) as total_requests,
                            SUM(prompt_tokens) as total_prompt,
                            SUM(completion_tokens) as total_completion,
                            SUM(cached_tokens) as cached_tokens
                        FROM token_usage
                        WHERE created_at > NOW() - INTERVAL '%s hours'
                        GROUP BY service_name, model_name
                        ORDER BY service_name, model_name
                    """, (hours,))
                elif start_date and end_date:
                    # Use date range
                    cur.execute("""
                        SELECT
                            service_name,
                            model_name,
                            COUNT(*) as total_requests,
                            SUM(prompt_tokens) as total_prompt,
                            SUM(completion_tokens) as total_completion,
                            SUM(cached_tokens) as cached_tokens
                        FROM token_usage
                        WHERE created_at >= %s AND created_at < %s
                        GROUP BY service_name, model_name
                        ORDER BY service_name, model_name
                    """, (start_date, end_date))
                else:
                    # Default to last 24 hours
                    cur.execute("""
                        SELECT
                            service_name,
                            model_name,
                            COUNT(*) as total_requests,
                            SUM(prompt_tokens) as total_prompt,
                            SUM(completion_tokens) as total_completion,
                            SUM(cached_tokens) as cached_tokens
                        FROM token_usage
                        WHERE created_at > NOW() - INTERVAL '24 hours'
                        GROUP BY service_name, model_name
                        ORDER BY service_name, model_name
                    """)
                return cur.fetchall()

    stats = await asyncio.to_thread(get_stats)

    # Calculate time range info
    if hours:
        range_info = f"Last {hours} hours"
    elif start_date and end_date:
        range_info = f"{start_date} to {end_date}"
    else:
        range_info = "Last 24 hours"

    return {"status": "ok", "range": range_info, "stats": stats}

@router.post("/analyze/trends", dependencies=[Depends(verify_api_key)])
async def analyze_trends(query: str, days: int = 30, analyzer = Depends(get_analyzer)):
    """
    Endpoint for performing trend analysis based on a user query over a specified number of past days.
    用于基于用户查询在过去指定天数内执行趋势分析的服务端点。
    
    Args:
        query (str): The search topic or question (e.g., "AI funding"). / 搜索主题或问题（例如，“AI 融资”）。
        days (int, optional): Number of days to look back. Defaults to 30. / 要回顾的天数。默认为 30。
        
    Returns:
        dict: Contains the 'result' key with the LLM-generated HTML report or error. / 包含 'result' 键，值为 LLM 生成的 HTML 报告或错误。
    """
    # Validate the days parameter
    # 验证 days 参数
    if days < 1 or days > 365:
        return {"error": "Days must be between 1 and 365"}
        
    result = await analyzer.analyze_trends(query, days=days)
    return {"result": result}

@router.post("/webhook/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook endpoint to receive and process Telegram updates (e.g., inline keyboard button clicks).
    Configured directly in Telegram Bot API to point here.
    用于接收和处理 Telegram 更新（例如内联键盘按钮点击）的 Webhook 接口。直接在 Telegram Bot API 中配置指向此处。
    
    Args:
        request (Request): The incoming raw FastAPI request object containing Telegram JSON payload. / 包含 Telegram JSON 负载的传入原始 FastAPI 请求对象。
        background_tasks (BackgroundTasks): FastAPI utility for scheduling. / FastAPI 调度工具。
        
    Returns:
        dict: A generic 200 OK status to acknowledge receipt to Telegram. / 通用的 200 OK 状态，以向 Telegram 确认接收。
    """
    update = await request.json()
    
    # Handle Callback Queries (Button Clicks from Inline Keyboards)
    # 处理回调查询（来自内联键盘的按钮点击）
    if "callback_query" in update:
        query = update["callback_query"]
        callback_id = query["id"]
        data = query.get("data", "")
        # Extract the user's chat_id so we know who clicked the button
        # 提取用户的 chat_id 以便我们知道是谁点击了按钮
        chat_id = query["message"]["chat"]["id"]
        
        # Acknowledge callback quickly via separate request so the button loading animation stops
        # 通过单独的请求快速确认回调，以停止按钮的加载动画
        import requests
        from ..config import settings
        # Get bot_token from first TG robot
        bot_token = settings.tg_robots[0].bot_token if settings.tg_robots else None
        ack_url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        try:
             # Send a brief "Analyzing..." message as toast
             # 发送一个简短的“分析中...”消息作为吐司提示
             requests.post(ack_url, json={"callback_query_id": callback_id, "text": "分析中，请稍候..."})
        except Exception:
             pass
        
        # Dispatch the actual heavy LLM analysis to a background job to avoid timeouts
        # 将实际繁重的 LLM 分析分派给后台任务以避免超时
        background_tasks.add_task(job_handle_telegram_callback, chat_id, data)
        
    # Always return 200 OK so Telegram stops retrying the webhook
    # 始终返回 200 OK，以便 Telegram 停止重试 Webhook
    return {"status": "ok"}


# ==========================
# Stats Endpoints (Dashboard)
# ==========================

@router.get("/stats/overview", dependencies=[Depends(verify_api_key)])
@cached_endpoint("stats:overview", ttl=60)
async def get_stats_overview():
    """
    Get system overview statistics for dashboard.
    获取仪表盘系统概览统计。

    Returns:
        dict: Overview stats including article count, events, token usage, etc.
    """
    import asyncio
    from .deps import get_db

    db = get_db()

    # Get article counts
    # Query article count statistics from database.
    # 从数据库查询文章统计信息。
    def get_article_counts():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 1) as classified,
                        COUNT(*) FILTER (WHERE status = 0) as unclassified,
                        COUNT(*) FILTER (WHERE score >= 60) as high_score,
                        COUNT(*) FILTER (WHERE publish_time > NOW() - INTERVAL '24 hours') as last_24h
                    FROM news_articles
                """)
                return cur.fetchone()

    # Get breaking news counts
    """
    Query breaking news event counts from database.
    从数据库查询突发新闻事件数量。
    """
    def get_breaking_counts():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total_events,
                        COUNT(*) FILTER (WHERE pushed = true) as pushed,
                        (SELECT COUNT(*) FROM breaking_stories WHERE status = 'developing') as active_stories
                    FROM breaking_events
                    WHERE created_at > NOW() - INTERVAL '7 days'
                """)
                return cur.fetchone()

    # Get twitter counts
    """
    Query Twitter stream statistics from database.
    从数据库查询 Twitter 流统计信息。
    """
    def get_twitter_counts():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total_tweets,
                        COUNT(*) FILTER (WHERE status = 1) as processed,
                        COUNT(*) FILTER (WHERE impact_score >= 80) as high_impact,
                        (SELECT COUNT(*) FROM twitter_events WHERE created_at > NOW() - INTERVAL '24 hours') as events_24h
                    FROM twitter_stream_raw
                """)
                return cur.fetchone()

    # Get RSS source health
    """
    Query RSS source health status from database.
    从数据库查询 RSS 源健康状态。
    """
    def get_rss_health():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE enabled = true) as enabled,
                        COUNT(*) FILTER (WHERE enabled = false) as disabled
                    FROM rss_sources
                """)
                return cur.fetchone()

    # Get LLM status
    """
    Query LLM model status from database.
    从数据库查询 LLM 模型状态。
    """
    def get_llm_status():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE is_active = true) as active,
                        SUM(fail_count) as total_failures
                    FROM llm_models
                """)
                return cur.fetchone()

    # Get Twitter accounts status
    """
    Query Twitter account pool status from database.
    从数据库查询 Twitter 账号池状态。
    """
    def get_twitter_accounts_status():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'active') as active,
                        COUNT(*) FILTER (WHERE status = 'cooling') as cooling,
                        COUNT(*) FILTER (WHERE status = 'error') as error
                    FROM twitter_accounts
                """)
                return cur.fetchone()

    # Run all queries
    articles = await asyncio.to_thread(get_article_counts)
    breaking = await asyncio.to_thread(get_breaking_counts)
    twitter = await asyncio.to_thread(get_twitter_counts)
    rss = await asyncio.to_thread(get_rss_health)
    llm = await asyncio.to_thread(get_llm_status)
    twitter_accounts = await asyncio.to_thread(get_twitter_accounts_status)

    return {
        "status": "ok",
        "articles": articles,
        "breaking_news": breaking,
        "twitter": twitter,
        "rss_sources": rss,
        "llm_models": llm,
        "twitter_accounts": twitter_accounts
    }


@router.get("/stats/articles", dependencies=[Depends(verify_api_key)])
@cached_endpoint("stats:articles", ttl=60)
async def get_article_stats(days: int = 7):
    """
    Get article statistics by category and score distribution.
    获取按分类和分数分布的文章统计。

    Args:
        days (int): Number of days to look back. Defaults to 7.
    """
    import asyncio
    from .deps import get_db

    if days < 1 or days > 90:
        return {"error": "Days must be between 1 and 90"}

    db = get_db()

    """
    Query article statistics including category distribution, score distribution, and daily trend.
    查询文章统计数据，包括分类分布、分数分布和每日趋势。
    """
    def get_stats():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Category distribution
                cur.execute("""
                    SELECT category, COUNT(*) as count
                    FROM news_articles
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    GROUP BY category
                    ORDER BY count DESC
                """, (days,))
                categories = cur.fetchall()

                # Score distribution
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE score >= 80) as high,
                        COUNT(*) FILTER (WHERE score >= 60 AND score < 80) as medium,
                        COUNT(*) FILTER (WHERE score < 60) as low
                    FROM news_articles
                    WHERE created_at > NOW() - INTERVAL '%s days'
                """, (days,))
                score_dist = cur.fetchone()

                # Daily trend
                cur.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM news_articles
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """, (days,))
                trend = cur.fetchall()

                return {"categories": categories, "score_distribution": score_dist, "daily_trend": trend}

    result = await asyncio.to_thread(get_stats)
    return {"status": "ok", "days": days, "stats": result}


@router.get("/stats/breaking", dependencies=[Depends(verify_api_key)])
@cached_endpoint("stats:breaking", ttl=30)
async def get_breaking_stats(days: int = 7):
    """
    Get breaking news statistics.
    获取突发新闻统计。

    Args:
        days (int): Number of days to look back. Defaults to 7.
    """
    import asyncio
    from .deps import get_db

    if days < 1 or days > 90:
        return {"error": "Days must be between 1 and 90"}

    db = get_db()

    """
    Query breaking news statistics including recent events, active stories, and summary.
    查询突发新闻统计数据，包括近期事件、活跃故事和摘要。
    """
    def get_stats():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Recent events
                cur.execute("""
                    SELECT id, event_title, summary, category, impact_score, pushed, created_at
                    FROM breaking_events
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    ORDER BY created_at DESC
                    LIMIT 20
                """, (days,))
                recent_events = cur.fetchall()

                # Active stories
                cur.execute("""
                    SELECT id, story_title, category, peak_score, source_count, status, pushed
                    FROM breaking_stories
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    ORDER BY peak_score DESC
                    LIMIT 10
                """, (days,))
                stories = cur.fetchall()

                # Stats
                cur.execute("""
                    SELECT
                        COUNT(*) as total_events,
                        COUNT(*) FILTER (WHERE pushed = true) as pushed,
                        AVG(impact_score) as avg_score,
                        MAX(impact_score) as max_score
                    FROM breaking_events
                    WHERE created_at > NOW() - INTERVAL '%s days'
                """, (days,))
                summary = cur.fetchone()

                return {"recent_events": recent_events, "active_stories": stories, "summary": summary}

    result = await asyncio.to_thread(get_stats)
    return {"status": "ok", "days": days, "stats": result}


@router.get("/stats/twitter", dependencies=[Depends(verify_api_key)])
@cached_endpoint("stats:twitter", ttl=30)
async def get_twitter_stats(days: int = 7):
    """
    Get Twitter monitoring statistics.
    获取推特监控统计。

    Args:
        days (int): Number of days to look back. Defaults to 7.
    """
    import asyncio
    from .deps import get_db

    if days < 1 or days > 90:
        return {"error": "Days must be between 1 and 90"}

    db = get_db()

    """
    Query Twitter statistics including account status, monitored users, recent events, and summary.
    查询 Twitter 统计数据，包括账户状态、监控用户、近期事件和摘要。
    """
    def get_stats():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Account status
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'active') as active,
                        COUNT(*) FILTER (WHERE status = 'cooling') as cooling,
                        COUNT(*) FILTER (WHERE status = 'error') as error
                    FROM twitter_accounts
                """)
                accounts = cur.fetchone()

                # Monitored users
                cur.execute("""
                    SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE is_active = true) as active
                    FROM twitter_monitored_users
                """)
                users = cur.fetchone()

                # Recent events
                cur.execute("""
                    SELECT id, event_title, summary, category, peak_score, source_count, pushed, created_at
                    FROM twitter_events
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    ORDER BY created_at DESC
                    LIMIT 10
                """, (days,))
                events = cur.fetchall()

                # Stats
                cur.execute("""
                    SELECT
                        COUNT(*) as total_tweets,
                        COUNT(*) FILTER (WHERE status = 1) as processed,
                        COUNT(*) FILTER (WHERE impact_score >= 80) as high_impact
                    FROM twitter_stream_raw
                    WHERE created_at > NOW() - INTERVAL '%s days'
                """, (days,))
                summary = cur.fetchone()

                return {"accounts": accounts, "monitored_users": users, "recent_events": events, "summary": summary}

    result = await asyncio.to_thread(get_stats)
    return {"status": "ok", "days": days, "stats": result}


@router.get("/stats/llm", dependencies=[Depends(verify_api_key)])
async def get_llm_stats(hours: int = None, start_date: str = None, end_date: str = None):
    """
    Get LLM model status and usage statistics.
    获取 LLM 模型状态和使用统计。

    Args:
        hours: Time range in hours (default 168 = 7 days).  / 时间范围（小时，默认 168 = 7 天）。
        start_date: Start date in ISO format (YYYY-MM-DD).  / 开始日期 (YYYY-MM-DD)。
        end_date: End date in ISO format (YYYY-MM-DD).  / 结束日期 (YYYY-MM-DD)。
    """
    import asyncio
    from .deps import get_db

    db = get_db()

    def get_stats():
        # Determine time filter
        if start_date and end_date:
            time_condition = "u.created_at >= %s AND u.created_at < %s"
            time_params = (start_date, end_date + ' 23:59:59')
        elif hours:
            time_condition = "u.created_at > NOW() - INTERVAL '%s hours'"
            time_params = (hours,)
        else:
            time_condition = "u.created_at > NOW() - INTERVAL '168 hours'"
            time_params = ()

        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Model list (static)
                cur.execute("""
                    SELECT id, name, model_name, priority, fail_count, is_active, last_error, last_success,
                           COALESCE(input_price_per_m, 7.0) as input_price_per_m,
                           COALESCE(output_price_per_m, 7.0) as output_price_per_m
                    FROM llm_models
                    ORDER BY priority DESC
                """)
                models = cur.fetchall()

                # Token usage by model with dynamic time range
                if start_date and end_date:
                    query = f"""
                        SELECT
                            u.model_name,
                            COUNT(*) as requests,
                            SUM(u.prompt_tokens) as prompt_tokens,
                            SUM(u.completion_tokens) as completion_tokens,
                            SUM(u.cached_tokens) as cached_tokens,
                            SUM(u.prompt_tokens + u.completion_tokens) as total_tokens,
                            COALESCE(m.input_price_per_m, 7.0) as input_price_per_m,
                            COALESCE(m.output_price_per_m, 7.0) as output_price_per_m,
                            ROUND(
                                (SUM(u.prompt_tokens) - SUM(COALESCE(u.cached_tokens, 0))) * COALESCE(m.input_price_per_m, 7.0) / 1000000.0
                                + SUM(COALESCE(u.cached_tokens, 0)) * COALESCE(m.input_price_per_m, 7.0) / 1000000.0 * 0.25
                                + SUM(u.completion_tokens) * COALESCE(m.output_price_per_m, 7.0) / 1000000.0
                            , 4) as estimated_cost
                        FROM token_usage u
                        LEFT JOIN llm_models m ON u.model_name = m.model_name
                        WHERE {time_condition}
                        GROUP BY u.model_name, m.input_price_per_m, m.output_price_per_m
                        ORDER BY total_tokens DESC
                    """
                    cur.execute(query, time_params)
                else:
                    query = f"""
                        SELECT
                            u.model_name,
                            COUNT(*) as requests,
                            SUM(u.prompt_tokens) as prompt_tokens,
                            SUM(u.completion_tokens) as completion_tokens,
                            SUM(u.cached_tokens) as cached_tokens,
                            SUM(u.prompt_tokens + u.completion_tokens) as total_tokens,
                            COALESCE(m.input_price_per_m, 7.0) as input_price_per_m,
                            COALESCE(m.output_price_per_m, 7.0) as output_price_per_m,
                            ROUND(
                                (SUM(u.prompt_tokens) - SUM(COALESCE(u.cached_tokens, 0))) * COALESCE(m.input_price_per_m, 7.0) / 1000000.0
                                + SUM(COALESCE(u.cached_tokens, 0)) * COALESCE(m.input_price_per_m, 7.0) / 1000000.0 * 0.25
                                + SUM(u.completion_tokens) * COALESCE(m.output_price_per_m, 7.0) / 1000000.0
                            , 4) as estimated_cost
                        FROM token_usage u
                        LEFT JOIN llm_models m ON u.model_name = m.model_name
                        WHERE {time_condition}
                        GROUP BY u.model_name, m.input_price_per_m, m.output_price_per_m
                        ORDER BY total_tokens DESC
                    """
                    cur.execute(query, time_params)

                usage = cur.fetchall()

                # Calculate totals
                total_prompt = sum(u['prompt_tokens'] or 0 for u in usage)
                total_completion = sum(u['completion_tokens'] or 0 for u in usage)
                total_cached = sum(u['cached_tokens'] or 0 for u in usage)
                total_cost = sum(u['estimated_cost'] or 0 for u in usage)

                return {
                    "models": models,
                    "token_usage": usage,
                    "summary": {
                        "total_prompt": total_prompt,
                        "total_completion": total_completion,
                        "total_cached": total_cached,
                        "total_tokens": total_prompt + total_completion,
                        "estimated_cost": round(total_cost, 4),
                        "cache_hit_rate": round((total_cached / total_prompt * 100), 2) if total_prompt > 0 else 0
                    }
                }

    result = await asyncio.to_thread(get_stats)
    return {"status": "ok", "stats": result}


# ==========================
# Config Endpoints (Settings Management)
# ==========================

@router.get("/config", dependencies=[Depends(verify_api_key)])
async def get_all_config():
    """
    Get all system configuration entries.
    获取所有系统配置条目。

    Merges database config with current runtime settings.
    合并数据库配置与当前运行时设置。
    """
    import asyncio
    from .deps import get_db
    from ..config import settings

    db = get_db()
    db_config = await asyncio.to_thread(db.get_all_config)

    # Get current runtime settings mapped to sections
    # 从当前运行时配置获取默认值
    runtime_config = _get_runtime_config()

    # Merge: database values override runtime values
    merged = {}
    for section, items in runtime_config.items():
        merged[section] = items.copy()

    # Apply database overrides
    for item in db_config:
        section = item.get('section', 'default')
        key = item.get('key')
        if section in merged:
            # Update existing or add new
            found = False
            for i, existing in enumerate(merged[section]):
                if existing.get('key') == key:
                    merged[section][i] = item
                    found = True
                    break
            if not found:
                merged[section].append(item)
        else:
            merged[section] = [item]

    return {"status": "ok", "config": merged, "source": "merged"}


def _get_runtime_config():
    """
    Get current runtime settings as config items.
    将当前运行时设置转换为配置项。
    """
    from ..config import settings
    import json

    config = {}

    # Breaking News section
    breaking_fields = [
        ("enable_breaking_news", "ENABLE_BREAKING_NEWS", "bool"),
        ("breaking_impact_threshold", "BREAKING_IMPACT_THRESHOLD", "int"),
        ("breaking_fetch_interval", "BREAKING_FETCH_INTERVAL_MINUTES", "int"),
        ("breaking_push_telegram", "BREAKING_PUSH_TELEGRAM", "bool"),
        ("breaking_push_dingtalk", "BREAKING_PUSH_DINGTALK", "bool"),
    ]
    config["breaking"] = []
    for field_name, env_name, value_type in breaking_fields:
        if hasattr(settings, field_name):
            val = getattr(settings, field_name)
            config["breaking"].append({
                "key": env_name,
                "value": str(val).lower() if value_type == "bool" else str(val),
                "value_type": value_type,
                "is_editable": True,
                "source": "runtime"
            })

    # Twitter section
    twitter_fields = [
        ("enable_twitter_alerts", "ENABLE_TWITTER_ALERTS", "bool"),
        ("twitter_impact_threshold", "TWITTER_IMPACT_THRESHOLD", "int"),
    ]
    config["twitter"] = []
    for field_name, env_name, value_type in twitter_fields:
        if hasattr(settings, field_name):
            val = getattr(settings, field_name)
            config["twitter"].append({
                "key": env_name,
                "value": str(val).lower() if value_type == "bool" else str(val),
                "value_type": value_type,
                "is_editable": True,
                "source": "runtime"
            })

    # Notifications section
    notif_fields = [
        ("summary_hour", "SUMMARY_HOUR", "string"),
        ("summary_minute", "SUMMARY_MINUTE", "int"),
    ]
    config["notifications"] = []
    for field_name, env_name, value_type in notif_fields:
        if hasattr(settings, field_name):
            val = getattr(settings, field_name)
            config["notifications"].append({
                "key": env_name,
                "value": str(val),
                "value_type": value_type,
                "is_editable": True,
                "source": "runtime"
            })

    # A-Stock section
    astock_fields = [
        ("enable_astock_analysis", "ENABLE_ASTOCK_ANALYSIS", "bool"),
        ("astock_push_telegram", "ASTOCK_PUSH_TELEGRAM", "bool"),
        ("astock_push_dingtalk", "ASTOCK_PUSH_DINGTALK", "bool"),
    ]
    config["astock"] = []
    for field_name, env_name, value_type in astock_fields:
        if hasattr(settings, field_name):
            val = getattr(settings, field_name)
            config["astock"].append({
                "key": env_name,
                "value": str(val).lower() if value_type == "bool" else str(val),
                "value_type": value_type,
                "is_editable": True,
                "source": "runtime"
            })

    # Prompts section
    prompt_fields = [
        ("prompt_breaking_onepass", "PROMPT_BREAKING_ONEPASS", "text"),
        ("prompt_twitter_onepass", "PROMPT_TWITTER_ONEPASS", "text"),
        ("prompt_daily_onepass", "PROMPT_DAILY_ONEPASS", "text"),
        ("prompt_overview", "PROMPT_OVERVIEW", "text"),
        ("prompt_critique", "PROMPT_CRITIQUE", "text"),
        ("prompt_translate_titles", "PROMPT_TRANSLATE_TITLES", "text"),
        ("prompt_twitter_batch_triage", "PROMPT_TWITTER_BATCH_TRIAGE", "text"),
    ]
    config["prompts"] = []
    for field_name, env_name, value_type in prompt_fields:
        if hasattr(settings, field_name):
            val = getattr(settings, field_name)
            # Truncate long prompts for display
            display_value = val[:500] + "..." if len(val) > 500 else val
            config["prompts"].append({
                "key": env_name,
                "value": display_value,
                "value_type": value_type,
                "is_editable": True,
                "source": "runtime"
            })

    return config


@router.get("/config/{section}", dependencies=[Depends(verify_api_key)])
async def get_config_section(section: str):
    """
    Get configuration for a specific section.
    获取指定配置节的配置。

    Args:
        section (str): The config section name (e.g., "breaking", "twitter").
    """
    import asyncio
    from .deps import get_db

    db = get_db()
    db_config = await asyncio.to_thread(db.get_config_by_section, section)

    # Also get runtime config for this section
    runtime_config = _get_runtime_config()
    runtime_items = runtime_config.get(section, [])

    # Merge: db values override runtime values
    merged = runtime_items.copy()
    for db_item in db_config:
        found = False
        for i, existing in enumerate(merged):
            if existing.get('key') == db_item.get('key'):
                merged[i] = db_item
                found = True
                break
        if not found:
            merged.append(db_item)

    return {"status": "ok", "section": section, "config": merged}


@router.get("/config/{section}/{key}", dependencies=[Depends(verify_api_key)])
async def get_config_value(section: str, key: str):
    """
    Get a specific config value (including full prompt text).
    获取特定配置值（包括完整的提示文本）。

    Args:
        section (str): The config section name.
        key (str): The config key.
    """
    import asyncio
    from .deps import get_db

    db = get_db()

    # First try database
    db_config = await asyncio.to_thread(db.get_config, section, key)
    if db_config and db_config.get('value'):
        return {"status": "ok", "value": db_config['value']}

    # Fall back to runtime config
    runtime_config = _get_runtime_config()
    for item in runtime_config.get(section, []):
        if item.get('key') == key:
            return {"status": "ok", "value": item.get('value', '')}

    return {"status": "ok", "value": ""}


@router.put("/config/{section}", dependencies=[Depends(verify_api_key)])
async def update_config_section(section: str, items: list[dict]):
    """
    Update configuration for a specific section.
    更新指定配置节的配置。

    Args:
        section (str): The config section name.
        items (list[dict]): List of config items to update with keys: key, value, value_type, description.
    """
    import asyncio
    from .deps import get_db

    db = get_db()

    updated = 0
    for item in items:
        key = item.get('key')
        value = item.get('value')
        value_type = item.get('value_type', 'string')
        description = item.get('description', '')

        if not key or value is None:
            continue

        # Convert value to string
        value_str = str(value)
        if isinstance(value, bool):
            value_str = 'true' if value else 'false'
        elif isinstance(value, (int, float)):
            value_str = str(value)

        success = await asyncio.to_thread(db.set_config, section, key, value_str, value_type, description)
        if success:
            updated += 1

    # Clear cache
    cache.delete("omnidigest:config")
    cache.delete(f"omnidigest:config:{section}")

    return {"status": "ok", "updated": updated, "section": section}


@router.post("/config", dependencies=[Depends(verify_api_key)])
async def create_config_entry(section: str, key: str, value: str, value_type: str = "string", description: str = ""):
    """
    Create a new configuration entry.
    创建新的配置条目。

    Args:
        section (str): The config section name.
        key (str): The config key.
        value (str): The config value.
        value_type (str): The type of value (string, int, bool, json).
        description (str): Description of this config.
    """
    import asyncio
    from .deps import get_db

    db = get_db()
    success = await asyncio.to_thread(db.set_config, section, key, value, value_type, description)

    if success:
        # Clear cache
        cache.delete("omnidigest:config")
        cache.delete(f"omnidigest:config:{section}")
        return {"status": "ok", "message": f"Config {section}.{key} created/updated"}
    return {"status": "error", "message": "Failed to create config"}


@router.delete("/config/{section}/{key}", dependencies=[Depends(verify_api_key)])
async def delete_config_entry(section: str, key: str):
    """
    Delete a configuration entry.
    删除配置条目。

    Args:
        section (str): The config section name.
        key (str): The config key.
    """
    import asyncio
    from .deps import get_db

    db = get_db()
    success = await asyncio.to_thread(db.delete_config, section, key)

    if success:
        # Clear cache
        cache.delete("omnidigest:config")
        cache.delete(f"omnidigest:config:{section}")
        return {"status": "ok", "message": f"Config {section}.{key} deleted"}
    return {"status": "error", "message": "Failed to delete config"}


# ==========================
# Sources Endpoints (RSS Management)
# ==========================

@router.get("/sources", dependencies=[Depends(verify_api_key)])
async def get_sources(service_type: str = "daily", enabled: bool = None):
    """
    Get RSS sources by service type.
    按服务类型获取 RSS 源。

    Args:
        service_type (str): Type of source - "daily", "breaking", or "twitter"
        enabled (bool): Filter by enabled status. If None, returns all.
    """
    import asyncio
    from .deps import get_db

    db = get_db()

    """
    Query RSS sources from database based on service type and enabled status.
    根据服务类型和启用状态从数据库查询 RSS 源。
    """
    def get_sources():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if service_type == "daily":
                    if enabled is not None:
                        cur.execute("""
                            SELECT id, url, name, enabled, fail_count, last_error, created_at
                            FROM rss_sources
                            WHERE enabled = %s
                            ORDER BY name
                        """, (enabled,))
                    else:
                        cur.execute("""
                            SELECT id, url, name, enabled, fail_count, last_error, created_at
                            FROM rss_sources
                            ORDER BY name
                        """)
                elif service_type == "breaking":
                    if enabled is not None:
                        cur.execute("""
                            SELECT id, url, name, platform, enabled, fail_count, success_count, last_error, created_at
                            FROM breaking_rss_sources
                            WHERE enabled = %s
                            ORDER BY name
                        """, (enabled,))
                    else:
                        cur.execute("""
                            SELECT id, url, name, platform, enabled, fail_count, success_count, last_error, created_at
                            FROM breaking_rss_sources
                            ORDER BY name
                        """)
                elif service_type == "twitter":
                    # Twitter uses accounts instead of RSS
                    if enabled is not None:
                        cur.execute("""
                            SELECT id, username, status, fail_count, last_error, last_used_at, created_at
                            FROM twitter_accounts
                            WHERE status = %s
                            ORDER BY username
                        """, ("active" if enabled else "error",))
                    else:
                        cur.execute("""
                            SELECT id, username, status, fail_count, last_error, last_used_at, created_at
                            FROM twitter_accounts
                            ORDER BY username
                        """)
                else:
                    cur.execute("SELECT NULL as id WHERE 1=0")

                return cur.fetchall()

    sources = await asyncio.to_thread(get_sources)
    return {"status": "ok", "service_type": service_type, "sources": sources, "count": len(sources)}


@router.get("/sources/rss", dependencies=[Depends(verify_api_key)])
async def get_rss_sources(enabled: bool = None):
    """
    Get all RSS sources (daily), optionally filtered by enabled status.
    获取所有 RSS 源（每日），可按启用状态筛选。

    Args:
        enabled (bool): Filter by enabled status. If None, returns all.
    """
    # Redirect to new endpoint
    return await get_sources(service_type="daily", enabled=enabled)


@router.post("/sources/rss", dependencies=[Depends(verify_api_key)])
async def add_rss_source(url: str, name: str):
    """
    Add a new RSS source.
    添加新的 RSS 源。

    Args:
        url (str): The RSS feed URL.
        name (str): Display name for the source.
    """
    import asyncio
    import uuid
    from .deps import get_db

    db = get_db()

    def add_source():
        import logging
        logger = logging.getLogger(__name__)
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                try:
                    cur.execute("""
                        INSERT INTO rss_sources (id, url, name, enabled)
                        VALUES (%s, %s, %s, true)
                        ON CONFLICT (url) DO NOTHING
                        RETURNING id
                    """, (str(uuid.uuid4()), url, name))
                    result = cur.fetchone()
                    conn.commit()
                    return result is not None
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to add RSS source: {e}")
                    return False

    success = await asyncio.to_thread(add_source)
    if success:
        # Clear cache
        cache.delete("omnidigest:sources:rss")
        cache.delete("omnidigest:sources")
        return {"status": "ok", "message": f"RSS source '{name}' added"}
    return {"status": "error", "message": "Failed to add RSS source (may already exist)"}


@router.put("/sources/rss/{source_id}", dependencies=[Depends(verify_api_key)])
async def update_rss_source(source_id: str, name: str = None, url: str = None):
    """
    Update an RSS source.
    更新 RSS 源。

    Args:
        source_id (str): The source UUID.
        name (str): New display name.
        url (str): New URL.
    """
    import asyncio
    from .deps import get_db
    import logging
    logger = logging.getLogger(__name__)

    db = get_db()

    def update_source():
        import logging
        logger = logging.getLogger(__name__)
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    if name and url:
                        cur.execute("""
                            UPDATE rss_sources SET name = %s, url = %s WHERE id = %s
                        """, (name, url, source_id))
                    elif name:
                        cur.execute("""
                            UPDATE rss_sources SET name = %s WHERE id = %s
                        """, (name, source_id))
                    elif url:
                        cur.execute("""
                            UPDATE rss_sources SET url = %s WHERE id = %s
                        """, (url, source_id))
                    else:
                        return False
                    conn.commit()
                    return cur.rowcount > 0
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to update RSS source: {e}")
                    return False

    success = await asyncio.to_thread(update_source)
    if success:
        # Clear cache
        cache.delete("omnidigest:sources:rss")
        cache.delete("omnidigest:sources")
        return {"status": "ok", "message": "RSS source updated"}
    return {"status": "error", "message": "Failed to update RSS source"}


@router.delete("/sources/rss/{source_id}", dependencies=[Depends(verify_api_key)])
async def delete_rss_source(source_id: str):
    """
    Delete an RSS source.
    删除 RSS 源。

    Args:
        source_id (str): The source UUID.
    """
    import asyncio
    from .deps import get_db
    import logging
    logger = logging.getLogger(__name__)

    db = get_db()

    def delete_source():
        import logging
        logger = logging.getLogger(__name__)
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("DELETE FROM rss_sources WHERE id = %s", (source_id,))
                    conn.commit()
                    return cur.rowcount > 0
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to delete RSS source: {e}")
                    return False

    success = await asyncio.to_thread(delete_source)
    if success:
        # Clear cache
        cache.delete("omnidigest:sources:rss")
        cache.delete("omnidigest:sources")
        return {"status": "ok", "message": "RSS source deleted"}
    return {"status": "error", "message": "Failed to delete RSS source"}


@router.post("/sources/rss/{source_id}/toggle", dependencies=[Depends(verify_api_key)])
async def toggle_rss_source(source_id: str):
    """
    Toggle RSS source enabled/disabled status.
    切换 RSS 源启用/禁用状态。

    Args:
        source_id (str): The source UUID.
    """
    import asyncio
    from .deps import get_db
    import logging
    logger = logging.getLogger(__name__)

    db = get_db()

    """
    Toggle RSS source enabled/disabled status in database.
    在数据库中切换 RSS 源启用/禁用状态。
    """
    def toggle_source():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                try:
                    # Get current status
                    cur.execute("SELECT enabled FROM rss_sources WHERE id = %s", (source_id,))
                    result = cur.fetchone()
                    if not result:
                        return None

                    new_status = not result['enabled']
                    cur.execute("""
                        UPDATE rss_sources SET enabled = %s WHERE id = %s
                    """, (new_status, source_id))
                    conn.commit()
                    return new_status
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to toggle RSS source: {e}")
                    return None

    result = await asyncio.to_thread(toggle_source)
    if result is not None:
        # Clear cache
        cache.delete("omnidigest:sources:rss")
        cache.delete("omnidigest:sources")
        return {"status": "ok", "enabled": result}
    return {"status": "error", "message": "Failed to toggle RSS source"}


# ==========================
# Auth Endpoints (API Key Management)
# ==========================

@router.get("/auth/keys", dependencies=[Depends(verify_api_key)])
async def list_api_keys():
    """
    List all API keys (without showing the actual key hash).
    列出所有 API 密钥（不显示实际密钥哈希）。
    """
    import asyncio
    from .deps import get_db

    db = get_db()

    """
    Query all API keys from database.
    从数据库查询所有 API 密钥。
    """
    def get_keys():
        with db._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, client_name, is_active, created_at
                    FROM api_keys
                    ORDER BY created_at DESC
                """)
                return cur.fetchall()

    keys = await asyncio.to_thread(get_keys)
    return {"status": "ok", "keys": keys, "count": len(keys)}


@router.post("/auth/keys", dependencies=[Depends(verify_api_key)])
async def create_api_key(client_name: str):
    """
    Create a new API key.
    创建新的 API 密钥。

    Args:
        client_name (str): Name/identifier for the client.
    """
    import asyncio
    from .deps import get_db
    from .auth import generate_api_key, hash_api_key
    import logging
    logger = logging.getLogger(__name__)

    db = get_db()

    def create_key():
        try:
            raw_key = generate_api_key()
            key_hash = hash_api_key(raw_key)

            with db._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        INSERT INTO api_keys (client_name, key_hash)
                        VALUES (%s, %s)
                        ON CONFLICT (client_name) DO UPDATE SET key_hash = EXCLUDED.key_hash, is_active = true
                        RETURNING id
                    """, (client_name, key_hash))
                    conn.commit()
                    return raw_key
        except Exception as e:
            logger.error(f"Failed to create API key: {e}")
            return None

    raw_key = await asyncio.to_thread(create_key)
    if raw_key:
        return {
            "status": "ok",
            "message": "API key created",
            "key": raw_key,
            "client_name": client_name,
            "note": "This is the only time you'll see this key. Save it securely!"
        }
    return {"status": "error", "message": "Failed to create API key"}


@router.delete("/auth/keys/{client_name}", dependencies=[Depends(verify_api_key)])
async def revoke_api_key(client_name: str):
    """
    Revoke (deactivate) an API key.
    撤销（停用）API 密钥。

    Args:
        client_name (str): The client name associated with the key.
    """
    import asyncio
    from .deps import get_db
    import logging
    logger = logging.getLogger(__name__)

    db = get_db()

    def revoke_key():
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("""
                        UPDATE api_keys SET is_active = false WHERE client_name = %s
                    """, (client_name,))
                    conn.commit()
                    return cur.rowcount > 0
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to revoke API key: {e}")
                    return False

    success = await asyncio.to_thread(revoke_key)
    if success:
        return {"status": "ok", "message": f"API key for '{client_name}' revoked"}
    return {"status": "error", "message": "Failed to revoke API key"}


@router.post("/auth/keys/{client_name}/activate", dependencies=[Depends(verify_api_key)])
async def activate_api_key(client_name: str):
    """
    Activate an API key.
    激活 API 密钥。

    Args:
        client_name (str): The client name associated with the key.
    """
    import asyncio
    from .deps import get_db
    import logging
    logger = logging.getLogger(__name__)

    db = get_db()

    def activate_key():
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("""
                        UPDATE api_keys SET is_active = true WHERE client_name = %s
                    """, (client_name,))
                    conn.commit()
                    return cur.rowcount > 0
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Failed to activate API key: {e}")
                    return False

    success = await asyncio.to_thread(activate_key)
    if success:
        return {"status": "ok", "message": f"API key for '{client_name}' activated"}
    return {"status": "error", "message": "Failed to activate API key"}


# ==========================
# Knowledge Graph Endpoints
# ==========================

@router.get("/kg/status", dependencies=[Depends(verify_api_key)])
async def get_kg_status():
    """
    Get Knowledge Graph (Dgraph) status.
    获取知识图谱（Dgraph）状态。
    """
    from ..config import settings

    enabled = settings.kg_enabled
    dgraph_url = settings.dgraph_alpha_url if hasattr(settings, 'dgraph_alpha_url') else 'localhost:9080'

    return {
        "status": "ok",
        "enabled": enabled,
        "dgraph_url": dgraph_url,
        "message": "Knowledge Graph is enabled" if enabled else "Knowledge Graph is not enabled"
    }


@router.get("/kg/stats", dependencies=[Depends(verify_api_key)])
async def get_kg_stats():
    """
    Get Knowledge Graph statistics.
    获取知识图谱统计信息。
    """
    from ..config import settings

    if not settings.kg_enabled:
        return {"status": "error", "message": "Knowledge Graph is not enabled"}

    import asyncio
    from ..domains.knowledge_graph.dgraph_client import DgraphClient
    from .deps import get_db
    from psycopg2.extras import RealDictCursor

    """
    Query Knowledge Graph statistics from Dgraph and PostgreSQL.
    从 Dgraph 和 PostgreSQL 查询知识图谱统计信息。
    """
    def get_stats():
        import logging
        try:
            # Get Dgraph stats
            client = DgraphClient()
            dgraph_stats = client.get_stats()
            logging.info(f"Dgraph stats: {dgraph_stats}")

            recent_entities = client.get_recent_entities(10)

            # Get graph visualization data
            graph_viz = client.get_graph_visualization(15)
            client.close()

            total_entities = dgraph_stats.get("persons", 0) + dgraph_stats.get("organizations", 0) + dgraph_stats.get("locations", 0) + dgraph_stats.get("events", 0)
            logging.info(f"Total entities: {total_entities}")

            # Get PostgreSQL stats for extraction tracking
            db = get_db()
            with db._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Check total records in breaking_stream_raw
                    cur.execute("SELECT COUNT(*) as total FROM breaking_stream_raw")
                    total_raw = cur.fetchone().get("total", 0)
                    logging.info(f"Total breaking_stream_raw: {total_raw}")

                    # Count kg_processed
                    cur.execute("SELECT COUNT(*) as processed FROM breaking_stream_raw WHERE kg_processed = true")
                    kg_processed = cur.fetchone().get("processed", 0)
                    logging.info(f"kg_processed count: {kg_processed}")

                    # Count extracted today (kg_processed = true in last 24 hours)
                    cur.execute("""
                        SELECT COUNT(*) as count
                        FROM breaking_stream_raw
                        WHERE kg_processed = true
                        AND created_at > NOW() - INTERVAL '24 hours'
                    """)
                    extracted_result = cur.fetchone()
                    extracted_today = extracted_result.get("count", 0) if extracted_result else 0

                    # Get last extraction time
                    cur.execute("""
                        SELECT MAX(created_at) as last_extraction
                        FROM breaking_stream_raw
                        WHERE kg_processed = true
                    """)
                    last_ext_result = cur.fetchone()
                    last_extraction = last_ext_result.get("last_extraction") if last_ext_result else None

            return {
                "total_entities": total_entities,
                "total_relations": dgraph_stats.get("total_relations", 0),
                "extracted_today": extracted_today,
                "last_extraction": last_extraction.isoformat() if last_extraction else None,
                "entity_types": [
                    {"name": "Person", "count": dgraph_stats.get("persons", 0), "icon": "👤", "color": "#4ade80"},
                    {"name": "Organization", "count": dgraph_stats.get("organizations", 0), "icon": "🏢", "color": "#60a5fa"},
                    {"name": "Location", "count": dgraph_stats.get("locations", 0), "icon": "📍", "color": "#f472b6"},
                    {"name": "Event", "count": dgraph_stats.get("events", 0), "icon": "📅", "color": "#fbbf24"}
                ],
                "recent_entities": recent_entities,
                "top_relations": dgraph_stats.get("top_relations", []),
                "graph_nodes": graph_viz.get("nodes", []),
                "graph_connections": graph_viz.get("connections", [])
            }
        except Exception as e:
            logging.error(f"KG Stats Error: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return {
                "total_entities": 0,
                "total_relations": 0,
                "extracted_today": 0,
                "last_extraction": None,
                "entity_types": [],
                "recent_entities": [],
                "top_relations": [],
                "graph_nodes": [],
                "graph_connections": [],
                "error": str(e)
            }

    stats = await asyncio.to_thread(get_stats)

    # Include error in response for debugging
    if "error" in stats:
        return {"status": "error", "message": stats["error"], "stats": stats}

    return {"status": "ok", "stats": stats}


@router.get("/kg/entities", dependencies=[Depends(verify_api_key)])
async def search_kg_entities(
    name: str = None,
    entity_type: str = None,
    start_time: str = None,
    end_time: str = None,
    limit: int = 50
):
    """
    Search entities in the Knowledge Graph with filters.
    在知识图谱中搜索实体，支持过滤器。
    """
    from ..config import settings

    if not settings.kg_enabled:
        return {"status": "error", "message": "Knowledge Graph is not enabled"}

    import asyncio
    from ..domains.knowledge_graph.dgraph_client import DgraphClient

    def search():
        try:
            client = DgraphClient()
            entities = client.search_entities(
                name=name,
                entity_type=entity_type,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            client.close()
            return entities
        except Exception as e:
            import logging
            logging.error(f"KG Entity Search Error: {e}")
            return []

    entities = await asyncio.to_thread(search)
    return {"status": "ok", "entities": entities, "count": len(entities)}


@router.get("/kg/entity/{uid}", dependencies=[Depends(verify_api_key)])
async def get_kg_entity_details(uid: str):
    """
    Get detailed information about a specific entity.
    获取特定实体的详细信息。
    """
    from ..config import settings

    if not settings.kg_enabled:
        return {"status": "error", "message": "Knowledge Graph is not enabled"}

    import asyncio
    from ..domains.knowledge_graph.dgraph_client import DgraphClient

    def get_details():
        try:
            client = DgraphClient()
            entity = client.get_entity_details(uid)
            client.close()
            return entity
        except Exception as e:
            import logging
            logging.error(f"KG Entity Details Error: {e}")
            return {}

    entity = await asyncio.to_thread(get_details)
    if entity:
        return {"status": "ok", "entity": entity}
    return {"status": "error", "message": "Entity not found"}


@router.get("/kg/relations", dependencies=[Depends(verify_api_key)])
async def get_kg_relations(
    from_uid: str = None,
    to_uid: str = None,
    relation_type: str = None,
    limit: int = 100
):
    """
    Query relations in the Knowledge Graph with filters.
    在知识图谱中查询关系，支持过滤器。
    """
    from ..config import settings

    if not settings.kg_enabled:
        return {"status": "error", "message": "Knowledge Graph is not enabled"}

    import asyncio
    from ..domains.knowledge_graph.dgraph_client import DgraphClient

    def get_relations():
        try:
            client = DgraphClient()
            relations = client.get_relations(
                from_uid=from_uid,
                to_uid=to_uid,
                relation_type=relation_type,
                limit=limit
            )
            client.close()
            return relations
        except Exception as e:
            import logging
            logging.error(f"KG Relations Error: {e}")
            return []

    relations = await asyncio.to_thread(get_relations)
    return {"status": "ok", "relations": relations, "count": len(relations)}


@router.get("/kg/search", dependencies=[Depends(verify_api_key)])
async def search_kg_path(
    start: str,
    end: str,
    max_depth: int = 3
):
    """
    Find path(s) between two entities in the Knowledge Graph.
    在知识图谱中查找两个实体之间的路径。
    """
    from ..config import settings

    if not settings.kg_enabled:
        return {"status": "error", "message": "Knowledge Graph is not enabled"}

    import asyncio
    from ..domains.knowledge_graph.dgraph_client import DgraphClient

    def search_path():
        try:
            client = DgraphClient()
            paths = client.search_path(start, end, max_depth)
            client.close()
            return paths
        except Exception as e:
            import logging
            logging.error(f"KG Path Search Error: {e}")
            return []

    paths = await asyncio.to_thread(search_path)
    return {"status": "ok", "paths": paths, "count": len(paths)}
