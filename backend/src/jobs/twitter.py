"""
Background Job: Twitter Ingestion & Intelligence.
Triggers the Twitter crawler and AI triage systematically.
后台任务：推特摄取与智能。
系统地触发推特爬虫和 AI 过滤。
"""
import logging
import asyncio
from ..domains.ingestion.twitter.client import TwitterClient
from ..domains.ingestion.twitter.crawler import TwitterCrawler
from ..domains.twitter.processor import TwitterProcessor
from ..core.database import DatabaseManager
from ..core.llm_manager import LLMManager

logger = logging.getLogger(__name__)

def job_twitter_crawl():
    """
    Background job to poll Twitter feeds for monitored users.
    用于轮询被监听用户推特消息的后台任务。
    """
    logger.info("--- [JOB] Twitter Crawl Started ---")
    db = DatabaseManager()
    try:
        client = TwitterClient(db)
        crawler = TwitterCrawler(db, client)
        crawler.run_ingestion_loop()
    except Exception as e:
        logger.error(f"Error in job_twitter_crawl: {e}")
    finally:
        db.close_all()
    logger.info("--- [JOB] Twitter Crawl Finished ---")

async def job_twitter_triage(limit: int = 50):
    """
    Background job to run AI triage on pending tweets.
    运行 AI 过滤待处理推文的后台任务。
    """
    logger.info("--- [JOB] Twitter AI Triage Started ---")
    db = DatabaseManager()
    llm = LLMManager(db)
    try:
        processor = TwitterProcessor(db, llm_manager=llm)
        await processor.process_pending_tweets(limit=limit)
    except Exception as e:
        logger.error(f"Error in job_twitter_triage: {e}")
    finally:
        db.close_all()
    logger.info("--- [JOB] Twitter AI Triage Finished ---")
