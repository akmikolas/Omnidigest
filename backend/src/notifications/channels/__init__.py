"""
Notification channels package.
通知渠道包。
"""
from .base import NotificationChannel, ChannelConfig, SendResult
from .telegram import TelegramChannel, TelegramChannelConfig
from .dingtalk import DingTalkChannel, DingTalkChannelConfig

__all__ = [
    "NotificationChannel",
    "ChannelConfig",
    "SendResult",
    "TelegramChannel",
    "TelegramChannelConfig",
    "DingTalkChannel",
    "DingTalkChannelConfig",
]
