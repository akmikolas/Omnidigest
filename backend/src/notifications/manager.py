"""
Notification Manager - unified interface for all notification channels.
"""
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .channels.base import NotificationChannel, SendResult
from .channels.telegram import TelegramChannel, TelegramChannelConfig
from .channels.dingtalk import DingTalkChannel, DingTalkChannelConfig
from ..config import settings

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Unified notification manager that handles all channels.

    Usage:
        manager = NotificationManager()
        await manager.send_event("breaking", story_data)

        # Or send to specific channels
        await manager.send_event("daily", data, channels=["telegram", "dingtalk"])
    """

    def __init__(self):
        self._channels: Dict[str, NotificationChannel] = {}
        self._jinja_env = None
        self._init_jinja()
        self._init_channels()

    def _init_jinja(self):
        """Initialize Jinja2 template engine."""
        import jinja2
        template_dir_path = Path(__file__).resolve().parent.parent / "templates"

        self._jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir_path)),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )

    def _init_channels(self):
        """Initialize all configured channels."""
        # Telegram channels
        for i, robot in enumerate(settings.tg_robots):
            if robot.bot_token and robot.chat_id:
                key = f"telegram_{i}" if len(settings.tg_robots) > 1 else "telegram"
                config = TelegramChannelConfig(
                    bot_token=robot.bot_token,
                    chat_id=robot.chat_id,
                    enable_daily=robot.enable_daily,
                    enable_breaking=robot.enable_breaking,
                    enable_twitter=robot.enable_twitter,
                    enable_astock=robot.enable_astock,
                    daily_template=robot.daily_template,
                    breaking_template=robot.breaking_template,
                    twitter_template=robot.twitter_template,
                    astock_template=robot.astock_template,
                )
                self._channels[key] = TelegramChannel(config)

        # DingTalk channels
        for i, robot in enumerate(settings.ding_robots):
            if robot.token:
                key = f"dingtalk_{i}" if len(settings.ding_robots) > 1 else "dingtalk"
                config = DingTalkChannelConfig(
                    token=robot.token,
                    secret=robot.secret,
                    keyword=robot.keyword,
                    enable_daily=robot.enable_daily,
                    enable_breaking=robot.enable_breaking,
                    enable_twitter=robot.enable_twitter,
                    enable_astock=robot.enable_astock,
                    daily_template=robot.daily_template,
                    breaking_template=robot.breaking_template,
                    twitter_template=robot.twitter_template,
                    astock_template=robot.astock_template,
                )
                self._channels[key] = DingTalkChannel(config)

        logger.info(f"Initialized {len(self._channels)} notification channels")

    def render_template(self, template_name: str, data: dict) -> str:
        """
        Render a Jinja2 template with provided data.

        Args:
            template_name: Template filename (e.g., 'telegram_default.html.j2').
            data: Dictionary of data to inject into template.

        Returns:
            Rendered string.
        """
        try:
            template = self._jinja_env.get_template(template_name)
            return template.render(**data).strip()
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            return f"Error rendering template: {e}"

    def get_template_for_channel(
        self,
        channel: NotificationChannel,
        event_type: str
    ) -> str:
        """
        Get the appropriate template name for a channel and event type.
        """
        template_attr = f"{event_type}_template"
        if hasattr(channel.config, template_attr):
            return getattr(channel.config, template_attr)

        # Default templates by channel type
        defaults = {
            "telegram": {
                "daily": "telegram_default.html.j2",
                "breaking": "telegram_breaking.html.j2",
                "twitter": "telegram_twitter_alert.html.j2",
                "astock": "telegram_astock_pre_market.html.j2",
            },
            "dingtalk": {
                "daily": "dingtalk_default.md.j2",
                "breaking": "dingtalk_breaking.md.j2",
                "twitter": "dingtalk_twitter_alert.md.j2",
                "astock": "dingtalk_astock_pre_market.md.j2",
            },
        }

        return defaults.get(channel.channel_name, {}).get(
            event_type,
            f"{channel.channel_name}_{event_type}.j2"
        )

    async def send_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        channels: Optional[List[str]] = None,
        title: Optional[str] = None,
        **kwargs
    ) -> Dict[str, SendResult]:
        """
        Send a notification event to configured channels.

        Args:
            event_type: Event type ('daily', 'breaking', 'twitter', 'astock').
            data: Event data for template rendering.
            channels: List of channel keys to use (None = all enabled).
            title: Message title.
            **kwargs: Additional options passed to channels.

        Returns:
            Dictionary mapping channel keys to SendResults.
        """
        results = {}

        # Get channels that have this event type enabled
        target_channels = self._get_enabled_channels(event_type, channels)

        for key, channel in target_channels.items():
            # Get template for this channel
            template_name = self.get_template_for_channel(channel, event_type)

            # Render content
            content = self.render_template(template_name, data)

            # Send
            try:
                result = await channel.send(content, title=title, **kwargs)
                results[key] = result

                if result.success:
                    logger.info(f"Event {event_type} sent via {key}")
                else:
                    logger.error(f"Event {event_type} failed via {key}: {result.error}")

            except Exception as e:
                logger.error(f"Channel {key} error: {e}")
                results[key] = SendResult(
                    success=False,
                    channel=key,
                    error=str(e)
                )

        return results

    async def send_message(
        self,
        content: str,
        channels: Optional[List[str]] = None,
        title: Optional[str] = None,
        **kwargs
    ) -> Dict[str, SendResult]:
        """
        Send pre-rendered message content to channels.

        Args:
            content: Pre-rendered message content.
            channels: List of channel keys (None = all).
            title: Message title.
            **kwargs: Additional options.

        Returns:
            Dictionary of results by channel key.
        """
        results = {}
        target_keys = channels or list(self._channels.keys())

        for key in target_keys:
            if key not in self._channels:
                continue

            channel = self._channels[key]
            try:
                result = await channel.send(content, title=title, **kwargs)
                results[key] = result
            except Exception as e:
                logger.error(f"Channel {key} error: {e}")
                results[key] = SendResult(
                    success=False,
                    channel=key,
                    error=str(e)
                )

        return results

    def _get_enabled_channels(
        self,
        event_type: str,
        specific_channels: Optional[List[str]] = None
    ) -> Dict[str, NotificationChannel]:
        """Get channels that have the given event type enabled."""
        enabled = {}

        for key, channel in self._channels.items():
            # Filter to specific channels if provided
            if specific_channels and key not in specific_channels:
                continue

            # Check if this event type is enabled
            if channel.is_event_enabled(event_type):
                enabled[key] = channel

        return enabled

    @property
    def channels(self) -> Dict[str, NotificationChannel]:
        """Get all registered channels."""
        return self._channels

    # ==================== Backward Compatibility API ====================

    def send_telegram(self, text: str, reply_markup: dict = None, chat_id: str = None):
        """
        Backward compatible Telegram send.
        Finds the first Telegram channel and sends synchronously.
        """
        for key, channel in self._channels.items():
            if isinstance(channel, TelegramChannel):
                if chat_id is None or channel.config.chat_id == chat_id:
                    return channel.send_sync(text, reply_markup=reply_markup)

        logger.warning("No matching Telegram channel found")
        return SendResult(success=False, channel="telegram", error="No channel found")

    def push_to_dingtalk(self, title: str, summary_data: dict, event_type: str = "daily"):
        """
        Backward compatible DingTalk send.
        Works when called from both sync and async contexts.
        """
        import asyncio
        import concurrent.futures

        target_channels = self._get_enabled_channels(event_type)

        if not target_channels:
            logger.warning(f"No DingTalk channels enabled for {event_type}")
            return

        try:
            # Check if we're in an async context
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None

            if running_loop is not None:
                # We're in an async context - use threadsafe approach
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_event(event_type, summary_data, channels=["dingtalk"], title=title)
                    )
                    future.result()
            else:
                # We're in a sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.send_event(event_type, summary_data, channels=["dingtalk"], title=title))
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Error in push_to_dingtalk: {e}")

    def push_to_telegram(self, summary_data: dict, event_type: str = "daily"):
        """
        Backward compatible Telegram push.
        Works when called from both sync and async contexts.
        """
        import asyncio
        import concurrent.futures

        target_channels = self._get_enabled_channels(event_type)

        if not target_channels:
            logger.warning(f"No Telegram channels enabled for {event_type}")
            return

        try:
            # Check if we're in an async context
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None

            if running_loop is not None:
                # We're in an async context - use threadsafe approach
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_event(event_type, summary_data)
                    )
                    future.result()
            else:
                # We're in a sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.send_event(event_type, summary_data))
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Error in push_to_telegram: {e}")
