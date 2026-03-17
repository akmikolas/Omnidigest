# <img src="frontend/public/favicon.svg" width="48" align="center"/> OmniDigest

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/Vue-3+-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![Version](https://img.shields.io/badge/Version-2.3.2-6366f1.svg)](https://github.com/akmikolas/Omnidigest)

*Automated AI-powered news aggregation, classification, and summarization system with real-time intelligence monitoring*

[**简体中文**](./README-zh.md) | [**快速开始**](#2-quick-start) | [**功能特性**](#4-core-features) | [**部署**](#22-docker-recommended)

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

### 2.1 Prerequisites

- **Docker & Docker Compose**: [Install Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Python 3.9+** (for local development)
- **PostgreSQL 15+** (included in docker-compose)
- **Redis** (optional, for caching)
- **Dgraph** (optional, for Knowledge Graph)

### 2.2 Docker (Recommended)

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

# 5. Access the application
# Frontend: http://localhost:3000
# API: http://localhost:8080/api/health
```

### 2.3 Local Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
cd backend
pip install -e .

# 3. Start PostgreSQL via Docker
docker run -d --name omnidigest_postgres \
  -e POSTGRES_USER=omnidigest \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=omnidigest \
  -p 5432:5432 \
  postgres:15-alpine

# 4. Configure environment
cp .env.example .env
# Edit .env with your settings

# 5. Start the application
python -m omnidigest.main

# 6. Start frontend (in another terminal)
cd frontend
npm install
npm run dev
```

### 2.4 Verify Installation

```bash
# Check API health
curl http://localhost:8080/api/health

# Expected response:
# {"status":"ok","scheduler_running":true}

# Access frontend at http://localhost:3000
```

---

## 3. Project Structure

```
.
├── backend/                  # Python backend (OmniDigest)
│   ├── src/omnidigest/     # Core package
│   │   ├── api/            # FastAPI routes & dependencies
│   │   ├── cli/            # CLI command handlers
│   │   ├── core/           # Infrastructure (Config, DB, LLM)
│   │   ├── domains/        # Feature-based domain modules
│   │   │   ├── ingestion/  # RSS & Twitter data ingestion
│   │   │   ├── breaking_news/  # Breaking news pipeline
│   │   │   ├── daily_digest/   # Daily summary processing
│   │   │   ├── knowledge_graph/ # Dgraph triple extraction
│   │   │   └── analysis/   # A-share market analysis
│   │   ├── jobs/           # Background scheduler
│   │   ├── migrations/     # Database migrations
│   │   ├── notifications/  # Multi-platform push
│   │   ├── templates/      # Jinja2 notification templates
│   │   ├── main.py        # Application entry
│   │   ├── manage.py      # CLI management tool
│   │   └── config.py      # Configuration
│   ├── pyproject.toml     # Python package config
│   ├── requirements.txt   # Dependencies
│   ├── Makefile          # CLI shortcuts
│   └── Dockerfile        # Container build
├── frontend/                 # Vue 3 + Vite frontend
│   ├── src/               # Frontend source
│   │   ├── views/         # Page components
│   │   ├── api/           # API client
│   │   └── router/        # Vue Router
│   ├── public/            # Static assets & logos
│   ├── package.json       # Dependencies
│   ├── vite.config.js     # Vite config
│   └── Dockerfile         # Container build
├── docs/                    # Documentation
├── docker-compose.yml       # Container orchestration
└── README.md               # This file
```

---

## 4. Core Features

### 4.1 Daily Digest Pipeline

A complete automated news processing workflow:

1. **Intelligent Crawling** - Parallel RSS fetching with auto-disable for failing feeds
2. **One-Pass Classification** - Unified LLM batch classification into 7 categories
3. **AI Summarization** - Bilingual Jinja2 templates for Telegram HTML & DingTalk Markdown
4. **Auto Cleanup** - Daily removal of low-quality articles

### 4.2 Breaking News System

Real-time news alert pipeline with enterprise-grade reliability:

- **High-Frequency Polling** - Monitors 25+ international media sources
- **One-Pass Triage** - Classification, scoring, clustering in single LLM call
- **Semantic Deduplication** - Event-level clustering to eliminate duplicates
- **Cross-Verification** - Story requires 2+ independent sources before alert
- **Impact Scoring** - 0-100 score, only >80 triggers instant alerts

### 4.3 Twitter Intelligence

Monitor global influencers and world leaders:

- **GraphQL Scraping** - Bypass API limits with account pool management
- **Batch Processing** - 10 tweets per LLM request for cost efficiency
- **Granular Routing** - Per-robot enable/disable and custom templates
- **Influence Tracking** - 16+ high-profile accounts monitored

### 4.4 Knowledge Graph

Entity and relationship extraction pipeline:

- **Triple Extraction** - Entities (Person, Organization, Location) + Relations
- **Dgraph Storage** - Bidirectional traversal with double-edge support
- **Entity Resolution** - Automatic deduplication and merging
- **Auto Extraction** - Runs every 15 minutes automatically

### 4.5 A-Share Market Analysis

Automated China stock market trend analysis:

- **Multi-Source Aggregation** - News articles, breaking stream, Twitter
- **Semantic Filtering** - LLM-powered market news filtering
- **Two-Stage Analysis** - Pre-market (8:30) + Intraday (14:30)
- **Accuracy Tracking** - Prediction history with accuracy metrics

### 4.6 One-Pass Framework

Generic unified AI analysis framework:

```python
# Consolidates multiple processing steps into single LLM call
- Triage + Scoring + Clustering → One Request
- Configurable context providers (recent events, active stories, RAG)
- Environment variable prompt overrides
```

---

## 5. Configuration

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

## 6. Makefile Commands

```bash
make help              # Show all commands
make db-init           # Initialize database
make db-migrate        # Run migrations
make rss-add URL=...   # Add RSS feed
make trigger-summary   # Trigger daily summary
make cleanup           # Clean low-quality articles
make test-tg           # Test Telegram push
make test-dingtalk     # Test DingTalk push
make test-push         # Test all platforms
```

---

## 7. API Endpoints

All endpoints require `X-API-Key` header authentication.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/trigger/fetch` | POST | Trigger news crawling |
| `/api/trigger/process` | POST | Trigger LLM classification |
| `/api/trigger/summary` | POST | Trigger daily summary |
| `/api/trigger/kg_extract` | POST | Trigger Knowledge Graph extraction |
| `/api/stats/overview` | GET | System statistics |
| `/api/sources/rss` | GET/POST | RSS source management |
| `/api/config` | GET/PUT | Configuration management |
| `/api/kg/*` | GET | Knowledge Graph queries |

---

## 8. Frontend

Modern Vue 3 + Vite SPA with:

- **Dashboard** - System overview and statistics
- **Sources** - RSS feed management
- **Config** - System configuration
- **Knowledge Graph** - Interactive entity visualization
- **Token Stats** - LLM usage tracking
- **PWA Support** - Installable web app

```bash
cd frontend
npm install
npm run dev     # Development: http://localhost:3000
npm run build   # Production build
```

---

## 9. Tech Stack

<div align="center">

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Python 3.9+, Uvicorn |
| Database | PostgreSQL 15+, Dgraph |
| Cache | Redis 8+ |
| AI/ML | OpenAI, Claude, DeepSeek, DashScope |
| Frontend | Vue 3, Vite, Chart.js |
| Deployment | Docker, Docker Compose |

</div>

---

## 10. Documentation

- [Change Log](./docs/change_log.md) - Version history
- [Python Commenting Standard](./docs/PYTHON_COMMENTING_STANDARD.md) - Bilingual docstring conventions
- [Dgraph Queries](./docs/dgraph_queries.md) - Knowledge Graph query examples

---

## 11. License

MIT License - See [LICENSE](LICENSE) for details.

---

## 12. Contributing

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

*Version 2.3.2 | Last Updated: 2026-03-17*

**OmniDigest** - Your AI-Powered News Intelligence Platform

</div>
