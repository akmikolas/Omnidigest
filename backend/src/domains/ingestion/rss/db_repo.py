"""
Database mixins for RSS feed source management (both standard and fast-lane breaking news).
RSS 订阅源管理的数据库 Mixins（包括标准 RSS 和突发新闻的快速 RSS）。
"""
import logging
import uuid
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class RssSourcesMixin:
    """
    Mixin for managing standard RSS subscription sources in the database.
    在数据库中管理标准 RSS 订阅源的 Mixin。
    """
    def get_rss_sources(self):
        """
        Retrieves all enabled RSS sources from the database.
        从数据库中检索所有已启用 RSS 源。
        """
        query = "SELECT url, name FROM rss_sources WHERE enabled = TRUE"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching RSS sources: {e}")
            return []

    def add_rss_source(self, url, name=None):
        """
        Adds a new RSS source to the database if it doesn't already exist.
        如果尚不存在，将新的 RSS 源添加到数据库。
        """
        query = """
        INSERT INTO rss_sources (id, url, name)
        VALUES (%s, %s, %s)
        ON CONFLICT (url) DO NOTHING
        RETURNING id;
        """
        source_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (source_id, url, name))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding RSS source: {e}")

    def increment_rss_failure(self, url: str, error_msg: str) -> int:
        """
        Increments the fail_count for a given RSS source and records the error. Returns the new fail_count.
        增加给定 RSS 源的 fail_count 并记录错误。返回新的 fail_count。
        """
        query = """
        UPDATE rss_sources 
        SET fail_count = COALESCE(fail_count, 0) + 1, last_error = %s
        WHERE url = %s
        RETURNING fail_count
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (error_msg, url))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if (result and result[0] is not None) else 0
        except Exception as e:
            logger.error(f"Error incrementing RSS failure for {url}: {e}")
            return 0

    def reset_rss_failure(self, url: str):
        """
        Resets the fail_count to 0 and clears the last_error.
        将 fail_count 重置为 0 并清除 last_error。
        """
        query = "UPDATE rss_sources SET fail_count = 0, last_error = NULL WHERE url = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (url,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error resetting RSS failure for {url}: {e}")

    def disable_rss_source(self, url: str):
        """
        Disables an RSS source.
        禁用 RSS 源。
        """
        query = "UPDATE rss_sources SET enabled = FALSE WHERE url = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (url,))
                conn.commit()
            logger.info(f"Successfully disabled RSS source: {url}")
        except Exception as e:
            logger.error(f"Error disabling RSS source {url}: {e}")

    def get_disabled_rss_sources(self):
        """
        Retrieves all disabled RSS sources along with their fail_count and last_error.
        检索所有禁用的 RSS 源以及它们的 fail_count 和 last_error。
        """
        query = "SELECT url, name, fail_count, last_error FROM rss_sources WHERE enabled = FALSE ORDER BY fail_count DESC"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching disabled RSS sources: {e}")
            return []

    def enable_rss_source(self, url: str):
        """
        Manually re-enables an RSS source and resets its fail counters.
        手动重新启用 RSS 源并重置其故障计数器。
        """
        query = "UPDATE rss_sources SET enabled = TRUE, fail_count = 0, last_error = NULL WHERE url = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (url,))
                conn.commit()
            logger.info(f"Successfully re-enabled RSS source: {url}")
        except Exception as e:
            logger.error(f"Error enabling RSS source {url}: {e}")


class FastRssSourcesMixin:
    """
    Mixin for managing high-frequency breaking news RSS sources.
    用于管理高频突发新闻 RSS 源的 Mixin。
    """
    def get_breaking_rss_sources(self):
        """
        Retrieves all enabled breaking RSS sources from the database.
        从数据库中检索所有已启用突发新闻 RSS 源。
        """
        query = "SELECT url, platform FROM breaking_rss_sources WHERE enabled = TRUE"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching breaking RSS sources: {e}")
            return []

    def add_breaking_rss_source(self, url: str, platform: str, name: str = None):
        """
        Adds a new breaking RSS source to the database if it doesn't already exist.
        如果尚不存在，将新的突发新闻 RSS 源添加到数据库。
        """
        query = """
        INSERT INTO breaking_rss_sources (id, url, name, platform)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING
        RETURNING id;
        """
        source_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (source_id, url, name, platform))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding breaking RSS source: {e}")

    def increment_breaking_rss_failure(self, url: str, error_msg: str) -> int:
        """
        Increments the fail_count for a breaking RSS source. If it exceeds 5, it automatically disables it.
        增加突发新闻 RSS 源的 fail_count。如果超过 5 次，则自动禁用它。
        """
        query = """
        UPDATE breaking_rss_sources 
        SET fail_count = COALESCE(fail_count, 0) + 1, last_error = %s
        WHERE url = %s
        RETURNING fail_count
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (error_msg, url))
                    result = cur.fetchone()
                    fail_count = result[0] if (result and result[0] is not None) else 0
                    
                    if fail_count >= 5:
                        cur.execute("UPDATE breaking_rss_sources SET enabled = FALSE WHERE url = %s", (url,))
                        logger.warning(f"Breaking RSS source {url} disabled due to continuous errors.")
                    
                conn.commit()
                return fail_count
        except Exception as e:
            logger.error(f"Error incrementing breaking RSS failure for {url}: {e}")
            return 0

    def increment_breaking_rss_success(self, url: str):
        """
        Increments the success_count for a breaking RSS source and resets fail_count to 0.
        增加突发新闻 RSS 源的 success_count 并将 fail_count 重置为 0。
        """
        query = """
        UPDATE breaking_rss_sources 
        SET success_count = COALESCE(success_count, 0) + 1, fail_count = 0, last_error = NULL
        WHERE url = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (url,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error incrementing breaking RSS success for {url}: {e}")

    def disable_breaking_rss_source(self, url: str):
        """
        Disables a breaking RSS source.
        禁用突发新闻 RSS 源。
        """
        query = "UPDATE breaking_rss_sources SET enabled = FALSE WHERE url = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (url,))
                conn.commit()
            logger.info(f"Successfully disabled breaking RSS source: {url}")
        except Exception as e:
            logger.error(f"Error disabling breaking RSS source {url}: {e}")
