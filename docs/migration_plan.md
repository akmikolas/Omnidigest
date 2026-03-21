# 通知模块重构迁移计划

## 概述

本文档描述 OmniDigest 通知模块从现有紧耦合架构迁移到模块化架构的计划。

## 当前状态

### 现有问题

| 问题 | 描述 | 影响 |
|------|------|------|
| 紧耦合 | `NotificationService` 同时处理 TG 和钉钉 | 添加新渠道需修改核心类 |
| 配置分散 | `TgRobotConfig` 和 `DingRobotConfig` 独立定义 | 配置管理复杂 |
| 模板绑定 | 模板与渠道硬编码关联 | 格式转换不灵活 |
| 错误处理不一致 | TG 有分块发送，钉钉无同等机制 | 部分消息发送失败 |

### 现有调用关系

```
BreakingAlerter ─────► pusher.send_telegram()
BreakingAlerter ─────► pusher.push_to_dingtalk()

TwitterAlerter ──────► notifier.push_to_telegram()
TwitterAlerter ──────► notifier.push_to_dingtalk()

AStockAlertService ──► _send_dingtalk()  (有 bug)

job_daily_summary ───► pusher.render_template()
job_daily_summary ───► pusher.send_telegram()
job_daily_summary ───► pusher.push_to_dingtalk()
```

## 迁移目标

1. **模块化** - 渠道可插拔，新增渠道只需实现接口
2. **统一配置** - 所有渠道使用统一的配置模型
3. **向后兼容** - 保留现有 API，渐进式迁移
4. **微信支持** - 新增企业微信渠道

## 迁移阶段

### Phase 1: 抽象接口定义

**目标**: 定义清晰的 `NotificationChannel` 抽象基类

**新增文件**:
- `backend/src/notifications/channels/__init__.py`
- `backend/src/notifications/channels/base.py`

**工作内容**:
1. 定义 `NotificationChannel` ABC
2. 定义 `SendResult` 数据类
3. 定义 `ChannelConfig` 基类
4. 定义 `NotificationManager` Facade

**验收标准**:
- [ ] 所有渠道实现继承 `NotificationChannel`
- [ ] `SendResult` 包含完整的状态信息
- [ ] `NotificationManager` 提供统一的发送接口

---

### Phase 2: 实现 Telegram 适配器

**目标**: 将现有 TG 发送逻辑迁移到 `TelegramChannel`

**新增文件**:
- `backend/src/notifications/channels/telegram.py`

**工作内容**:
1. 实现 `TelegramChannel` 类
2. 迁移现有分块发送逻辑
3. 迁移 HTML 降级逻辑
4. 保持与现有配置的兼容

**验收标准**:
- [ ] 现有 TG 发送功能正常
- [ ] 分块发送正常工作
- [ ] HTML 降级机制正常

---

### Phase 3: 实现 DingTalk 适配器

**目标**: 将现有钉钉发送逻辑迁移到 `DingTalkChannel`

**新增文件**:
- `backend/src/notifications/channels/dingtalk.py`

**工作内容**:
1. 实现 `DingTalkChannel` 类
2. 迁移 HMAC-SHA256 签名逻辑
3. 迁移 Markdown 格式逻辑
4. 修复现有 bug (如 `_send_dingtalk` 问题)

**验收标准**:
- [ ] 现有钉钉发送功能正常
- [ ] HMAC 签名认证正常
- [ ] 修复 AStockAlertService 的调用问题

---

### Phase 4: 实现微信渠道

**目标**: 新增 `WeChatChannel`

**新增文件**:
- `backend/src/notifications/channels/wechat.py`
- `backend/src/templates/wechat/*.j2`

**工作内容**:
1. 实现 `WeChatChannel` 类
2. 实现 Webhook 接收 API
3. 创建企业微信模板
4. 添加限流处理

**验收标准**:
- [ ] Webhook API 正常接收消息
- [ ] 消息可转发到 TG/钉钉
- [ ] 限流机制正常

---

### Phase 5: 重构 NotificationManager

**目标**: 统一管理所有渠道

**修改文件**:
- `backend/src/notifications/manager.py` (新建/重写)

**工作内容**:
1. 实现渠道注册机制
2. 实现事件路由
3. 实现模板渲染抽象
4. 添加向后兼容 facade

**验收标准**:
- [ ] 所有渠道通过 Manager 统一管理
- [ ] 事件类型路由正确
- [ ] 模板渲染正常

---

### Phase 6: 迁移调用方

**目标**: 更新所有调用方使用新架构

**修改文件**:
- `backend/src/domains/breaking_news/alerter.py`
- `backend/src/domains/twitter/alerter.py`
- `backend/src/domains/analysis/alert_service.py`
- `backend/src/jobs/__init__.py`

**工作内容**:
1. 将 `pusher.send_telegram()` 改为 `manager.send_event()`
2. 将 `pusher.push_to_dingtalk()` 改为 `manager.send_event()`
3. 更新 `api/deps.py` 返回新 Manager

**验收标准**:
- [ ] BreakingAlerter 正常工作
- [ ] TwitterAlerter 正常工作
- [ ] AStockAlertService 正常工作
- [ ] job_daily_summary 正常工作

---

### Phase 7: 清理与优化

**目标**: 删除废弃代码，优化性能

**删除/修改文件**:
- 删除 `backend/src/notifications/pusher.py` (如确认无引用)
- 优化模板加载缓存
- 添加渠道健康检查

**工作内容**:
1. 确认无引用后删除旧文件
2. 添加模板缓存
3. 添加监控指标
4. 更新文档

**验收标准**:
- [ ] 无废弃代码残留
- [ ] 性能有所提升
- [ ] 文档完整

## 文件清单

### 新建文件

| 文件 | 阶段 | 说明 |
|------|------|------|
| `backend/src/notifications/channels/__init__.py` | 1 | 渠道模块初始化 |
| `backend/src/notifications/channels/base.py` | 1 | 抽象基类 |
| `backend/src/notifications/channels/telegram.py` | 2 | TG 适配器 |
| `backend/src/notifications/channels/dingtalk.py` | 3 | 钉钉适配器 |
| `backend/src/notifications/channels/wechat.py` | 4 | 微信渠道 |
| `backend/src/notifications/manager.py` | 5 | 统一管理器 |
| `backend/src/templates/wechat/*.j2` | 4 | 微信模板 |
| `backend/src/api/webhook.py` | 4 | Webhook API |
| `doc/notification_module_design.md` | - | 架构文档 |
| `doc/wechat_webhook_api.md` | - | API 文档 |
| `doc/migration_plan.md` | - | 本文档 |

### 修改文件

| 文件 | 阶段 | 修改内容 |
|------|------|----------|
| `backend/src/config.py` | 1-4 | 新增渠道配置模型 |
| `backend/src/api/deps.py` | 6 | 更新 get_pusher() |
| `backend/src/domains/breaking_news/alerter.py` | 6 | 迁移到新 API |
| `backend/src/domains/twitter/alerter.py` | 6 | 迁移到新 API |
| `backend/src/domains/analysis/alert_service.py` | 3,6 | 修复 bug，迁移 |
| `backend/src/jobs/__init__.py` | 6 | 迁移到新 API |

### 删除文件

| 文件 | 阶段 | 说明 |
|------|------|------|
| `backend/src/notifications/pusher.py` | 7 | 确认无引用后删除 |

## 配置变更

### config.py 新增字段

```python
# 通知模块配置
enable_telegram: bool = True
enable_dingtalk: bool = True
enable_wechat: bool = False

# 渠道配置
telegram_channels: List[TelegramChannelConfig] = []
dingtalk_channels: List[DingTalkChannelConfig] = []
wechat_channels: List[WeChatChannelConfig] = []

# Webhook 密钥
wechat_webhook_secret: str = ""
```

### .env.example 新增

```bash
# WeChat Webhook
WECHAT_WEBHOOK_SECRET=your_secret_key_here
```

## 测试计划

### 单元测试

| 测试项 | 测试内容 |
|--------|----------|
| TelegramChannel | send(), chunk_message(), format_message() |
| DingTalkChannel | send(), _sign() |
| WeChatChannel | send(), Webhook 验证 |
| NotificationManager | send_event(), send_message() |

### 集成测试

| 测试项 | 测试内容 |
|--------|----------|
| BreakingAlerter | 模拟突发事件，验证转发 |
| TwitterAlerter | 模拟 Twitter 消息，验证转发 |
| job_daily_summary | 验证每日摘要发送 |
| Webhook API | POST 消息，验证转发 |

### 回归测试

| 测试项 | 验证内容 |
|--------|----------|
| 现有 TG 发送 | bot_token, chat_id 配置有效时正常发送 |
| 现有钉钉发送 | token, secret 配置有效时正常发送 |
| 模板渲染 | 各模板渲染结果符合预期 |

## 时间估算

| 阶段 | 预计工作量 | 风险等级 |
|------|-----------|----------|
| Phase 1 | 1 天 | 低 |
| Phase 2 | 1 天 | 低 |
| Phase 3 | 1 天 | 中 |
| Phase 4 | 2 天 | 中 |
| Phase 5 | 1 天 | 低 |
| Phase 6 | 2 天 | 高 |
| Phase 7 | 1 天 | 低 |
| **总计** | **9 天** | |

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 迁移破坏现有功能 | 高 | Phase 6 完整回归测试 |
| 微信 API 变更 | 中 | 使用 Webhook 简单模式 |
| 模板迁移遗漏 | 中 | 保留旧模板，逐步替换 |
| AStockAlertService bug | 中 | Phase 3 单独修复 |

## 回滚计划

如迁移过程中出现问题：

1. **Phase 1-5**: 保留 `pusher.py`，回滚 Manager 调用方更改
2. **Phase 6**: 将调用方改回使用 `pusher.py`
3. **Phase 7**: 从 Git 恢复已删除文件

## 后续扩展

完成基础迁移后，可考虑：

1. **微信公众号渠道** - 模板消息
2. **Slack 渠道** - Webhook 集成
3. **邮件渠道** - SMTP 发送
4. **消息队列** - 异步发送，削峰填谷
5. **消息撤回** - 支持撤回已发送消息
