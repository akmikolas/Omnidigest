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
import re
from typing import Optional, List, Dict, Any
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

    Supports signed webhooks and Feishu post/rich text message format.
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
        return False  # Feishu uses post format

    @property
    def max_message_length(self) -> int:
        return 4000  # Reasonable limit

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
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{self._config.secret}"

        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")

        return timestamp, sign

    def _parse_markdown_to_post(self, content: str, title: str = "") -> Dict[str, Any]:
        """
        Parse markdown-like content to Feishu post format.

        Supports:
        - **bold** or <b>bold</b> for bold text
        - [text](url) for links
        - # heading for titles (first one used)
        - --- for dividers (translated to empty lines)
        - Regular text lines

        Returns:
            Feishu post message structure.
        """
        paragraphs: List[List[Dict]] = []
        first_heading = title

        # Split content into lines but preserve structure
        lines = content.strip().split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line == "---":
                # Empty line or divider - add spacing paragraph
                paragraphs.append([{"tag": "text", "text": " "}])
                i += 1
                continue

            # Skip mermaid/flowchart code blocks
            if line.startswith("```"):
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    i += 1
                i += 1
                continue

            # Parse line into paragraph with tags
            paragraph = self._parse_line_to_tags(line)
            if paragraph:
                paragraphs.append(paragraph)

            i += 1

        # Build post structure
        post_content: Dict[str, Any] = {
            "post": {
                "zh_cn": {
                    "title": first_heading or "OmniDigest 通知",
                    "content": paragraphs
                }
            }
        }

        return post_content

    def _parse_line_to_tags(self, line: str) -> List[Dict]:
        """
        Parse a single line of markdown-like content into Feishu tags.

        Handles:
        - **bold** or <b>bold</b>
        - [text](url)
        - Regular text (may contain **bold** inline)

        Returns:
            List of Feishu tag objects.
        """
        tags: List[Dict] = []

        # Handle inline markdown: **bold** and [text](url)
        # Pattern: markdown link [text](url) or bold **text**

        # First, process all inline elements
        # Pattern for links: [text](url)
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'

        # Pattern for bold: **text** or <b>text</b>
        bold_pattern = r'\*\*([^*]+)\*\*|<b>([^<]+)</b>'

        # We'll use a combined approach: split by special markers
        combined_pattern = r'(\*\*[^*]+\*\*|<b>[^<]+</b>|\[[^\]]+\]\([^)]+\))'
        parts = re.split(combined_pattern, line)

        for part in parts:
            if not part:
                continue

            # Check if it's a bold part
            bold_match = re.match(r'\*\*([^*]+)\*\*$', part) or re.match(r'<b>([^<]+)</b>$', part)
            if bold_match:
                text = bold_match.group(1)
                tags.append({"tag": "text", "text": text, "bold": True})
                continue

            # Check if it's a link
            link_match = re.match(r'\[([^\]]+)\]\(([^)]+)\)$', part)
            if link_match:
                text, href = link_match.groups()
                tags.append({"tag": "a", "text": text, "href": href})
                continue

            # Check if it's a standalone URL (without markdown link format)
            if part.startswith("http://") or part.startswith("https://"):
                tags.append({"tag": "a", "text": part, "href": part})
                continue

            # Regular text
            if part.strip():
                tags.append({"tag": "text", "text": part})

        return tags if tags else [{"tag": "text", "text": line}]

    async def send(
        self,
        content: str,
        title: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a rich text (post) message to Feishu.

        Args:
            content: Markdown-formatted message content.
            title: Message title.
            **kwargs: Additional options.

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

        # Build post (rich text) payload
        post_content = self._parse_markdown_to_post(content, title or "")

        payload = {
            "msg_type": "post",
            "content": post_content
        }

        # Add signature to body if secret is configured
        if self._config.secret:
            timestamp, sign = self._sign()
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, json=payload, timeout=10)
            )
            response.raise_for_status()
            result = response.json()

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
