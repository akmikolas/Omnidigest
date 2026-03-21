"""
Notification package for OmniDigest.
"""
from .manager import NotificationManager
from .channels import (
    NotificationChannel,
    ChannelConfig,
    SendResult,
    TelegramChannel,
    TelegramChannelConfig,
    DingTalkChannel,
    DingTalkChannelConfig,
)

__all__ = [
    "NotificationManager",
    "NotificationChannel",
    "ChannelConfig",
    "SendResult",
    "TelegramChannel",
    "TelegramChannelConfig",
    "DingTalkChannel",
    "DingTalkChannelConfig",
]
