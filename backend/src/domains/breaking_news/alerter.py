"""
Breaking News Alert Service — Story-level Push with Cross-Verification.
Monitors the `breaking_stories` table for verified, high-impact stories
and pushes them to configured channels (Telegram/DingTalk).
Only pushes stories that have been verified by ≥2 independent sources.
突发新闻警报服务 — 故事线级别推送，带交叉验证。
监控 `breaking_stories` 表中已验证的高影响力故事线，
并推送到配置的频道。仅推送经过 ≥2 个独立信息源验证的故事线。
"""
import logging
import asyncio
from typing import Set
from ...core.database import DatabaseManager
from ...notifications.pusher import NotificationService
from ...config import settings

logger = logging.getLogger(__name__)

class BreakingAlerter:
    """
    Monitors database for verified breaking stories and triggers push.
    Pushes at Story level to prevent duplicate notifications for the same narrative.
    监控数据库中已验证的突发故事线并触发推送。
    以故事线级别推送，防止同一叙事的重复通知。
    """
    def __init__(self, db: DatabaseManager, pusher: NotificationService):
        """
        Initializes the BreakingAlerter with database and notification service.
        使用数据库和通知服务初始化 BreakingAlerter。
        
        Args:
            db (DatabaseManager): Relational database manager. / 关系数据库管理器。
            pusher (NotificationService): Notification service for pushing alerts. / 用于推送警报的通知服务。
        """
        self.db = db
        self.pusher = pusher
        self.notified_stories: Set[str] = set()
        self.threshold = settings.breaking_impact_threshold

    async def check_and_push(self):
        """
        Polls the database for pushable stories: verified + above threshold + not yet pushed
        (or significantly updated since last push).
        轮询数据库中可推送的故事线：已验证 + 超过阈值 + 未推送（或上次推送后有重大更新）。
        """
        try:
            pushable_stories = await asyncio.to_thread(self.db.get_pushable_stories, threshold=self.threshold)

            for story in pushable_stories:
                story_id = str(story['id'])
                peak_score = story.get('peak_score', 0)
                is_update = story.get('pushed', False)

                # Memory cache double-check to avoid re-push within same process lifetime
                cache_key = f"{story_id}:{peak_score}"
                if cache_key in self.notified_stories:
                    continue

                if is_update:
                    logger.info(f"📢 STORY UPDATE ALERT: '{story['story_title']}' (Score: {peak_score}, Sources: {story.get('source_count', 0)})")
                else:
                    logger.info(f"🚨🚨 NEW STORY ALERT: '{story['story_title']}' (Score: {peak_score}, Sources: {story.get('source_count', 0)})")

                await self._push_story_alert(story, is_update=is_update)
                self.notified_stories.add(cache_key)
                # Mark persistent state in DB so restart doesn't resend
                await asyncio.to_thread(self.db.mark_story_pushed, story_id, peak_score)

        except Exception as e:
            logger.error(f"Error checking breaking story alerts: {e}")

    async def _push_story_alert(self, story: dict, is_update: bool = False):
        """
        Formats and sends the story alert to all platforms.
        Includes a timeline of child events for context.
        格式化并将故事线警报发送到所有平台。包含子事件时间线作为上下文。
        """
        # Fetch child events for this story to build a timeline
        story_events = await asyncio.to_thread(self.db.get_story_events, story['id'])

        payload = {
            "story": story,
            "events": story_events,
            "is_update": is_update
        }

        # 1. Telegram Push
        if settings.breaking_push_telegram:
            tg_html = self.pusher.render_template('telegram_breaking.html.j2', payload)
            await asyncio.to_thread(self.pusher.send_telegram, tg_html)

        # 2. DingTalk Push
        if settings.breaking_push_dingtalk:
            prefix = "📢更新" if is_update else "🔴突发"
            title = f"{prefix}: {story['story_title']}"
            await asyncio.to_thread(self.pusher.push_to_dingtalk, title, payload, event_type="breaking")

    async def run_alerter_loop(self, interval_seconds: int = 60):
        """
        Runs a single alert check cycle. Scheduler manages the loop timing.
        运行单次告警检查周期。调度器管理循环时间。
        """
        logger.debug(f"Breaking Alerter check cycle. Threshold: {self.threshold}, Interval: {interval_seconds}s")
        await self.check_and_push()
