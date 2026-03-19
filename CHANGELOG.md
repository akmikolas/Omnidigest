# Changelog

All notable changes to this project will be documented in this file.

## [2.3.5] - 2026-03-19

### Added
- **Redis Caching Layer**: 22 API endpoints now support Redis caching
  - Token stats: 5min TTL
  - Stats (overview/articles/breaking/twitter): 30s-180s TTL
  - Knowledge Graph: 60s-120s TTL
  - A-Stock (quotes/sectors/news/stocks): 3-10min TTL
  - Response time reduced from ~5s to ~20ms (cache hit)

- **A-Share Analysis Page**: New stock market analysis dashboard
  - Real-time index quotes (Shanghai, Shenzhen)
  - Sector performance ranking
  - Financial news aggregation
  - Market prediction (pre-market, intraday, post-market)
  - Prediction accuracy tracking
  - Alert status monitoring

- **Alert Service**: Abnormal fluctuation detection for A-Stocks
  - Monitors unusual price/volume changes
  - Configurable thresholds
  - Telegram/DingTalk push notifications

- **CI/CD Workflows**: GitHub Actions automation
  - `ci.yml`: Linting, type checking, testing
  - `cd.yml`: Docker build and Harbor push

- **API Documentation**: Complete REST API reference
  - `docs/API.md`: 51 endpoints documented
  - Request/response examples

### Fixed
- API path mismatch (frontend missing `/api` prefix)
- Backend `.env` loading issue (ENV_FILE not passed)
- Redis connection initialization timing

### Changed
- Backend port standardized to 7080 (dev environment)
- All UI text unified to English
- Vite proxy configuration updated

---

## [2.3.4] - 2026-03-18

### Added
- **Mobile Responsive Design**: Full mobile support for all pages
  - Added drawer-style sidebar navigation for mobile devices
  - Added mobile-specific header with hamburger menu
  - Added overlay for mobile menu backdrop
  - Added 480px and 375px breakpoint styles
  - Added PWA support with `apple-mobile-web-app-capable` and viewport restrictions

- **Responsive Adapters for All Pages**:
  - Dashboard: Vertical stat cards, adaptive event list heights
  - Config: Grid transforms from 4→2→1 columns on smaller screens
  - Sources: Form and list cards responsive adaptation
  - TokenStats: Responsive stat cards, horizontal table scrolling
  - KnowledgeGraph: Adaptive stat cards and graph heights

- **Global CSS Enhancements**:
  - Added comprehensive mobile media queries in main.css
  - Optimized padding, font sizes, and button sizes for touch devices

### Changed
- Updated index.html with proper mobile viewport meta tags
- Theme color updated to match dark sidebar (#1a1a2e)

---

## [2.3.2] - 2026-03-17

### Added
- **Auto Database Initialization**: Database tables are now automatically created on first startup if they don't exist
  - No longer requires manual `make db-init` before first run
  - System checks for empty database and creates schema automatically

---

## [2.3.1] - 2026-03-17

### Added
- **Twitter Event Push**: Now includes ALL tweet URLs in the story, not just the first one
  - Added `get_twitter_event_tweet_urls` method in db_repo.py
  - Updated processor.py to fetch and include tweet_urls
  - Updated alerter.py to include tweet_urls in push payload
  - Updated Telegram and DingTalk templates to display all tweet links

- **Token Stats by Service**: Added "Token Usage by Service" table to Token Stats page
  - Shows token consumption grouped by service type (breaking, daily, twitter, knowledge_graph, etc.)
  - Displays service badges with color coding
  - Shows percentage of total consumption per service

- **Open Source Preparation**: Added comprehensive installation guide
  - Added "Installation from Scratch" section to README
  - Moved deployment scripts to private `deployment/` directory
  - Replaced Harbor references with generic image names
  - Added detailed environment configuration instructions

---

## [2.3.0] - 2026-03-17

### Added
- **Knowledge Graph v2**: Enhanced entity resolution with type filtering and similarity calculation
  - Added relation type normalization mapping (Chinese to English standardized types)
  - Enhanced entity resolution with edit distance and substring matching
  - Added source tracking for entities (tracks which articles entities come from)
  - Added confidence scores and aliases for entities
  - Added time-aware relations (start_time, end_time, extracted_at)

- **Knowledge Graph API**: New endpoints for interactive queries
  - `GET /api/kg/entities` - Search entities with filters
  - `GET /api/kg/entity/{uid}` - Get entity details
  - `GET /api/kg/relations` - Query relations with filters
  - `GET /api/kg/search` - Find paths between entities

- **Dashboard Enhancements**
  - Added today's API cost display in overview stats
  - Added Twitter account pool status (Active/Cooling/Error)
  - Added auto-scrolling news events (hover to pause)
  - Reduced LLM Models and Breaking News card sizes

- **Frontend UI**
  - Added collapsible sidebar with logo
  - Added SVG logo icon
  - Enhanced KnowledgeGraph.vue with interactive features:
    - Entity search panel with name and type filters
    - Path search between entities
    - Entity details sidebar
    - Interactive graph visualization using real data

### Changed
- Refactored graph visualization to use real data from API
- Reorganized dashboard layout: 5-column stats, 3-column system status, vertical scrolling events

### Fixed
- Fixed entity relations query to properly return data from Dgraph

---

## [2.2.1] - 2026-03-16

### Fixed
- Telegram push bug fix
- Added app icons and favicon for web and PWA

---

## [2.2.0] - 2026-03-16

### Added
- LLM pricing and cache tracking with frontend display

---

## [2.1.1] - 2026-03-16

### Fixed
- Enable Redis cache by default
- Fix docstring compliance

---

## [2.1.0] - 2026-03-15

### Added
- Redis caching system for API endpoints

---

## [2.0.0] - 2026-03-14

### Added
- Dashboard UI with prompts config, custom time range, dark mode
- Configuration API endpoints
- Sources by service display

---

## [1.9.0] - 2026-03-10

### Added
- Domain-driven architecture refactoring
- Multi-source news aggregation for A-Share market analysis
- Knowledge Graph pipeline with Dgraph storage

---

## [1.8.0] - 2026-03-05

### Added
- Twitter Intelligence Pipeline with GraphQL scraping
- Influence monitoring and granular alert routing

---

## [1.7.0] - 2026-02-20

### Added
- Breaking News Pipeline with semantic deduplication
- Story timeline mapping and cross-verification
- Real-time push alerts

---

## [1.3.0] - 2026-02-10

### Added
- High-intensity RSS polling for breaking news
- One-pass LLM triage

---

## [1.0.0] - 2026-01-15

### Added
- Core pipeline: Scheduled RSS Crawling → PostgreSQL → One-Pass LLM Classification & Scoring → AI Daily Summary → Multi-Platform Push
