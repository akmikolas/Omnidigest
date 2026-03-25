"""
Telegram notification channel implementation.
"""
import asyncio
import re
import logging
from typing import Optional, Dict
from dataclasses import dataclass
import requests

from .base import NotificationChannel, ChannelConfig, SendResult

logger = logging.getLogger(__name__)


@dataclass
class TelegramChannelConfig(ChannelConfig):
    """Configuration for Telegram channel."""
    bot_token: str = ""
    chat_id: str = ""
    parse_mode: str = "HTML"


class TelegramChannel(NotificationChannel):
    """
    Telegram notification channel.

    Supports HTML formatting, automatic chunking for long messages,
    and fallback to plain text on HTML parsing errors.
    """

    def __init__(self, config: TelegramChannelConfig):
        super().__init__(config)
        self._config: TelegramChannelConfig = config
        self._base_url = f"https://api.telegram.org/bot{config.bot_token}"

    @property
    def channel_name(self) -> str:
        return "telegram"

    @property
    def supports_html(self) -> bool:
        return True

    @property
    def max_message_length(self) -> int:
        return 4000  # Leave buffer under 4096 limit

    def format_message(self, content: str, **kwargs) -> str:
        """
        Format HTML content for Telegram by cleaning and converting markdown.
        """
        # Replace <br> variants with newlines
        content = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
        # Convert markdown bold to HTML bold
        content = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', content)
        # Convert markdown underline to HTML underline
        content = re.sub(r'__(.*?)__', r'<u>\1</u>', content)
        return content

    async def send(
        self,
        content: str,
        title: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a message to Telegram.

        Args:
            content: HTML-formatted message content.
            title: Ignored for Telegram (no title in TG messages).
            **kwargs: Additional options including 'reply_markup'.

        Returns:
            SendResult indicating success or failure.
        """
        reply_markup = kwargs.get("reply_markup")

        if not self._config.bot_token or not self._config.chat_id:
            return SendResult(
                success=False,
                channel=self.channel_name,
                error="Telegram credentials missing"
            )

        formatted = self.format_message(content)
        chunks = self.chunk_message(formatted)

        url = f"{self._base_url}/sendMessage"
        parse_mode = self._config.parse_mode if self.supports_html else None

        for i, chunk in enumerate(chunks):
            payload = {
                "chat_id": self._config.chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }

            if reply_markup and i == len(chunks) - 1:
                payload["reply_markup"] = reply_markup

            try:
                # Use run_in_executor to avoid blocking the event loop
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(url, json=payload)
                )
                response.raise_for_status()

                # Try HTML first, on 400 fallback to plain
                if response.status_code == 400:
                    payload.pop("parse_mode")
                    response = await loop.run_in_executor(
                        None,
                        lambda: requests.post(url, json=payload)
                    )
                    response.raise_for_status()

                logger.info(f"Telegram chunk {i + 1}/{len(chunks)} sent.")

            except Exception as e:
                error_msg = str(e)
                if hasattr(e, 'response') and e.response is not None:
                    error_msg += f" | Response: {e.response.text}"

                return SendResult(
                    success=False,
                    channel=self.channel_name,
                    error=error_msg,
                    chunks=len(chunks)
                )

        return SendResult(
            success=True,
            channel=self.channel_name,
            chunks=len(chunks)
        )

    def send_sync(
        self,
        content: str,
        title: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Synchronous send for backward compatibility.
        Handles being called from both sync and async contexts.
        """
        import asyncio
        import concurrent.futures

        try:
            # Try to get the running loop
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None

            if running_loop is not None:
                # We're in an async context - use run_coroutine_threadsafe from a thread pool
                # This avoids the "running loop" issue
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send(content, title, **kwargs)
                    )
                    return future.result()
            else:
                # We're in a sync context - use get_event_loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.send(content, title, **kwargs))
                finally:
                    loop.close()
        except Exception as e:
            logger.error(f"Telegram send_sync failed: {e}")
            return SendResult(
                success=False,
                channel=self.channel_name,
                error=str(e)
            )
