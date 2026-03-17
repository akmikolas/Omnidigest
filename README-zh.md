# <img src="frontend/public/favicon.svg" width="48" align="center"/> OmniDigest (万象简报)

<div align="center">

[![许可: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 版本](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/Vue-3+-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![版本](https://img.shields.io/badge/Version-2.3.2-6366f1.svg)](https://github.com/akmikolas/Omnidigest)

*自动化 AI 驱动的新闻聚合、分类与摘要系统，具备实时情报监测能力*

[**English**](./README.md) | [**快速开始**](#2-快速开始) | [**功能特性**](#4-核心功能) | [**部署**](#22-docker-推荐)

</div>

---

## 1. 概述

OmniDigest 是一个高度自动化的 AI 驱动的新闻情报平台，彻底改变您获取和分析全球新闻的方式。它从多个来源聚合内容，使用大语言模型进行智能分类，并提供个性化的每日摘要和实时突发新闻告警。

### 架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OmniDigest 架构                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   RSS 订阅源│    │   Twitter   │    │  自定义数据  │    │   A股市场   │  │
│  │   (25+)     │    │   (GraphQL) │    │    源       │    │    数据     │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │          │
│         └──────────────────┴────────┬────────┴──────────────────┘          │
│                                    ▼                                         │
│                    ┌───────────────────────────────┐                        │
│                    │      One-Pass LLM 引擎      │                        │
│                    │   (分类与评分)               │                        │
│                    └───────────────────────────────┘                        │
│                                    │                                         │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐     │
│  │  每日简报    │           │   突发新闻   │           │   知识图谱   │     │
│  │   流水线    │           │    流水线    │           │    流水线    │     │
│  └──────┬──────┘           └──────┬──────┘           └──────┬──────┘     │
│         │                        │                        │               │
│         ▼                        ▼                        ▼               │
│  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐     │
│  │  Telegram   │           │   实时告警   │           │   Dgraph    │     │
│  │   钉钉      │           │    推送      │           │    存储      │     │
│  └─────────────┘           └─────────────┘           └─────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 数据流水线

| 流水线 | 版本 | 说明 |
|--------|------|------|
| **每日简报** | v1.0+ | 定时 RSS 抓取 → LLM 分类 → AI 摘要 → 多平台推送 |
| **突发新闻** | v1.3+ | 高频轮询 → One-Pass 分类 → 语义去重 → 实时告警 |
| **推特情报** | v1.7+ | GraphQL 抓取 → 批量分类 → 影响监测 → 精细路由 |
| **知识图谱** | v1.5+ | 三元组抽取 → Dgraph 存储 → 实体消解 |
| **A股分析** | v1.8+ | 多源聚合 → 趋势分析 → 市场预测 |

---

## 2. 快速开始

### 2.1 环境要求

- **Docker & Docker Compose**: [安装 Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Python 3.9+**（本地开发用）
- **PostgreSQL 15+**（包含在 docker-compose 中）
- **Redis**（可选，用于缓存）
- **Dgraph**（可选，用于知识图谱）

### 2.2 Docker（推荐）

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

# 5. 访问应用
# 前端：http://localhost:3000
# API：http://localhost:8080/api/health
```

### 2.3 本地开发

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装依赖
cd backend
pip install -e .

# 3. 通过 Docker 启动 PostgreSQL
docker run -d --name omnidigest_postgres \
  -e POSTGRES_USER=omnidigest \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=omnidigest \
  -p 5432:5432 \
  postgres:15-alpine

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入配置

# 5. 启动应用
python -m omnidigest.main

# 6. 启动前端（另一终端）
cd frontend
npm install
npm run dev
```

### 2.4 验证安装

```bash
# 检查 API 健康状态
curl http://localhost:8080/api/health

# 预期返回：
# {"status":"ok","scheduler_running":true}

# 访问前端：http://localhost:3000
```

---

## 3. 项目结构

```
.
├── backend/                  # Python 后端 (OmniDigest)
│   ├── src/omnidigest/     # 核心包
│   │   ├── api/            # FastAPI 路由与依赖
│   │   ├── cli/            # CLI 命令处理器
│   │   ├── core/           # 基础设施（配置、数据库、LLM）
│   │   ├── domains/        # 领域业务模块
│   │   │   ├── ingestion/  # RSS 与 Twitter 数据获取
│   │   │   ├── breaking_news/  # 突发新闻流水线
│   │   │   ├── daily_digest/   # 每日摘要处理
│   │   │   ├── knowledge_graph/ # Dgraph 三元组抽取
│   │   │   └── analysis/   # A 股市场分析
│   │   ├── jobs/           # 后台调度器
│   │   ├── migrations/     # 数据库迁移
│   │   ├── notifications/  # 多平台推送
│   │   ├── templates/      # Jinja2 通知模板
│   │   ├── main.py        # 应用入口
│   │   ├── manage.py      # CLI 管理工具
│   │   └── config.py      # 配置
│   ├── pyproject.toml     # Python 包配置
│   ├── requirements.txt   # 依赖
│   ├── Makefile          # CLI 快捷方式
│   └── Dockerfile        # 容器构建
├── frontend/                 # Vue 3 + Vite 前端
│   ├── src/               # 前端源码
│   │   ├── views/         # 页面组件
│   │   ├── api/           # API 客户端
│   │   └── router/        # Vue Router
│   ├── public/            # 静态资源与 Logo
│   ├── package.json       # 依赖
│   ├── vite.config.js    # Vite 配置
│   └── Dockerfile        # 容器构建
├── docs/                    # 文档
├── docker-compose.yml       # 容器编排
└── README.md              # 本文件
```

---

## 4. 核心功能

### 4.1 每日简报流水线

完整的自动化新闻处理工作流：

1. **智能抓取** - 并行 RSS 抓取，自动禁用失败源
2. **One-Pass 分类** - 统一 LLM 批量分类为 7 个类别
3. **AI 摘要** - 双语 Jinja2 模板，支持 Telegram HTML 与钉钉 Markdown
4. **自动清理** - 每日删除低质量文章

### 4.2 突发新闻系统

具备企业级可靠性的实时新闻告警流水线：

- **高频轮询** - 监控 25+ 国际媒体来源
- **One-Pass 分类** - 单次 LLM 调用完成分类、评分、聚类
- **语义去重** - 事件级聚类消除重复
- **交叉验证** - 故事需 2+ 独立来源才触发告警
- **影响评分** - 0-100 分，仅 >80 分触发即时告警

### 4.3 推特情报

监控全球影响者和世界领导人：

- **GraphQL 抓取** - 绕过 API 限制，带账户池管理
- **批量处理** - 每请求 10 条推文，成本效率最大化
- **精细路由** - 每个机器人独立启用/禁用和自定义模板
- **影响追踪** - 监控 16+ 高影响力账户

### 4.4 知识图谱

实体和关系抽取流水线：

- **三元组抽取** - 实体（人、组织、地点）+ 关系
- **Dgraph 存储** - 双向遍历，支持双边
- **实体消解** - 自动去重和合并
- **自动抽取** - 每 15 分钟自动运行

### 4.5 A 股市场分析

自动化的中国股市趋势分析：

- **多源聚合** - 新闻文章、突发流、推特
- **语义过滤** - LLM 驱动的市场新闻过滤
- **两阶段分析** - 盘前 (8:30) + 盘中 (14:30)
- **准确率追踪** - 预测历史与准确率指标

### 4.6 One-Pass 框架

通用统一 AI 分析框架：

```python
# 将多个处理步骤合并为单次 LLM 调用
- 分类 + 评分 + 聚类 → 一次请求
- 可配置上下文提供者（最近事件、活跃故事、RAG）
# 环境变量提示词覆盖
```

---

## 5. 配置说明

所有设置通过 `.env` 文件管理：

### 必填配置

```bash
# 数据库
DB_HOST=postgres
DB_PORT=5432
DB_USER=omnidigest
DB_PASSWORD=your_secure_password
DB_NAME=omnidigest

# LLM（至少一个提供商）
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

# 通知
TG_ROBOTS='[{"bot_token": "...", "chat_id": "...", ...}]'
DING_ROBOTS='[{"token": "...", ...}]'
```

### 可选配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `KG_ENABLED` | 启用知识图谱 | `false` |
| `REDIS_ENABLED` | 启用 Redis 缓存 | `true` |
| `ENABLE_BREAKING_NEWS` | 启用突发新闻 | `true` |
| `ENABLE_TWITTER_ALERTS` | 启用推特监测 | `true` |
| `ENABLE_ASTOCK_ANALYSIS` | 启用 A 股分析 | `true` |

---

## 6. Makefile 命令

```bash
make help              # 显示所有命令
make db-init           # 初始化数据库
make db-migrate        # 运行迁移
make rss-add URL=...   # 添加 RSS 源
make trigger-summary   # 触发每日摘要
make cleanup           # 清理低质量文章
make test-tg           # 测试 Telegram 推送
make test-dingtalk     # 测试钉钉推送
make test-push         # 测试全平台推送
```

---

## 7. API 接口

所有接口需要 `X-API-Key` 头认证。

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/trigger/fetch` | POST | 触发新闻抓取 |
| `/api/trigger/process` | POST | 触发 LLM 分类 |
| `/api/trigger/summary` | POST | 触发每日摘要 |
| `/api/trigger/kg_extract` | POST | 触发知识图谱抽取 |
| `/api/stats/overview` | GET | 系统统计 |
| `/api/sources/rss` | GET/POST | RSS 源管理 |
| `/api/config` | GET/PUT | 配置管理 |
| `/api/kg/*` | GET | 知识图谱查询 |

---

## 8. 前端

现代 Vue 3 + Vite 单页应用，包含：

- **仪表板** - 系统概览与统计
- **订阅源** - RSS 源管理
- **配置** - 系统配置
- **知识图谱** - 交互式实体可视化
- **Token 统计** - LLM 使用量追踪
- **PWA 支持** - 可安装的网页应用

```bash
cd frontend
npm install
npm run dev     # 开发：http://localhost:3000
npm run build   # 生产构建
```

---

## 9. 技术栈

<div align="center">

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI, Python 3.9+, Uvicorn |
| 数据库 | PostgreSQL 15+, Dgraph |
| 缓存 | Redis 8+ |
| AI/ML | OpenAI, Claude, DeepSeek, DashScope |
| 前端 | Vue 3, Vite, Chart.js |
| 部署 | Docker, Docker Compose |

</div>

---

## 10. 文档

- [变更日志](./docs/change_log.md) - 版本历史
- [Python 注释标准](./docs/PYTHON_COMMENTING_STANDARD.md) - 双语文档字符串约定
- [Dgraph 查询](./docs/dgraph_queries.md) - 知识图谱查询示例

---

## 11. 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE)。

---

## 12. 贡献指南

欢迎贡献！请随时提交 Pull Request。

```bash
# 1. Fork 仓库
# 2. 创建功能分支
git checkout -b feature/amazing-feature
# 3. 提交更改
git commit -m 'Add amazing feature'
# 4. 推送到分支
git push origin feature/amazing-feature
# 5. 打开 Pull Request
```

---

<div align="center">

*版本 2.3.2 | 最后更新：2026-03-17*

**OmniDigest** - 您的 AI 驱动的新闻情报平台

</div>
