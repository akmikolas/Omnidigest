# OmniDigest

[中文 README](./README-zh.md)

OmniDigest is a fully automated, AI-powered news aggregation, classification, and summarization backend with real-time intelligence monitoring.

**Core Pipeline (v1.0+)**: Scheduled RSS Crawling → PostgreSQL → One-Pass LLM Classification & Scoring → AI Daily Summary → Multi-Platform Push (Telegram / DingTalk)

**Breaking News Pipeline (v1.3+)**: High-Intensity RSS Polling → One-Pass LLM Triage → Semantic Deduplication → Story Timeline Mapping & Cross-Verification → Real-Time Push Alerts

**Twitter Intelligence Pipeline (v1.7+)**: GraphQL Scraping → One-Pass LLM Batch Triage → Influence Monitoring → Granular Alert Routing

**Knowledge Graph Pipeline (v1.5+)**: Continuous Triple Extraction → Dgraph Storage → Entity Resolution → Bi-directional Traversal

**A-Share Market Analysis Pipeline (v1.8+)**: Multi-Source News Aggregation → Semantic Filtering → One-Pass LLM Trend Analysis → Pre-Market & Intraday Predictions → Accuracy Tracking

*Latest release: v2.3.2 (2026-03-17) - Auto Database Initialization*
*Latest stable release: v2.3.2 (2026-03-17)*

## 1. Project Structure (v1.9.0+ Domain-Driven Architecture)

```text
.
├── src/omnidigest/            # Core source package
│   ├── api/                   # FastAPI routes & Dependencies (router, deps, auth)
│   ├── cli/                   # CLI command handlers (db, rss, jobs, auth, rag, kg, twitter, tests, lint)
│   ├── core/                  # Infrastructure (Config, Database Connection, LLM Management)
│   │   └── onepass.py       # Generic One-Pass framework for unified AI analysis
│   ├── domains/               # Feature-based Domain Modules
│   │   ├── ingestion/         # Data ingestion domain
│   │   │   ├── rss/          # Standard & breaking RSS crawling & data access
│   │   │   └── twitter/      # Twitter/X GraphQL scraping & data access
│   │   ├── breaking_news/     # Fast-lane polling, One-Pass triage, clustering & story timelines
│   │   ├── daily_digest/     # Daily summary processing logic (One-Pass)
│   │   │   └── models.py     # Pydantic models for structured output
│   │   ├── analysis/          # Trend analysis based on RAG (A-Stock, Market Data)
│   │   ├── knowledge_base/    # RAGFlow client and syncing
│   │   ├── knowledge_graph/    # Dgraph triple extraction & resolution
│   │   ├── twitter/          # Twitter intelligence processing & alerting (One-Pass)
│   │   │   └── models.py     # Pydantic models for structured output
│   │   └── auth/              # API Keys and authentication operations
│   ├── jobs/                  # Background scheduler setup (daily, breaking, twitter, kg)
│   ├── migrations/            # SQL schema migration scripts
│   ├── notifications/         # Multi-platform push dispatcher (Telegram/DingTalk)
│   ├── templates/             # Jinja2 notification templates
│   ├── main.py                # Application entry (FastAPI + scheduler)
│   └── manage.py              # CLI management tool entry
├── tests/                     # Test suite & diagnostics
├── docs/                      # Documentation (ChangeLog, Standards)
├── frontend/                  # Vue 3 + Vite frontend application
│   ├── src/                   # Frontend source code
│   │   ├── views/           # Vue page components
│   │   └── main.js          # Frontend entry
│   ├── public/               # Static assets (favicon, icons)
│   ├── index.html            # HTML entry
│   ├── vite.config.js        # Vite configuration
│   └── package.json          # Frontend dependencies
├── Makefile                   # CLI shortcuts
├── Dockerfile                 # Multi-stage Docker build
├── docker-compose.yml         # Container orchestration
├── pyproject.toml             # Python package config
└── .env.example               # Environment variable template
```

## 2. Quick Start

### 2.1 Prerequisites

1. **Start database**:
   ```bash
   docker-compose up -d postgres
   ```

2. **Install dependencies**:
   ```bash
   pip install -e .
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys, DB credentials, and preferences
   ```

4. **Start the application** - Database tables are automatically created on first startup.
   ```bash
   docker-compose up -d
   ```

### 2.2 Run the System

**Docker (recommended)**:
```bash
docker-compose up -d
```

**Local development**:
```bash
python -m omnidigest.main
```

The API server starts at `http://0.0.0.0:8080`.

### 2.3 Installation from Scratch

This section describes how to set up OmniDigest from a fresh installation.

#### 2.3.1 Prerequisites

- **Docker & Docker Compose**: Install [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Python 3.11+** (for local development)
- **PostgreSQL 15+** (included in docker-compose)
- **Redis** (optional, for caching)
- **Dgraph** (optional, for Knowledge Graph)

#### 2.3.2 Quick Docker Setup (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/akmikolas/Omnidigest.git
cd omnidigest

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env with your configuration
# Required: DB_PASSWORD, LLM_API_KEY, TG_ROBOTS/DING_ROBOTS

# 4. Start all services
docker-compose up -d

# 5. Check status
docker-compose ps
```

#### 2.3.3 Local Development Setup

```bash
# 1. Install Python dependencies
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .

# 2. Start PostgreSQL via Docker
docker run -d --name omnidigest_postgres \
  -e POSTGRES_USER=omnidigest \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=omnidigest \
  -p 5432:5433 \
  postgres:15-alpine

# 3. Copy and configure environment
cp .env.example .env
# Edit .env with:
#   DB_HOST=localhost
#   DB_PORT=5432
#   DB_USER=omnidigest
#   DB_PASSWORD=your_password
#   DB_NAME=omnidigest

# 4. Initialize database
make db-init

# 5. Start the application
python -m omnidigest.main
```

#### 2.3.4 Required Configuration

Minimum required environment variables:

```bash
# Database
DB_HOST=postgres
DB_PORT=5432
DB_USER=omnidigest
DB_PASSWORD=your_secure_password
DB_NAME=omnidigest

# LLM (at least one provider)
# Option 1: OpenAI
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

# Or Option 2: Use database LLM providers table

# Notifications (Telegram and/or DingTalk)
TG_ROBOTS='[{"bot_token": "...", "chat_id": "...", ...}]'
DING_ROBOTS='[{"token": "...", ...}]'
```

#### 2.3.5 Optional Features

**Knowledge Graph (Dgraph)**:
```bash
KG_ENABLED=true
DGRAPH_ALPHA_URL=dgraph:9080
```

**Redis Caching**:
```bash
REDIS_ENABLED=true
REDIS_HOST=redis
REDIS_PORT=6379
```

#### 2.3.6 Verify Installation

```bash
# Check API health
curl http://localhost:8080/api/health

# Check database connection
curl http://localhost:8080/api/stats/overview

# Access frontend
# Open http://localhost:3000 in browser
```

---

## 3. Makefile Commands

All common operations are available via `make`:

| Command | Description |
|---|---|
| `make db-init` | Initialize database schema |
| `make db-migrate` | Run all pending database migrations |
| `make rss-add URL=...` | Add a new RSS feed |
| `make rss-check` | List disabled/failed feeds |
| `make trigger-summary` | Manually trigger daily summary |
| `make cleanup` | Remove low-quality articles |
| `make test-tg` | Test breaking news push to Telegram |
| `make test-dingtalk` | Test breaking news push to DingTalk |
| `make test-push` | Test push to all platforms |
| `make lint` | Lint bilingual docstrings |
| `make help` | Show all available commands |

For the full list, run `make help`.

## 4. Core Features

### 4.1 Daily Digest Pipeline (v1.0+, v1.9+ One-Pass)

1.  **Crawling** (`NewsCrawler`): Parallel RSS fetching with 15s timeout and auto-disable for persistently failing feeds.
2.  **One-Pass Processing** (`ContentProcessor`): Unified LLM-powered batch classification into 7 categories using the generic OnePass framework. Consolidates batch processing into single structured `instructor` requests for maximum efficiency.
3.  **Knowledge Base**: Optional RAGFlow integration for full-text vectorization (`RAGFLOW_ENABLED`).
4.  **Summary & Push** (`AnalysisService` → `NotificationService`): Configurable cron schedule, bilingual Jinja2 templates, simultaneous Telegram HTML + DingTalk Markdown delivery.
5.  **Auto Cleanup**: Daily removal of articles scoring below threshold.

### 4.2 Breaking News System (v1.3+, v1.9+ One-Pass)

A completely independent, real-time news alert pipeline:

1.  **Breaking Crawler**: Polls 25+ international media RSS sources (BBC, CNN, NYT, Reuters, Al Jazeera, SCMP, 财新网, 华尔街见闻, etc.) at a configurable interval.
2.  **One-Pass LLM Triage**: Each raw stream is evaluated by the generic OnePass framework to perform triage, scoring, clustering, and story matching in a single LLM call.
3.  **Semantic Deduplication (Event Level)**: When multiple sources report on the same event, the LLM clusters them into a single event.
4.  **Story Timeline Mapping & Cross-Verification (Story Level)**: Events are dynamically grouped into overarching `Stories` (narrative arcs) with configurable lookback window (`BREAKING_STORY_LOOKBACK_DAYS`). A story must be cross-verified by at least 2 independent sources before pushing, drastically reducing false positives.
5.  **Impact Scoring**: Stories are scored 0-100. Only stories exceeding `BREAKING_IMPACT_THRESHOLD` trigger instant alerts, which include a robust timeline of child events spanning days or years with direct source hyperlinks.
6.  **Real-Time Alerting** (`BreakingAlerter`): Continuously monitors the database and pushes verified, high-impact stories to configured platforms with HTML (Telegram) and Markdown (DingTalk) formatted notifications.

### 4.3 Twitter Intelligence & Influence Monitoring (v1.7+, v1.9+ One-Pass)

A high-efficiency monitoring system for global influencers and world leaders:

1.  **Batch Ingestion**: Uses GraphQL scraping to bypass API limits with high-water mark tracking and account pool management.
2.  **One-Pass Batch Triage**: Uses the generic OnePass framework to perform triage, scoring, and event matching in a single LLM call. Processes 10 tweets per request for maximum cost efficiency.
3.  **Granular Alert Routing**: Per-robot enabled/disabled states (`enable_twitter`) and custom templates (`twitter_template`) for Telegram and DingTalk.
4.  **Global Control Switches**: Top-level configuration via `ENABLE_TWITTER_ALERTS`, `TWITTER_PUSH_TELEGRAM`, and `TWITTER_PUSH_DINGTALK`.
5.  **Influential Leader Monitoring**: Tracks 16+ high-profile accounts (World Leaders, News Wires, Global Organizations) for real-time policy and sentiment tracking.
6.  **DingTalk Compliance**: Includes "新闻" keyword in alerts to meet DingTalk robot requirements.

### 4.4 Knowledge Graph Extraction Engine (v1.5+)

A systematic entity and relationship extraction pipeline built on top of Dgraph:

1.  **Triple Extraction**: Continuously extracts Entities (Person, Organization, Location) and Relations from incoming news articles using LLMs with political alignment tracking.
2.  **Idempotent Mutations**: Batches node and edge mutations inside single transactions to eliminate race conditions and graph corruption, with double-edge support for bi-directional traversal.
3.  **Entity Resolution**: Supports automatic deduplication and merging of identical entities across the graph.
4.  **LLM Failover Integration**: Leverages the centralized `LLMManager` for automatic model failover and retry logic.
5.  **Trigger Mechanisms**: Runs every 15 minutes automatically, fully controllable via CLI (`manage.py kg extract`) and API (`/trigger/kg_extract`) with thread-safe concurrency locks.

### 4.5 LLM Management & Robustness (v1.5+)

A robust multi-model management system ensuring high availability and provider compatibility:

1.  **Automatic Failover System**: Dynamic model selection with automatic retries and deactivation after 5 consecutive failures (`llm_models` table).
2.  **Provider Compatibility**: Centralized LLM provider detection (DashScope/Qwen) with automatic mode switching for `instructor` (Mode.JSON / Mode.MD_JSON).
3.  **Robust JSON Parsing**: System-wide `_clean_json_output` utility to strip Markdown blocks and handle XML-like noise from certain models.
4.  **Token Usage Tracking**: System-wide logging of prompt and completion tokens for audit and cost control (`llm_usage` table).
5.  **Centralized Management**: All models, API keys, and base URLs are managed via the `llm_models` database table with priority-based selection.

### 4.6 A-Share Market Analysis (v1.8+)

An automated A-share (China stock market) trend analysis system:

1.  **Multi-Source News Aggregation**: Collects market-relevant news from three sources (news_articles, breaking_stream_raw, twitter_stream_raw).
2.  **Semantic Filtering**: Uses LLM to filter and analyze relevant market news.
3.  **Two-Stage Analysis**:
    - **Pre-Market Analysis (8:30)**: Analyzes past 24h news to predict daily trend.
    - **Intraday Analysis (14:30)**: Updates predictions based on midday news.
4.  **Prediction Tracking**: Stores predictions in `astock_predictions` table with accuracy tracking.
5.  **Multi-Channel Push**: Supports Telegram and DingTalk notifications.

### 4.7 One-Pass Framework (v1.9.0+)

A generic framework for unified AI analysis that consolidates multiple processing steps into a single LLM call:

1.  **Architecture**:
    - **Config-Driven**: Each processor has a configurable `OnePassConfig` with prompt template, response model, and context providers.
    - **Pluggable Providers**: Built-in providers for `recent_events`, `active_stories`, and `RAG` context retrieval.
    - **Environment Override**: All prompts can be customized via environment variables.

2.  **Benefits**:
    - **Reduced API Calls**: Combines triage, scoring, clustering into single request.
    - **Token Optimization**: Configurable context limits reduce prompt size.
    - **Consistency**: Unified architecture across all processors (Breaking, Twitter, Daily).

3.  **Processors**:
    - **BreakingProcessor**: Triage + Scoring + Event Clustering + Story Matching.
    - **TwitterProcessor**: Triage + Scoring + Event Matching.
    - **ContentProcessor**: Batch classification + Summary generation.

### 4.8 API Endpoints

All non-webhook endpoints require `X-API-Key` header authentication.

| Endpoint | Method | Description |
|---|---|---|
| `/trigger/fetch` | POST | Trigger news crawling |
| `/trigger/process` | POST | Trigger LLM classification |
| `/trigger/summary` | POST | Trigger daily summary |
| `/trigger/kg_extract`| POST | Trigger Knowledge Graph extraction |
| `/trigger/sync/rag` | POST | Trigger RAGFlow sync |
| `/trigger/twitter_crawl` | POST | Trigger Twitter crawling |
| `/analyze/trends` | POST | Generate trend analysis report |
| `/health` | GET | Health check |
| `/dingtalk/callback` | POST | DingTalk webhook callback |

## 5. Configuration

All settings are managed via `.env`. Key parameters:

### Database & LLM
| Variable | Description | Default |
|---|---|---|
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | PostgreSQL connection | `localhost:5432` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME` | LLM provider config (fallback, primary from database) | DeepSeek |

### Push Channels & Routing (v1.6+, v1.9.0+)
| Variable | Description |
|---|---|
| `TG_ROBOTS` | Telegram bots with merged `bot_token` in JSON, per-chat granular control (enable_daily, enable_breaking, enable_twitter, *_template) |
| `DING_ROBOTS` | DingTalk robot(s) with per-robot template and enabled/disabled toggle |

### One-Pass Framework (v1.9.0+)
| Variable | Description |
|---|---|
| `PROMPT_BREAKING_ONEPASS` | Prompt for Breaking News One-Pass processing |
| `PROMPT_TWITTER_ONEPASS` | Prompt for Twitter One-Pass processing |
| `PROMPT_DAILY_ONEPASS` | Prompt for Daily News One-Pass processing |
| `BREAKING_CONTEXT_RECENT_EVENTS` | Number of recent events in LLM context (default: 3) |
| `BREAKING_CONTEXT_ACTIVE_STORIES` | Number of active stories in LLM context (default: 10) |

### Breaking News Subsystem
| Variable | Description | Default |
|---|---|---|
| `ENABLE_BREAKING_NEWS` | Master switch | `True` |
| `BREAKING_IMPACT_THRESHOLD` | Min score for push alert | `80` |
| `BREAKING_FETCH_INTERVAL_MINUTES` | RSS polling interval | `5` |
| `BREAKING_PUSH_TELEGRAM` | Enable Telegram alerts | `True` |
| `BREAKING_PUSH_DINGTALK` | Enable DingTalk alerts | `True` |
| `BREAKING_PROCESSOR_CONCURRENCY` | Max parallel LLM tasks | `6` |
| `BREAKING_PROCESSOR_BATCH_SIZE` | Streams per batch | `10` |
| `BREAKING_STORY_LOOKBACK_DAYS` | Historical window for story clustering | `10` |

### Twitter Intelligence Subsystem (v1.7+)
| Variable | Description | Default |
|---|---|---|
| `ENABLE_TWITTER_ALERTS` | Master switch for Twitter monitoring | `True` |
| `TWITTER_PUSH_TELEGRAM` | Enable Twitter alerts to Telegram | `True` |
| `TWITTER_PUSH_DINGTALK` | Enable Twitter alerts to DingTalk | `True` |
| `TWITTER_CRAWL_INTERVAL_MINUTES` | Twitter crawling interval | `15` |
| `TWITTER_PROCESSOR_CONCURRENCY` | Max parallel LLM tasks | `3` |
| `TWITTER_PROCESSOR_BATCH_SIZE` | Tweets per LLM request | `10` |
| `PROMPT_TWITTER_BATCH_TRIAGE` | LLM prompt for tweet triage | (see config.py) |

### A-Share Analysis Subsystem (v1.8+)
| Variable | Description | Default |
|---|---|---|
| `ENABLE_ASTOCK_ANALYSIS` | Enable A股 analysis | `True` |
| `ASTOCK_PRE_MARKET_HOUR` | Pre-market analysis hour | `8` |
| `ASTOCK_PRE_MARKET_MINUTE` | Pre-market analysis minute | `30` |
| `ASTOCK_INTRADAY_HOUR` | Intraday analysis hour | `14` |
| `ASTOCK_INTRADAY_MINUTE` | Intraday analysis minute | `30` |
| `ASTOCK_PUSH_TELEGRAM` | Enable A股 alerts to Telegram | `True` |
| `ASTOCK_PUSH_DINGTALK` | Enable A股 alerts to DingTalk | `True` |
| `ASTOCK_NEWS_HOURS` | News lookback hours | `24` |

### Scheduler
| Variable | Description | Default |
|---|---|---|
| `SUMMARY_HOUR` | Summary cron hours (comma-separated) | `0,12` |
| `SUMMARY_MINUTE` | Summary cron minute | `0` |
| `KG_EXTRACT_INTERVAL_MINUTES` | Knowledge Graph extraction interval | `15` |

## 6. Frontend

OmniDigest frontend is a Vue 3 + Vite single-page application providing a visual dashboard.

### 6.1 Tech Stack
- **Vue 3** - Progressive frontend framework
- **Vite** - Modern build tool
- **Vue Router** - Client-side routing
- **Axios** - HTTP client
- **Chart.js + vue-chartjs** - Data visualization

### 6.2 Frontend Build

```bash
# Install dependencies
cd frontend
npm install

# Development mode
npm run dev

# Production build
npm run build

# Preview build
npm run preview
```

### 6.3 Docker Deployment

Deploy using docker-compose:

```bash
docker-compose up -d
```

### 6.4 Environment Variables

Frontend uses Vite, environment variables must be prefixed with `VITE_`:

| Variable | Description |
|---|---|
| `VITE_API_URL` | Production API URL (leave empty when using Nginx proxy) |

### 6.5 PWA Support

Frontend supports PWA installation:
- Service Worker caches static assets
- Add to home screen
- Offline access support

### 6.6 Nginx Configuration

Production environment uses Nginx reverse proxy:
- `/api` -> Backend API (port 8080)
- Static files -> Frontend build output

## 7. Documentation

- [Change Log](docs/change_log.md) — Version history and release notes
- [Python Commenting Standard](docs/PYTHON_COMMENTING_STANDARD.md) — Bilingual docstring conventions

---

## 8. License

MIT License

Copyright (c) 2026 OmniDigest

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 9. Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
