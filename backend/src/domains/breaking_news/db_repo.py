"""
Database mixin for the Breaking News subsystem.
突发新闻子系统的数据库 Mixin。

Provides methods for managing breaking RSS sources, raw stream ingestion,
event creation/clustering, stream-to-event mapping, and alert state tracking.
提供管理突发新闻 RSS 源、原始流摄入、事件创建/聚类、流到事件的映射以及警报状态跟踪的方法。
"""
import logging
import uuid
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class BreakingNewsMixin:
    """
    Mixin for managing high-impact breaking news data in PostgreSQL.
    用于在 PostgreSQL 中管理高影响力突发新闻数据的 Mixin。
    """
    # =========================================================================
    # Breaking News Subsystem Methods
    # 突发新闻子系统方法
    # =========================================================================

    def add_breaking_stream_raw(self, source_platform: str, source_url: str, raw_text: str, author: str = None, publish_time=None):
        """
        Inserts raw incoming stream data into the database.
        将原始的传入流数据插入到数据库中。
        """
        query = """
        INSERT INTO breaking_stream_raw (id, source_platform, source_url, raw_text, author, publish_time)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_url) DO NOTHING
        RETURNING id;
        """
        stream_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (stream_id, source_platform, source_url, raw_text, author, publish_time))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding breaking stream raw: {e}")
            return None

    def get_unprocessed_breaking_streams(self, limit=50):
        """
        Fetches a batch of unclassified breaking streams.
        获取一批未分类的突发新闻流。
        """
        query = """
        SELECT id, source_platform, source_url, raw_text, author, publish_time
        FROM breaking_stream_raw
        WHERE status = 0
        ORDER BY created_at ASC
        LIMIT %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (limit,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching unprocessed breaking streams: {e}")
            return []

    def update_breaking_stream_status(self, stream_id: str, status: int):
        """
        Updates the status of a raw stream item (e.g., 1=processed, 2=ignored).
        更新原始流项目的状态（例如，1=已处理，2=已忽略）。
        """
        query = "UPDATE breaking_stream_raw SET status = %s WHERE id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (status, stream_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating stream status {stream_id}: {e}")

    def create_breaking_event(self, title: str, summary: str, category: str, score: int, ragflow_id: str = None):
        """
        Creates a new finalized breaking event.
        创建一个最终版的突发事件。
        """
        query = """
        INSERT INTO breaking_events (id, event_title, summary, category, impact_score, ragflow_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        """
        event_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (event_id, title, summary, category, score, ragflow_id))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error creating breaking event: {e}")
            return None

    def update_breaking_event(self, event_id: str, title: str, summary: str, score: int, ragflow_id: str = None):
        """
        Updates an existing breaking event details.
        更新现有突发事件的详情。
        """
        query = """
        UPDATE breaking_events 
        SET event_title = %s, summary = %s, impact_score = %s, ragflow_id = COALESCE(%s, ragflow_id), updated_at = NOW()
        WHERE id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (title, summary, score, ragflow_id, event_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating breaking event {event_id}: {e}")

    def get_recent_breaking_events(self, hours: int = 24):
        """
        Retrieves breaking events created or updated recently.
        检索最近创建或更新的突发事件。
        """
        query = """
        SELECT id, event_title, summary, category, impact_score, ragflow_id, updated_at, pushed
        FROM breaking_events
        WHERE updated_at > NOW() - (%s || ' hours')::INTERVAL
        ORDER BY updated_at DESC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (str(hours),))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching recent breaking events: {e}")
            return []

    def mark_breaking_event_pushed(self, event_id: str):
        """
        Marks a breaking event as successfully pushed to notifications.
        将突发事件标记为已成功推送至通知系统。
        """
        query = "UPDATE breaking_events SET pushed = TRUE WHERE id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (event_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error marking event {event_id} as pushed: {e}")

    def get_breaking_event_sources(self, event_id: str):
        """
        Retrieves original sources mapped to a specific breaking event.
        检索映射到特定突发事件的原始信息源。
        """
        query = """
        SELECT DISTINCT r.source_platform AS platform, r.source_url AS url
        FROM event_stream_mapping m
        JOIN breaking_stream_raw r ON m.stream_id = r.id
        WHERE m.event_id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (event_id,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching sources for event {event_id}: {e}")
            return []

    def link_stream_to_event(self, stream_id: str, event_id: str):
        """
        Maps a raw stream item to a consolidated event.
        将原始流条目映射到合并的事件。
        """
        # First check if event exists
        check_query = "SELECT 1 FROM breaking_events WHERE id = %s"
        insert_query = """
        INSERT INTO event_stream_mapping (id, event_id, stream_id)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING;
        """
        mapping_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if event exists before linking
                    cur.execute(check_query, (event_id,))
                    if not cur.fetchone():
                        logger.warning(f"Event {event_id} not found, skipping stream linkage for {stream_id}")
                        return
                    # Link stream to event
                    cur.execute(insert_query, (mapping_id, event_id, stream_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error linking stream {stream_id} to event {event_id}: {e}")

    # =========================================================================
    # Story Timeline Methods (故事线时间线方法)
    # =========================================================================

    def create_story(self, title: str, summary: str, category: str, initial_score: int) -> str:
        """
        Creates a new story (narrative arc) that groups related events.
        创建一个新的故事线（叙事弧线），用于将相关事件分组。
        """
        query = """
        INSERT INTO breaking_stories (id, story_title, story_summary, category, peak_score, source_count)
        VALUES (%s, %s, %s, %s, %s, 1)
        RETURNING id;
        """
        story_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (story_id, title, summary, category, initial_score))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error creating story: {e}")
            return None

    def update_story(self, story_id: str, title: str, summary: str, peak_score: int, source_count: int):
        """
        Updates an existing story's details (title, summary, score, source count).
        更新现有故事线的详情（标题、摘要、分数、信息源数量）。
        """
        query = """
        UPDATE breaking_stories
        SET story_title = %s, story_summary = %s, peak_score = GREATEST(peak_score, %s),
            source_count = %s, updated_at = NOW()
        WHERE id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (title, summary, peak_score, source_count, story_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating story {story_id}: {e}")

    def get_active_stories(self, hours: int = 24):
        """
        Retrieves active stories (not resolved) from the last N hours.
        检索最近 N 小时内的活跃故事线（未结束的）。
        """
        query = """
        SELECT id, story_title, story_summary, category, peak_score, source_count, status, pushed,
               push_count, last_pushed_at, last_pushed_score, created_at, updated_at
        FROM breaking_stories
        WHERE status != 'resolved' AND updated_at > NOW() - (%s || ' hours')::INTERVAL
        ORDER BY updated_at DESC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (str(hours),))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching active stories: {e}")
            return []

    def get_story_source_count(self, story_id: str) -> int:
        """
        Counts distinct source platforms for all streams linked to events in this story.
        统计此故事线下所有事件关联的流的独立信息源平台数量。
        """
        query = """
        SELECT COUNT(DISTINCT r.source_platform) as cnt
        FROM breaking_events e
        JOIN event_stream_mapping m ON m.event_id = e.id
        JOIN breaking_stream_raw r ON r.id = m.stream_id
        WHERE e.story_id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (story_id,))
                    result = cur.fetchone()
                    return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error counting sources for story {story_id}: {e}")
            return 0

    def link_event_to_story(self, event_id: str, story_id: str):
        """
        Links an event to a story by setting its story_id FK.
        通过设置 story_id 外键将事件关联到故事线。
        """
        query = "UPDATE breaking_events SET story_id = %s WHERE id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (story_id, event_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error linking event {event_id} to story {story_id}: {e}")

    def mark_story_pushed(self, story_id: str, score: int):
        """
        Marks a story as pushed and records the push metadata.
        将故事线标记为已推送并记录推送元数据。
        """
        query = """
        UPDATE breaking_stories
        SET pushed = TRUE, push_count = push_count + 1,
            last_pushed_at = NOW(), last_pushed_score = %s, status = 'verified'
        WHERE id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (score, story_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error marking story {story_id} as pushed: {e}")

    def update_story_verification(self, story_id: str, source_count: int):
        """
        Updates story verification status based on source count.
        根据信息源数量更新故事线的验证状态。
        """
        status = 'verified' if source_count >= 2 else 'developing'
        query = """
        UPDATE breaking_stories
        SET source_count = %s, status = CASE WHEN status = 'resolved' THEN 'resolved' ELSE %s END,
            updated_at = NOW()
        WHERE id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (source_count, status, story_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating story verification {story_id}: {e}")

    def get_pushable_stories(self, threshold: int = 80):
        """
        Retrieves stories that are eligible for push: verified + peak_score >= threshold +
        either never pushed, or significantly updated since last push.
        Joins with the latest event to provide a primary source URL.
        获取可推送的故事线：已验证 + peak_score >= 阈值 + 未推送或上次推送后有重大更新。关联最新事件以获取主信息源 URL。
        """
        query = """
        SELECT DISTINCT ON (s.id) s.id, s.story_title, s.story_summary, s.category, s.peak_score, s.source_count,
               s.status, s.pushed, s.push_count, s.last_pushed_at, s.last_pushed_score, s.created_at, s.updated_at,
               r.source_url
        FROM breaking_stories s
        LEFT JOIN breaking_events e ON s.id = e.story_id
        LEFT JOIN event_stream_mapping m ON e.id = m.event_id
        LEFT JOIN breaking_stream_raw r ON m.stream_id = r.id
        WHERE s.status = 'verified' AND s.peak_score >= %s
          AND (s.pushed = FALSE OR (s.peak_score - s.last_pushed_score >= 10 AND s.updated_at > s.last_pushed_at))
        ORDER BY s.id, r.created_at DESC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (threshold,))
                    results = cur.fetchall()
                    # Re-sort by score since DISTINCT ON requires sorting by its key first
                    results.sort(key=lambda x: x['peak_score'], reverse=True)
                    return results
        except Exception as e:
            logger.error(f"Error fetching pushable stories: {e}")
            return []

    def get_story_events(self, story_id: str):
        """
        Retrieves all events belonging to a story, ordered by creation time.
        Includes a source URL for each event.
        获取属于某个故事线的所有事件，按创建时间排序。包含每个事件的信息源 URL。
        """
        query = """
        SELECT DISTINCT ON (e.id) e.id, e.event_title, e.summary, e.category, e.impact_score, e.created_at, e.updated_at,
               r.source_url
        FROM breaking_events e
        LEFT JOIN event_stream_mapping m ON e.id = m.event_id
        LEFT JOIN breaking_stream_raw r ON m.stream_id = r.id
        WHERE e.story_id = %s
        ORDER BY e.id, r.created_at ASC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (story_id,))
                    results = cur.fetchall()
                    # Re-sort by creation time
                    results.sort(key=lambda x: x['created_at'])
                    return results
        except Exception as e:
            logger.error(f"Error fetching events for story {story_id}: {e}")
            return []

    def get_events_without_story(self, hours: int = 24):
        """
        Retrieves recent breaking events that are not yet linked to any story.
        检索尚未关联任何故事线的近期突发新闻事件。
        """
        query = """
        SELECT id, event_title, summary, category, impact_score
        FROM breaking_events
        WHERE story_id IS NULL AND created_at > NOW() - (INTERVAL '1 hour' * %s)
        ORDER BY created_at ASC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (hours,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching events without story: {e}")
            return []
