"""
Feishu (飞书) notification channel implementation.
飞书自定义机器人通知渠道实现。
"""
import asyncio
import hmac
import hashlib
import base64
import time
import logging
from typing import Optional
from dataclasses import dataclass
import requests

from .base import NotificationChannel, ChannelConfig, SendResult

logger = logging.getLogger(__name__)


@dataclass
class FeishuChannelConfig(ChannelConfig):
    """Configuration for Feishu channel."""
    webhook_url: str = ""  # Full webhook URL
    secret: str = ""  # HMAC-SHA256 signing secret
    enable_daily: bool = True
    enable_breaking: bool = True
    enable_twitter: bool = True
    enable_astock: bool = True
    daily_template: str = "feishu_default.md.j2"
    breaking_template: str = "feishu_breaking.md.j2"
    twitter_template: str = "feishu_twitter_alert.md.j2"
    astock_template: str = "feishu_astock.md.j2"


class FeishuChannel(NotificationChannel):
    """
    Feishu notification channel (custom robot/webhook).

    Supports signed webhooks and Markdown message format.
    API Docs: https://open.feishu.cn/open-apis/bot/v2/hook/
    """

    def __init__(self, config: FeishuChannelConfig):
        super().__init__(config)
        self._config: FeishuChannelConfig = config
        self._webhook_url = config.webhook_url

    @property
    def channel_name(self) -> str:
        return "feishu"

    @property
    def supports_html(self) -> bool:
        return False  # Feishu uses Markdown

    @property
    def max_message_length(self) -> int:
        return 4000  # Reasonable limit for Markdown

    def _sign(self) -> tuple:
        """
        Generate HMAC-SHA256 signature for Feishu webhook.

        Feishu signature formula:
            sign = Base64(HMAC-SHA256(timestamp + "\n" + secret, secret))

        Note: In Feishu, timestamp is in SECONDS (not milliseconds),
        and the HMAC key is the string_to_sign itself.

        Returns:
            Tuple of (timestamp, sign) strings.
        """
        # Timestamp in SECONDS (not milliseconds)
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{self._config.secret}"

        # HMAC with key=string_to_sign, data="" (empty)
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")

        return timestamp, sign

    async def send(
        self,
        content: str,
        title: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a Markdown message to Feishu.

        Args:
            content: Markdown-formatted message content.
            title: Message title (shown in notification).
            **kwargs: Additional options (unused).

        Returns:
            SendResult indicating success or failure.
        """
        if not self._webhook_url:
            return SendResult(
                success=False,
                channel=self.channel_name,
                error="Feishu webhook_url missing"
            )

        url = self._webhook_url

        # Build payload
        payload = {
            "msg_type": "text",
            "content": {
                "text": content
            }
        }

        # Add signature to body if secret is configured
        # Feishu requires timestamp and sign in the JSON body (not headers)
        if self._config.secret:
            timestamp, sign = self._sign()
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        try:
            # Use run_in_executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=payload, timeout=10)
            )
            response.raise_for_status()
            result = response.json()

            # Feishu returns code=0 for success
            if result.get("code") != 0:
                return SendResult(
                    success=False,
                    channel=self.channel_name,
                    error=f"Feishu API error: code={result.get('code')}, msg={result.get('msg')}",
                    raw_response=result
                )

            logger.info(f"Feishu notification sent successfully")
            return SendResult(success=True, channel=self.channel_name)

        except Exception as e:
            logger.error(f"Feishu push error: {e}")
            return SendResult(
                success=False,
                channel=self.channel_name,
                error=str(e)
            )
