# <img src="frontend/public/favicon.svg" width="48" align="center"/> OmniDigest

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/Vue-3+-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![Version](https://img.shields.io/badge/Version-2.3.37-6366f1.svg)](https://github.com/akmikolas/Omnidigest)

*Automated AI-powered news aggregation, classification, and summarization system with real-time intelligence monitoring*

[**简体中文**](./README-zh.md) | [**Quick Start**](#2-quick-start) | [**Features**](#4-core-features) | [**Deploy**](#22-docker-recommended)

</div>

---

## 1. Overview

OmniDigest is a fully automated, AI-driven news intelligence platform that transforms the way you consume and analyze global news. It aggregates content from multiple sources, applies intelligent classification using Large Language Models, and delivers personalized daily summaries and real-time breaking news alerts.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OmniDigest Architecture                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   RSS Feeds │    │   Twitter   │    │  Custom     │    │  A-Share    │  │
│  │   (25+)     │    │   (GraphQL) │    │  Sources    │    │   Market    │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │          │
│         └──────────────────┴────────┬────────┴──────────────────┘          │
│                                    ▼                                         │
│                    ┌───────────────────────────────┐                        │
│                    │      One-Pass LLM Engine      │                        │
│                    │   (Classification & Scoring)  │                        │
│                    └───────────────────────────────┘                        │
│                                    │                                         │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐     │
│  │Daily Digest │           │  Breaking   │           │ Knowledge   │     │
│  │  Pipeline   │           │   News     │           │   Graph     │     │
│  └──────┬──────┘           └──────┬──────┘           └──────┬──────┘     │
│         │                        │                        │               │
│         ▼                        ▼                        ▼               │
│  ┌─────────────┐           ┌─────────────┐           ┌─────────────┐     │
│  │  Telegram   │           │  Real-Time  │           │   Dgraph    │     │
│  │  DingTalk   │           │   Alerts    │           │   Storage   │     │
│  │  Feishu     │           │             │           │             │     │
│  └─────────────┘           └─────────────┘           └─────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Pipelines

| Pipeline | Version | Description |
|----------|---------|-------------|
| **Daily Digest** | v1.0+ | Scheduled RSS crawling → LLM classification → AI summary → Multi-platform push |
| **Breaking News** | v1.3+ | High-frequency polling → One-Pass triage → Semantic deduplication → Real-time alerts |
| **Twitter Intelligence** | v1.7+ | GraphQL scraping → Batch triage → Influence monitoring → Granular routing |
| **Knowledge Graph** | v1.5+ | Continuous triple extraction → Dgraph storage → Entity resolution |
| **A-Share Analysis** | v1.8+ | Multi-source aggregation → Trend analysis → Market predictions |

---

## 2. Quick Start

### 2.1 One Command Startup (v2.3.37+)

```bash
# 1. Clone and enter
git clone https://github.com/akmikolas/Omnidigest.git
cd omnidigest

# 2. Copy dev config (edit LLM_API_KEY if needed)
cp .env.dev .env

# 3. Start infrastructure (one-time, runs indefinitely)
./dev-build.sh --infra

# 4. Build and launch the application
./dev-build.sh
```

On first launch, an API key is automatically generated and printed to the console:

```
============================================
  DEFAULT API KEY CREATED
  omni-init:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
============================================
```

Open `http://localhost:3000`, enter this key in the login modal, and you're ready to go.

**Automated bootstrap** (no manual CLI steps required):
- Database tables created automatically (including `api_keys`)
- Default API key generated
- LLM model auto-registered from `.env`
- System config seeded with defaults

### 2.2 Docker (Recommended)

```bash
# Clone and configure
git clone https://github.com/akmikolas/Omnidigest.git
cd omnidigest
cp .env.example .env

# Start all services
docker-compose -f docker-compose.infra.yml up -d   # infrastructure
docker-compose up -d --build                        # application

# Get auto-generated API key
docker-compose exec backend cat /data/init_api_key.txt

# Frontend: http://localhost:3000
# API: http://localhost:7080/api/health
```

### 2.3 Local Development

```bash
# Backend
cd backend
pip install -e .
cp ../.env.dev .env
python src/main.py

# Frontend (another terminal)
cd frontend
npm install
npm run dev
```

### 2.4 Verify Installation

```bash
# Check API health
curl http://localhost:7080/api/health
# → {"status":"ok","scheduler_running":false}

# Frontend at http://localhost:3000
```

---

## 3. dev-build.sh Commands

Unified build/test/deploy script for development and production:

```bash
./dev-build.sh                      # Build + start + health check (dev)
./dev-build.sh --backend-only       # Rebuild backend only
./dev-build.sh --frontend-only      # Rebuild frontend only
./dev-build.sh --skip-build         # Skip build, just start/test
./dev-build.sh --infra              # Start/restart infrastructure only
./dev-build.sh --down               # Stop app containers (keep infra)
./dev-build.sh --down-all           # Stop all containers
./dev-build.sh --release v2.3.37    # Build → test → push to Harbor
./dev-build.sh --release v2.3.37 --force  # Force overwrite Harbor tag
```

Infrastructure (PostgreSQL, Redis, Dgraph) runs separately via `docker-compose.infra.yml` and persists across app rebuilds.

---

## 4. Project Structure

```
.
├── backend/                     # Python backend (FastAPI)
│   ├── src/                     # Source code
│   │   ├── api/                 # FastAPI routes & dependencies
│   │   ├── cli/                 # CLI command handlers
│   │   ├── core/                # Infrastructure (Config, DB, LLM, Cache)
│   │   ├── domains/             # Feature-based domain modules
│   │   │   ├── ingestion/       # RSS & Twitter data ingestion
│   │   │   ├── breaking_news/   # Breaking news pipeline
│   │   │   ├── daily_digest/    # Daily summary processing
│   │   │   ├── knowledge_graph/ # Dgraph triple extraction
│   │   │   └── analysis/        # A-share market analysis
│   │   ├── jobs/                # Background scheduler
│   │   ├── migrations/          # Database migrations
│   │   ├── notifications/       # Multi-platform push
│   │   ├── templates/           # Jinja2 notification templates
│   │   ├── main.py              # Application entry
│   │   ├── manage.py            # CLI management tool
│   │   ├── bootstrap.py         # First-launch auto-initializer
│   │   └── config.py            # Configuration
│   ├── docker-entrypoint.sh     # Docker entrypoint (calls bootstrap)
│   ├── Dockerfile               # Container build
│   ├── Makefile                 # CLI shortcuts
│   └── requirements.txt         # Dependencies
├── frontend/                    # Vue 3 + Vite frontend
│   ├── src/views/               # Page components
│   ├── src/api/                 # API client
│   └── src/router/              # Vue Router
├── dev-build.sh                 # Unified build/test/deploy script
├── docker-compose.infra.yml     # Infrastructure only (long-running)
├── docker-compose.yml           # Application services
├── .env.dev                     # Dev environment config template
└── README.md                    # This file
```

---

## 5. Core Features

### 5.1 Daily Digest Pipeline

A complete automated news processing workflow:

1. **Intelligent Crawling** - Parallel RSS fetching with auto-disable for failing feeds
2. **One-Pass Classification** - Unified LLM batch classification into 7 categories
3. **AI Summarization** - Bilingual Jinja2 templates for Telegram HTML, DingTalk & Feishu Markdown
4. **Auto Cleanup** - Daily removal of low-quality articles

### 5.2 Breaking News System

Real-time news alert pipeline with enterprise-grade reliability:

- **High-Frequency Polling** - Monitors 25+ international media sources
- **One-Pass Triage** - Classification, scoring, clustering in single LLM call
- **Semantic Deduplication** - Event-level clustering to eliminate duplicates
- **Cross-Verification** - Story requires 2+ independent sources before alert
- **Impact Scoring** - 0-100 score, only >80 triggers instant alerts

### 5.3 Twitter Intelligence

Monitor global influencers and world leaders:

- **GraphQL Scraping** - Bypass API limits with account pool management
- **Batch Processing** - 10 tweets per LLM request for cost efficiency
- **Granular Routing** - Per-robot enable/disable and custom templates
- **Influence Tracking** - 16+ high-profile accounts monitored

### 5.4 Knowledge Graph

Entity and relationship extraction pipeline:

- **Triple Extraction** - Entities (Person, Organization, Location) + Relations
- **Dgraph Storage** - Bidirectional traversal with double-edge support
- **Entity Resolution** - Automatic deduplication and merging
- **Auto Extraction** - Runs every 15 minutes automatically

### 5.5 A-Share Market Analysis

Automated China stock market trend analysis:

- **Multi-Source Aggregation** - News articles, breaking stream, Twitter
- **Semantic Filtering** - LLM-powered market news filtering
- **Two-Stage Analysis** - Pre-market (8:30) + Intraday (14:30)
- **Accuracy Tracking** - Prediction history with accuracy metrics

### 5.6 One-Pass Framework

Generic unified AI analysis framework:

```python
# Consolidates multiple processing steps into single LLM call
- Triage + Scoring + Clustering → One Request
- Configurable context providers (recent events, active stories, RAG)
- Environment variable prompt overrides
```

---

## 6. Configuration

All settings via `.env` file:

### Required

```bash
# Database
DB_HOST=postgres
DB_PORT=5432
DB_USER=omnidigest
DB_PASSWORD=your_secure_password
DB_NAME=omnidigest

# LLM (at least one provider)
LLM_API_KEY=sk-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_NAME=gpt-4o-mini

# Notifications
TG_ROBOTS='[{"bot_token": "...", "chat_id": "...", ...}]'
DING_ROBOTS='[{"token": "...", ...}]'
FEISHU_ROBOTS='[{"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/...", "secret": "...", ...}]'
```

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `KG_ENABLED` | Enable Knowledge Graph | `false` |
| `REDIS_ENABLED` | Enable Redis caching | `true` |
| `ENABLE_BREAKING_NEWS` | Enable breaking news | `true` |
| `ENABLE_TWITTER_ALERTS` | Enable Twitter monitoring | `true` |
| `ENABLE_ASTOCK_ANALYSIS` | Enable A-share analysis | `true` |

---

## 7. Makefile Commands

```bash
make help              # Show all commands
make db-init           # Initialize database
make db-migrate        # Run migrations
make rss-add URL=...   # Add RSS feed
make trigger-summary   # Trigger daily summary
make cleanup           # Clean low-quality articles
make test-tg           # Test Telegram push
make test-dingtalk     # Test DingTalk push
make test-feishu       # Test Feishu push
make test-push         # Test all platforms
```

---

## 8. API Endpoints

All endpoints require `X-API-Key` header authentication (except health).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check (no auth) |
| `/api/bootstrap/status` | GET | First-launch bootstrap status (no auth) |
| `/api/trigger/fetch` | POST | Trigger news crawling |
| `/api/trigger/process` | POST | Trigger LLM classification |
| `/api/trigger/summary` | POST | Trigger daily summary |
| `/api/trigger/kg_extract` | POST | Trigger Knowledge Graph extraction |
| `/api/stats/overview` | GET | System statistics |
| `/api/sources/rss` | GET/POST | RSS source management |
| `/api/config` | GET/PUT | Configuration management |
| `/api/kg/*` | GET | Knowledge Graph queries |

---

## 9. Frontend

Modern Vue 3 + Vite SPA with:

- **Dashboard** - System overview and statistics
- **A-Stock** - A-share market analysis
- **Knowledge Graph** - Interactive entity visualization
- **Configuration** - Runtime config with dark mode and search
- **RSS Sources** - Feed management
- **Token Stats** - LLM usage tracking
- **PWA Support** - Installable web app

```bash
cd frontend
npm install
npm run dev     # Development: http://localhost:3000
npm run build   # Production build
```

---

## 10. Tech Stack

<div align="center">

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Python 3.9+, Uvicorn |
| Database | PostgreSQL 15+, Dgraph |
| Cache | Redis 8+ |
| AI/ML | OpenAI, Claude, DeepSeek, DashScope, MiniMax |
| Frontend | Vue 3, Vite, Chart.js, D3.js |
| Deployment | Docker, Docker Compose |

</div>

---

## 11. Documentation

- [Change Log](./docs/change_log.md) - Version history
- [Python Commenting Standard](./docs/PYTHON_COMMENTING_STANDARD.md) - Bilingual docstring conventions
- [Dgraph Queries](./docs/dgraph_queries.md) - Knowledge Graph query examples

---

## 12. License

MIT License - See [LICENSE](LICENSE) for details.

---

## 13. Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

```bash
# 1. Fork the repository
# 2. Create feature branch
git checkout -b feature/amazing-feature
# 3. Commit changes
git commit -m 'Add amazing feature'
# 4. Push to branch
git push origin feature/amazing-feature
# 5. Open Pull Request
```

---

<div align="center">

*Version 2.3.37 | Last Updated: 2026-05-29*

**OmniDigest** - Your AI-Powered News Intelligence Platform

</div>
