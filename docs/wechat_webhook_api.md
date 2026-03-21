# 微信双向通信 API 设计

## 概述

OmniDigest 与微信服务器之间采用双向通信架构：

- **Outbound (推送)**：OmniDigest 调用微信 API 主动推送消息到用户
- **Inbound (接收)**：微信服务器回调 OmniDigest Webhook 接收用户消息

```
┌─────────────────┐                         ┌─────────────────┐
│  OmniDigest     │                         │  微信服务器      │
│  Backend        │                         │                 │
│                 │                         │                 │
│  ┌───────────┐  │  POST /wechat/send      │  ┌───────────┐  │
│  │ WeChat    │─►┼────────────────────────┼─►│  消息接口  │  │
│  │ Client    │  │                         │  │           │  │
│  └───────────┘  │                         │  └───────────┘  │
│       ▲         │                         │       │        │
│       │         │                         │       ▼        │
│  ┌───────────┐  │  POST /wechat/webhook   │  ┌───────────┐  │
│  │ Webhook   │◄┼────────────────────────┼─│  回调接口  │  │
│  │ Handler   │  │                         │  │           │  │
│  └───────────┘  │                         │  └───────────┘  │
└─────────────────┘                         └─────────────────┘
```

## 一、Outbound API (OmniDigest → 微信)

### 1.1 发送文字消息

**请求**

```http
POST /wechat/api/send/text
Content-Type: application/json
X-WeChat-App-ID: {app_id}
X-WeChat-Secret: {secret}

{
  "to_user": "OPENID 或 用户ID",
  "content": "消息内容",
  "priority": "normal"
}
```

**响应**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "msg_id": "MSG_123456",
    "status": "sent"
  }
}
```

### 1.2 发送 Markdown 消息

**请求**

```http
POST /wechat/api/send/markdown
Content-Type: application/json
X-WeChat-App-ID: {app_id}
X-WeChat-Secret: {secret}

{
  "to_user": "OPENID 或 用户ID",
  "content": "## 标题\n\n这是**加粗**文字\n- 列表项1\n- 列表项2",
  "priority": "high"
}
```

**响应**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "msg_id": "MSG_123457",
    "status": "sent"
  }
}
```

### 1.3 发送图文消息

**请求**

```http
POST /wechat/api/send/news
Content-Type: application/json
X-WeChat-App-ID: {app_id}
X-WeChat-Secret: {secret}

{
  "to_user": "OPENID 或 用户ID",
  "articles": [
    {
      "title": "文章标题",
      "description": "文章描述",
      "url": "https://example.com/article",
      "picurl": "https://example.com/image.jpg"
    }
  ]
}
```

**响应**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "msg_id": "MSG_123458",
    "status": "sent"
  }
}
```

### 1.4 发送模板消息

**请求**

```http
POST /wechat/api/send/template
Content-Type: application/json
X-WeChat-App-ID: {app_id}
X-WeChat-Secret: {secret}

{
  "to_user": "OPENID",
  "template_id": "TEMPLATE_ID",
  "data": {
    "first": {
      "value": "您好，您有一条新消息",
      "color": "#173177"
    },
    "keyword1": {
      "value": "内容摘要",
      "color": "#173177"
    },
    "keyword2": {
      "value": "2024-01-01 12:00",
      "color": "#173177"
    },
    "remark": {
      "value": "点击查看详情",
      "color": "#173177"
    }
  },
  "url": "https://example.com/detail"
}
```

**响应**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "msg_id": "MSG_123459",
    "status": "sent"
  }
}
```

### 1.5 批量发送

**请求**

```http
POST /wechat/api/send/batch
Content-Type: application/json
X-WeChat-App-ID: {app_id}
X-WeChat-Secret: {secret}

{
  "users": ["user1", "user2", "user3"],
  "msg_type": "text",
  "content": "群发消息内容",
  "priority": "low"
}
```

**响应**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "batch_id": "BATCH_123",
    "total": 3,
    "sent": 3,
    "failed": 0
  }
}
```

---

## 二、Inbound Webhook (微信 → OmniDigest)

微信服务器将用户消息回调到 OmniDigest。

### 2.1 回调端点

**端点**

```http
POST /api/wechat/webhook
```

### 2.2 回调验证 (GET)

微信服务器在配置回调 URL 时会发送 GET 请求验证合法性。

**请求**

```
GET /api/wechat/webhook?echostr=ENCRYPTED_STRING&signature=SIGNATURE&timestamp=TIMESTAMP&nonce=NONCE
```

**响应**

```
返回 echostr 参数值表示验证成功
```

### 2.3 接收消息 (POST)

**请求头**

```
Content-Type: application/xml
X-WeChat-Signature: {signature}
```

**请求体 (文字消息)**

```xml
<xml>
  <ToUserName><![CDATA[to_user]]></ToUserName>
  <FromUserName><![CDATA[from_user]]></FromUserName>
  <CreateTime>1234567890</CreateTime>
  <MsgType><![CDATA[text]]></MsgType>
  <Content><![CDATA[用户输入的内容]]></Content>
  <MsgId>1234567890123456</MsgId>
</xml>
```

**请求体 (图片消息)**

```xml
<xml>
  <ToUserName><![CDATA[to_user]]></ToUserName>
  <FromUserName><![CDATA[from_user]]></FromUserName>
  <CreateTime>1234567890</CreateTime>
  <MsgType><![CDATA[image]]></MsgType>
  <PicUrl><![CDATA[图片URL]]></PicUrl>
  <MediaId><![CDATA[media_id]]></MediaId>
  <MsgId>1234567890123456</MsgId>
</xml>
```

**请求体 (事件推送)**

```xml
<xml>
  <ToUserName><![CDATA[to_user]]></ToUserName>
  <FromUserName><![CDATA[from_user]]></FromUserName>
  <CreateTime>1234567890</CreateTime>
  <MsgType><![CDATA[event]]></MsgType>
  <Event><![CDATA[subscribe]]></Event>
  <EventKey><![CDATA[]]></EventKey>
</xml>
```

### 2.4 响应格式

OmniDigest 返回空字符串表示接收成功，或返回消息进行自动回复：

**被动回复 (文本)**

```xml
<xml>
  <ToUserName><![CDATA[from_user]]></ToUserName>
  <FromUserName><![CDATA[to_user]]></FromUserName>
  <CreateTime>1234567890</CreateTime>
  <MsgType><![CDATA[text]]></MsgType>
  <Content><![CDATA[收到消息，感谢您的反馈]]></Content>
</xml>
```

**被动回复 (图片)**

```xml
<xml>
  <ToUserName><![CDATA[from_user]]></ToUserName>
  <FromUserName><![CDATA[to_user]]></FromUserName>
  <CreateTime>1234567890</CreateTime>
  <MsgType><![CDATA[image]]></MsgType>
  <Image>
    <MediaId><![CDATA[media_id]]></MediaId>
  </Image>
</xml>
```

---

## 三、OmniDigest 内部 Webhook 端点设计

### 3.1 微信回调处理 API

**端点**

```
POST /api/wechat/webhook
```

**OmniDigest 内部处理逻辑**

```python
class WeChatWebhookHandler:
    """处理微信服务器回调"""

    async def handle(self, request: Request) -> Response:
        """
        1. 验证签名
        2. 解析消息
        3. 转换为内部格式
        4. 触发业务处理
        """

        # 获取原始数据
        body = await request.body()

        # 解密（如果是加密模式）
        if self.is_encrypted:
            body = self.decrypt(body, request.query_params)

        # 解析 XML
        msg = self.parse_xml(body)

        # 转换为内部事件
        event = self.to_internal_event(msg)

        # 分发处理
        await self.dispatcher.dispatch(event)

        # 返回成功
        return Response("")
```

### 3.2 微信消息转内部事件

```python
@dataclass
class WeChatMessageEvent:
    """微信消息事件"""
    msg_type: str              # text, image, event, etc.
    from_user: str            # 发送者 OpenID
    to_user: str              # 接收者 (公众号)
    content: str              # 消息内容
    msg_id: str               # 消息 ID
    create_time: int          # 创建时间
    raw_data: Dict            # 原始数据

    # 事件特定字段
    event: Optional[str] = None     # subscribe, unsubscribe, etc.
    event_key: Optional[str] = None # 事件 Key
```

### 3.3 业务分发

```python
# 消息类型路由
MSG_TYPE_HANDLERS = {
    "text": handle_text_message,
    "image": handle_image_message,
    "voice": handle_voice_message,
    "event": handle_event_message,
}

EVENT_HANDLERS = {
    "subscribe": handle_subscribe,
    "unsubscribe": handle_unsubscribe,
    "CLICK": handle_menu_click,
    "VIEW": handle_menu_view,
}
```

---

## 四、配置模型

### 4.1 微信渠道配置

```python
class WeChatChannelConfig(ChannelConfig):
    """微信渠道配置"""

    # 连接配置
    app_id: str = ""           # 微信 AppID
    app_secret: str = ""       # 微信 AppSecret

    # API 端点 (可配置，支持私有化部署)
    api_base_url: str = "https://api.weixin.qq.com"

    # 回调配置
    webhook_path: str = "/api/wechat/webhook"  # 回调路径
    webhook_token: str = ""    # 回调 Token (用于验证)
    encoding_aes_key: str = "" # 消息加密密钥 (可选)

    # 限流配置
    rate_limit: int = 100      # 每分钟发送上限
    rate_limit_period: int = 60

    # 重试配置
    max_retries: int = 3
    retry_delay: float = 1.0  # 秒
```

### 4.2 环境变量

```bash
# 微信配置
WECHAT_APP_ID=wx_your_app_id
WECHAT_APP_SECRET=your_app_secret
WECHAT_API_BASE_URL=https://api.weixin.qq.com  # 可选
WECHAT_WEBHOOK_TOKEN=your_callback_token
WECHAT_WEBHOOK_AES_KEY=your_aes_key  # 可选
```

---

## 五、API 统一响应格式

### 5.1 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

### 5.2 错误响应

```json
{
  "code": 40001,
  "message": "错误描述",
  "data": null
}
```

### 5.3 错误码

| code | 说明 | HTTP 状态码 |
|------|------|-------------|
| 0 | 成功 | 200 |
| 40001 | 签名验证失败 | 401 |
| 40002 | 无效的消息类型 | 400 |
| 40003 | 用户不存在 | 404 |
| 40004 | 内容超长 | 400 |
| 40005 | 频率限制 | 429 |
| 50001 | 微信 API 调用失败 | 502 |
| 50002 | 内部处理错误 | 500 |

---

## 六、消息类型支持

| 消息类型 | 发送 | 接收 | 说明 |
|----------|------|------|------|
| text | ✅ | ✅ | 文字消息 |
| image | ✅ | ✅ | 图片消息 |
| voice | ✅ | ✅ | 语音消息 |
| video | ✅ | ❌ | 视频消息 |
| music | ✅ | ❌ | 音乐消息 |
| news | ✅ | ❌ | 图文消息 |
| markdown | ✅ | ❌ | Markdown (部分渠道) |
| template | ✅ | ❌ | 模板消息 |
| miniprogram | ✅ | ❌ | 小程序卡片 |
| event | ❌ | ✅ | 事件推送 |

---

## 七、实现示例

### 7.1 微信客户端

```python
# backend/src/notifications/channels/wechat/client.py

import aiohttp
import asyncio
from typing import Optional, List, Dict, Any
from .config import WeChatChannelConfig
from .base import SendResult

class WeChatClient:
    """微信 API 客户端"""

    def __init__(self, config: WeChatChannelConfig):
        self.config = config
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _ensure_token(self) -> str:
        """获取或刷新 access_token"""
        import time
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        # 获取新 token
        url = f"{self.config.api_base_url}/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.config.app_id,
            "secret": self.config.app_secret
        }

        session = await self._get_session()
        async with session.get(url, params=params) as resp:
            data = await resp.json()

            if "access_token" in data:
                self._access_token = data["access_token"]
                self._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
                return self._access_token
            else:
                raise Exception(f"Failed to get access_token: {data}")

    async def send_text(
        self,
        to_user: str,
        content: str,
        priority: str = "normal"
    ) -> SendResult:
        """发送文字消息"""
        token = await self._ensure_token()
        url = f"{self.config.api_base_url}/cgi-bin/message/custom/send"
        params = {"access_token": token}

        payload = {
            "touser": to_user,
            "msgtype": "text",
            "text": {"content": content}
        }

        return await self._post(url, params, payload)

    async def send_markdown(
        self,
        to_user: str,
        content: str,
        priority: str = "normal"
    ) -> SendResult:
        """发送 Markdown 消息 (企业微信或兼容渠道)"""
        token = await self._ensure_token()
        url = f"{self.config.api_base_url}/cgi-bin/message/custom/send"
        params = {"access_token": token}

        payload = {
            "touser": to_user,
            "msgtype": "markdown",
            "markdown": {"content": content}
        }

        return await self._post(url, params, payload)

    async def send_news(
        self,
        to_user: str,
        articles: List[Dict[str, str]]
    ) -> SendResult:
        """发送图文消息"""
        token = await self._ensure_token()
        url = f"{self.config.api_base_url}/cgi-bin/message/custom/send"
        params = {"access_token": token}

        payload = {
            "touser": to_user,
            "msgtype": "news",
            "news": {"articles": articles}
        }

        return await self._post(url, params, payload)

    async def _post(
        self,
        url: str,
        params: Dict,
        payload: Dict
    ) -> SendResult:
        """POST 请求并处理响应"""
        session = await self._get_session()
        async with session.post(url, params=params, json=payload) as resp:
            data = await resp.json()

            if data.get("errcode") == 0:
                return SendResult(
                    success=True,
                    channel="wechat",
                    message_id=data.get("msgid")
                )
            else:
                return SendResult(
                    success=False,
                    channel="wechat",
                    error=f"errcode: {data.get('errcode')}, errmsg: {data.get('errmsg')}"
                )

    async def close(self):
        if self._session:
            await self._session.close()
```

### 7.2 Webhook 处理器

```python
# backend/src/api/wechat_webhook.py

from fastapi import APIRouter, Request, Query
from typing import Optional
import xml.etree.ElementTree as ET
import hashlib
import time

router = APIRouter(prefix="/api/wechat", tags=["wechat"])


class WeChatWebhookHandler:
    """微信回调处理器"""

    def __init__(self, webhook_token: str, encoding_aes_key: Optional[str] = None):
        self.webhook_token = webhook_token
        self.encoding_aes_key = encoding_aes_key
        self.is_encrypted = encoding_aes_key is not None

    def verify(self, params: dict) -> bool:
        """验证回调签名"""
        signature = params.get("signature", "")
        timestamp = params.get("timestamp", "")
        nonce = params.get("nonce", "")

        # 排序拼接
        tmp_list = sorted([self.webhook_token, timestamp, nonce])
        tmp_str = "".join(tmp_list)

        # SHA1 校验
        expected = hashlib.sha1(tmp_str.encode()).hexdigest()
        return signature == expected

    def parse_message(self, body: bytes) -> dict:
        """解析 XML 消息"""
        root = ET.fromstring(body)

        msg = {}
        for child in root:
            msg[child.tag] = child.text

        return msg

    def to_event(self, msg: dict) -> WeChatMessageEvent:
        """转换为内部事件"""
        return WeChatMessageEvent(
            msg_type=msg.get("MsgType", "text"),
            from_user=msg.get("FromUserName", ""),
            to_user=msg.get("ToUserName", ""),
            content=msg.get("Content", ""),
            msg_id=msg.get("MsgId", ""),
            create_time=int(msg.get("CreateTime", 0)),
            raw_data=msg,
            event=msg.get("Event"),
            event_key=msg.get("EventKey")
        )


handler = WeChatWebhookHandler(
    webhook_token=settings.WECHAT_WEBHOOK_TOKEN,
    encoding_aes_key=settings.WECHAT_WEBHOOK_AES_KEY
)


@router.get("/webhook")
async def verify_webhook(
    echostr: str = Query(...),
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...)
):
    """验证回调 URL"""
    if handler.verify({"signature": signature, "timestamp": timestamp, "nonce": nonce}):
        return Response(content=echostr)
    return Response(status_code=403)


@router.post("/webhook")
async def receive_message(request: Request):
    """接收微信消息"""
    body = await request.body()

    # 解析消息
    msg = handler.parse_message(body)
    event = handler.to_event(msg)

    # 分发处理
    await dispatcher.dispatch(event)

    # 返回空表示接收成功
    return Response("")
```

---

## 八、部署注意事项

1. **回调 URL 必须 HTTPS**
2. **配置防火墙允许微信服务器 IP 段访问**
3. **建议启用消息加密 (AES)**
4. **配置消息队列缓冲高并发**
5. **实现幂等处理防止重复消息**
