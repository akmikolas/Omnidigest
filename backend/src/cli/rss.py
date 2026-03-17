"""
RSS feed management CLI command handlers.
RSS 源管理 CLI 命令处理器。

Provides functions for adding individual feeds, batch importing predefined
feed lists, checking for disabled/failed feeds, and re-enabling them.
提供添加单个源、批量导入预定义源列表、检查已禁用/失败的源以及重新启用它们的函数。
"""
import sys
import logging
from src.omnidigest.core.database import DatabaseManager
from src.omnidigest.cli.db import override_db_settings

logger = logging.getLogger("manage.rss")

def add_rss(args):
    """
    CLI handler to add a single RSS feed to the database.
    CLI 处理器，用于向数据库添加单个 RSS 订阅源。
    
    Args:
        args (argparse.Namespace): Arguments containing 'url' and 'name'. / 包含 'url' 和 'name' 的参数。
    """
    override_db_settings(args)
    logger.info(f"Adding RSS source: {args.url} (Name: {args.name})")
    try:
        db = DatabaseManager()
        if not db.check_integrity():
             logger.warning("Database tables missing. Attempting to initialize...")
             db.init_db()
        result = db.add_rss_source(url=args.url, name=args.name)
        if result:
            logger.info(f"✅ Successfully added RSS source. ID: {result}")
        else:
            logger.warning("⚠️ Failed to add RSS source. It might already exist or an error occurred.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

def add_breaking_rss(args):
    """
    CLI handler to add a single breaking RSS feed to the database.
    CLI 处理器，用于向数据库添加单个突发新闻 RSS 订阅源。
    
    Args:
        args (argparse.Namespace): Arguments containing 'url', 'platform', and 'name'. / 包含 'url'、'platform' 和 'name' 的参数。
    """
    override_db_settings(args)
    logger.info(f"Adding Breaking RSS source: {args.url} (Platform: {args.platform}, Name: {args.name})")
    try:
        db = DatabaseManager()
        if not db.check_integrity():
             db.init_db()
        result = db.add_breaking_rss_source(url=args.url, platform=args.platform, name=args.name)
        if result:
            logger.info(f"✅ Successfully added Breaking RSS source. ID: {result}")
        else:
            logger.warning("⚠️ Failed to add Breaking RSS source. It might already exist or an error occurred.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

def batch_import_rss(args):
    """
    CLI handler to batch import a predefined list of high-quality RSS feeds.
    CLI 处理器，用于批量导入预定义的高质量 RSS 订阅源列表。
    
    Args:
        args (argparse.Namespace): CLI arguments. / CLI 参数。
    """
    override_db_settings(args)
    FEEDS = [
        ("https://www.scmp.com/rss/36/feed", "South China Morning Post"),
        ("http://feeds.bbci.co.uk/news/technology/rss.xml", "BBC Technology"),
        ("http://rss.cnn.com/rss/edition_technology.rss", "CNN Technology"),
        ("https://sspai.com/feed", "少数派"),
        ("https://tech.meituan.com/feed", "美团技术团队"),
        ("https://v2ex.com/index.xml", "V2EX"),
        ("https://www.solidot.org/index.rss", "Solidot"),
        ("https://www.zhihu.com/rss", "知乎"),
        ("http://feed.appinn.com/", "小众软件"),
        ("https://36kr.com/feed", "36Kr"),
        ("https://rsshub.app/zhihu/daily", "知乎日报"),
        ("http://www.geekpark.net/rss", "极客公园"),
        ("https://rsshub.app/oschina/news/project", "OSChina Project News"),
        ("https://thenewstack.io/feed/", "The New Stack"),
        ("https://www.infoq.com/feed/devops/", "InfoQ DevOps"),
        ("https://devops.com/feed/", "DevOps.com"),
        ("http://highscalability.com/rss.xml", "High Scalability"),
        ("https://tldr.tech/ai/rss", "TLDR AI"),
        ("https://openai.com/news/rss.xml", "OpenAI Blog"),
        ("https://huggingface.co/blog/feed.xml", "Hugging Face Blog"),
        ("http://arxiv-sanity-lite.com/static/rss.xml", "Arxiv AI Sanity"),
    ]
    
    logger.info(f"Starting batch import of {len(FEEDS)} predefined feeds...")
    db = DatabaseManager()
    if not db.check_integrity():
         db.init_db()
         
    success_count = 0
    fail_count = 0
    
    for url, name in FEEDS:
        logger.info(f"Processing: {name} ({url})")
        if db.add_rss_source(url, name):
            logger.info(f"✅ Success: {name}")
            success_count += 1
        else:
            logger.warning(f"⚠️ Skipped/Exists: {name}")
            fail_count += 1
            
    logger.info(f"Batch import completed. Total: {len(FEEDS)}, Inserted: {success_count}, Existing/Failed: {fail_count}")

def rss_check_failures(args):
    """
    CLI handler to list all RSS sources that have been disabled due to repeated failures.
    CLI 处理器，用于列出因重复失败而禁用的所有 RSS 源。
    
    Args:
        args (argparse.Namespace): CLI arguments. / CLI 参数。
    """
    override_db_settings(args)
    db = DatabaseManager()
    disabled_sources = db.get_disabled_rss_sources()
    
    if not disabled_sources:
        print("\n✅ Good news! All registered RSS feeds are currently healthy and enabled.\n")
        return
        
    print("\n" + "="*80)
    print(f"⚠️ FOUND {len(disabled_sources)} DISABLED RSS FEED(S) ⚠️")
    print("="*80)
    for index, src in enumerate(disabled_sources, 1):
        print(f"\n{index}. Feed Name : {src['name']}")
        print(f"   URL       : {src['url']}")
        print(f"   Failures  : {src['fail_count']}")
        print(f"   Last Error: {src['last_error']}")
    print("\n" + "="*80)
    print("Use `python manage.py rss enable <url>` to re-enable them after fixing the issue.\n")

def rss_enable(args):
    """
    CLI handler to manually re-enable a specific RSS feed by its URL.
    CLI 处理器，用于通过 URL 手动重新启用特定的 RSS 订阅源。
    
    Args:
        args (argparse.Namespace): Arguments containing the 'url' of the feed to enable. / 包含要启用的订阅源 'url' 的参数。
    """
    override_db_settings(args)
    db = DatabaseManager()
    if db.enable_rss_source(args.url):
        print(f"✅ Feed {args.url} has been re-enabled and its error count reset to 0.")
    else:
        print(f"❌ Failed to enable {args.url}. Please check the logs.")
