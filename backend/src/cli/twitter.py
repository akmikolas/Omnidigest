"""
Twitter Ingestion Domain — CLI Subcommands.
Allows manual management of Twitter accounts, influencers, and manual crawl triggers.
推特摄取领域 — CLI 子命令。
允许手动管理推特账号、监听者以及手动抓取触发。
"""
import logging
import uuid
import sys
import asyncio
from .rss import override_db_settings
from ..core.database import DatabaseManager
from ..core.llm_manager import LLMManager
from ..domains.ingestion.twitter.client import TwitterClient
from ..domains.ingestion.twitter.crawler import TwitterCrawler
from ..domains.twitter.processor import TwitterProcessor

logger = logging.getLogger(__name__)

def twitter_add_account(args):
    """
    Adds a new Twitter account to the session pool.
    向会话池添加新的推特账号。
    """
    override_db_settings(args)
    db = DatabaseManager()
    query = """
    INSERT INTO twitter_accounts (id, username, auth_token, ct0)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (username) DO UPDATE SET auth_token = EXCLUDED.auth_token, ct0 = EXCLUDED.ct0
    RETURNING id;
    """
    try:
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (str(uuid.uuid4()), args.username, args.auth_token, args.ct0))
                res = cur.fetchone()
            conn.commit()
            logger.info(f"✅ Twitter account @{args.username} added/updated. ID: {res[0]}")
    except Exception as e:
        logger.error(f"Failed to add Twitter account: {e}")
        sys.exit(1)

def twitter_add_influencer(args):
    """
    Adds a new monitored influencer to the list.
    向列表添加新的被监听影响力人物。
    """
    override_db_settings(args)
    db = DatabaseManager()
    query = """
    INSERT INTO twitter_monitored_users (rest_id, screen_name, category)
    VALUES (%s, %s, %s)
    ON CONFLICT (screen_name) DO UPDATE SET 
        rest_id = EXCLUDED.rest_id,
        category = EXCLUDED.category;
    """
    try:
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (args.rest_id, args.screen_name, args.category))
            conn.commit()
            logger.info(f"✅ Following @{args.screen_name} (ID: {args.rest_id})")
    except Exception as e:
        logger.error(f"Failed to follow Twitter user: {e}")
        sys.exit(1)

def twitter_trigger_crawl(args):
    """
    Manually triggers a Twitter crawl cycle.
    手动触发一次推特抓取周期。
    """
    override_db_settings(args)
    db = DatabaseManager()
    try:
        client = TwitterClient(db)
        # LLM not needed for crawl
        crawler = TwitterCrawler(db, client)
        crawler.run_ingestion_loop()
    except Exception as e:
        logger.error(f"Crawl trigger failed: {e}")
    finally:
        db.close_all()

def twitter_process_tweets(args):
    """
    Manually triggers a Twitter triage/scoring cycle.
    手动触发一次推特过滤/打分周期。
    """
    override_db_settings(args)
    db = DatabaseManager()
    llm = LLMManager(db)
    try:
        processor = TwitterProcessor(db, llm_manager=llm)
        asyncio.run(processor.process_pending_tweets(limit=args.limit))
    except Exception as e:
        logger.error(f"Tweet processing failed: {e}")
    finally:
        db.close_all()
