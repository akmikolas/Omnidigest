#!/usr/bin/env python
"""
OmniDigest First-Launch Bootstrap Script.
OmniDigest 首次启动引导脚本。

Handles:
  1. Wait for PostgreSQL / Redis readiness
  2. Create all database tables (including api_keys, astock_predictions)
  3. Run pending data migrations
  4. Seed default system configuration
  5. Generate default API key if none exist
  6. Auto-register LLM model from environment variables
"""
import logging
import os
import secrets
import sys
import time
import uuid

sys.path.insert(0, '/app')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger('bootstrap')

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def env(key, default=''):
    return os.environ.get(key, default)


def wait_for_postgres(max_retries=30, interval=2):
    """Wait for PostgreSQL to accept connections."""
    host = env('DB_HOST', 'localhost')
    port = env('DB_PORT', '5432')
    user = env('DB_USER', 'frank')
    password = env('DB_PASSWORD', '')
    dbname = env('DB_NAME', 'omnidigest')

    import psycopg2

    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                host=host, port=port, user=user,
                password=password, dbname=dbname,
            )
            conn.close()
            logger.info(f'PostgreSQL ready ({host}:{port})')
            return True
        except Exception:
            logger.info(f'Waiting for PostgreSQL... ({i + 1}/{max_retries})')
            time.sleep(interval)
    logger.warning('PostgreSQL may not be ready, continuing anyway.')
    return False


def wait_for_redis(max_retries=15, interval=2):
    """Wait for Redis to accept connections (if enabled)."""
    if env('REDIS_ENABLED', 'true').lower() != 'true':
        logger.info('Redis disabled, skipping.')
        return False

    import redis
    host = env('REDIS_HOST', 'redis')
    port = int(env('REDIS_PORT', '6379'))
    password = env('REDIS_PASSWORD', '') or None

    for i in range(max_retries):
        try:
            r = redis.Redis(
                host=host, port=port, password=password,
                socket_connect_timeout=2,
            )
            r.ping()
            logger.info(f'Redis ready ({host}:{port})')
            return True
        except Exception:
            logger.info(f'Waiting for Redis... ({i + 1}/{max_retries})')
            time.sleep(interval)
    logger.warning('Redis may not be ready.')
    return False


def run_psql(query, fetch=False):
    """Execute raw SQL via psycopg2 (bypassing DatabaseManager)."""
    import psycopg2
    from src.config import settings

    conn = psycopg2.connect(
        host=settings.db_host, port=settings.db_port,
        user=settings.db_user, password=settings.db_password,
        dbname=settings.db_name,
    )
    try:
        cur = conn.cursor()
        cur.execute(query)
        if fetch:
            result = cur.fetchall()
        else:
            result = None
        conn.commit()
        cur.close()
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Bootstrap steps
# ---------------------------------------------------------------------------

def step_init_schema():
    """Create core tables and api_keys table."""
    logger.info('Initializing database schema...')
    from src.core.database import DatabaseManager
    db = DatabaseManager()
    db.init_db()
    db.create_api_keys_table()
    logger.info('Schema created (includes api_keys, astock_predictions).')


def step_migrate():
    """Run pending data migrations (safe idempotent ALTER DO blocks)."""
    logger.info('Running migrations...')

    # v2: category, score, summary_raw columns on news_articles
    run_psql("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name='news_articles' AND column_name='category') THEN
            ALTER TABLE omnidigest.news_articles ADD COLUMN category VARCHAR(100);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name='news_articles' AND column_name='score') THEN
            ALTER TABLE omnidigest.news_articles ADD COLUMN score INT;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name='news_articles' AND column_name='summary_raw') THEN
            ALTER TABLE omnidigest.news_articles ADD COLUMN summary_raw TEXT;
        END IF;
    END $$;
    CREATE INDEX IF NOT EXISTS idx_news_category ON omnidigest.news_articles(category);
    CREATE INDEX IF NOT EXISTS idx_news_score ON omnidigest.news_articles(score);
    """)
    logger.info('  migration v2: ok')

    # v4: fail_count, last_error on rss_sources
    run_psql("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name='rss_sources' AND column_name='fail_count') THEN
            ALTER TABLE omnidigest.rss_sources ADD COLUMN fail_count INT DEFAULT 0;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name='rss_sources' AND column_name='last_error') THEN
            ALTER TABLE omnidigest.rss_sources ADD COLUMN last_error TEXT;
        END IF;
    END $$;
    """)
    logger.info('  migration v4: ok')

    logger.info('Migrations complete.')


def step_seed_config():
    """Seed system_config table if empty."""
    logger.info('Checking system configuration seed...')
    from src.config import settings
    from src.core.database import DatabaseManager
    db = DatabaseManager()
    if not db.has_config_entries():
        db.seed_default_config(settings)
        logger.info('Config seeded from defaults.')
    else:
        logger.info('Config entries already exist, skipping.')


def step_create_api_key():
    """Generate a default API key if none exist."""
    logger.info('Checking API keys...')
    from src.core.database import DatabaseManager
    from src.domains.auth.db_repo import AuthMixin
    from src.api.auth import hash_api_key

    class DB(DatabaseManager, AuthMixin):
        pass

    db = DB()
    try:
        existing = db.list_api_keys()
    except Exception as e:
        logger.warning(f'Could not list API keys: {e}')
        existing = []

    if existing:
        logger.info(f'{len(existing)} API key(s) already exist, skipping.')
        return

    client_name = env('INIT_API_KEY_NAME', 'omni-init')
    raw_key = secrets.token_urlsafe(32)
    hashed = hash_api_key(raw_key)
    db.create_api_key(client_name, hashed)
    full_key = f'{client_name}:{raw_key}'

    os.makedirs('/data', exist_ok=True)
    with open('/data/init_api_key.txt', 'w') as f:
        f.write(full_key + '\n')

    logger.info('========================================')
    logger.info('DEFAULT API KEY CREATED')
    logger.info('----------------------------------------')
    logger.info(f'  {full_key}')
    logger.info('----------------------------------------')
    logger.info('Saved to: /data/init_api_key.txt')
    logger.info('Retrieve via: docker compose exec backend cat /data/init_api_key.txt')
    logger.info('========================================')


def step_seed_llm_model():
    """Auto-register LLM model from environment variables."""
    logger.info('Checking LLM model configuration...')
    from src.config import settings

    if not settings.llm_api_key:
        logger.info('LLM_API_KEY not set, skipping.')
        return
    if not settings.db_host:
        logger.info('DB config not available, skipping.')
        return

    from src.core.database import DatabaseManager
    db = DatabaseManager()
    existing = db.get_active_llm_models()
    if existing:
        logger.info(f'{len(existing)} LLM model(s) already configured, skipping.')
        return
    db.seed_llm_model_from_env()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    logger.info('========================================')
    logger.info('OmniDigest Bootstrap - Starting')
    logger.info(f'  Time: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    logger.info('========================================')

    # 1. Wait for dependencies
    wait_for_postgres()
    wait_for_redis()

    # 2. Create tables
    step_init_schema()

    # 3. Migrations
    step_migrate()

    # 4. Seed config
    step_seed_config()

    # 5. Default API key
    step_create_api_key()

    # 6. LLM model
    step_seed_llm_model()

    logger.info('========================================')
    logger.info('OmniDigest Bootstrap - Complete')
    logger.info(f'  Time: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    logger.info('========================================')


if __name__ == '__main__':
    main()
