"""
OmniDigest Management CLI entry point.
OmniDigest 管理命令行工具入口。

This module serves as a pure argument parser and router. It defines all CLI
subcommands (db, rss, jobs, auth, rag) and dispatches them to their respective
handler modules under the `commands/` package.
本模块是一个纯粹的参数解析器和路由器。它定义了所有 CLI 子命令（db、rss、jobs、auth、rag），
并将它们分发到 `commands/` 包下对应的处理器模块。
"""
import sys
import argparse
import logging
from pathlib import Path

# Add the project root to sys.path
# 将项目根目录添加到 sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import os
env_name = os.getenv("OMNIDIGEST_ENV", "dev")
logging.info(f"CLI starting up in [{env_name}] mode...")

from src.omnidigest.cli import db as db_cmds
from src.omnidigest.cli import rss as rss_cmds
from src.omnidigest.cli import jobs as jobs_cmds
from src.omnidigest.cli import auth as auth_cmds
from src.omnidigest.cli import rag as rag_cmds
from src.omnidigest.cli import tests as test_cmds
from src.omnidigest.cli import kg as kg_cmds
from src.omnidigest.cli import twitter as twitter_cmds
from src.omnidigest.cli import lint as lint_cmds

def main():
    """
    Main entry point for the OmniDigest Management CLI.
    OmniDigest 管理命令行工具的主要入口。
    
    Parses global database arguments and dispatches commands to respective handlers.
    解析全局数据库参数并将命令分发给相应的处理器。
    """
    parser = argparse.ArgumentParser(description="OmniDigest Management CLI")
    
    # Global DB arguments
    parser.add_argument("--db-host", help="Database host address", default=None)
    parser.add_argument("--db-port", help="Database port", type=int, default=None)
    parser.add_argument("--db-user", help="Database username", default=None)
    parser.add_argument("--db-password", help="Database password", default=None)
    parser.add_argument("--db-name", help="Database name", default=None)

    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    subparsers.required = True

    # DB Commands
    db_parser = subparsers.add_parser("db", help="Database operations")
    db_subparsers = db_parser.add_subparsers(dest="db_command", help="Database commands")
    db_subparsers.required = True
    
    db_subparsers.add_parser("init", help="Initialize the database schema")
    db_subparsers.add_parser("migrate-v2", help="Run the v2 database migration")
    db_subparsers.add_parser("migrate-v3-apikeys", help="Run the v3 database migration to add api_keys table")
    db_subparsers.add_parser("migrate-v4-rss-failures", help="Run the v4 database migration to add rss_sources failure tracking")
    db_subparsers.add_parser("migrate-v5", help="Run DB migration v5 (Token Tracking)")
    db_subparsers.add_parser("migrate-v7", help="Run DB migration v7 (Twitter Ingestion)")
    db_subparsers.add_parser("migrate-rss", help="Import legacy RSS feeds from txt file")
    db_subparsers.add_parser("backfill", help="Run LLM classification backfill for unclassified articles")
    
    bf_stories = db_subparsers.add_parser("backfill-stories", help="Run Story matching backfill for events without story")
    bf_stories.add_argument("--hours", type=int, default=48, help="How many hours back to look for events (default: 48)")

    token_stats_parser = db_subparsers.add_parser("token-stats", help="Show LLM token usage statistics")
    token_stats_parser.add_argument("--days", type=int, default=30, help="Number of days to look back (default: 30)")

    # RSS Commands
    rss_parser = subparsers.add_parser("rss", help="RSS feed management")
    rss_subparsers = rss_parser.add_subparsers(dest="rss_command", help="RSS commands")
    rss_subparsers.required = True
    
    rss_add_parser = rss_subparsers.add_parser("add", help="Add a new RSS feed")
    rss_add_parser.add_argument("url", help="URL of the RSS feed")
    rss_add_parser.add_argument("--name", help="Optional name for the feed", default=None)
    
    rss_subparsers.add_parser("batch-import", help="Batch import predefined popular tech feeds")
    rss_subparsers.add_parser("check-failures", help="List all disabled RSS feeds and their failure reasons")
    
    rss_enable_parser = rss_subparsers.add_parser("enable", help="Re-enable a disabled RSS feed")
    rss_enable_parser.add_argument("url", help="URL of the disabled RSS feed")

    rss_add_breaking_parser = rss_subparsers.add_parser("add-breaking", help="Add a new breaking news RSS feed")
    rss_add_breaking_parser.add_argument("url", help="URL of the RSS feed")
    rss_add_breaking_parser.add_argument("--platform", required=True, help="Platform name (e.g., 'BBC', '财新')")
    rss_add_breaking_parser.add_argument("--name", help="Optional friendly name for the feed", default=None)

    # Jobs Commands
    jobs_parser = subparsers.add_parser("jobs", help="Background job triggers")
    jobs_subparsers = jobs_parser.add_subparsers(dest="jobs_command", help="Jobs commands")
    jobs_subparsers.required = True
    
    trigger_summary_parser = jobs_subparsers.add_parser("trigger-summary", help="Trigger daily summary generation")
    trigger_summary_parser.add_argument("--dry-run", action="store_true", help="Generate summary but do not push to external platforms")
    
    jobs_subparsers.add_parser("cleanup", help="Trigger low quality article cleanup")
    
    test_push_parser = jobs_subparsers.add_parser("test-breaking-push", help="Test formatted push of the latest breaking news")
    test_push_parser.add_argument("--platform", choices=['dingtalk', 'tg', 'telegram', 'all'], default='all', help="Platform to test (default: all)")

    # Auth Commands
    auth_parser = subparsers.add_parser("auth", help="Authentication and API Key management")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", help="Auth commands")
    auth_subparsers.required = True
    
    auth_create_parser = auth_subparsers.add_parser("create-key", help="Create a new API key")
    auth_create_parser.add_argument("client_name", help="Identifier for the client using this key")
    
    auth_subparsers.add_parser("list-keys", help="List all API keys")
    
    auth_revoke_parser = auth_subparsers.add_parser("revoke-key", help="Revoke an API key")
    auth_revoke_parser.add_argument("client_name", help="Identifier for the client whose key will be revoked")

    # RAG Commands
    rag_parser = subparsers.add_parser("rag", help="RAGFlow management")
    rag_subparsers = rag_parser.add_subparsers(dest="rag_command", help="RAG commands")
    rag_subparsers.required = True
    
    rag_subparsers.add_parser("init-breaking", help="Initialize the Breaking News dataset in RAGFlow")

    # Test Commands
    test_parser = subparsers.add_parser("test", help="Test mature features end-to-end")
    test_subparsers = test_parser.add_subparsers(dest="test_command", help="Test commands")
    test_subparsers.required = True

    test_subparsers.add_parser("all", help="Run all end-to-end tests (Daily & Breaking)")
    test_subparsers.add_parser("breaking", help="Test Breaking News pipeline (Crawler -> Processor -> Alerter)")
    test_subparsers.add_parser("daily", help="Test Daily News pipeline (Crawler -> Summary -> Push)")

    # Knowledge Graph Commands
    kg_parser = subparsers.add_parser("kg", help="Knowledge Graph operations (Dgraph)")
    kg_subparsers = kg_parser.add_subparsers(dest="kg_command", help="KG commands")
    kg_subparsers.required = True

    kg_subparsers.add_parser("init", help="Initialize Dgraph Knowledge Graph schema")
    kg_extract_parser = kg_subparsers.add_parser("extract", help="Extract entities & relations from breaking news into Dgraph")
    kg_extract_parser.add_argument("--hours", type=int, default=48, help="How many hours back to look for streams (default: 48)")
    kg_subparsers.add_parser("stats", help="Show Knowledge Graph statistics")
    kg_subparsers.add_parser("resolve", help="Run entity resolution (deduplicate entities across languages)")

    # Twitter Commands
    twitter_parser = subparsers.add_parser("twitter", help="Twitter ingestion management")
    twitter_subparsers = twitter_parser.add_subparsers(dest="twitter_command", help="Twitter commands")
    twitter_subparsers.required = True
    
    twitter_add_acc_parser = twitter_subparsers.add_parser("add-account", help="Add/update a Twitter account session")
    twitter_add_acc_parser.add_argument("username", help="Twitter username")
    twitter_add_acc_parser.add_argument("auth_token", help="auth_token from cookies")
    twitter_add_acc_parser.add_argument("ct0", help="ct0 from cookies")
    
    twitter_add_inf_parser = twitter_subparsers.add_parser("add-influencer", help="Follow a new influencer")
    twitter_add_inf_parser.add_argument("rest_id", help="Twitter numeric ID")
    twitter_add_inf_parser.add_argument("screen_name", help="Twitter screen name")
    twitter_add_inf_parser.add_argument("--category", help="Category for this influencer", default="General")
    
    twitter_trigger_parser = twitter_subparsers.add_parser("trigger-crawl", help="Manually trigger a Twitter crawl")
    
    twitter_process_parser = twitter_subparsers.add_parser("process-tweets", help="Manually trigger a Twitter triage/scoring cycle")
    twitter_process_parser.add_argument("--limit", type=int, default=20, help="Number of tweets to process (default: 20)")

    # Lint Commands
    lint_parser = subparsers.add_parser("lint", help="Code quality and standard enforcement")
    lint_subparsers = lint_parser.add_subparsers(dest="lint_command", help="Lint commands")
    lint_subparsers.required = True
    
    lint_subparsers.add_parser("comments", help="Check for bilingual docstring compliance")

    args = parser.parse_args()

    # Dispatch logic mapped to new command modules
    if args.command == "db":
        if args.db_command == "init":
            db_cmds.init_db(args)
        elif args.db_command == "migrate-v2":
            db_cmds.migrate_db_v2(args)
        elif args.db_command == "migrate-v3-apikeys":
            db_cmds.migrate_db_v3_apikeys(args)
        elif args.db_command == "migrate-v4-rss-failures":
            db_cmds.migrate_db_v4_rss_failures(args)
        elif args.db_command == "migrate-v5":
            db_cmds.migrate_db_v5_token(args)
        elif args.db_command == "migrate-v7":
            db_cmds.migrate_db_v7_twitter(args)
        elif args.db_command == "migrate-rss":
            db_cmds.migrate_rss(args)
        elif args.db_command == "backfill":
            db_cmds.backfill_classification(args)
        elif args.db_command == "backfill-stories":
            db_cmds.backfill_stories(args)
        elif args.db_command == "token-stats":
            db_cmds.token_stats(args)
            
    elif args.command == "rss":
        if args.rss_command == "add":
            rss_cmds.add_rss(args)
        elif args.rss_command == "batch-import":
            rss_cmds.batch_import_rss(args)
        elif args.rss_command == "check-failures":
            rss_cmds.rss_check_failures(args)
        elif args.rss_command == "enable":
            rss_cmds.rss_enable(args)
        elif args.rss_command == "add-breaking":
            rss_cmds.add_breaking_rss(args)
            
    elif args.command == "jobs":
        if args.jobs_command == "trigger-summary":
            jobs_cmds.trigger_summary(args)
        elif args.jobs_command == "cleanup":
            jobs_cmds.cleanup_jobs(args)
        elif args.jobs_command == "test-breaking-push":
            jobs_cmds.test_breaking_push(args)
            
    elif args.command == "auth":
        if args.auth_command == "create-key":
            auth_cmds.auth_create_key(args)
        elif args.auth_command == "list-keys":
            auth_cmds.auth_list_keys(args)
        elif args.auth_command == "revoke-key":
            auth_cmds.auth_revoke_key(args)
            
    elif args.command == "rag":
        if args.rag_command == "init-breaking":
            rag_cmds._init_breaking_dataset()
            
    elif args.command == "test":
        if args.test_command == "all":
            test_cmds.test_all(args)
        elif args.test_command == "breaking":
            test_cmds.test_breaking(args)
        elif args.test_command == "daily":
            test_cmds.test_daily(args)

    elif args.command == "kg":
        if args.kg_command == "init":
            kg_cmds.kg_init(args)
        elif args.kg_command == "extract":
            kg_cmds.kg_extract(args)
        elif args.kg_command == "stats":
            kg_cmds.kg_stats(args)
        elif args.kg_command == "resolve":
            kg_cmds.kg_resolve(args)
            
    elif args.command == "twitter":
        if args.twitter_command == "add-account":
            twitter_cmds.twitter_add_account(args)
        elif args.twitter_command == "add-influencer":
            twitter_cmds.twitter_add_influencer(args)
        elif args.twitter_command == "trigger-crawl":
            twitter_cmds.twitter_trigger_crawl(args)
        elif args.twitter_command == "process-tweets":
            twitter_cmds.twitter_process_tweets(args)

    elif args.command == "lint":
        if args.lint_command == "comments":
            lint_cmds.lint_comments(args)

if __name__ == "__main__":
    main()
