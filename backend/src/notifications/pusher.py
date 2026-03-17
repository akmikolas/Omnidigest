"""
Notification pushing service. Handles formatting and dispatching messages securely to external platforms like Telegram and DingTalk.
通知推送服务。处理格式化并安全地将消息分发到 Telegram 和钉钉等外部平台。
"""
import requests
import hmac
import hashlib
import base64
import time
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Handles sending notifications to external platforms (Telegram, DingTalk).
    处理向外部平台（Telegram, DingTalk）发送通知。
    """
    def __init__(self):
        """
        Initializes the notification service by setting up the Jinja2 template environment.
        通过设置 Jinja2 模板环境来初始化推送服务。
        
        Loads templates from the package templates directory.
        从包模板目录加载模板。
        """
        import jinja2
        from pathlib import Path

        # Resolve the template directory path (relative to this file)
        # 解析模板目录路径（相对于此文件）
        template_dir_path = Path(__file__).resolve().parent.parent / "templates"
        
        # Setup Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir_path)),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )

    def render_template(self, template_name: str, data: dict) -> str:
        """
        Loads the specified Jinja2 template and renders it with the provided data.
        加载指定的 Jinja2 模板并使用提供的数据进行渲染。
        
        Args:
            template_name (str): Name of the template file (e.g. 'telegram_default.html.j2'). / 模板文件的名称（例如 'telegram_default.html.j2'）。
            data (dict): Data dictionary to inject into the template. / 要注入到模板中的数据字典。
            
        Returns:
            str: Rendered string. / 渲染的字符串。
        """
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**data).strip()
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            return f"Error rendering template: {e}"

    def send_telegram(self, text: str, reply_markup: dict = None, chat_id: str = None):
        """
        Sends a formatted HTML message to a Telegram chat, intelligently chunking it if it exceeds the Telegram message length limit (4096 chars).
        向 Telegram 聊天室发送格式化的 HTML 消息，如果超过 Telegram 消息长度限制（4096 个字符），则智能分块。
        
        Args:
            text (str): The HTML-formatted message text to send. / 要发送的 HTML 格式消息文本。
            reply_markup (dict, optional): A dictionary representing an inline keyboard to attach. / 表示要附加的内联键盘的字典。
            chat_id (str, optional): The target chat ID. Defaults to the one in settings. / 目标聊天 ID。默认为设置中的聊天 ID。
            
        Returns:
            None: / 无返回值。
        """
        import re
        # Sanitize HTML for Telegram: Replace <br> variants with newlines
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        # Convert stray markdown bold to HTML bold just in case
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'__(.*?)__', r'<u>\1</u>', text)
        
        # Use provided chat_id, or fall back to the first configured TG robot's chat_id
        target_chat_id = chat_id
        bot_token = None
        if settings.tg_robots:
            if not target_chat_id:
                target_chat_id = settings.tg_robots[0].chat_id
            # Find the robot that matches the target chat_id
            for robot in settings.tg_robots:
                if robot.chat_id == target_chat_id:
                    bot_token = robot.bot_token
                    break
            # Fallback to first robot if no match found
            if not bot_token:
                bot_token = settings.tg_robots[0].bot_token

        if not bot_token or not target_chat_id:
            logger.warning("Telegram credentials missing or chat ID not provided. Please set TG_ROBOTS environment variable.")
            return

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        max_length = 4000
        
        # Smart chunking by lines to avoid breaking HTML tags
        # 按行智能分块，以避免破坏 HTML 标签
        lines = text.split('\n')
        chunks = []
        current_chunk = ""
        
        for line in lines:
            if len(current_chunk) + len(line) + 1 > max_length:
                chunks.append(current_chunk)
                current_chunk = line
            else:
                current_chunk += "\n" + line if current_chunk else line
        if current_chunk:
            chunks.append(current_chunk)

        logger.info(f"Sending Telegram message. Total length: {len(text)}. Chunks: {len(chunks)}")
        
        for i, chunk in enumerate(chunks):
            # Try HTML first
            # 优先尝试 HTML 格式
            payload = {"chat_id": target_chat_id, "text": chunk, "parse_mode": "HTML", "disable_web_page_preview": True}
            
            # Attach reply_markup only to the last chunk
            if reply_markup and i == len(chunks) - 1:
                payload["reply_markup"] = reply_markup
                
            try:
                response = requests.post(url, json=payload)
                response.raise_for_status()
                logger.info(f"Telegram notification chunk {i+1}/{len(chunks)} sent (HTML).")
            except Exception as e:
                # If HTML fails (e.g. invalid tag or arbitrary split), fallback to plain text
                # 如果 HTML 发送失败（例如无效标签或任意分割），回退到纯文本
                error_msg = str(e)
                is_400 = False
                if hasattr(e, 'response') and e.response is not None:
                     error_msg += f" | Response: {e.response.text}"
                     if e.response.status_code == 400:
                         is_400 = True
                
                logger.warning(f"Telegram HTML send failed: {error_msg}. Retrying as plain text...")
                
                if is_400:
                    payload.pop("parse_mode")
                    try:
                        requests.post(url, json=payload).raise_for_status()
                        logger.info(f"Telegram notification chunk {i+1}/{len(chunks)} sent (Plain Text).")
                    except Exception as e2:
                        logger.error(f"Telegram retry failed: {e2}")
                else:
                    logger.error("Non-400 error, not ensuring retry.")

    def push_to_dingtalk(self, title: str, summary_data: dict, event_type: str = "daily"):
        """
        Sends a Markdown-formatted message to all configured DingTalk robots via Webhook based on their configuration.
        根据每个钉钉机器人的配置，通过 Webhook 发送 Markdown 格式的消息。
        
        Args:
            title (str): The title of the Markdown message. / Markdown 消息的标题。
            summary_data (dict): The dictionary containing article categories. / 包含文章类别的字典。
            event_type (str): "daily" or "breaking" to determine which routing to use.
            
        Returns:
            None: / 无返回值。
        """
        robots = settings.ding_robots
        if not robots:
            logger.warning("No DingTalk robots configured in DING_ROBOTS.")
            return

        for robot in robots:
            if event_type == "daily" and robot.enable_daily:
                content = self.render_template(robot.daily_template, summary_data)
                self._send_one_dingtalk(robot.token, robot.secret, title, content)
            elif event_type == "breaking" and robot.enable_breaking:
                content = self.render_template(robot.breaking_template, summary_data)
                self._send_one_dingtalk(robot.token, robot.secret, title, content)
            elif event_type == "twitter" and robot.enable_twitter:
                content = self.render_template(robot.twitter_template, summary_data)
                self._send_one_dingtalk(robot.token, robot.secret, title, content)

    def push_astock_to_dingtalk(self, title: str, analysis_data: dict, template: str = "dingtalk_astock_pre_market.md.j2"):
        """
        Sends A股 analysis results to all configured DingTalk robots.

        Args:
            title (str): The title of the message.
            analysis_data (dict): The A股 analysis result data.
            template (str): The template to use for rendering.

        Returns:
            None.
        """
        robots = settings.ding_robots
        if not robots:
            logger.warning("No DingTalk robots configured in DING_ROBOTS.")
            return

        for robot in robots:
            if getattr(robot, 'enable_astock', True):
                content = self.render_template(template, analysis_data)
                self._send_one_dingtalk(robot.token, robot.secret, title, content)

    def _send_one_dingtalk(self, token: str, secret: str, title: str, content: str):
        """
        Internal helper method to construct the payload, calculate the HMAC signature (if required), and execute the HTTP POST request to a single DingTalk robot API endpoint.
        内部辅助方法，用于构建有效负载、计算 HMAC 签名（如果需要），并执行向单个钉钉机器人 API 端点的 HTTP POST 请求。
        
        Args:
            token (str): The access token for the robot webhook. / 机器人 webhook 的访问令牌。
            secret (str): The signing secret for the robot webhook (can be empty). / 机器人 webhook 的签名密钥（可以为空）。
            title (str): Message title. / 消息标题。
            content (str): Message content. / 消息内容。
        """
        timestamp = str(round(time.time() * 1000))
        url = f"https://oapi.dingtalk.com/robot/send?access_token={token}"
        
        if secret:
            string_to_sign = f'{timestamp}\n{secret}'
            hmac_code = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
            sign = base64.b64encode(hmac_code).decode('utf-8')
            # URL encode the signature
            # 对签名进行 URL 编码
            from urllib.parse import quote_plus
            sign = quote_plus(sign)
            url += f"&timestamp={timestamp}&sign={sign}"

        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title, "text": content}
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            if result.get("errcode") != 0:
                logger.error(f"DingTalk API error for token {token[:6]}...: {result}")
            else:
                logger.info(f"DingTalk notification sent to robot {token[:6]}...")
        except Exception as e:
            logger.error(f"DingTalk push error for token {token[:6]}...: {e}")

    def push_to_telegram(self, summary_data: dict, event_type: str = "daily"):
        """
        Pushes a rendered summary string to all configured Telegram chats.
        将渲染好的摘要字符串推送到所有配置的 Telegram 聊天室。
        
        Args:
            summary_data (dict): The payload dictionary required by the template.
            event_type (str): "daily" or "breaking".
        """
        robots = settings.tg_robots
        if not robots:
            logger.warning("No Telegram robots configured in TG_ROBOTS.")
            return

        for robot in robots:
            if event_type == "daily" and robot.enable_daily:
               content = self.render_template(robot.daily_template, summary_data)
               self.send_telegram(content, chat_id=robot.chat_id)
            elif event_type == "breaking" and robot.enable_breaking:
               content = self.render_template(robot.breaking_template, summary_data)
               self.send_telegram(content, chat_id=robot.chat_id)
            elif event_type == "twitter" and robot.enable_twitter:
               content = self.render_template(robot.twitter_template, summary_data)
               self.send_telegram(content, chat_id=robot.chat_id)
