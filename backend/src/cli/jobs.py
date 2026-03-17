"""
Background job trigger CLI command handlers.
后台任务触发 CLI 命令处理器。

Provides functions for manually triggering summary generation, article cleanup,
and sending test breaking news push notifications to DingTalk/Telegram.
提供手动触发摘要生成、文章清理以及向钉钉/Telegram 发送测试突发新闻推送通知的函数。
"""
import sys
import logging
import asyncio
from src.omnidigest.core.database import DatabaseManager
from src.omnidigest.cli.db import override_db_settings

logger = logging.getLogger("manage.jobs")

def trigger_summary(args):
    """
    CLI handler to manually trigger the daily summary generation job.
    CLI 处理器，用于手动触发每日总结生成任务。
    
    Args:
        args (argparse.Namespace): Arguments containing 'dry_run' flag. / 包含 'dry_run' 标志的参数。
    """
    override_db_settings(args)
    logger.info(f"Manually triggering summary jobs... (Dry Run: {args.dry_run})")
    from src.omnidigest.jobs import job_daily_summary
    if args.dry_run:
        asyncio.run(job_daily_summary(push_telegram=False, push_dingtalk=False))
    else:
        asyncio.run(job_daily_summary())

def cleanup_jobs(args):
    """
    CLI handler to manually trigger the database cleanup for low-quality articles.
    CLI 处理器，用于手动触发针对低质量文章的数据库清理任务。
    
    Args:
        args (argparse.Namespace): CLI arguments. / CLI 参数。
    """
    override_db_settings(args)
    logger.info("Manually triggering cleanup job...")
    from src.omnidigest.jobs import job_cleanup_low_quality
    asyncio.run(job_cleanup_low_quality())

def test_breaking_push(args):
    """
    CLI handler to send a test breaking news notification to specified platforms.
    CLI 处理器，用于向指定平台发送测试性的突发新闻通知。
    
    Args:
        args (argparse.Namespace): Arguments containing 'platform' (dingtalk/telegram/all). / 包含 'platform'（钉钉/电报/全部）的参数。
    """
    override_db_settings(args)
    from src.omnidigest.notifications.pusher import NotificationService
    
    db = DatabaseManager()
    events = db.get_recent_breaking_events(hours=48)
    if not events:
        print("No breaking events found in DB to test.")
        return
        
    event = events[0]
    platform = args.platform.lower()
    
    print(f"Manually pushing {platform.upper()} event: {event['event_title']}")
    
    # Fetch actual source URLs from the database
    source_urls = db.get_breaking_event_sources(event['id'])
    
    payload = {"event": event}
    payload["event"]["source_urls"] = source_urls
    
    pusher = NotificationService()
    
    if platform in ['dingtalk', 'all']:
        title = f"🔴突发新闻: {event['event_title']}"
        pusher.push_to_dingtalk(title, payload, event_type="breaking")
        print("✅ DingTalk push complete.")
        
    if platform in ['tg', 'telegram', 'all']:
        tg_html = pusher.render_template('telegram_breaking.html.j2', payload)
        pusher.send_telegram(tg_html)
        print("✅ Telegram push complete.")
