# Breaking News 处理架构

本文档详细描述 OmniDigest 系统中 Breaking News（突发新闻）的完整处理流程。

## 1. 系统架构概览

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              APScheduler (后台任务调度)                              │
│  ┌─────────────────┐    ┌──────────────────────┐    ┌────────────────────────┐  │
│  │ breaking_fetch  │───▶│ breaking_processor   │───▶│ breaking_alerter      │  │
│  │ (定时抓取)      │    │ (LLM 分析处理)       │    │ (告警推送)           │  │
│  │ 每 N 分钟       │    │ 每 60 秒             │    │ 每 60 秒             │  │
│  └─────────────────┘    └──────────────────────┘    └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                  数据流程                                            │
│                                                                                     │
│  RSS Feeds ──────▶ breaking_stream_raw ──▶ breaking_events ──▶ breaking_stories   │
│  (原始信息流)        (待处理)                (事件)              (故事线)          │
│                                                                                     │
│         Telegram/DingTalk ◀─── breaking_alerter ◀─── breaking_stories             │
│            (推送通知)              (已验证故事线)                                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## 2. 数据源

### 2.1 RSS 订阅源

系统配置了多个全球突发新闻 RSS 源，按地区分类：

| 地区 | 来源 |
|------|------|
| 亚洲 | 共同网、韩联社、联合早报、越南通讯社、卫星通讯社 |
| 欧洲 | 路透社、德国之声、欧盟理事会、瑞士资讯 |
| 美洲 | 美联社、美国之音、加拿大广播公司、巴西通讯社 |
| 中东/非洲 | 以色列时报、阿纳多卢通讯社、News24 |
| 国际组织 | 联合国新闻、WHO、IMF |

**配置表**: `breaking_rss_sources`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| url | VARCHAR(512) | RSS 链接（唯一） |
| name | VARCHAR(100) | 来源名称 |
| platform | VARCHAR(50) | 平台/地区 |
| enabled | BOOLEAN | 是否启用 |
| fail_count | INT | 失败次数 |
| success_count | INT | 成功次数 |

## 3. 处理流程详解

### 3.1 抓取阶段 (BreakingCrawler)

**入口**: `jobs/__init__.py` - `job_breaking_fetch()`

**配置参数**:
- `breaking_fetch_interval_minutes`: 抓取间隔（默认 5 分钟）

**处理流程**:

```
1. 从数据库获取所有 enabled=true 的 RSS 源
2. 使用 ThreadPoolExecutor 并发抓取（max_workers=15）
3. 对每个 RSS 源:
   a. 解析 RSS/Atom 格式
   b. 提取文章标题、链接、发布时间
   c. 使用 newspaper3k 提取正文内容
   d. 调用 db.add_breaking_stream_raw() 存入数据库
4. 记录成功/失败次数
```

**数据库表 - breaking_stream_raw**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| source_platform | VARCHAR(100) | 来源平台（如 BBC、NYT） |
| source_url | TEXT | 原文链接（唯一约束） |
| raw_text | TEXT | 抓取的正文内容 |
| author | VARCHAR(255) | 作者 |
| publish_time | TIMESTAMP | 发布时间 |
| status | SMALLINT | 0=待处理, 1=已处理, 2=噪音 |
| created_at | TIMESTAMP | 入库时间 |

### 3.2 分析阶段 (BreakingProcessor)

**入口**: `jobs/__init__.py` - `run_processing_cycle()`

**调度**: 每 60 秒执行一次

**配置参数**:
- `breaking_processor_batch_size`: 批次大小（默认 10）
- `breaking_processor_concurrency`: 并发数（默认 6）
- `breaking_impact_threshold`: 告警阈值（默认 80）

**处理流程**:

```
1. 从数据库获取 status=0 的 streams（最多 batch_size 条）
2. 使用 Semaphore 控制并发（最多 concurrency 个）
3. 对每个 stream 调用 LLM 分析（OnePass 框架）
4. 根据 LLM 结果处理:
   - is_breaking=false → 标记为噪音 (status=2)
   - is_breaking=true → 创建/更新事件
5. 事件关联到故事线（Story）
6. 验证：story 获得 ≥2 个独立 source 后标记为 verified
7. 可选：同步到 RAGFlow
```

**LLM 分析 (OnePass)**:

LLM 使用 OnePass 框架进行结构化分析，返回字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| is_breaking | bool | 是否为突发新闻 |
| event_title | str | 中文标题 |
| summary | str | 1-2 句中文摘要 |
| category | str | 分类（战争/国际关系/宏观经济/灾难/科技/其他） |
| impact_score | int | 影响力评分 (0-100) |
| matched_event_id | UUID | 匹配的事件 ID |
| matched_story_id | UUID | 匹配的故事线 ID |

**评分标准**:
- >90: 改变世界的事件
- 80-89: 国际危机或国家级紧急事件
- 70-79: 重大地区事件
- <70: 常规新闻

**数据库表 - breaking_events**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| event_title | VARCHAR(512) | 事件标题 |
| summary | TEXT | 事件摘要 |
| category | VARCHAR(100) | 分类 |
| impact_score | INT | 影响力评分 |
| ragflow_id | VARCHAR(100) | RAGFlow 文档 ID |
| pushed | BOOLEAN | 是否已推送 |
| story_id | UUID | 关联的故事线 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**数据库表 - breaking_stories**:

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| story_title | VARCHAR(512) | 故事线标题 |
| story_summary | TEXT | 故事线摘要 |
| category | VARCHAR(100) | 分类 |
| peak_score | INT | 最高影响力分数 |
| source_count | INT | 独立来源数量 |
| status | VARCHAR(20) | 状态: developing/verified/resolved |
| pushed | BOOLEAN | 是否已推送 |
| push_count | INT | 推送次数 |
| last_pushed_at | TIMESTAMP | 上次推送时间 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

**状态流转**:
```
developing ──(source_count ≥2)──▶ verified ──(手动/超时)──▶ resolved
```

### 3.3 告警阶段 (BreakingAlerter)

**入口**: `jobs/__init__.py` - `run_alerter_loop()`

**调度**: 每 60 秒执行一次

**配置参数**:
- `breaking_impact_threshold`: 告警阈值（默认 80）
- `breaking_push_telegram`: 是否推送 Telegram
- `breaking_push_dingtalk`: 是否推送钉钉

**处理流程**:

```
1. 查询可推送 stories:
   - status = 'verified'
   - peak_score >= threshold
   - (未推送 OR 分数更新 ≥10)
2. 内存缓存去重
3. 标记已推送状态
4. 渲染通知模板
5. 推送至 Telegram/DingTalk
6. 更新数据库 push 状态
```

## 4. 调度配置

| Job ID | 类型 | 间隔 | 说明 |
|--------|------|------|------|
| breaking_fetch | interval | 5 分钟 | 抓取 RSS |
| breaking_processor_loop | interval | 60 秒 | LLM 分析 |
| breaking_alerter_loop | interval | 60 秒 | 告警推送 |
| kg_extract_interval | interval | 15 分钟 | 知识图谱抽取 |
| kg_resolve_cron | cron | 0,6,12,18点15分 | 实体消歧 |

## 5. 环境变量配置

```bash
# 开关
ENABLE_BREAKING_NEWS=true

# 抓取
BREAKING_FETCH_INTERVAL_MINUTES=5

# 处理
BREAKING_PROCESSOR_CONCURRENCY=6
BREAKING_PROCESSOR_BATCH_SIZE=10
BREAKING_IMPACT_THRESHOLD=80

# 上下文（OnePass）
BREAKING_CONTEXT_RECENT_EVENTS=3
BREAKING_CONTEXT_ACTIVE_STORIES=10

# 告警推送
BREAKING_PUSH_TELEGRAM=true
BREAKING_PUSH_DINGTALK=true

# RAGFlow 同步
BREAKING_RAG_ENABLED=false
BREAKING_RAG_DATASET_ID=
```

## 6. 关键代码文件

| 文件 | 职责 |
|------|------|
| `jobs/__init__.py` | 调度任务定义 |
| `domains/ingestion/rss/fast_crawler.py` | RSS 抓取 |
| `domains/breaking_news/processor.py` | LLM 分析处理 |
| `domains/breaking_news/alerter.py` | 告警推送 |
| `domains/breaking_news/db_repo.py` | 数据库操作 |
| `domains/core/onepass.py` | 通用 LLM 分析框架 |
| `core/llm_manager.py` | LLM 服务管理 |

## 7. 故障排查

### 7.1 日志关键词

```
# 抓取
"Ingested X new breaking streams"

# 分析
"validated as BREAKING NEWS"
"linked to Story"

# 告警
"🚨🚨 NEW STORY ALERT"
"📢 STORY UPDATE ALERT"
```

### 7.2 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| job 被跳过 | 执行时间超过间隔 | 增加间隔或 max_instances |
| LLM 调用失败 | API 限流/网络问题 | 检查日志中的模型切换 |
| 重复告警 | 缓存未生效 | 检查 mark_story_pushed |
| RSS 抓取失败 | 网络/源不可用 | 检查 fail_count |

## 8. 监控指标

- `/metrics` 端点提供 Prometheus 指标
- 关键指标：
  - `breaking_streams_total`: 入库总数
  - `breaking_events_created`: 创建事件数
  - `breaking_alerts_sent`: 发送告警数
