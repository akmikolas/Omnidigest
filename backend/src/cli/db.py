"""
Database management CLI command handlers.
数据库管理 CLI 命令处理器。

Provides functions for database initialization, schema migrations,
legacy data import, and LLM classification backfill operations.
提供数据库初始化、Schema 迁移、旧数据导入和 LLM 分类回填操作的函数。
"""
import os
import sys
import logging
import asyncio
from pathlib import Path
from src.omnidigest.config import settings
from src.omnidigest.core.database import DatabaseManager

logger = logging.getLogger("manage.db")

def override_db_settings(args) -> None:
    """
    Overrides global database connection settings from CLI arguments.
    从 CLI 参数覆盖全局数据库连接设置。

    Args:
        args (argparse.Namespace): Parsed CLI arguments. / 解析后的 CLI 参数。
    """
    if hasattr(args, 'db_host') and args.db_host:
        settings.db_host = args.db_host
    if hasattr(args, 'db_port') and args.db_port:
        settings.db_port = args.db_port
    if hasattr(args, 'db_user') and args.db_user:
        settings.db_user = args.db_user
    if hasattr(args, 'db_password') and args.db_password:
        settings.db_password = args.db_password
    if hasattr(args, 'db_name') and args.db_name:
        settings.db_name = args.db_name

def init_db(args) -> None:
    """
    Initializes the database schema and creates all required tables.
    初始化数据库 Schema 并创建所有必需的表。

    Args:
        args (argparse.Namespace): Parsed CLI arguments. / 解析后的 CLI 参数。
    """
    override_db_settings(args)
    logger.info("Starting manual database initialization...")
    try:
        db = DatabaseManager()
        db.init_db()
        db.create_api_keys_table()
        logger.info("Database initialization completed successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)

def migrate_db_v2(args):
    """
    Executes database migration v2: Adds category, score, and summary_raw columns to news_articles.
    执行数据库迁移 v2：向 news_articles 表添加 category、score 和 summary_raw 列。
    
    Args:
        args (argparse.Namespace): CLI arguments. / CLI 参数。
    """
    override_db_settings(args)
    logger.info("Starting database migration v2...")
    import psycopg2
    conn = None
    try:
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            dbname=settings.db_name
        )
        cur = conn.cursor()
        
        logger.info("Adding 'category' column...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='news_articles' AND column_name='category') THEN
                    ALTER TABLE news_articles ADD COLUMN category VARCHAR(100);
                END IF;
            END
            $$;
        """)
        
        logger.info("Adding 'score' column...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='news_articles' AND column_name='score') THEN
                    ALTER TABLE news_articles ADD COLUMN score INT;
                END IF;
            END
            $$;
        """)
        
        logger.info("Adding 'summary_raw' column...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='news_articles' AND column_name='summary_raw') THEN
                    ALTER TABLE news_articles ADD COLUMN summary_raw TEXT;
                END IF;
            END
            $$;
        """)

        logger.info("Adding indexes...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_news_category ON news_articles(category);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_news_score ON news_articles(score);")

        conn.commit()
        logger.info("Migration v2 completed successfully.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            cur.close()
            conn.close()

def migrate_db_v3_apikeys(args):
    """
    Executes database migration v3: Creates the api_keys table.
    执行数据库迁移 v3：创建 api_keys 表。
    
    Args:
        args (argparse.Namespace): CLI arguments. / CLI 参数。
    """
    override_db_settings(args)
    logger.info("Starting database migration v3 (API Keys)...")
    try:
        db = DatabaseManager()
        db.create_api_keys_table()
        logger.info("Migration v3 completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

def migrate_db_v4_rss_failures(args):
    """
    Executes database migration v4: Adds failure tracking columns to rss_sources.
    执行数据库迁移 v4：向 rss_sources 表添加失败跟踪列。
    
    Args:
        args (argparse.Namespace): CLI arguments. / CLI 参数。
    """
    override_db_settings(args)
    logger.info("Starting database migration v4 (RSS Failures)...")
    import psycopg2
    conn = None
    try:
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            dbname=settings.db_name
        )
        cur = conn.cursor()
        
        logger.info("Adding 'fail_count' and 'last_error' columns to rss_sources...")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='rss_sources' AND column_name='fail_count') THEN
                    ALTER TABLE rss_sources ADD COLUMN fail_count INT DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                               WHERE table_name='rss_sources' AND column_name='last_error') THEN
                    ALTER TABLE rss_sources ADD COLUMN last_error TEXT;
                END IF;
            END
            $$;
        """)
        conn.commit()
        logger.info("Migration v4 completed successfully.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            cur.close()
            conn.close()

def migrate_db_v5_token(args):
    """
    Executes database migration v5: Creates the token_usage tracking table.
    执行数据库迁移 v5：创建 token_usage 跟踪表。
    
    Args:
        args (argparse.Namespace): CLI arguments. / CLI 参数。
    """
    override_db_settings(args)
    logger.info("Starting database migration v5 (Token Tracking)...")
    import psycopg2
    conn = None
    try:
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            dbname=settings.db_name
        )
        cur = conn.cursor()
        
        logger.info("Creating token_usage table if not exists...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id UUID PRIMARY KEY,
            service_name VARCHAR(100) NOT NULL,
            model_name VARCHAR(100) NOT NULL,
            prompt_tokens INT DEFAULT 0,
            completion_tokens INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_tu_service ON token_usage(service_name);
        CREATE INDEX IF NOT EXISTS idx_tu_model ON token_usage(model_name);
        CREATE INDEX IF NOT EXISTS idx_tu_date ON token_usage(created_at);
        """)
        conn.commit()
        logger.info("Migration v5 completed successfully.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            cur.close()
            conn.close()

def migrate_db_v7_twitter(args):
    """
    Executes database migration v7: Adds Twitter ingestion tables.
    执行数据库迁移 v7：添加推特摄取相关的表。
    """
    override_db_settings(args)
    logger.info("Starting database migration v7 (Twitter)...")
    import psycopg2
    conn = None
    try:
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            dbname=settings.db_name
        )
        cur = conn.cursor()
        
        logger.info("Creating Twitter tables...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS twitter_accounts (
            id UUID PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            auth_token TEXT NOT NULL,
            ct0 TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            last_error TEXT,
            last_used_at TIMESTAMP,
            fail_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_twitter_accounts_status ON twitter_accounts(status);

        CREATE TABLE IF NOT EXISTS twitter_monitored_users (
            rest_id VARCHAR(50) PRIMARY KEY,
            screen_name VARCHAR(100) UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            category VARCHAR(50),
            last_seen_tweet_id VARCHAR(50) DEFAULT '0',
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_twitter_monitored_active ON twitter_monitored_users(is_active);

        CREATE TABLE IF NOT EXISTS twitter_stream_raw (
            id UUID PRIMARY KEY,
            tweet_id VARCHAR(50) UNIQUE NOT NULL,
            author_screen_name VARCHAR(100),
            raw_text TEXT NOT NULL,
            is_reply BOOLEAN DEFAULT FALSE,
            reply_to_tweet_id VARCHAR(50),
            metadata JSONB,
            status SMALLINT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_twitter_stream_id ON twitter_stream_raw(tweet_id);
        """)
        conn.commit()
        logger.info("Migration v7 completed successfully.")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            cur.close()
            conn.close()

def migrate_rss(args):
    """
    Imports legacy RSS feeds from a flat text file into the database.
    将旧的 RSS 订阅源从纯文本文件导入到数据库中。
    
    Args:
        args (argparse.Namespace): CLI arguments. / CLI 参数。
    """
    override_db_settings(args)
    db = DatabaseManager()
    logger.info("Checking database before RSS migration...")
    if not db.check_integrity():
        db.init_db()
    
    # Path is relative to the old script location, but now we'll look safely in the project root/scripts or where needed
    rss_file_path = Path(__file__).resolve().parent.parent / "manage.py" # Dirty hack to find it if it was next to manage
    rss_txt = rss_file_path.parent / "rss_feeds.txt"
    if not rss_txt.exists():
        logger.error(f"Legacy RSS feeds file not found at: {rss_txt}")
        return

    logger.info(f"Migrating RSS feeds from: {rss_txt}")
    with open(rss_txt, 'r') as f:
        lines = f.readlines()
    
    count = 0
    for line in lines:
        url = line.strip()
        if url and not url.startswith('#') and url.startswith('http'):
            logger.info(f"Adding source: {url}")
            if db.add_rss_source(url):
                count += 1
            else:
                logger.debug(f"Source likely already exists: {url}")
                
    logger.info(f"Migration completed. Added {count} new sources.")

async def _run_backfill():
    from src.omnidigest.domains.daily_digest.processor import ContentProcessor
    class RAGClientWrapper:
        """
        Bypasses full RAGFlow initialization for legacy backfill tasks.
        在旧的回填任务中绕过完整的 RAGFlow 初始化。
        """
        def __init__(self):
            """
            Initializes a mock-like RAG client with a direct LLM connection.
            使用直接的 LLM 连接初始化一个类似 mock 的 RAG 客户端。
            """
            from openai import OpenAI
            self.llm_client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url
            )
            
    db = DatabaseManager()
    rag = RAGClientWrapper()
    processor = ContentProcessor(db, rag)
    
    total_processed = 0
    batch_num = 1
    
    while True:
        logger.info(f"Processing Batch {batch_num}...")
        count = await processor.run_processing_cycle()
        if count == 0:
            logger.info("No more unclassified articles found.")
            break
        total_processed += count
        batch_num += 1
        logger.info(f"Batch {batch_num-1} complete. Total processed: {total_processed}")
        import asyncio
        await asyncio.sleep(2)

    logger.info(f"Backfill Complete! Total processed: {total_processed}")

async def _run_story_backfill(hours: int):
    from src.omnidigest.domains.breaking_news.processor import BreakingProcessor
    from src.omnidigest.domains.knowledge_base.rag_client import RAGClient
    
    db = DatabaseManager()
    rag = RAGClient()
    processor = BreakingProcessor(db, rag)
    
    events = await asyncio.to_thread(db.get_events_without_story, hours=hours)
    if not events:
        logger.info(f"No events without story found in the last {hours} hours.")
        return
        
    logger.info(f"Found {len(events)} events to backfill. Starting story matching...")
    
    for ev in events:
        event_id = ev['id']
        title = ev['event_title']
        summary = ev['summary']
        category = ev['category']
        score = ev['impact_score']
        
        logger.info(f"Backfilling Event: {title} [{event_id}]")
        
        story_id = await processor._match_story(title, summary, category)
        if story_id:
            await asyncio.to_thread(db.link_event_to_story, event_id, story_id)
            source_count = await asyncio.to_thread(db.get_story_source_count, story_id)
            await asyncio.to_thread(db.update_story, story_id, title, summary, score, source_count)
            await asyncio.to_thread(db.update_story_verification, story_id, source_count)
            logger.info(f"-> Linked to existing Story [{story_id}]")
        else:
            story_id = await asyncio.to_thread(db.create_story, title, summary, category, score)
            if story_id:
                await asyncio.to_thread(db.link_event_to_story, event_id, story_id)
                logger.info(f"-> Created NEW Story [{story_id}]")
                
    logger.info("Story backfill complete.")

    import asyncio
    asyncio.run(_run_story_backfill(hours))

def token_stats(args):
    """
    Displays aggregated token usage statistics from the database.
    从数据库中显示汇总的 token 使用统计数据。
    
    Args:
        args (argparse.Namespace): Arguments containing optional 'days' for lookback. / 包含可选的回溯 'days' 的参数。
    """
    override_db_settings(args)
    days = getattr(args, 'days', 30)
    db = DatabaseManager()
    stats = db.get_token_usage_stats(days=days)
    
    if not stats:
        print(f"No token usage data found for the last {days} days.")
        return

    print(f"\n--- Token Usage Statistics (Past {days} days) ---")
    print(f"{'Service':<30} | {'Model':<20} | {'Prompt':<8} | {'Comp':<8} | {'Reqs':<5}")
    print("-" * 85)
    
    grand_total_prompt = 0
    grand_total_comp = 0
    
    for row in stats:
        service = row['service_name']
        model = row['model_name']
        prompt = row['total_prompt']
        comp = row['total_completion']
        reqs = row['total_requests']
        
        print(f"{service:<30} | {model:<20} | {prompt:<8} | {comp:<8} | {reqs:<5}")
        grand_total_prompt += prompt
        grand_total_comp += comp
        
    print("-" * 85)
    print(f"{'TOTAL':<30} | {'':<20} | {grand_total_prompt:<8} | {grand_total_comp:<8} |")
    print("\n")
