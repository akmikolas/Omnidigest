"""
Notification channel base classes and interfaces.
通知渠道抽象基类和接口。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class ChannelConfig:
    """Base configuration for notification channels."""
    enabled: bool = True
    enable_daily: bool = True
    enable_breaking: bool = True
    enable_twitter: bool = True
    enable_astock: bool = True
    daily_template: str = "default"
    breaking_template: str = "breaking"
    twitter_template: str = "twitter_alert"
    astock_template: str = "astock"


@dataclass
class SendResult:
    """Result of a send operation."""
    success: bool
    channel: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    chunks: int = 1
    raw_response: Optional[Dict[str, Any]] = None


class NotificationChannel(ABC):
    """
    Abstract base class for notification channels.
    All channel implementations must inherit from this class.
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Channel identifier (e.g., 'telegram', 'dingtalk')."""
        pass

    @property
    def supports_html(self) -> bool:
        """Whether the channel supports HTML formatting."""
        return False

    @property
    def max_message_length(self) -> int:
        """Maximum message length in characters."""
        return 4096

    @property
    def config(self) -> ChannelConfig:
        """Channel configuration."""
        return self._config

    def __init__(self, config: ChannelConfig):
        self._config = config

    @abstractmethod
    async def send(
        self,
        content: str,
        title: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a message through the channel.

        Args:
            content: Message content.
            title: Optional message title (for channels that need it).
            **kwargs: Additional channel-specific parameters.

        Returns:
            SendResult with success status and details.
        """
        pass

    def format_message(self, content: str, **kwargs) -> str:
        """
        Format message content for the channel.
        Subclasses can override to perform channel-specific formatting.
        """
        return content

    def chunk_message(self, content: str) -> List[str]:
        """
        Split long messages into chunks that fit within the channel's limits.
        Default implementation splits by lines to avoid breaking formatting.
        """
        if len(content) <= self.max_message_length:
            return [content]

        lines = content.split('\n')
        chunks = []
        current = ""

        for line in lines:
            if len(current) + len(line) + 1 > self.max_message_length:
                chunks.append(current)
                current = line
            else:
                current += "\n" + line if current else line

        if current:
            chunks.append(current)

        return chunks

    def is_event_enabled(self, event_type: str) -> bool:
        """
        Check if a specific event type is enabled for this channel.

        Args:
            event_type: One of 'daily', 'breaking', 'twitter', 'astock'

        Returns:
            True if the event type is enabled.
        """
        if not self._config.enabled:
            return False

        flag_map = {
            "daily": "enable_daily",
            "breaking": "enable_breaking",
            "twitter": "enable_twitter",
            "astock": "enable_astock",
        }

        flag = flag_map.get(event_type)
        if flag and hasattr(self._config, flag):
            return getattr(self._config, flag)

        return True
