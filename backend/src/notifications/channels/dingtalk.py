"""
DingTalk (钉钉) notification channel implementation.
"""
import asyncio
import hmac
import hashlib
import base64
import time
import logging
from typing import Optional
from dataclasses import dataclass
from urllib.parse import quote_plus
import requests

from .base import NotificationChannel, ChannelConfig, SendResult

logger = logging.getLogger(__name__)


@dataclass
class DingTalkChannelConfig(ChannelConfig):
    """Configuration for DingTalk channel."""
    token: str = ""
    secret: str = ""  # HMAC-SHA256 signing secret
    keyword: str = ""  # Security keyword that must appear in message content


class DingTalkChannel(NotificationChannel):
    """
    DingTalk notification channel.

    Supports HMAC-SHA256 signed webhooks and Markdown message format.
    """

    def __init__(self, config: DingTalkChannelConfig):
        super().__init__(config)
        self._config: DingTalkChannelConfig = config
        self._webhook_url = f"https://oapi.dingtalk.com/robot/send?access_token={config.token}"

    @property
    def channel_name(self) -> str:
        return "dingtalk"

    @property
    def supports_html(self) -> bool:
        return False  # DingTalk uses Markdown

    @property
    def max_message_length(self) -> int:
        return 4000  # Reasonable limit for Markdown

    def _sign(self) -> tuple:
        """
        Generate HMAC-SHA256 signature for DingTalk webhook.

        Returns:
            Tuple of (timestamp, sign) strings.
        """
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f'{timestamp}\n{self._config.secret}'

        hmac_code = hmac.new(
            self._config.secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = quote_plus(base64.b64encode(hmac_code).decode('utf-8'))

        return timestamp, sign

    async def send(
        self,
        content: str,
        title: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a Markdown message to DingTalk.

        Args:
            content: Markdown-formatted message content.
            title: Message title (shown in notification).
            **kwargs: Additional options (unused).

        Returns:
            SendResult indicating success or failure.
        """
        if not self._config.token:
            return SendResult(
                success=False,
                channel=self.channel_name,
                error="DingTalk token missing"
            )

        url = self._webhook_url
        if self._config.secret:
            timestamp, sign = self._sign()
            url += f"&timestamp={timestamp}&sign={sign}"

        # Prepend keyword if configured (DingTalk security requirement)
        if self._config.keyword:
            content = f"{self._config.keyword}\n\n{content}"

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title or "OmniDigest Notification",
                "text": content
            }
        }

        try:
            # Use run_in_executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=payload)
            )
            response.raise_for_status()
            result = response.json()

            if result.get("errcode") != 0:
                return SendResult(
                    success=False,
                    channel=self.channel_name,
                    error=f"DingTalk API error: {result.get('errmsg')}",
                    raw_response=result
                )

            logger.info(f"DingTalk notification sent to robot {self._config.token[:6]}...")
            return SendResult(success=True, channel=self.channel_name)

        except Exception as e:
            logger.error(f"DingTalk push error: {e}")
            return SendResult(
                success=False,
                channel=self.channel_name,
                error=str(e)
            )
