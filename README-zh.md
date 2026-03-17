# OmniDigest (万象简报)

OmniDigest 是一个高度自动化的、AI 驱动的新闻聚合、分类和汇总后端服务，具备实时情报监测能力。

**核心流水线 (v1.0+)**：定时 RSS 抓取 → PostgreSQL → One-Pass LLM 分类与评分 → AI 每日摘要 → 多平台推送 (Telegram / 钉钉)

**突发新闻流水线 (v1.3+)**：高频 RSS 轮询 → One-Pass LLM 分类 → 语义去重 → 故事时间线映射与交叉验证 → 实时推送告警

**推特情报流水线 (v1.7+)**：GraphQL 抓取 → One-Pass LLM 批量分类 → 影响力度监测 → 精细化告警路由

**知识图谱流水线 (v1.5+)**：持续三元组抽取 → Dgraph 存储 → 实体消解 → 双向遍历

**A股市场分析流水线 (v1.8+)**：多源新闻聚合 → 语义过滤 → One-Pass LLM 趋势分析 → 盘前与盘中预测 → 准确率追踪

*最新版本：v2.3.2 (2026-03-17) - 自动初始化数据库*
*最新稳定版本：v2.3.2 (2026-03-17)*

## 1. 项目结构 (v1.9.0+ 领域驱动架构)

```text
.
├── src/omnidigest/            # 核心源码包
│   ├── api/                   # FastAPI 路由与依赖注入 (router, deps, auth)
│   ├── cli/                   # CLI 命令处理器 (db, rss, jobs, auth, rag, kg, twitter, tests, lint)
│   ├── core/                  # 基础设施 (配置、数据库连接、LLM 管理)
│   │   └── onepass.py       # 通用 One-Pass 框架，统一 AI 分析
│   ├── domains/               # 领域业务模块
│   │   ├── ingestion/         # 数据获取领域
│   │   │   ├── rss/          # 标准与突发 RSS 抓取及数据访问
│   │   │   └── twitter/      # Twitter/X GraphQL 抓取及数据访问
│   │   ├── breaking_news/     # 快速轮询、One-Pass 分类、聚类与故事时间线
│   │   ├── daily_digest/     # 每日摘要处理逻辑 (One-Pass)
│   │   │   └── models.py     # Pydantic 结构化输出模型
│   │   ├── analysis/          # 基于 RAG 的趋势分析 (A股、行情数据)
│   │   ├── knowledge_base/    # RAGFlow 客户端与同步
│   │   ├── knowledge_graph/    # Dgraph 三元组抽取与消解
│   │   ├── twitter/          # 推特情报处理与告警 (One-Pass)
│   │   │   └── models.py     # Pydantic 结构化输出模型
│   │   └── auth/              # API 密钥与认证操作
│   ├── jobs/                  # 后台调度器设置 (daily, breaking, twitter, kg)
│   ├── migrations/            # SQL 数据库迁移脚本
│   ├── notifications/         # 多平台推送调度器 (Telegram/钉钉)
│   ├── templates/             # Jinja2 通知模板
│   ├── main.py                # 应用入口 (FastAPI + 调度器)
│   └── manage.py              # CLI 管理工具入口
├── tests/                     # 测试套件与诊断
├── docs/                      # 文档 (变更日志、标准)
├── frontend/                  # Vue 3 + Vite 前端应用
│   ├── src/                   # 前端源码
│   │   ├── views/           # Vue 页面组件
│   │   └── main.js          # 前端入口
│   ├── public/               # 静态资源 (favicon, icons)
│   ├── index.html            # HTML 入口
│   ├── vite.config.js        # Vite 配置
│   └── package.json          # 前端依赖
├── Makefile                   # CLI 快捷方式
├── Dockerfile                 # 多阶段 Docker 构建
├── docker-compose.yml         # 容器编排
├── pyproject.toml             # Python 包配置
└── .env.example               # 环境变量模板
```

## 2. 快速开始

### 2.1 环境准备

1. **启动数据库**：
   ```bash
   docker-compose up -d postgres
   ```

2. **安装依赖**：
   ```bash
   pip install -e .
   ```

3. **配置环境变量**：
   ```bash
   cp .env.example .env
   # 编辑 .env，填入你的 API 密钥、数据库凭据等
   ```

4. **启动应用** - 首次启动时数据库表会自动创建。
   ```bash
   docker-compose up -d
   ```

### 2.2 运行系统

**Docker（推荐）**：
```bash
docker-compose up -d
```

**本地开发**：
```bash
python -m omnidigest.main
```

API 服务启动于 `http://0.0.0.0:8080`。

### 2.3 从零安装

本节介绍如何从全新安装开始设置 OmniDigest。

#### 2.3.1 环境要求

- **Docker & Docker Compose**：安装 [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Python 3.11+**（本地开发用）
- **PostgreSQL 15+**（包含在 docker-compose 中）
- **Redis**（可选，用于缓存）
- **Dgraph**（可选，用于知识图谱）

#### 2.3.2 快速 Docker 安装（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/akmikolas/Omnidigest.git
cd omnidigest

# 2. 复制环境模板
cp .env.example .env

# 3. 编辑 .env 配置
# 必填：DB_PASSWORD, LLM_API_KEY, TG_ROBOTS/DING_ROBOTS

# 4. 启动所有服务
docker-compose up -d

# 5. 查看状态
docker-compose ps
```

#### 2.3.3 本地开发环境安装

```bash
# 1. 安装 Python 依赖
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .

# 2. 通过 Docker 启动 PostgreSQL
docker run -d --name omnidigest_postgres \
  -e POSTGRES_USER=omnidigest \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=omnidigest \
  -p 5432:5433 \
  postgres:15-alpine

# 3. 复制并配置环境变量
cp .env.example .env
# 编辑 .env 填入：
#   DB_HOST=localhost
#   DB_PORT=5432
#   DB_USER=omnidigest
#   DB_PASSWORD=your_password
#   DB_NAME=omnidigest

# 4. 初始化数据库
make db-init

# 5. 启动应用
python -m omnidigest.main
```

#### 2.3.4 必要配置

最低环境变量要求：

```bash
# 数据库
DB_HOST=postgres
DB_PORT=5432
DB_USER=omnidigest
DB_PASSWORD=your_secure_password
DB_NAME=omnidigest

# LLM（至少一个提供商）
# 选项 1: OpenAI
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

# 或选项 2: 使用数据库 llm_models 表

# 通知（Telegram 和/或钉钉）
TG_ROBOTS='[{"bot_token": "...", "chat_id": "...", ...}]'
DING_ROBOTS='[{"token": "...", ...}]'
```

#### 2.3.5 可选功能

**知识图谱 (Dgraph)**：
```bash
KG_ENABLED=true
DGRAPH_ALPHA_URL=dgraph:9080
```

**Redis 缓存**：
```bash
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
```

#### 2.3.6 验证安装

```bash
# 检查 API 健康状态
curl http://localhost:8080/api/health

# 检查数据库连接
curl http://localhost:8080/api/stats/overview

# 访问前端
# 在浏览器中打开 http://localhost:3000
```

---

## 3. Makefile 命令

所有常用操作都可通过 `make` 完成：

| 命令 | 说明 |
|---|---|
| `make db-init` | 初始化数据库结构 |
| `make db-migrate` | 运行所有待处理的数据库迁移 |
| `make rss-add URL=...` | 添加新的 RSS 源 |
| `make rss-check` | 列出已禁用/失败的 RSS 源 |
| `make trigger-summary` | 手动触发每日摘要 |
| `make cleanup` | 清理低质量文章 |
| `make test-tg` | 测试 Telegram 突发推送 |
| `make test-dingtalk` | 测试钉钉突发推送 |
| `make test-push` | 测试全平台推送 |
| `make lint` | 检查双语文档字符串 |
| `make help` | 显示所有可用命令 |

完整命令列表请运行 `make help`。

## 4. 核心功能

### 4.1 每日简报流水线 (v1.0+, v1.9+ One-Pass)

1.  **抓取** (`NewsCrawler`)：并行 RSS 抓取，15 秒超时，自动禁用持续失败的源。
2.  **One-Pass 处理** (`ContentProcessor`)：使用通用 OnePass 框架进行统一的 LLM 批量分类，将批次处理合并为单个结构化 `instructor` 请求，效率最大化。
3.  **知识库**：可选的 RAGFlow 集成，用于全文向量化 (`RAGFLOW_ENABLED`)。
4.  **摘要与推送** (`AnalysisService` → `NotificationService`)：可配置的 cron 计划，双语 Jinja2 模板，同时推送 Telegram HTML 和钉钉 Markdown。
5.  **自动清理**：每日删除评分低于阈值的文章。

### 4.2 突发新闻系统 (v1.3+, v1.9+ One-Pass)

一个完全独立的实时新闻告警流水线：

1.  **突发抓取器**：以可配置间隔轮询 25+ 国际媒体 RSS 源（BBC、CNN、NYT、路透社、半岛电视台、财新网、华尔街见闻等）。
2.  **One-Pass LLM 分类**：每个原始流由通用 OnePass 框架评估，在单次 LLM 调用中完成分类、评分、聚类和故事匹配。
3.  **语义去重（事件级）**：当多个来源报道同一事件时，LLM 将它们聚类为单个事件。
4.  **故事时间线映射与交叉验证（故事级）**：事件动态分组为更大的 `Stories`（叙事弧），具有可配置的回溯窗口 (`BREAKING_STORY_LOOKBACK_DAYS`)。故事必须被至少 2 个独立来源交叉验证后才推送，大幅减少误报。
5.  **影响评分**：故事评分 0-100。只有超过 `BREAKING_IMPACT_THRESHOLD` 的故事才会触发即时告警，包含跨越数天或数年的子事件时间线和直接来源链接。
6.  **实时告警** (`BreakingAlerter`)：持续监控数据库，将已验证的高影响力故事以 HTML (Telegram) 和 Markdown (钉钉) 格式推送到已配置的平台。

### 4.3 推特情报与影响力度监测 (v1.7+, v1.9+ One-Pass)

一个针对全球影响者和世界领导人的高效监测系统：

1.  **批量获取**：使用 GraphQL 抓取绕过 API 限制，带有高水位标记跟踪和账户池管理。
2.  **One-Pass 批量分类**：使用通用 OnePass 框架在单次 LLM 调用中完成分类、评分和事件匹配。每次请求处理 10 条推文，成本效率最大化。
3.  **精细化告警路由**：每个机器人独立启用/禁用状态 (`enable_twitter`) 和自定义模板 (`twitter_template`)，适用于 Telegram 和钉钉。
4.  **全局控制开关**：通过 `ENABLE_TWITTER_ALERTS`、`TWITTER_PUSH_TELEGRAM` 和 `TWITTER_PUSH_DINGTALK` 进行顶层配置。
5.  **有影响力领导人监测**：追踪 16+ 高影响力账户（世界领导人、新闻通讯社、全球组织），进行实时政策和情绪追踪。
6.  **钉钉合规**：告警中包含"新闻"关键词，满足钉钉机器人要求。

### 4.4 知识图谱抽取引擎 (v1.5+)

建立在 Dgraph 之上的系统性实体和关系抽取流水线：

1.  **三元组抽取**：使用 LLM 从 incoming 新闻文章中持续抽取实体（人、组织、地点）和关系，并追踪政治倾向。
2.  **幂等变更**：在单个事务中批量处理节点和边变更，消除竞争条件和图损坏，支持双向遍历的双边。
3.  **实体消解**：支持跨图的自动去重和合并相同实体。
4.  **LLM 故障转移集成**：利用集中的 `LLMManager` 实现自动模型故障转移和重试逻辑。
5.  **触发机制**：每 15 分钟自动运行，完全可通过 CLI (`manage.py kg extract`) 和 API (`/trigger/kg_extract`) 控制，带有线程安全并发锁。

### 4.5 大模型管理与健壮性 (v1.5+)

确保高可用性和提供商兼容性的健壮多模型管理系统：

1.  **自动故障转移系统**：动态模型选择，连续 5 次失败后自动重试和停用 (`llm_models` 表)。
2.  **提供商兼容性**：集中的 LLM 提供商检测 (DashScope/Qwen)，为 `instructor` 自动切换模式 (Mode.JSON / Mode.MD_JSON)。
3.  **健壮 JSON 解析**：系统级 `_clean_json_output` 工具，去除 Markdown 块并处理某些模型的 XML 类噪声。
4.  **Token 使用追踪**：系统级记录 prompt 和 completion token，用于审计和成本控制 (`llm_usage` 表)。
5.  **集中管理**：所有模型、API 密钥和 base URL 通过 `llm_models` 数据库表管理，支持优先级选择。

### 4.6 A股趋势分析 (v1.8+)

自动化的 A 股（中国股市）趋势分析系统：

1.  **多源新闻聚合**：从三个来源收集市场相关新闻 (news_articles, breaking_stream_raw, twitter_stream_raw)。
2.  **语义过滤**：使用 LLM 过滤和分析相关市场新闻。
3.  **两阶段分析**：
    - **盘前分析 (8:30)**：分析过去 24 小时新闻预测每日趋势。
    - **盘中分析 (14:30)**：根据午间新闻更新预测。
4.  **预测追踪**：在 `astock_predictions` 表中存储预测结果并进行准确率追踪。
5.  **多渠道推送**：支持 Telegram 和钉钉通知。

### 4.7 One-Pass 框架 (v1.9.0+)

将多个处理步骤合并为单个 LLM 调用的通用统一 AI 分析框架：

1.  **架构**：
    - **配置驱动**：每个处理器都有可配置的 `OnePassConfig`，包含提示模板、响应模型和上下文提供者。
    - **可插拔提供者**：内置 `recent_events`、`active_stories` 和 `RAG` 上下文检索提供者。
    - **环境覆盖**：所有提示都可通过环境变量自定义。

2.  **优势**：
    - **减少 API 调用**：将分类、评分、聚类合并为单个请求。
    - **Token 优化**：可配置的上下文限制减少提示大小。
    - **一致性**：所有处理器（突发、推特、每日）统一架构。

3.  **处理器**：
    - **BreakingProcessor**：分类 + 评分 + 事件聚类 + 故事匹配。
    - **TwitterProcessor**：分类 + 评分 + 事件匹配。
    - **ContentProcessor**：批量分类 + 摘要生成。

### 4.8 API 接口

所有非 webhook 接口都需要 `X-API-Key` 头认证。

| 接口 | 方法 | 说明 |
|---|---|---|
| `/trigger/fetch` | POST | 触发新闻抓取 |
| `/trigger/process` | POST | 触发 LLM 分类 |
| `/trigger/summary` | POST | 触发每日摘要 |
| `/trigger/kg_extract`| POST | 触发知识图谱抽取 |
| `/trigger/sync/rag` | POST | 触发 RAGFlow 同步 |
| `/trigger/twitter_crawl` | POST | 触发推特抓取 |
| `/analyze/trends` | POST | 生成趋势分析报告 |
| `/health` | GET | 健康检查 |
| `/dingtalk/callback` | POST | 钉钉 webhook 回调 |

## 5. 配置说明

所有设置通过 `.env` 管理。主要参数：

### 数据库 & LLM
| 变量 | 说明 | 默认值 |
|---|---|---|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | PostgreSQL 连接 | `localhost:5432` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME` | LLM 提供商配置（备用，主要来自数据库）| DeepSeek |

### 推送渠道与路由 (v1.6+, v1.9.0+)
| 变量 | 说明 |
|---|---|
| `TG_ROBOTS` | Telegram 机器人，JSON 格式的合并 `bot_token`，每聊天细粒度控制 (enable_daily, enable_breaking, enable_twitter, *_template) |
| `DING_ROBOTS` | 钉钉机器人，每个机器人独立模板和启用/禁用开关 |

### One-Pass 框架 (v1.9.0+)
| 变量 | 说明 |
|---|---|
| `PROMPT_BREAKING_ONEPASS` | 突发新闻 One-Pass 处理提示 |
| `PROMPT_TWITTER_ONEPASS` | 推特 One-Pass 处理提示 |
| `PROMPT_DAILY_ONEPASS` | 每日新闻 One-Pass 处理提示 |
| `BREAKING_CONTEXT_RECENT_EVENTS` | LLM 上下文中最近事件数量（默认：3）|
| `BREAKING_CONTEXT_ACTIVE_STORIES` | LLM 上下文中活跃故事数量（默认：10）|

### 突发新闻子系统
| 变量 | 说明 | 默认值 |
|---|---|---|
| `ENABLE_BREAKING_NEWS` | 总开关 | `True` |
| `BREAKING_IMPACT_THRESHOLD` | 推送告警最低评分 | `80` |
| `BREAKING_FETCH_INTERVAL_MINUTES` | RSS 轮询间隔 | `5` |
| `BREAKING_PUSH_TELEGRAM` | 启用 Telegram 告警 | `True` |
| `BREAKING_PUSH_DINGTALK` | 启用钉钉告警 | `True` |
| `BREAKING_PROCESSOR_CONCURRENCY` | 最大并行 LLM 任务数 | `6` |
| `BREAKING_PROCESSOR_BATCH_SIZE` | 每批流数量 | `10` |
| `BREAKING_STORY_LOOKBACK_DAYS` | 故事聚类历史窗口 | `10` |

### 推特情报子系统 (v1.7+)
| 变量 | 说明 | 默认值 |
|---|---|---|
| `ENABLE_TWITTER_ALERTS` | 推特监测总开关 | `True` |
| `TWITTER_PUSH_TELEGRAM` | 启用推特告警到 Telegram | `True` |
| `TWITTER_PUSH_DINGTALK` | 启用推特告警到钉钉 | `True` |
| `TWITTER_CRAWL_INTERVAL_MINUTES` | 推特抓取间隔 | `15` |
| `TWITTER_PROCESSOR_CONCURRENCY` | 最大并行 LLM 任务数 | `3` |
| `TWITTER_PROCESSOR_BATCH_SIZE` | 每 LLM 请求推文数 | `10` |
| `PROMPT_TWITTER_BATCH_TRIAGE` | 推文分类 LLM 提示 | (见 config.py) |

### A股分析子系统 (v1.8+)
| 变量 | 说明 | 默认值 |
|---|---|---|
| `ENABLE_ASTOCK_ANALYSIS` | 启用 A股分析 | `True` |
| `ASTOCK_PRE_MARKET_HOUR` | 盘前分析小时 | `8` |
| `ASTOCK_PRE_MARKET_MINUTE` | 盘前分析分钟 | `30` |
| `ASTOCK_INTRADAY_HOUR` | 盘中分析小时 | `14` |
| `ASTOCK_INTRADAY_MINUTE` | 盘中分析分钟 | `30` |
| `ASTOCK_PUSH_TELEGRAM` | 启用 A股告警到 Telegram | `True` |
| `ASTOCK_PUSH_DINGTALK` | 启用 A股告警到钉钉 | `True` |
| `ASTOCK_NEWS_HOURS` | 新闻回溯小时数 | `24` |

### 调度器
| 变量 | 说明 | 默认值 |
|---|---|---|
| `SUMMARY_HOUR` | 摘要 cron 小时（逗号分隔）| `0,12` |
| `SUMMARY_MINUTE` | 摘要 cron 分钟 | `0` |
| `KG_EXTRACT_INTERVAL_MINUTES` | 知识图谱抽取间隔 | `15` |

## 6. 前端

OmniDigest 前端是一个基于 Vue 3 + Vite 的单页应用，提供可视化仪表板。

### 6.1 技术栈
- **Vue 3** - 渐进式前端框架
- **Vite** - 现代构建工具
- **Vue Router** - 客户端路由
- **Axios** - HTTP 请求库
- **Chart.js + vue-chartjs** - 数据可视化

### 6.2 前端构建

```bash
# 安装依赖
cd frontend
npm install

# 开发模式
npm run dev

# 生产构建
npm run build

# 预览构建结果
npm run preview
```

### 6.3 Docker 部署

使用 docker-compose 进行部署：

```bash
docker-compose up -d
```

### 6.4 环境变量

前端使用 Vite，环境变量以 `VITE_` 开头：

| 变量 | 说明 |
|---|---|
| `VITE_API_URL` | 生产环境 API 地址（通过 Nginx 代理时留空） |

### 6.5 PWA 支持

前端支持 PWA 安装：
- Service Worker 缓存静态资源
- 可添加到主屏幕
- 支持离线访问

### 6.6 Nginx 配置

生产环境通过 Nginx 反向代理：
- `/api` -> 后端 API (port 8080)
- 静态文件 -> 前端构建产物

## 7. 详细文档

- [变更日志](docs/change_log.md) — 版本历史与发布说明
- [Python 注释标准](docs/PYTHON_COMMENTING_STANDARD.md) — 双语文档字符串约定

---

## 8. 许可证

MIT 许可证

版权所有 (c) 2026 OmniDigest

特此免费授予获得本软件及相关文档文件（"软件"）副本的任何人不受限制地处理本软件的权利，包括但不限于使用、复制、修改、合并、发布、分发、再许可和/或出售本软件副本，并允许获得本软件的人员在满足以下条件的情况下这样做：

上述版权声明和本许可声明应包含在本软件的所有副本或重要部分中。

本软件按"原样"提供，不提供任何明示或暗示的保证，包括但不限于对适销性、特定用途适用性和非侵权的保证。在任何情况下，作者或版权持有人均不对任何索赔、损害或其他责任承担责任，无论是在合同、侵权或其他诉讼中，均由本软件或本软件的使用或其他交易引起或与之相关。

---

## 9. 贡献指南

欢迎贡献！请随时提交 Pull Request。

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request
