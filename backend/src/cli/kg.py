"""
Knowledge Graph CLI command handlers.
知识图谱 CLI 命令处理器。

Provides functions to initialize the Dgraph schema, run KG extraction,
and view graph statistics.
提供初始化 Dgraph Schema、运行知识图谱抽取和查看图谱统计信息的函数。
"""
import asyncio
import logging
from src.omnidigest.core.database import DatabaseManager
from src.omnidigest.core.llm_manager import LLMManager
from src.omnidigest.domains.knowledge_graph.dgraph_client import DgraphClient
from src.omnidigest.domains.knowledge_graph.extractor import KGExtractor
from src.omnidigest.cli.db import override_db_settings

logger = logging.getLogger("manage.kg")


def kg_init(args):
    """
    Initializes the Dgraph Knowledge Graph schema.
    初始化 Dgraph 知识图谱 Schema。
    """
    override_db_settings(args)
    logger.info("Initializing Dgraph Knowledge Graph Schema...")
    dgraph = DgraphClient()
    try:
        dgraph.init_schema()
        logger.info("✅ Schema initialized. You can now run 'manage.py kg extract'.")
    except Exception as e:
        logger.error(f"❌ Schema initialization failed: {e}")
    finally:
        dgraph.close()


def kg_extract(args):
    """
    Runs the KG extraction pipeline on unprocessed breaking news streams.
    对未处理的突发新闻流运行知识图谱抽取管线。
    """
    override_db_settings(args)
    hours = args.hours if hasattr(args, "hours") else 48
    logger.info(f"Starting Knowledge Graph Extraction (last {hours} hours)...")

    db = DatabaseManager()
    dgraph = DgraphClient()
    extractor = KGExtractor(db, dgraph, LLMManager(db))

    try:
        asyncio.run(extractor.run(hours=hours))
    except Exception as e:
        logger.error(f"❌ KG Extraction failed: {e}")
    finally:
        dgraph.close()


def kg_resolve(args):
    """
    Runs entity resolution (deduplication) across the Knowledge Graph.
    对知识图谱中的实体运行消歧合并。
    """
    override_db_settings(args)
    logger.info("Starting Entity Resolution...")

    db = DatabaseManager()
    dgraph = DgraphClient()
    extractor = KGExtractor(db, dgraph)

    try:
        asyncio.run(extractor.resolve_entities())
    except Exception as e:
        logger.error(f"❌ Entity Resolution failed: {e}")
    finally:
        dgraph.close()


def kg_stats(args):
    """
    Displays basic Knowledge Graph statistics.
    显示知识图谱的基本统计信息。
    """
    override_db_settings(args)
    logger.info("Fetching Knowledge Graph Statistics...")
    dgraph = DgraphClient()
    try:
        stats = dgraph.get_stats()
        logger.info("📊 Knowledge Graph Stats:")
        logger.info(f"  Persons:       {stats['persons']}")
        logger.info(f"  Organizations: {stats['organizations']}")
        logger.info(f"  Locations:     {stats['locations']}")
        logger.info(f"  Events:        {stats['events']}")
    except Exception as e:
        logger.error(f"❌ Failed to fetch stats: {e}")
    finally:
        dgraph.close()
