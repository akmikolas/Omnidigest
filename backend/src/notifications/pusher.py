"""
Notification pushing service - Facade for backward compatibility.
This module wraps the new NotificationManager while maintaining
the existing API for backward compatibility.

通知推送服务 - 向后兼容的 Facade。
"""
import logging
from pathlib import Path

from .manager import NotificationManager

logger = logging.getLogger(__name__)

# Singleton instance
_manager = None


def _get_manager() -> NotificationManager:
    """Get or create the singleton NotificationManager."""
    global _manager
    if _manager is None:
        _manager = NotificationManager()
    return _manager


class NotificationService:
    """
    Handles sending notifications to external platforms (Telegram, DingTalk).
    This class is now a facade wrapping NotificationManager.

    For new code, prefer using NotificationManager directly:
        manager = NotificationManager()
        await manager.send_event("breaking", data)
    """

    def __init__(self):
        """Initialize the notification service (template loading is now in manager)."""
        # Ensure manager is initialized
        _get_manager()

    @property
    def jinja_env(self):
        """Backward compatible property - delegates to manager."""
        return _get_manager()._jinja_env

    def render_template(self, template_name: str, data: dict) -> str:
        """
        Load and render a Jinja2 template with provided data.

        Args:
            template_name: Name of the template file.
            data: Data dictionary to inject into the template.

        Returns:
            Rendered string.
        """
        return _get_manager().render_template(template_name, data)

    def send_telegram(self, text: str, reply_markup: dict = None, chat_id: str = None):
        """
        Send a formatted HTML message to a Telegram chat.
        Intelligently chunks if it exceeds 4096 characters.

        Args:
            text: HTML-formatted message text.
            reply_markup: Optional inline keyboard.
            chat_id: Target chat ID (uses configured default if not provided).
        """
        return _get_manager().send_telegram(text, reply_markup, chat_id)

    def push_to_dingtalk(self, title: str, summary_data: dict, event_type: str = "daily"):
        """
        Send a Markdown-formatted message to all configured DingTalk robots.

        Args:
            title: Message title.
            summary_data: Dictionary containing article categories.
            event_type: "daily", "breaking", "twitter", etc.
        """
        _get_manager().push_to_dingtalk(title, summary_data, event_type)

    def push_to_telegram(self, summary_data: dict, event_type: str = "daily"):
        """
        Push a rendered summary to all configured Telegram chats.

        Args:
            summary_data: The payload dictionary required by the template.
            event_type: "daily" or "breaking".
        """
        _get_manager().push_to_telegram(summary_data, event_type)

    def push_astock_to_dingtalk(self, title: str, analysis_data: dict,
                                  template: str = "dingtalk_astock_pre_market.md.j2"):
        """
        Send A股 analysis results to all configured DingTalk robots.

        Args:
            title: Message title.
            analysis_data: The A股 analysis result data.
            template: Template to use for rendering.
        """
        import asyncio

        # Render the content
        content = _get_manager().render_template(template, analysis_data)

        # Send to all enabled DingTalk channels
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    _get_manager().send_message(content, channels=["dingtalk"], title=title)
                )
            else:
                loop.run_until_complete(
                    _get_manager().send_message(content, channels=["dingtalk"], title=title)
                )
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                _get_manager().send_message(content, channels=["dingtalk"], title=title)
            )

    @property
    def robots(self):
        """Backward compatible property - returns configured robots."""
        from ..config import settings
        return settings.tg_robots + settings.ding_robots
