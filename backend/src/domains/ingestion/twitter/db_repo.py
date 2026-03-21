"""
Twitter Ingestion Domain — Data Access & Repository.
Handles persistence for accounts, monitored users, and raw tweet streams.
推特摄取领域 — 数据访问与仓库。
处理账号、监听用户和原始推文流的持久化。
"""
import logging
import uuid
from typing import List, Dict, Optional
from psycopg2.extras import RealDictCursor, Json

logger = logging.getLogger(__name__)

class TwitterDbMixin:
    """
    Database mixin for Twitter ingestion operations.
    用于推特摄取操作的数据库 Mixin。
    """
    
    # --- Account Pool Management ---

    def get_active_twitter_accounts(self) -> List[Dict]:
        """
        Retrieves all active twitter accounts for the session pool.
        Also includes accounts that have cooled down (cooling period expired).
        Automatically releases accounts from cooling when their cooldown period has expired.
        从会话池中检索所有活跃的推特账号。也包括冷却期已过的账号。
        自动释放冷却期已过的账号。
        """
        # First, release accounts that have cooled down
        release_query = """
            UPDATE omnidigest.twitter_accounts
            SET status = 'active', last_error = NULL
            WHERE status = 'cooling' AND cooled_until IS NOT NULL AND cooled_until <= NOW()
        """

        query = """
            SELECT id, username, auth_token, ct0 FROM omnidigest.twitter_accounts
            WHERE status = 'active'
               OR (status = 'cooling' AND (cooled_until IS NULL OR cooled_until <= NOW()))
            ORDER BY fail_count ASC, last_used_at ASC NULLS FIRST
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Release cooled accounts first
                    cur.execute(release_query)
                    conn.commit()
                    # Then fetch available accounts
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching active twitter accounts: {e}")
            return []

    def update_twitter_account_status(self, account_id: str, status: str, error_msg: Optional[str] = None, cooling_minutes: int = 15):
        """
        Updates the status of a twitter account (e.g., cooling, disabled).
        When status is 'cooling', sets cooled_until timestamp.
        更新推特账号状态（例如：冷却中、已禁用）。
        当状态为 'cooling' 时，设置冷却时间戳。
        """
        if status == 'cooling':
            query = """
                UPDATE omnidigest.twitter_accounts
                SET status = %s, last_error = %s, fail_count = fail_count + 1,
                    cooled_until = NOW() + INTERVAL '%s minutes'
                WHERE id = %s
            """
        else:
            query = """
                UPDATE omnidigest.twitter_accounts
                SET status = %s, last_error = %s, fail_count = fail_count + 1,
                    cooled_until = NULL
                WHERE id = %s
            """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    if status == 'cooling':
                        cur.execute(query, (status, error_msg, cooling_minutes, account_id))
                    else:
                        cur.execute(query, (status, error_msg, account_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating twitter account {account_id}: {e}")

    def mark_twitter_account_used(self, account_id: str):
        """
        Updates the last_used_at timestamp for an account.
        更新账号的最后使用时间戳。
        """
        query = "UPDATE omnidigest.twitter_accounts SET last_used_at = NOW(), fail_count = 0 WHERE id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (account_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error marking twitter account {account_id} as used: {e}")

    # --- Monitored Users (Influencers) ---

    def get_monitored_twitter_users(self) -> List[Dict]:
        """
        Retrieves all active monitored Twitter users.
        检索所有活跃的被监听推特用户。
        """
        query = "SELECT rest_id, screen_name, last_seen_tweet_id FROM omnidigest.twitter_monitored_users WHERE is_active = TRUE"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching monitored twitter users: {e}")
            return []

    def update_twitter_high_water_mark(self, rest_id: str, tweet_id: str):
        """
        Updates the last_seen_tweet_id for a monitored user.
        更新被监听用户的最后见到的推文 ID。
        """
        query = "UPDATE omnidigest.twitter_monitored_users SET last_seen_tweet_id = %s WHERE rest_id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (tweet_id, rest_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating water-mark for twitter user {rest_id}: {e}")

    def get_unprocessed_twitter_streams(self, limit: int = 20) -> List[Dict]:
        """
        Retrieves unprocessed raw tweets.
        检索未处理的原始推文。
        """
        query = "SELECT id, tweet_id, author_screen_name, raw_text, is_reply FROM omnidigest.twitter_stream_raw WHERE status = 0 LIMIT %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (limit,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching unprocessed twitter streams: {e}")
            return []

    def update_twitter_stream_triage(self, stream_id: str, status: int, impact_score: int, category: str, summary: str, is_thread_start: bool):
        """
        Updates the triage results for a twitter stream.
        更新推文流的过滤结果。
        """
        query = """
        UPDATE omnidigest.twitter_stream_raw
        SET status = %s, impact_score = %s, category = %s, summary_zh = %s, is_thread_start = %s
        WHERE id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (status, impact_score, category, summary, is_thread_start, stream_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating triage for twitter stream {stream_id}: {e}")

    # --- Raw Stream Management ---

    def add_twitter_stream_raw(self, tweet_id: str, author: str, text: str, is_reply: bool, reply_to: str, metadata: Dict) -> Optional[str]:
        """
        Inserts a raw tweet into the ingestion stream.
        将原始推文插入摄取流。
        """
        query = """
        INSERT INTO omnidigest.twitter_stream_raw (id, tweet_id, author_screen_name, raw_text, is_reply, reply_to_tweet_id, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tweet_id) DO NOTHING
        RETURNING id;
        """
        stream_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (stream_id, tweet_id, author, text, is_reply, reply_to, Json(metadata)))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding twitter stream raw: {e}")
            return None

    # --- Twitter Event Management ---

    def get_recent_twitter_events(self, hours: int = 24) -> List[Dict]:
        """
        Retrieves recent twitter events within the specified hours.
        检索指定小时内的最近推特事件。
        """
        query = """
        SELECT id, event_title, summary, category, peak_score, source_count,
               first_tweet_id, pushed, push_count, last_pushed_at, "created_at", "updated_at"
        FROM omnidigest.twitter_events
        WHERE "created_at" >= NOW() - INTERVAL '%s hours'
        ORDER BY "created_at" DESC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (hours,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching recent twitter events: {e}")
            return []

    def find_similar_twitter_events(self, search_text: str, lookback_minutes: int = 10) -> List[Dict]:
        """
        Finds similar twitter events based on text search within the lookback window.
        在回溯窗口内根据文本搜索查找相似的推特事件。
        Uses simple text similarity - checks if search_text keywords appear in recent events.
        """
        query = """
        SELECT id, event_title, summary, category, peak_score, source_count,
               first_tweet_id, pushed, push_count, last_pushed_at, "created_at", "updated_at"
        FROM omnidigest.twitter_events
        WHERE "created_at" >= NOW() - INTERVAL '%s minutes'
          AND (
            -- Title contains any word from search text (simple matching)
            %s::text ILIKE '%%' || split_part(%s::text, ' ', 1) || '%%'
            OR %s::text ILIKE '%%' || split_part(%s::text, ' ', 2) || '%%'
            OR %s::text ILIKE '%%' || split_part(%s::text, ' ', 3) || '%%'
          )
        ORDER BY peak_score DESC
        LIMIT 5
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Use the first few significant words for matching
                    words = search_text.split()[:3]
                    for i, w in enumerate(words):
                        words[i] = w.strip('.,!?;:')
                    search_pattern = ' '.join(words[:3]) if words else search_text[:50]
                    cur.execute(query, (lookback_minutes, search_pattern, search_pattern, search_pattern, search_pattern, search_pattern, search_pattern))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error finding similar twitter events: {e}")
            return []

    def create_twitter_event(self, title: str, summary: str, category: str, score: int, first_tweet_id: str) -> Optional[str]:
        """
        Creates a new twitter event.
        创建新的推特事件。
        """
        query = """
        INSERT INTO omnidigest.twitter_events (id, event_title, summary, category, peak_score, source_count, first_tweet_id)
        VALUES (%s, %s, %s, %s, %s, 1, %s)
        RETURNING id;
        """
        event_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (event_id, title, summary, category, score, first_tweet_id))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error creating twitter event: {e}")
            return None

    def update_twitter_event(self, event_id: str, title: str = None, summary: str = None, score: int = None) -> bool:
        """
        Updates an existing twitter event.
        更新现有的推特事件。
        """
        updates = []
        params = []

        if title is not None:
            updates.append("event_title = %s")
            params.append(title)
        if summary is not None:
            updates.append("summary = %s")
            params.append(summary)
        if score is not None:
            updates.append("peak_score = GREATEST(peak_score, %s)")
            params.append(score)

        if not updates:
            return False

        updates.append('"updated_at" = NOW()')
        params.append(event_id)

        query = f"UPDATE omnidigest.twitter_events SET {', '.join(updates)} WHERE id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating twitter event {event_id}: {e}")
            return False

    def increment_twitter_event_source_count(self, event_id: str) -> int:
        """
        Increments the source_count for an event and returns the new count.
        增加事件的 source_count 并返回新计数。
        """
        query = """
        UPDATE omnidigest.twitter_events
        SET source_count = source_count + 1, "updated_at" = NOW()
        WHERE id = %s
        RETURNING source_count;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (event_id,))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error incrementing source count for event {event_id}: {e}")
            return 0

    def link_tweet_to_event(self, event_id: str, tweet_id: str, author: str) -> bool:
        """
        Links a tweet to an event.
        将推文链接到事件。
        """
        query = """
        INSERT INTO omnidigest.twitter_event_tweet_mapping (id, event_id, tweet_id, author_screen_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT DO NOTHING;
        """
        mapping_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (mapping_id, event_id, tweet_id, author))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error linking tweet to event: {e}")
            return False

    def get_twitter_event_source_count(self, event_id: str) -> int:
        """
        Gets the source_count for an event.
        获取事件的 source_count。
        """
        query = "SELECT source_count FROM omnidigest.twitter_events WHERE id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (event_id,))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting source count for event {event_id}: {e}")
            return 0

    def mark_twitter_event_pushed(self, event_id: str) -> bool:
        """
        Marks an event as pushed and updates push_count.
        将事件标记为已推送并更新 push_count。
        """
        query = """
        UPDATE omnidigest.twitter_events
        SET pushed = TRUE, push_count = push_count + 1, last_pushed_at = NOW(), "updated_at" = NOW()
        WHERE id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (event_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error marking event {event_id} as pushed: {e}")
            return False

    def get_twitter_event_tweet_sources(self, event_id: str) -> List[Dict]:
        """
        Gets all tweet sources (authors) for an event.
        获取事件的所有推文来源（作者）。
        """
        query = """
        SELECT author_screen_name, COUNT(*) as tweet_count
        FROM omnidigest.twitter_event_tweet_mapping
        WHERE event_id = %s
        GROUP BY author_screen_name
        ORDER BY tweet_count DESC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (event_id,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error getting tweet sources for event {event_id}: {e}")
            return []

    def get_twitter_event_tweet_urls(self, event_id: str, limit: int = 20) -> List[Dict]:
        """
        Gets all tweet URLs and text for an event.
        获取事件的所有推文链接和内容。
        """
        query = """
        SELECT r.tweet_url, r.text
        FROM omnidigest.twitter_event_tweet_mapping m
        JOIN omnidigest.twitter_stream_raw r ON r.tweet_id = m.tweet_id
        WHERE m.event_id = %s
        ORDER BY r."created_at" ASC
        LIMIT %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (event_id, limit))
                    results = cur.fetchall()
                    return [{'url': r['tweet_url'], 'text': r.get('text', '')} for r in results if r.get('tweet_url')]
        except Exception as e:
            logger.error(f"Error getting tweet URLs for event {event_id}: {e}")
            return []

    def get_twitter_event_by_id(self, event_id: str) -> Optional[Dict]:
        """
        Gets a twitter event by ID.
        根据 ID 获取推特事件。
        """
        query = """
        SELECT id, event_title, summary, category, peak_score, source_count,
               first_tweet_id, pushed, push_count, last_pushed_at, "created_at", "updated_at"
        FROM omnidigest.twitter_events
        WHERE id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (event_id,))
                    return cur.fetchone()
        except Exception as e:
            logger.error(f"Error fetching twitter event {event_id}: {e}")
            return None
