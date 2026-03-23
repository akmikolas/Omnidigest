"""
Twitter Intelligence Domain — Alerter.
Handles real-time notifications for aggregated Twitter events.
推特智能领域 — 警报器。
处理聚合推特事件的实时通知。
"""
import logging
from typing import Dict
from ...notifications.pusher import NotificationService
from ...config import settings

logger = logging.getLogger(__name__)

class TwitterAlerter:
    """
    Service for pushing aggregated Twitter event alerts.
    用于推送聚合推特事件警报的服务。
    """

    def __init__(self, notifier: NotificationService = None):
        """
        Initializes the TwitterAlerter.
        初始化 TwitterAlerter。
        """
        self.notifier = notifier or NotificationService()

    def push_alert(self, event_data: Dict):
        """
        Sends a Twitter event alert to configured Telegram and DingTalk robots.
        将推特事件警报发送到配置的 Telegram 和钉钉机器人。

        Args:
            event_data (Dict): Dictionary containing event metadata (event_title, summary, source_count, sources, etc.)
        """
        event_title = event_data.get('event_title', 'Unknown Event')
        source_count = event_data.get('source_count', 0)
        category = event_data.get('category', 'Unknown')
        summary = event_data.get('summary', '')
        sources = event_data.get('sources', [])
        tweet_data = event_data.get('tweet_urls', [])  # List of dicts: {'url': ..., 'text': ...}

        # Format sources list
        source_list = [s['author_screen_name'] for s in sources]
        sources_str = ', '.join([f"@{s}" for s in source_list]) if source_list else 'Unknown'

        # Format tweet URLs with titles, limit to first 5
        tweet_urls_list = []
        for i, item in enumerate(tweet_data[:5]):  # Limit to first 5
            if isinstance(item, dict):
                url = item.get('tweet_url', '')
                text = item.get('text', '')[:50]  # Truncate text for display
                if text and url:
                    tweet_urls_list.append(f"{text}...|{url}")
                elif url:
                    tweet_urls_list.append(url)
            else:
                tweet_urls_list.append(str(item))
        tweet_urls_str = '\n'.join(tweet_urls_list) if tweet_urls_list else ''

        title = f"🔴 [新闻] 推特事件聚合: {source_count}个来源报道 (分类: {category})"
        payload = {
            "event": {
                "event_title": event_title,
                "summary": summary,
                "category": category,
                "source_count": source_count,
                "sources": sources_str,
                "tweet_urls": tweet_urls_str,
                "first_tweet_id": event_data.get('first_tweet_id'),
                "push_count": event_data.get('push_count', 0),
                "created_at": str(event_data.get('created_at', ''))
            }
        }

        logger.info(f"Triggering event alert: {event_title} (Sources: {source_count})")

        # Push to Telegram
        if settings.twitter_push_telegram:
            try:
                self.notifier.push_to_telegram(payload, event_type="twitter")
            except Exception as e:
                logger.error(f"Failed to push Twitter event alert to Telegram: {e}")

        # Push to DingTalk
        if settings.twitter_push_dingtalk:
            try:
                self.notifier.push_to_dingtalk(title, payload, event_type="twitter")
            except Exception as e:
                logger.error(f"Failed to push Twitter event alert to DingTalk: {e}")
