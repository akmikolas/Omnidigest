"""
Database manager for PostgreSQL interactions. Handles database initialization, CRUD operations for news articles, and high-score filtering.
PostgreSQL 交互的数据库管理器。处理数据库初始化、新闻文章的 CRUD 操作和高分过滤。
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
import uuid
import logging
import time
import threading
from typing import Dict, Any
from ..config import settings

logger = logging.getLogger(__name__)

# Connection pool configuration / 连接池配置
DEFAULT_MIN_CONN = 10
DEFAULT_MAX_CONN = 2000  # Increased to handle high concurrent requests
CONNECTION_TIMEOUT = 10  # seconds
IDLE_CONNECTION_THRESHOLD = 300  # seconds - warn if connection idle for too long


from ..domains.daily_digest.db_repo import DailyNewsMixin
from ..domains.ingestion.rss.db_repo import RssSourcesMixin, FastRssSourcesMixin
from ..domains.auth.db_repo import AuthMixin
from ..domains.breaking_news.db_repo import BreakingNewsMixin
from ..domains.ingestion.twitter.db_repo import TwitterDbMixin

class DatabaseManager(DailyNewsMixin, RssSourcesMixin, FastRssSourcesMixin, AuthMixin, BreakingNewsMixin, TwitterDbMixin):
    """
    Manages database interactions for news articles.
    管理新闻文章的数据库交互。

    Features:
    - Connection pooling with configurable limits / 连接池，可配置限制
    - Connection health checking / 连接健康检查
    - Leak detection for idle connections / 空闲连接泄漏检测
    - Pool status metrics / 连接池状态指标
    """
    def __init__(self):
        """
        Initialize the DatabaseManager. Sets the internal pool object to None. Connection is lazily instantiated.
        初始化 DatabaseManager。将内部连接池对象设置为 None。连接是延迟实例化的。
        """
        self._pool = None
        self._connection_timestamps: Dict[Any, float] = {}  # Track connection checkout times
        self._lock = threading.Lock()
        self._stats = {
            "total_checkouts": 0,
            "total_checkins": 0,
            "health_checks": 0,
            "failed_health_checks": 0,
            "leak_warnings": 0
        }

    def _initialize_pool(self):
        """
        Initialize the connection pool if not already done.
        如果连接池尚未初始化，则初始化它。
        """
        if not self._pool:
            with self._lock:
                # Double-check after acquiring lock
                if not self._pool:
                    logger.info(f"Initializing connection pool: min={DEFAULT_MIN_CONN}, max={DEFAULT_MAX_CONN}")
                    self._pool = ThreadedConnectionPool(
                        minconn=DEFAULT_MIN_CONN,
                        maxconn=DEFAULT_MAX_CONN,
                        host=settings.db_host,
                        port=settings.db_port,
                        user=settings.db_user,
                        password=settings.db_password,
                        dbname=settings.db_name,
                        connection_factory=None,
                        cursor_factory=None
                    )
                    logger.info("Connection pool initialized successfully")

    def get_pool_status(self) -> Dict[str, Any]:
        """
        Get current connection pool status metrics.
        获取当前连接池状态指标。

        Returns:
            dict: Pool status including connections, health, and stats.
        """
        self._initialize_pool()
        pool = self._pool

        # Count idle and used connections by checking the internal pool state
        # Note: psycopg2 doesn't expose this directly, so we estimate
        try:
            # Try to get a connection to test pool responsiveness
            test_conn = pool.getconn()
            pool.putconn(test_conn)
            pool_healthy = True
        except Exception:
            pool_healthy = False

        return {
            "pool_initialized": self._pool is not None,
            "pool_healthy": pool_healthy,
            "max_connections": DEFAULT_MAX_CONN,
            "min_connections": DEFAULT_MIN_CONN,
            "stats": self._stats.copy()
        }

    def _check_connection_health(self, conn) -> bool:
        """
        Check if a connection is still healthy.
        检查连接是否仍然健康。

        Args:
            conn: The database connection to check.

        Returns:
            bool: True if connection is healthy.
        """
        try:
            conn.isolation_level
            # Try a simple query to verify connection is alive
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception as e:
            logger.warning(f"Connection health check failed: {e}")
            return False

    @contextmanager
    def _get_connection(self):
        """
        Retrieves an active PostgreSQL database connection from the pool. If the pool doesn't exist, a new one is created using settings.
        从连接池检索活动的 PostgreSQL 数据库连接。如果池不存在，则使用设置创建一个新池。

        Features:
        - Lazy pool initialization / 延迟池初始化
        - Connection checkout time tracking / 连接检出时间跟踪
        - Automatic health check on checkout / 检出时自动健康检查

        Yields:
            psycopg2.extensions.connection: The active database connection object. / 活动的数据库连接对象。
        """
        # Initialize pool if needed
        self._initialize_pool()

        conn = self._pool.getconn()
        checkout_time = time.time()

        # Track checkout
        with self._lock:
            self._connection_timestamps[id(conn)] = checkout_time
            self._stats["total_checkouts"] += 1

        try:
            # Health check on checkout - only if connection was used recently
            if self._stats["total_checkouts"] % 10 == 0:  # Check every 10 checkouts
                self._stats["health_checks"] += 1
                if not self._check_connection_health(conn):
                    self._stats["failed_health_checks"] += 1
                    logger.warning("Health check failed, attempting to reconnect...")
                    # Force a new connection by resetting
                    self._pool.putconn(conn, close=True)
                    conn = self._pool.getconn()
                    # Update timestamp for new connection
                    with self._lock:
                        self._connection_timestamps[id(conn)] = time.time()

            # Check for potential leaks (connections checked out too long)
            idle_time = time.time() - checkout_time
            if idle_time > IDLE_CONNECTION_THRESHOLD:
                self._stats["leak_warnings"] += 1
                logger.warning(f"Potential connection leak: connection checked out for {idle_time:.1f}s")

            yield conn
        finally:
            # Return connection to pool (with safety check in case pool was closed)
            if self._pool is not None:
                try:
                    self._pool.putconn(conn)
                except Exception as e:
                    logger.warning(f"Failed to return connection to pool: {e}")
            # Clean up timestamp regardless
            with self._lock:
                self._stats["total_checkins"] += 1
                if id(conn) in self._connection_timestamps:
                    del self._connection_timestamps[id(conn)]

    def check_pool_health(self) -> bool:
        """
        Perform a comprehensive health check on the connection pool.
        对连接池执行全面的健康检查。

        Returns:
            bool: True if pool is healthy.
        """
        if not self._pool:
            return False

        try:
            # Test getting a connection from the pool
            conn = self._pool.getconn()
            try:
                # Execute a simple query
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            finally:
                self._pool.putconn(conn)
        except Exception as e:
            logger.error(f"Pool health check failed: {e}")
            return False

    def close_all(self):
        """
        Closes all connections in the pool.
        关闭池中的所有连接。
        """
        if self._pool:
            logger.info("Closing all database connections...")
            self._pool.closeall()
            self._pool = None
            with self._lock:
                self._connection_timestamps.clear()
                # Reset stats but keep them for reference
                logger.info(f"Final pool stats: {self._stats}")

    def check_integrity(self):
        """
        Validates that required tables exist in the database. If tables don't exist, automatically creates them.
        验证数据库中必需的表是否存在。如果表不存在，则自动创建。

        Returns:
            bool: True if all required tables exist (or were created), False otherwise. / 如果所有必需的表都存在（或已创建），则返回 True，否则返回 False。
        """
        required_tables = ['news_articles', 'rss_sources', 'breaking_stream_raw', 'breaking_events', 'twitter_accounts', 'twitter_monitored_users']
        try:
            # Open a connection and a cursor to execute queries
            # 打开连接和游标以执行查询
            missing_tables = []
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    for table in required_tables:
                        # Query the information_schema to verify table presence
                        # 查询 information_schema 以验证表是否存在
                        cur.execute(
                            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'omnidigest' AND table_name = %s",
                            (table,)
                        )
                        if not cur.fetchone():
                            missing_tables.append(table)
                            logger.warning(f"Missing table: {table}")

            if missing_tables:
                logger.info(f"Auto-initializing database: creating {len(missing_tables)} missing tables...")
                self.init_db()
                # Verify again after init
                with self._get_connection() as conn:
                    with conn.cursor() as cur:
                        for table in missing_tables:
                            cur.execute(
                                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'omnidigest' AND table_name = %s",
                                (table,)
                            )
                            if not cur.fetchone():
                                logger.error(f"Failed to create table: {table}")
                                return False
                logger.info("Database auto-initialization completed successfully.")

            return True
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False

    def init_db(self):
        """
        Initializes the database schema if tables do not exist. Creates all required tables under the 'omnidigest' schema.
        如果表不存在，初始化数据库模式。在 'omnidigest' schema 下创建所有必需的表。
        """
        schema = "omnidigest"
        queries = [
            f"""CREATE SCHEMA IF NOT EXISTS {schema};""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.news_articles (
                id UUID PRIMARY KEY,
                title VARCHAR(512) NOT NULL,
                content TEXT NOT NULL,
                source_url TEXT UNIQUE,
                source_name VARCHAR(100),
                status SMALLINT DEFAULT 0,
                ragflow_id VARCHAR(100),
                category VARCHAR(100),
                score INT,
                summary_raw TEXT,
                publish_time TIMESTAMP,
                "created_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_news_status ON {schema}.news_articles(status);
            CREATE INDEX IF NOT EXISTS idx_news_url ON {schema}.news_articles(source_url);
            CREATE INDEX IF NOT EXISTS idx_news_category ON {schema}.news_articles(category);
            CREATE INDEX IF NOT EXISTS idx_news_score ON {schema}.news_articles(score);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.rss_sources (
                id UUID PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                name VARCHAR(255),
                enabled BOOLEAN DEFAULT TRUE,
                fail_count INT DEFAULT 0,
                last_error TEXT,
                "created_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_rss_enabled ON {schema}.rss_sources(enabled);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.breaking_rss_sources (
                id UUID PRIMARY KEY,
                url VARCHAR(512) UNIQUE NOT NULL,
                name VARCHAR(100),
                platform VARCHAR(50) NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                fail_count INT DEFAULT 0,
                success_count INT DEFAULT 0,
                last_error TEXT,
                "created_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_brss_url ON {schema}.breaking_rss_sources(url);
            CREATE INDEX IF NOT EXISTS idx_brss_enabled ON {schema}.breaking_rss_sources(enabled);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.breaking_stream_raw (
                id UUID PRIMARY KEY,
                source_platform VARCHAR(100) NOT NULL,
                source_url TEXT UNIQUE NOT NULL,
                raw_text TEXT NOT NULL,
                author VARCHAR(255),
                publish_time TIMESTAMP,
                status SMALLINT DEFAULT 0,
                kg_processed BOOLEAN DEFAULT FALSE,
                "created_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_bsr_status ON {schema}.breaking_stream_raw(status);
            CREATE INDEX IF NOT EXISTS idx_bsr_platform ON {schema}.breaking_stream_raw(source_platform);
            CREATE INDEX IF NOT EXISTS idx_bsr_pub_time ON {schema}.breaking_stream_raw(publish_time);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.breaking_stories (
                id UUID PRIMARY KEY,
                story_title VARCHAR(512) NOT NULL,
                story_summary TEXT,
                category VARCHAR(100),
                peak_score INT DEFAULT 0,
                source_count INT DEFAULT 0,
                status VARCHAR(50) DEFAULT 'developing',
                pushed BOOLEAN DEFAULT FALSE,
                push_count INT DEFAULT 0,
                last_pushed_at TIMESTAMP,
                last_pushed_score INT DEFAULT 0,
                "created_at" TIMESTAMP DEFAULT NOW(),
                "updated_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_stories_score ON {schema}.breaking_stories(peak_score);
            CREATE INDEX IF NOT EXISTS idx_stories_status ON {schema}.breaking_stories(status);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.breaking_events (
                id UUID PRIMARY KEY,
                event_title VARCHAR(512) NOT NULL,
                summary TEXT,
                category VARCHAR(100),
                impact_score INT DEFAULT 0,
                ragflow_id VARCHAR(100),
                pushed BOOLEAN DEFAULT FALSE,
                story_id UUID REFERENCES {schema}.breaking_stories(id) ON DELETE SET NULL,
                "created_at" TIMESTAMP DEFAULT NOW(),
                "updated_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_be_score ON {schema}.breaking_events(impact_score);
            CREATE INDEX IF NOT EXISTS idx_be_cat ON {schema}.breaking_events(category);
            CREATE INDEX IF NOT EXISTS idx_be_story ON {schema}.breaking_events(story_id);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.event_stream_mapping (
                id UUID PRIMARY KEY,
                event_id UUID REFERENCES {schema}.breaking_events(id) ON DELETE CASCADE,
                stream_id UUID REFERENCES {schema}.breaking_stream_raw(id) ON DELETE CASCADE,
                "created_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_esm_event ON {schema}.event_stream_mapping(event_id);
            CREATE INDEX IF NOT EXISTS idx_esm_stream ON {schema}.event_stream_mapping(stream_id);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.twitter_accounts (
                id UUID PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                auth_token TEXT NOT NULL,
                ct0 TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'active',
                last_error TEXT,
                last_used_at TIMESTAMP,
                fail_count INT DEFAULT 0,
                "created_at" TIMESTAMP DEFAULT NOW(),
                account_label VARCHAR(50),
                last_active_at TIMESTAMP,
                proxy_url TEXT,
                cooled_until TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_twitter_accounts_status ON {schema}.twitter_accounts(status);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.twitter_monitored_users (
                rest_id VARCHAR(50) PRIMARY KEY,
                screen_name VARCHAR(100) UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                category VARCHAR(50),
                last_seen_tweet_id VARCHAR(50) DEFAULT '0',
                "created_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_twitter_monitored_active ON {schema}.twitter_monitored_users(is_active);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.twitter_stream_raw (
                id UUID PRIMARY KEY,
                tweet_id VARCHAR(50) UNIQUE NOT NULL,
                author_screen_name VARCHAR(100),
                raw_text TEXT NOT NULL,
                is_reply BOOLEAN DEFAULT FALSE,
                reply_to_tweet_id VARCHAR(50),
                metadata JSONB,
                status SMALLINT DEFAULT 0,
                "created_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_twitter_stream_id ON {schema}.twitter_stream_raw(tweet_id);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.llm_models (
                id UUID PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                base_url TEXT NOT NULL,
                api_key TEXT NOT NULL,
                model_name VARCHAR(100) NOT NULL,
                priority INT DEFAULT 0,
                fail_count INT DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                last_error TEXT,
                last_success TIMESTAMP,
                input_price_per_m DECIMAL(10, 2) DEFAULT 7.0,
                output_price_per_m DECIMAL(10, 2) DEFAULT 7.0,
                "created_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_llm_active ON {schema}.llm_models(is_active);
            CREATE INDEX IF NOT EXISTS idx_llm_priority ON {schema}.llm_models(priority);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.token_usage (
                id UUID PRIMARY KEY,
                service_name VARCHAR(100) NOT NULL,
                model_name VARCHAR(100) NOT NULL,
                prompt_tokens INT DEFAULT 0,
                completion_tokens INT DEFAULT 0,
                cached_tokens INT DEFAULT 0,
                "created_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_tu_service ON {schema}.token_usage(service_name);
            CREATE INDEX IF NOT EXISTS idx_tu_model ON {schema}.token_usage(model_name);
            CREATE INDEX IF NOT EXISTS idx_tu_date ON {schema}.token_usage("created_at");""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.system_config (
                id UUID PRIMARY KEY,
                section VARCHAR(50) NOT NULL,
                key VARCHAR(100) NOT NULL,
                value TEXT,
                value_type VARCHAR(20) DEFAULT 'string',
                description VARCHAR(255),
                is_editable BOOLEAN DEFAULT TRUE,
                "created_at" TIMESTAMP DEFAULT NOW(),
                "updated_at" TIMESTAMP DEFAULT NOW(),
                UNIQUE(section, key)
            );
            CREATE INDEX IF NOT EXISTS idx_sys_config_section ON {schema}.system_config(section);""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.twitter_events (
                id UUID PRIMARY KEY,
                event_title VARCHAR(512) NOT NULL,
                summary TEXT,
                category VARCHAR(100),
                peak_score INT DEFAULT 0,
                source_count INT DEFAULT 0,
                first_tweet_id VARCHAR(50),
                status VARCHAR(50) DEFAULT 'active',
                pushed BOOLEAN DEFAULT FALSE,
                "created_at" TIMESTAMP DEFAULT NOW(),
                "updated_at" TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_te_score ON {schema}.twitter_events(peak_score);
            CREATE INDEX IF NOT EXISTS idx_te_status ON {schema}.twitter_events(status);
            CREATE INDEX IF NOT EXISTS idx_te_created ON {schema}.twitter_events("created_at");""",

            f"""CREATE TABLE IF NOT EXISTS {schema}.twitter_event_tweet_mapping (
                id UUID PRIMARY KEY,
                event_id UUID REFERENCES {schema}.twitter_events(id) ON DELETE CASCADE,
                tweet_id VARCHAR(50),
                author_screen_name VARCHAR(100),
                "created_at" TIMESTAMP DEFAULT NOW(),
                UNIQUE(event_id, tweet_id)
            );
            CREATE INDEX IF NOT EXISTS idx_tetm_event ON {schema}.twitter_event_tweet_mapping(event_id);
            CREATE INDEX IF NOT EXISTS idx_tetm_tweet ON {schema}.twitter_event_tweet_mapping(tweet_id);""",
        ]
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    for query in queries:
                        cur.execute(query)
                conn.commit()
            logger.info("Database initialized successfully under omnidigest schema.")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def create_api_keys_table(self):
        """
        Creates the 'api_keys' table if it does not exist under omnidigest schema.
        如果 'api_keys' 表不存在则在 omnidigest schema 下创建它。
        """
        query = """
        CREATE TABLE IF NOT EXISTS omnidigest.api_keys (
            id SERIAL PRIMARY KEY,
            client_name VARCHAR(100) UNIQUE NOT NULL,
            key_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            "created_at" TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_api_keys_client ON omnidigest.api_keys(client_name);
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                conn.commit()
            logger.info("api_keys table ensured.")
        except Exception as e:
            logger.error(f"Failed to create api_keys table: {e}")
            raise

    # ==========================
    # LLM Model Failover Methods
    # ==========================

    def get_active_llm_models(self) -> list[dict]:
        """
        Retrieves all currently active LLM models from the 'llm_models' table, ordered by priority.
        从 'llm_models' 表中检索所有当前处于活跃状态的大语言模型，按优先级排序。
        
        Returns:
            list[dict]: A list of model configurations as dictionaries. / 包含模型配置字典的列表。
        """
        query = """
        SELECT id, name, base_url, api_key, model_name, priority, fail_count, input_price_per_m, output_price_per_m
        FROM omnidigest.llm_models
        WHERE is_active = TRUE
        ORDER BY priority DESC, "created_at" ASC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to fetch active LLM models: {e}")
            return []

    def increment_llm_failure(self, name: str, error: str, threshold: int = 5):
        """
        Increments the failure counter for a given LLM model and records the last error message.
        增加指定大语言模型模型的失败计数器，并记录最后一条错误信息。
        
        Args:
            name (str): The unique name/identifier of the LLM model. / 大语言模型的唯一名称/标识符。
            error (str): The error message to record. / 要记录的错误信息。
        """
        logger.info(f"Incrementing failure count for LLM: {name}")
        query = """
        UPDATE omnidigest.llm_models
        SET fail_count = fail_count + 1, last_error = %s
        WHERE name = %s
        RETURNING fail_count
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (error, name))
                    result = cur.fetchone()
                    if result and result[0] >= threshold:
                        cur.execute("UPDATE omnidigest.llm_models SET is_active = FALSE WHERE name = %s", (name,))
                        logger.warning(f"LLM Model {name} deactivated due to {result[0]} consecutive failures.")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to increment LLM failure for {name}: {e}")

    def reset_llm_failure(self, name: str):
        """
        Resets the failure counter to zero and updates the 'last_success' timestamp for a specific model.
        将特定模型的失败计数器重置为零，并更新 'last_success' 时间戳。
        
        Args:
            name (str): The name of the LLM model to reset. / 要重置的大语言模型名称。
        """
        query = """
        UPDATE omnidigest.llm_models
        SET fail_count = 0, last_success = NOW(), last_error = NULL
        WHERE name = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (name,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to reset LLM failure for {name}: {e}")

    def add_llm_model(self, name, base_url, api_key, model_name, priority=0, input_price_per_m=7.0, output_price_per_m=7.0):
        """
        Registers a new LLM provider model in the database.
        在数据库中注册一个新的大语言模型模型提供商。

        Args:
            name (str): Display name for the model. / 模型的显示名称。
            base_url (str): API base URL. / API 基础 URL。
            api_key (str): Authentication key. / 身份验证密钥。
            model_name (str): The specific model ID (e.g., 'gpt-4'). / 特定模型 ID（例如 'gpt-4'）。
            priority (int): Selection priority (higher is better). / 选择优先级（越高越好）。
            input_price_per_m (float): Input price per million tokens (RMB). / 每百万输入 token 的人民币价格。
            output_price_per_m (float): Output price per million tokens (RMB). / 每百万输出 token 的人民币价格。
        """
        query = """
        INSERT INTO omnidigest.llm_models (id, name, base_url, api_key, model_name, priority, input_price_per_m, output_price_per_m)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """
        model_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (model_id, name, base_url, api_key, model_name, priority, input_price_per_m, output_price_per_m))
                conn.commit()
                return model_id
        except Exception as e:
            logger.error(f"Failed to add LLM model: {e}")
            return None

    # ==========================
    # Token Tracking Methods
    # ==========================

    def record_token_usage(self, service: str, model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0):
        """
        Persists LLM token consumption metrics for a specific service call.
        持久化特定服务调用的模型 token 消耗指标。

        Args:
            service (str): Name of the calling domain/service. / 调用领域/服务的名称。
            model (str): Name of the model used. / 使用的模型名称。
            prompt_tokens (int): Count of input tokens. / 输入 token 数量。
            completion_tokens (int): Count of output tokens. / 输出 token 数量。
            cached_tokens (int): Count of cached tokens (from API response). / 缓存 token 数量（来自 API 响应）。
        """
        query = """
        INSERT INTO omnidigest.token_usage (id, service_name, model_name, prompt_tokens, completion_tokens, cached_tokens)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (str(uuid.uuid4()), service, model, prompt_tokens, completion_tokens, cached_tokens))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to record token usage: {e}")

    def get_token_usage_stats(self, days: int = 30) -> list[dict]:
        """
        Aggregates system-wide token usage statistics over the given number of days, grouped by service and model.
        汇总按服务和模型分组的全系统 token 使用统计数据。
        
        Args:
            days (int): The number of past days to aggregate statistics for. / 聚合统计数据的天数。
            
        Returns:
            list[dict]: Summary of token usage counts. / token 使用计数汇总。
        """
        query = """
        SELECT service_name, model_name,
               CAST(SUM(prompt_tokens) AS INTEGER) as total_prompt,
               CAST(SUM(completion_tokens) AS INTEGER) as total_completion,
               CAST(COUNT(*) AS INTEGER) as total_requests
        FROM omnidigest.token_usage
        WHERE "created_at" >= NOW() - INTERVAL '1 day' * %s
        GROUP BY service_name, model_name
        ORDER BY service_name, model_name
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (days,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to get token usage stats: {e}")
            return []

    # ==========================
    # System Config Methods
    # ==========================

    def get_all_config(self) -> list[dict]:
        """
        Retrieves all system configuration entries.
        获取所有系统配置条目。

        Returns:
            list[dict]: List of config entries as dictionaries. / 配置条目字典列表。
        """
        query = """
        SELECT id, section, key, value, value_type, description, is_editable, "created_at", "updated_at"
        FROM omnidigest.system_config
        ORDER BY section, key
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to get all config: {e}")
            return []

    def get_config_by_section(self, section: str) -> list[dict]:
        """
        Retrieves system configuration entries for a specific section.
        获取指定配置节的系统配置条目。

        Args:
            section (str): The config section name. / 配置节名称。

        Returns:
            list[dict]: List of config entries as dictionaries. / 配置条目字典列表。
        """
        query = """
        SELECT id, section, key, value, value_type, description, is_editable, "created_at", "updated_at"
        FROM omnidigest.system_config
        WHERE section = %s
        ORDER BY key
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (section,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Failed to get config by section: {e}")
            return []

    def get_config(self, section: str, key: str) -> dict | None:
        """
        Retrieves a single system configuration entry.
        获取单个系统配置条目。

        Args:
            section (str): The config section name. / 配置节名称。
            key (str): The config key. / 配置键。

        Returns:
            dict | None: Config entry as dictionary, or None if not found. / 配置条目字典，未找到返回 None。
        """
        query = """
        SELECT id, section, key, value, value_type, description, is_editable, "created_at", "updated_at"
        FROM omnidigest.system_config
        WHERE section = %s AND key = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (section, key))
                    return cur.fetchone()
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            return None

    def set_config(self, section: str, key: str, value: str, value_type: str = "string", description: str = "", is_editable: bool = True) -> bool:
        """
        Creates or updates a system configuration entry.
        创建或更新系统配置条目。

        Args:
            section (str): The config section name. / 配置节名称。
            key (str): The config key. / 配置键。
            value (str): The config value. / 配置值。
            value_type (str): The type of value (string, int, bool, json). / 值类型。
            description (str): Description of this config. / 配置描述。
            is_editable (bool): Whether this config can be edited via API. / 是否可通过 API 编辑。

        Returns:
            bool: True if successful. / 成功返回 True。
        """
        query = """
        INSERT INTO omnidigest.system_config (id, section, key, value, value_type, description, is_editable, "updated_at")
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (section, key) DO UPDATE SET
            value = EXCLUDED.value,
            value_type = EXCLUDED.value_type,
            description = EXCLUDED.description,
            is_editable = EXCLUDED.is_editable,
            "updated_at" = NOW()
        """
        try:
            import uuid
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (str(uuid.uuid4()), section, key, value, value_type, description, is_editable))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to set config: {e}")
            return False

    def delete_config(self, section: str, key: str) -> bool:
        """
        Deletes a system configuration entry.
        删除系统配置条目。

        Args:
            section (str): The config section name. / 配置节名称。
            key (str): The config key. / 配置键。

        Returns:
            bool: True if successful. / 成功返回 True。
        """
        query = """
        DELETE FROM omnidigest.system_config WHERE section = %s AND key = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (section, key))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete config: {e}")
            return False

