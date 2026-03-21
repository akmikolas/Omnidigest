"""
End-to-End Test Suite CLI command handlers.
端到端测试套件 CLI 命令处理器。

Provides functions to manually trigger and verify the full workflow of 
Daily News generation and Breaking News clustering and alerting.
提供手动触发和验证常规新闻生成流程、以及突发新闻聚类与警报完整工作流的函数。
"""
import asyncio
import logging
import uuid
from datetime import datetime
from src.omnidigest.core.database import DatabaseManager
from src.omnidigest.cli.db import override_db_settings
from src.omnidigest.domains.breaking_news.alerter import BreakingAlerter
from src.omnidigest.notifications.pusher import NotificationService
from src.omnidigest.config import settings

logger = logging.getLogger("manage.tests")

def test_breaking(args):
    """
    Tests the breaking news pipeline by injecting mock data, processing it, and pushing an alert.
    测试突发新闻链路：注入 Mock 数据，处理数据并推送警报。
    """
    override_db_settings(args)
    logger.info("=== START: Breaking News End-to-End Test ===")
    
    from src.omnidigest.domains.breaking_news.processor import BreakingProcessor
    from src.omnidigest.domains.knowledge_base.rag_client import RAGClient
    from src.omnidigest.core.llm_manager import LLMManager
    
    db = DatabaseManager()
    rag = RAGClient()
    llm = LLMManager(db)
    processor = BreakingProcessor(db, llm, rag)
    pusher = NotificationService()
    alerter = BreakingAlerter(db, pusher)

    # 0. Cleanup old test data
    logger.info("0. Cleaning up all data related to [TEST] streams...")
    try:
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Clear mappings first to avoid FK constraint issues
                cur.execute("""
                    DELETE FROM omnidigest.event_stream_mapping WHERE stream_id IN (
                        SELECT id FROM omnidigest.breaking_stream_raw WHERE raw_text LIKE '%%[TEST]%%'
                    )
                """)
                # 2. Delete events linked to TEST streams
                cur.execute("""
                    DELETE FROM omnidigest.breaking_events WHERE id IN (
                        SELECT e.id FROM omnidigest.breaking_events e
                        JOIN omnidigest.event_stream_mapping m ON m.event_id = e.id
                        JOIN omnidigest.breaking_stream_raw r ON r.id = m.stream_id
                        WHERE r.raw_text LIKE '%%[TEST]%%'
                    ) OR event_title LIKE '%%[TEST]%%'
                """)
                # 3. Delete stories (if any events were linked to them or they have TEST in title)
                # Note: This might still leave stories if they have multiple events, some not being TEST events.
                # But for tests, usually everything is TEST-related.
                cur.execute("""
                    DELETE FROM omnidigest.breaking_stories WHERE story_title LIKE '%%[TEST]%%'
                """)
                # Also delete stories that no longer have events
                cur.execute("""
                    DELETE FROM omnidigest.breaking_stories WHERE id NOT IN (SELECT DISTINCT story_id FROM omnidigest.breaking_events WHERE story_id IS NOT NULL)
                    AND (story_title LIKE '%%[TEST]%%' OR "created_at" > NOW() - INTERVAL '1 hour')
                """)
                # 4. Finally delete raw streams
                cur.execute("DELETE FROM omnidigest.breaking_stream_raw WHERE raw_text LIKE '%%[TEST]%%'")
            conn.commit()
        logger.info("✅ Deep cleanup successful.")
    except Exception as e:
        logger.warning(f"Cleanup encountered issues: {e}")

    # 1. Inject Mock Streams with unique identifiers
    test_id = str(uuid.uuid4())[:8]
    stream1 = {
        'id': str(uuid.uuid4()),
        'source_platform': 'CNBC',
        'raw_text': f'[TEST] BREAKING({test_id}): The Global Stock Market Index has suddenly crashed by 15% in early trading following unexpected interest rate hikes. Panic selling across tech sectors.',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    stream2 = {
        'id': str(uuid.uuid4()),
        'source_platform': 'Financial Times',
        'raw_text': f'[TEST] URGENT({test_id}): Widespread market panic as global indices plummet over 15% within hours. Tech giants see billions wiped out amidst rate hike fears.',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    logger.info(f"1. Injecting 2 different raw streams with Test Tag [{test_id}]...")
    query = """
    INSERT INTO omnidigest.breaking_stream_raw (id, source_platform, source_url, raw_text, status)
    VALUES (%s, %s, %s, %s, 0)
    """
    try:
        with db._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (stream1['id'], stream1['source_platform'], f'http://test.cnbc.com/{stream1["id"]}', stream1['raw_text']))
                cur.execute(query, (stream2['id'], stream2['source_platform'], f'http://test.ft.com/{stream2["id"]}', stream2['raw_text']))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to inject test streams: {e}")
        return

    # 2. Process Streams (Test LLM Clustering)
    logger.info("\n2. Processing injected streams (triggering AI triage, scoring, and story matching)...")
    logger.info("Processing stream 1...")
    asyncio.run(processor.process_single_stream(stream1))
    
    logger.info("Processing stream 2...")
    asyncio.run(processor.process_single_stream(stream2))

    # 3. Check DB mapping
    logger.info("\n3. Verifying Story mapping in DB...")
    with db._get_connection() as conn:
        with conn.cursor() as cur:
            # We look up based on the stream IDs we just injected and processed
            cur.execute("""
                SELECT s.id, s.story_title, s.category, s.peak_score, s.source_count, s.status, e.event_title
                FROM omnidigest.breaking_stories s
                JOIN omnidigest.breaking_events e ON e.story_id = s.id
                JOIN omnidigest.event_stream_mapping m ON m.event_id = e.id
                WHERE m.stream_id = %s OR m.stream_id = %s
                ORDER BY s."created_at" DESC
                LIMIT 2
            """, (stream1["id"], stream2["id"]))
            rows = cur.fetchall()
            if rows:
                logger.info(f"✅ Found {len(rows)} mappings. Story Mapping:")
                logger.info(f"Story: {rows[0][1]} (Score: {rows[0][3]}, Sources: {rows[0][4]}, Status: {rows[0][5]})")
                logger.info("Child Events:")
                for r in set([r[6] for r in rows]): # Deduplicate in case of multiple rows
                    logger.info(f"- {r}")
            else:
                logger.warning("❌ No matching stories found in DB after processing.")

    # 4. Push Alerts
    logger.info("\n4. Triggering Alerter logic...")
    logger.info("Note: The real alert will be sent with a [TEST] prefix if it meets the criteria.")
    try:
        # Force threshold override for test to ensure it fires
        original_threshold = alerter.threshold
        alerter.threshold = 50 # Lower threshold to ensure test fire
        alerter.check_and_push()
        alerter.threshold = original_threshold
        logger.info("✅ Breaking News Test Complete.")
    except Exception as e:
        logger.error(f"❌ Pushing failed: {e}")
        
    logger.info("=== END: Breaking News End-to-End Test ===")

def test_daily(args):
    """
    Tests the daily news pipeline by running the summary job.
    测试常规新闻链路：运行每日摘要作业生成总结并推送。
    """
    override_db_settings(args)
    logger.info("=== START: Daily News End-to-End Test ===")
    logger.info("This will trigger a REAL daily summary push to your active groups.")
    
    from src.omnidigest.jobs import job_daily_summary
    
    try:
        # We pass dry_run=False explicitly and prefix the title so users know it's a test.
        asyncio.run(job_daily_summary(custom_title_prefix="[TEST] "))
        logger.info("✅ Daily News Test Complete.")
    except Exception as e:
        logger.error(f"❌ Daily test failed: {e}")
        
    logger.info("=== END: Daily News End-to-End Test ===")

def test_all(args):
    """
    Runs both breaking and daily test suites sequentially.
    依次运行突发新闻和常规新闻的测试套件。
    """
    test_breaking(args)
    print("\n" + "="*50 + "\n")
    test_daily(args)
