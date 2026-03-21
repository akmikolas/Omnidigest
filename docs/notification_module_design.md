# OmniDigest 通知模块架构设计

## 概述

OmniDigest 通知模块负责将各类事件（突发新闻、Twitter 动态、每日摘要、A股告警）推送到用户配置的渠道（目前支持 Telegram、钉钉）。

当前问题：通知逻辑与渠道实现紧耦合，添加新渠道需要修改核心类。

## 目标架构

### 设计原则

1. **接口隔离** - 定义 `NotificationChannel` 抽象接口
2. **配置统一** - 统一渠道配置模型
3. **向后兼容** - 保留现有 API，渐进式迁移
4. **可扩展** - 新增渠道只需实现接口，无需修改核心代码

### 类图

```
┌─────────────────────────────────────────────────────────────┐
│                     NotificationManager                      │
│  (Facade, 保持向后兼容)                                      │
├─────────────────────────────────────────────────────────────┤
│  - channels: Dict[str, NotificationChannel]                 │
│  - template_engine: Jinja2                                  │
│  + send_event(event_type, data, channels) -> Dict          │
│  + render_template(template_name, data) -> str            │
│  + send_to_channel(channel, content, **kwargs) -> Result  │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ TelegramChannel │  │  DingTalkChannel│  │  WeChatChannel  │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ - bot_token     │  │ - token        │  │ - webhook_url   │
│ - chat_id       │  │ - secret       │  │ - secret        │
│ - parse_mode    │  │ + sign()       │  │ + send_markdown │
│ + send()       │  │ + send()       │  │ + send_text()   │
│ + chunk()      │  │                │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                              │                   │
                              └─────────┬─────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │     NotificationChannel       │
                        │     (ABC)                     │
                        ├──────────────────────────────┤
                        │ + channel_name: str          │
                        │ + supports_html: bool         │
                        │ + max_message_length: int     │
                        │ + send(content, **kwargs)     │
                        │   -> SendResult               │
                        │ + format_message(content)     │
                        │ + chunk_message(content)      │
                        └──────────────────────────────┘
```

## 核心接口

### NotificationChannel (ABC)

```python
class NotificationChannel(ABC):
    """通知渠道抽象基类"""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """渠道名称 (如 'telegram', 'dingtalk', 'wechat')"""
        pass

    @property
    def supports_html(self) -> bool:
        """是否支持 HTML 格式，默认 False"""
        return False

    @property
    def max_message_length(self) -> int:
        """单条消息最大长度，默认 4096"""
        return 4096

    @abstractmethod
    async def send(
        self,
        content: str,
        title: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        发送消息

        Args:
            content: 消息内容
            title: 标题 (部分渠道需要)
            **kwargs: 额外参数 (reply_markup, at_users 等)

        Returns:
            SendResult: 发送结果
        """
        pass

    def format_message(self, content: str, **kwargs) -> str:
        """格式化消息，子类可覆盖"""
        return content

    def chunk_message(self, content: str) -> List[str]:
        """分割长消息，默认按行分割"""
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
```

### SendResult

```python
@dataclass
class SendResult:
    """发送结果"""
    success: bool
    channel: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    chunks: int = 1
    raw_response: Optional[Dict] = None
```

### ChannelConfig

```python
@dataclass
class ChannelConfig:
    """渠道配置基类"""
    enabled: bool = True
    enable_daily: bool = True
    enable_breaking: bool = True
    enable_twitter: bool = True
    enable_astock: bool = True
    daily_template: str = "default"
    breaking_template: str = "breaking"
    twitter_template: str = "twitter_alert"
    astock_template: str = "astock"
```

## 渠道实现

### TelegramChannel

**配置**:
```python
class TelegramChannelConfig(ChannelConfig):
    bot_token: str = ""
    chat_id: str = ""
    parse_mode: str = "HTML"  # HTML, Markdown, Plain
```

**特性**:
- 支持 HTML 格式解析
- 消息超过 4096 字符自动分块
- HTML 发送失败时自动降级为纯文本

### DingTalkChannel

**配置**:
```python
class DingTalkChannelConfig(ChannelConfig):
    token: str = ""
    secret: str = ""  # HMAC-SHA256 签名密钥
```

**特性**:
- 支持 HMAC-SHA256 签名认证
- Markdown 消息格式
- 自动重试机制

### WeChatChannel

**配置**:
```python
class WeChatChannelConfig(ChannelConfig):
    webhook_url: str = ""
    secret: str = ""
```

**特性**:
- 企业微信群机器人 Webhook
- 支持 Markdown (部分格式)
- 消息限流: 20条/分钟/群

## NotificationManager

```python
class NotificationManager:
    """
    通知管理器

    用法:

    # 发送事件到所有启用渠道
    manager = NotificationManager()
    await manager.send_event("breaking", story_data)

    # 发送到特定渠道
    await manager.send_event("daily", data, channels=["telegram", "dingtalk"])

    # 直接发送渲染后的消息
    await manager.send_message("Hello", channels=["dingtalk"])
    """

    def __init__(self):
        self._channels: Dict[str, NotificationChannel] = {}
        self._init_channels()

    async def send_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        channels: Optional[List[str]] = None,
        title: Optional[str] = None
    ) -> Dict[str, SendResult]:
        """发送通知事件"""
        ...

    async def send_message(
        self,
        content: str,
        channels: Optional[List[str]] = None,
        title: Optional[str] = None,
        **kwargs
    ) -> Dict[str, SendResult]:
        """直接发送已渲染的消息"""
        ...

    def render_template(self, template_name: str, data: dict) -> str:
        """渲染 Jinja2 模板"""
        ...

    # 向后兼容 API
    def send_telegram(self, text: str, reply_markup: dict = None, chat_id: str = None):
        """向后兼容: 发送 Telegram 消息"""

    def push_to_dingtalk(self, title: str, summary_data: dict, event_type: str = "daily"):
        """向后兼容: 发送到钉钉"""
```

## 配置模型

### Settings 新增字段

```python
class NotificationSettings(BaseSettings):
    # 渠道开关
    enable_telegram: bool = True
    enable_dingtalk: bool = True
    enable_wechat: bool = False

    # Telegram 渠道配置
    telegram_channels: List[TelegramChannelConfig] = []

    # 钉钉渠道配置
    dingtalk_channels: List[DingTalkChannelConfig] = []

    # 企业微信渠道配置
    wechat_channels: List[WeChatChannelConfig] = []

    # 微信 Webhook 密钥 (用于验证微信调用)
    wechat_webhook_secret: str = ""
```

### 环境变量

```bash
# Telegram
TG_ROBOTS='[{"bot_token": "...", "chat_id": "...", ...}]'

# DingTalk
DING_ROBOTS='[{"token": "...", "secret": "...", ...}]'

# WeChat
WECHAT_WEBHOOK_SECRET=your_secret_key
```

## 事件类型

| 事件类型 | 说明 | 触发来源 |
|----------|------|----------|
| `daily` | 每日摘要 | job_daily_summary |
| `breaking` | 突发新闻 | BreakingAlerter |
| `twitter` | Twitter 动态 | TwitterAlerter |
| `astock` | A股分析 | AStockAnalyzer |
| `astock_alert` | A股异常告警 | AStockAlertService |

## 模板系统

### 模板目录结构

```
backend/src/templates/
├── telegram/
│   ├── daily.html.j2
│   ├── breaking.html.j2
│   └── twitter_alert.html.j2
├── dingtalk/
│   ├── daily.md.j2
│   ├── breaking.md.j2
│   └── twitter_alert.md.j2
├── wechat/
│   ├── daily.md.j2
│   └── breaking.md.j2
└── shared/
    ├── header.j2
    └── footer.j2
```

### 模板渲染

```python
def render_template(self, template_name: str, data: dict) -> str:
    """渲染模板，返回字符串"""
    if not template_name.endswith('.j2'):
        template_name += '.j2'
    template = self._jinja_env.get_template(template_name)
    return template.render(**data).strip()
```

## 现有文件

| 文件 | 说明 |
|------|------|
| `backend/src/notifications/pusher.py` | 现有实现，需重构为 facade |
| `backend/src/config.py` | 配置模型 |
| `backend/src/templates/` | Jinja2 模板 |
