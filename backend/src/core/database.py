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
from ..config import settings

logger = logging.getLogger(__name__)


from ..domains.daily_digest.db_repo import DailyNewsMixin
from ..domains.ingestion.rss.db_repo import RssSourcesMixin, FastRssSourcesMixin
from ..domains.auth.db_repo import AuthMixin
from ..domains.breaking_news.db_repo import BreakingNewsMixin
from ..domains.ingestion.twitter.db_repo import TwitterDbMixin

class DatabaseManager(DailyNewsMixin, RssSourcesMixin, FastRssSourcesMixin, AuthMixin, BreakingNewsMixin, TwitterDbMixin):
    """
    Manages database interactions for news articles.
    管理新闻文章的数据库交互。
    """
    def __init__(self):
        """
        Initialize the DatabaseManager. Sets the internal pool object to None. Connection is lazily instantiated.
        初始化 DatabaseManager。将内部连接池对象设置为 None。连接是延迟实例化的。
        """
        self._pool = None

    @contextmanager
    def _get_connection(self):
        """
        Retrieves an active PostgreSQL database connection from the pool. If the pool doesn't exist, a new one is created using settings.
        从连接池检索活动的 PostgreSQL 数据库连接。如果池不存在，则使用设置创建一个新池。
        
        Yields:
            psycopg2.extensions.connection: The active database connection object. / 活动的数据库连接对象。
        """
        # Check if the pool is uninitialized
        # 检查池是否未初始化
        if not self._pool:
            self._pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                host=settings.db_host,
                port=settings.db_port,
                user=settings.db_user,
                password=settings.db_password,
                dbname=settings.db_name
            )
            
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def close_all(self):
        """
        Closes all connections in the pool.
        关闭池中的所有连接。
        """
        if self._pool:
            self._pool.closeall()
            self._pool = None

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
                        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
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
                            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,))
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
        Initializes the database schema if tables do not exist. Creates the 'news_articles' and 'rss_sources' tables along with necessary indexes.
        如果表不存在，初始化数据库模式。创建 'news_articles' 和 'rss_sources' 表以及必要的索引。
        """
        query = """
        CREATE TABLE IF NOT EXISTS news_articles (
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
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_news_status ON news_articles(status);
        CREATE INDEX IF NOT EXISTS idx_news_url ON news_articles(source_url);
        CREATE INDEX IF NOT EXISTS idx_news_category ON news_articles(category);
        CREATE INDEX IF NOT EXISTS idx_news_score ON news_articles(score);
        
        CREATE TABLE IF NOT EXISTS rss_sources (
            id UUID PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            name VARCHAR(255),
            enabled BOOLEAN DEFAULT TRUE,
            fail_count INT DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_rss_enabled ON rss_sources(enabled);
        
        -- Breaking News Subsystem Tables
        CREATE TABLE IF NOT EXISTS breaking_rss_sources (
            id UUID PRIMARY KEY,
            url VARCHAR(512) UNIQUE NOT NULL,
            name VARCHAR(100),
            platform VARCHAR(50) NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            fail_count INT DEFAULT 0,
            success_count INT DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_brss_url ON breaking_rss_sources(url);
        CREATE INDEX IF NOT EXISTS idx_brss_enabled ON breaking_rss_sources(enabled);

    CREATE TABLE IF NOT EXISTS breaking_stream_raw (
        id UUID PRIMARY KEY,
        source_platform VARCHAR(100) NOT NULL,
        source_url TEXT UNIQUE NOT NULL,
        raw_text TEXT NOT NULL,
        author VARCHAR(255),
        publish_time TIMESTAMP,
        status SMALLINT DEFAULT 0,
        kg_processed BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_bsr_status ON breaking_stream_raw(status);
    CREATE INDEX IF NOT EXISTS idx_bsr_platform ON breaking_stream_raw(source_platform);
    CREATE INDEX IF NOT EXISTS idx_bsr_pub_time ON breaking_stream_raw(publish_time);
    
    CREATE TABLE IF NOT EXISTS breaking_stories (
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
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_stories_score ON breaking_stories(peak_score);
    CREATE INDEX IF NOT EXISTS idx_stories_status ON breaking_stories(status);

    CREATE TABLE IF NOT EXISTS breaking_events (
        id UUID PRIMARY KEY,
        event_title VARCHAR(512) NOT NULL,
        summary TEXT,
        category VARCHAR(100),
        impact_score INT DEFAULT 0,
        ragflow_id VARCHAR(100),
        pushed BOOLEAN DEFAULT FALSE,
        story_id UUID REFERENCES breaking_stories(id) ON DELETE SET NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_be_score ON breaking_events(impact_score);
    CREATE INDEX IF NOT EXISTS idx_be_cat ON breaking_events(category);
    CREATE INDEX IF NOT EXISTS idx_be_story ON breaking_events(story_id);
    
        CREATE TABLE IF NOT EXISTS event_stream_mapping (
            id UUID PRIMARY KEY,
            event_id UUID REFERENCES breaking_events(id) ON DELETE CASCADE,
            stream_id UUID REFERENCES breaking_stream_raw(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT NOW()
        );

        -- Twitter Ingestion Module Tables
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
        created_at TIMESTAMP DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_esm_event ON event_stream_mapping(event_id);
    CREATE INDEX IF NOT EXISTS idx_esm_stream ON event_stream_mapping(stream_id);

        -- LLM Model Management Table
        CREATE TABLE IF NOT EXISTS llm_models (
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
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_llm_active ON llm_models(is_active);
        CREATE INDEX IF NOT EXISTS idx_llm_priority ON llm_models(priority);

        -- Token Usage Tracking Table
        CREATE TABLE IF NOT EXISTS token_usage (
            id UUID PRIMARY KEY,
            service_name VARCHAR(100) NOT NULL,
            model_name VARCHAR(100) NOT NULL,
            prompt_tokens INT DEFAULT 0,
            completion_tokens INT DEFAULT 0,
            cached_tokens INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_tu_service ON token_usage(service_name);
        CREATE INDEX IF NOT EXISTS idx_tu_model ON token_usage(model_name);
        CREATE INDEX IF NOT EXISTS idx_tu_date ON token_usage(created_at);

        -- System Configuration Table (for dynamic config management)
        CREATE TABLE IF NOT EXISTS system_config (
            id UUID PRIMARY KEY,
            section VARCHAR(50) NOT NULL,
            key VARCHAR(100) NOT NULL,
            value TEXT,
            value_type VARCHAR(20) DEFAULT 'string',
            description VARCHAR(255),
            is_editable BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(section, key)
        );
        CREATE INDEX IF NOT EXISTS idx_sys_config_section ON system_config(section);
        """
        try:
            # Execute the DDL query and commit the transaction
            # 执行 DDL 查询并提交事务
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                conn.commit()
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def create_api_keys_table(self):
        """
        Creates the 'api_keys' table if it does not exist.
        如果 'api_keys' 表不存在则创建它。
        """
        query = """
        CREATE TABLE IF NOT EXISTS api_keys (
            id SERIAL PRIMARY KEY,
            client_name VARCHAR(100) UNIQUE NOT NULL,
            key_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_api_keys_client ON api_keys(client_name);
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
        FROM llm_models
        WHERE is_active = TRUE
        ORDER BY priority DESC, created_at ASC
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
        UPDATE llm_models 
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
                        cur.execute("UPDATE llm_models SET is_active = FALSE WHERE name = %s", (name,))
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
        UPDATE llm_models 
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
        INSERT INTO llm_models (id, name, base_url, api_key, model_name, priority, input_price_per_m, output_price_per_m)
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
        INSERT INTO token_usage (id, service_name, model_name, prompt_tokens, completion_tokens, cached_tokens)
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
        FROM token_usage
        WHERE created_at >= NOW() - INTERVAL '1 day' * %s
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
        SELECT id, section, key, value, value_type, description, is_editable, created_at, updated_at
        FROM system_config
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
        SELECT id, section, key, value, value_type, description, is_editable, created_at, updated_at
        FROM system_config
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
        SELECT id, section, key, value, value_type, description, is_editable, created_at, updated_at
        FROM system_config
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
        INSERT INTO system_config (id, section, key, value, value_type, description, is_editable, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (section, key) DO UPDATE SET
            value = EXCLUDED.value,
            value_type = EXCLUDED.value_type,
            description = EXCLUDED.description,
            is_editable = EXCLUDED.is_editable,
            updated_at = NOW()
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
        DELETE FROM system_config WHERE section = %s AND key = %s
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

