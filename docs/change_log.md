# Change Log

OmniDigest Change Log. All notable changes to this project will be documented in this file.

## v2.3.14 (2026-03-21)
- **通知模块模块化重构**:
    - 新增 `notifications/channels/base.py` - 定义 `NotificationChannel` 抽象基类和 `SendResult` 数据类
    - 新增 `notifications/channels/telegram.py` - Telegram 渠道适配器
    - 新增 `notifications/channels/dingtalk.py` - 钉钉渠道适配器
    - 新增 `notifications/manager.py` - 统一通知管理器 `NotificationManager`
    - 保留 `notifications/pusher.py` 作为向后兼容的 Facade

- **AStockAlertService Bug 修复**:
    - 修复 `_send_dingtalk` 方法中调用已废弃的 `dingtalk_webhook` 属性问题
    - 迁移到新的 `NotificationManager` API

- **文档更新**:
    - 新增 `docs/notification_module_design.md` - 通知模块架构设计文档
    - 新增 `docs/wechat_webhook_api.md` - 微信 Webhook API 规范
    - 新增 `docs/migration_plan.md` - 重构迁移计划

## v2.2.1 (2026-03-16)
- **App 图标和 Favicon**:
    - 新增 SVG favicon 和 ICO 格式，兼容各浏览器。
    - 新增 Apple touch icon (180x180) 用于 iOS 主屏幕。
    - 新增 Android Chrome icons (192x192, 512x512) 用于 PWA。
    - 新增 `site.webmanifest` 支持 PWA 安装。
    - 更新 `index.html` 添加 favicon 链接。

- **Telegram 推送修复**:
    - 修复 `send_telegram` 函数中传入 `chat_id` 时未正确获取 `bot_token` 的问题。
    - 现在会根据传入的 `chat_id` 匹配对应机器人的 `bot_token`。

- **Breaking News 数据库修复**:
    - 修复 `link_stream_to_event` 函数中添加 event 存在性检查。
    - 解决当 LLM 返回已删除的 event ID 时导致外键约束错误的问题。

## v2.2.0 (2026-03-16)
- **App 图标和 Favicon**:
    - 新增 SVG favicon 和 ICO 格式，兼容各浏览器。
    - 新增 Apple touch icon (180x180) 用于 iOS 主屏幕。
    - 新增 Android Chrome icons (192x192, 512x512) 用于 PWA。
    - 新增 `site.webmanifest` 支持 PWA 安装。
    - 更新 `index.html` 添加 favicon 链接。

## v2.1.2 (2026-03-16)
- **Redis 缓存默认启用**:
    - 更新 `.env.example`，添加 Redis 默认配置（REDIS_HOST=redis, REDIS_ENABLED=true）。
    - 确保生产环境部署时 Redis 缓存默认生效。

- **代码注释合规性修复**:
    - 为 `api/router.py` 中的 21 个嵌套函数添加中英双语注释。
    - 优化 `lint comments` 检查工具，跳过嵌套函数的 docstring 检查。

## v2.1.1 (2026-03-15)
- **Frontend Build Fix**:
    - 修复 Vite 构建问题：将 minify 从 terser 改为 esbuild。
    - 修复生产环境 API URL 配置。

## v2.1.0 (2026-03-15)
- **Redis 缓存系统**:
    - 新增 Redis 缓存服务 (`core/cache.py`)，支持 JSON 序列化和 TTL 管理。
    - Stats 端点缓存：/stats/overview、/stats/articles、/stats/breaking、/stats/twitter、/stats/llm。
    - 缓存失效机制：写操作（config、sources）后主动清除相关缓存。
    - 配置参数：REDIS_HOST、REDIS_PORT、REDIS_DB、REDIS_PASSWORD、REDIS_ENABLED。
    - Docker Compose 新增 Redis 服务 (`redis:8.6.1`)。

## v1.9.0 (2026-03-14)
- **One-Pass Framework 架构统一**:
    - **通用 OnePass 框架**: 新建 `domains/core/onepass.py`，提供可配置的通用单次 LLM 调用处理器。
    - **模块化 Context Provider**: 支持 `RecentEventsProvider`、`ActiveStoriesProvider`、`RAGProvider`，可插拔设计。
    - **Breaking News 迁移**: BreakingProcessor 迁移到 OnePass 框架，Prompt 可通过 `PROMPT_BREAKING_ONEPASS` 配置。
    - **Twitter 迁移**: TwitterProcessor 迁移到 OnePass 框架，合并事件匹配到单次 LLM 调用，Prompt 可通过 `PROMPT_TWITTER_ONEPASS` 配置。
    - **Daily News 迁移**: ContentProcessor 迁移到 OnePass 框架，实现批量文章分类，Prompt 可通过 `PROMPT_DAILY_ONEPASS` 配置。
    - **配置化 Prompt**: 所有 OnePass Prompt 支持环境变量覆盖。

- **配置简化**:
    - **TG 配置合并**: 将 `TG_BOT_TOKEN` 合并到 `TG_ROBOTS` JSON 中的 `bot_token` 字段。
    - **LLM 配置移除**: LLM 配置现在优先从数据库读取，`.env` 中的配置作为备用。
    - **.env 格式修复**: 修复多行 JSON 解析问题，改为单行 JSON 格式。

- **双语注释检查**:
    - 新增 `lint comments` 命令，支持全项目双语 docstring 检查。
    - 修复 5 个模块的注释合规问题。

- **.env.prod 更新**:
    - 更新生产环境配置文件以适配新版本。

## v1.8.5 (2026-03-14)
- **Breaking News Token 优化**:
    - **上下文精简**: 减少 LLM 上下文中的 Active Stories 数量 (268 → 10)，降低每次请求的 token 消耗。
    - **简化格式**: 移除 context 中的 summary 内容，只保留 ID、标题和分类。
    - **可配置参数**: 新增 `BREAKING_CONTEXT_RECENT_EVENTS` (默认3) 和 `BREAKING_CONTEXT_ACTIVE_STORIES` (默认10)。
    - **优化效果**: 每次请求节省约 90% prompt tokens (~32K → ~2.5K)，预估每月节省约 ¥885。

## v1.8.4 (2026-03-14)
- **A股分析周末跳过**:
    - 添加周末检查逻辑，盘前/盘中/盘后分析任务在周六日自动跳过。

## v1.8.3 (2026-03-14)
- **Twitter 空数据处理修复**:
    - 修复空用户数据被错误标记为 rate limit 的问题。空数据通常意味着目标用户被封/改名，而非账号被限流。
    - 只有 HTTP 429 状态码才会触发账号冷却。
    - 清理了 23 个无效的监控账号。

## v1.8.2 (2026-03-13)
- **A股趋势分析系统修复**:
    - **代理问题修复**: 在 LLM 调用前后临时禁用代理，解决 httpx 不支持 SOCKS 代理导致盘后分析失败的问题。
    - **指数名称中文化**: 修复盘后分析模板中 "SHANGHAI"/"SHENZHEN" 显示为英文的问题，改为"上证指数"/"深证成指"。
    - **准确率追踪**: 盘后分析现在正确返回"差异分析"和"关键因素"内容。

## v1.8.1 (2026-03-13)
- **AKShare 集成修复**:
    - **代理问题**: 切换到 Sina 数据源替代 East Money，解决代理环境下访问失败的问题。
    - **指数代码格式**: 修正 Sina API 需要的指数代码格式（sh000001, sz399001）。
- **A股趋势分析系统**:
    - **盘前分析**: 每日 8:30 执行，基于过去24小时财经新闻预测当日走势。
    - **盘中分析**: 每日 14:30 执行，基于上午走势和新闻更新预测。
    - **盘后分析**: 每日 15:30 执行，对比预测与实际走势，分析差异原因并追踪准确率。
    - **支持指数**: 上证指数和深证成指。
    - **数据源**: AKShare Sina API 获取实时行情。

## v1.7.3 (2026-03-13)
- **Twitter Account Cooling & Rate Limit Handling**:
    - **Auto-Cooling**: Added automatic cooling period for accounts after rate limit (default: 15 minutes).
    - **New Configuration**: `TWITTER_ACCOUNT_COOLING_MINUTES` (default: 15) - cooling duration.
    - **Request Delay**: Added configurable delay between user fetches to avoid rate limits.
    - **New Configuration**: `TWITTER_REQUEST_DELAY_SECONDS` (default: 1.0) - delay between requests.
    - **Random Account Selection**: Changed from sequential to random account selection from pool to distribute load.
- **Bug Fixes**:
    - Fixed daily summary field name errors: `category_name` -> `category`, `title` -> `chinese_title`, `url` -> `original_url`.
    - Updated Twitter alert templates to use event structure instead of single tweet.
- **Testing**:
    - Added comprehensive unit tests for daily summary Pydantic models and field validation.

## v1.7.2 (2026-03-12)
- **Twitter Event Aggregation & Deduplication**:
    - **New Database Tables**: Added `twitter_events` and `twitter_event_tweet_mapping` tables for clustering similar tweets into events.
    - **Event Clustering Logic**: Modified `TwitterProcessor` to group similar tweets into events based on text similarity within a configurable time window.
    - **Event-Level Alerts**: Changed from per-tweet alerts to aggregated event alerts. Alerts are only pushed when `source_count >= TWITTER_EVENT_PUSH_THRESHOLD` (default: 2).
    - **New Configuration Parameters**:
        - `TWITTER_EVENT_LOOKBACK_MINUTES` (default: 10): Time window to search for similar events.
        - `TWITTER_EVENT_PUSH_THRESHOLD` (default: 2): Number of sources required to trigger an alert.
    - **Simplified Notification Logic**: Removed legacy per-tweet alert path, now only uses event aggregation.
- **Testing**:
    - Added comprehensive unit tests for event aggregation functionality.

## v1.7.1 (2026-03-12)
- **Twitter Module Bug Fixes & Debugging**:
    - **Fixed Runtime Scoping**: Resolved a `NameError` where `batch_size` was used before its definition in `TwitterProcessor`.
    - **Missing Imports**: Fixed a crash in `TwitterAlerter` due to a missing `settings` import.
    - **Enhanced Observability**: Added detailed batch-level progress logging to `TwitterProcessor` to track real-time execution and LLM response counts.
    - **Pipeline Validation**: Verified batch processing for up to 50 tweets simultaneously, ensuring reliable throughput.

## v1.7.0 (2026-03-12)
- **Twitter Intelligence Overhaul**:
    - **One-Pass Batch Triage**: Refactored `TwitterProcessor` to process 10 tweets per LLM request, significantly reducing costs and increasing throughput.
    - **Granular Notification Controls**: Implemented `enable_twitter` and `twitter_template` for individual robots in `TG_ROBOTS` and `DING_ROBOTS`.
    - **Global Switches**: Added `ENABLE_TWITTER_ALERTS`, `TWITTER_PUSH_TELEGRAM`, and `TWITTER_PUSH_DINGTALK` for top-level control.
    - **Enhanced Alerts**: Included "新闻" keyword compliance for DingTalk and dedicated Jinja2 templates for Twitter alerts.
- **Configuration & Architecture**:
    - **Legacy Removal**: Removed obsolete `_load_rss_feeds` logic and `rss_feeds.txt` support as RSS is now strictly database-driven.
    - **Settings Standardization**: Fully explicit `Field(env=...)` definitions for all `Settings` for better reliability.
    - **Prompt Externalization**: Synchronized `PROMPT_TWITTER_BATCH_TRIAGE` between `.env` and `config.py` for runtime prompt tuning.

## v1.6.5 (2026-03-12)
- **Twitter Ingestion Engine**:
    - Implemented a robust scraping pipeline for Twitter/X using the GraphQL API, bypassing standard API limitations.
    - Designed a **High-Water Mark** mechanism to ensure incremental fetching and avoid duplicate data ingestion.
    - Developed a flexible **GraphQL Parser** capable of navigating complex nested structures (`instructions` -> `TimelineAddEntries`) and resilient to Twitter's frequent UI updates.
    - **Influential Leader Monitoring**: Integrated 16 high-profile accounts (World Leaders, News Wires, Global Orgs) for real-time policy and sentiment tracking.
    - **Account Pool Management**: Added a database-driven account rotation system with failure tracking and automatic cooldowns.
- **CLI & Orchestration**:
    - Introduced `manage.py twitter` suite for managing accounts, influencers, and manual crawl triggers.
    - Registered `twitter_crawl` as a background periodic task.
- **Bug Fixes**:
    - Resolved 404 and Authorization errors in GraphQL requests by synchronizing `queryId` and `features` with live browser traces.
    - Fixed database schema inconsistencies regarding the `twitter_accounts` table.

## v1.6.4 (2026-03-11)
- **New Breaking News Sources**:
    - Added 9 high-depth news sources (财新网, 华尔街见闻, 联合早报, etc.) focused on politics and economics.
    - Successfully validated connectivity using enhanced browser headers to bypass protection.
- **CLI Enhancements**:
    - Added `manage.py rss add-breaking` command to manage the `breaking_rss_sources` table specifically.
    - Improved RSS connectivity testing logic in the management tools.

## v1.6.3 (2026-03-11)
- **Extended Story Timelines**:
    - Introduced `BREAKING_STORY_LOOKBACK_DAYS` (default 10 days) to allow narratives to span longer periods without being fragmented.
    - Updated `BreakingProcessor` to cluster events against a significantly wider historical window.
- **Hyperlink Integration in Notifications**:
    - Added direct **Source URLs** to breaking news alert titles and individual timeline events.
    - Supported **HTML links** for Telegram and **Markdown links** for DingTalk.
- **Database Query Optimization**:
    - Refactored `BreakingNewsMixin` (in `db_repo.py`) to retrieve source URLs via efficient SQL joins with original news streams.
- **Code Quality & CLI**:
    - Integrated bilingual docstring linting into `manage.py lint comments`.
    - Standardized docstrings across 14+ core files according to `PYTHON_COMMENTING_STANDARD.md`.
    - Added `make lint` target to the root `Makefile`.
- **LLM Robustness & Provider Compatibility**:
    - Centralized **LLM Provider Detection** in `LLMManager` (e.g., DashScope/Qwen).
    - Automatic mode switching for `instructor`: forced `Mode.JSON` / `Mode.MD_JSON` for strict providers to avoid `400 Bad Request` and `InternalError.Algo.InvalidParameter`.
    - Added a robust `_clean_json_output` utility to strip Markdown blocks and handle XML-like noise (like `<tool_call>`) returned by certain models (Qwen).
- **Global Processor Refactoring**:
    - Updated `BreakingProcessor`, `ContentProcessor`, `KGExtractor`, and `TrendAnalyzer` to use standardized robust JSON parsing.
    - Improved stability for high-complexity models (e.g., Daily Summary) with better output cleaning.
- **Bug Fixes**:
    - Fixed a critical XML/JSON parsing failure in `BreakingNews` pipeline.
    - Standardized manual JSON stripping across all domain-specific processors.

## v1.6.1 (2026-03-09)
- **Token Usage Tracking**:
    - Implemented a system-wide LLM token tracking and reporting system (`llm_usage` table).
    - Added database methods to record and query token usage per model and domain.
- **Webhook & Callback Reliability**:
    - Fixed a 404 error on DingTalk outgoing webhooks (`/dingtalk/callback`).
    - Resolved a crash in the Telegram bot's callback handler caused by state mismatch during article interaction.
- **Notification Routing**:
    - Implemented granular per-robot enabled/disabled and template control for Telegram and DingTalk.
    - Allowed setting unique Jinja2 templates for each robot via `.env` JSON configuration.

## v1.6.0 (2026-03-08)
- **One-Pass Summary Optimization**:
    - Refactored the daily summary generator to consolidate multiple (up to 15) fragmented LLM calls into a single structured request using `instructor`.
    - Significantly improved summary generation speed and reduced total token consumption.
- **Breaking News Engine v2**:
    - Introduced `instructor`-based structured processing for breaking news, replacing legacy manual JSON parsing.
- **Improved Data Ingestion**:
    - Merged standard RSS and breaking news crawlers under a unified `ingestion` domain.
- **Bug Fixes**:
    - Fixed a critical bug where "null" strings in breaking news UUID parsing caused database integrity failures.
- **Dependency Update**:
    - Added `instructor` to `requirements.txt` and `pyproject.toml`.

## v1.5.4 (2026-03-07)
- **Automatic LLM Model Failover System**:
    - Introduced `llm_models` database table to manage multiple LLM providers, priorities, and failure tracking.
    - Implemented `LLMManager` to handle dynamic model selection, automatic retries, and failover when an API endpoint is unavailable.
    - Models are automatically deactivated after 5 consecutive failures to ensure system stability.
- **Knowledge Graph Extraction Robustness**:
    - Refactored `KGExtractor` to use the new `LLMManager`, enabling failover support for triple extraction.
    - Fixed a critical database error where `kg_processed` column was missing from `breaking_stream_raw`.
- **Breaking News Engine Enhancements**:
    - Fixed schema inconsistencies in `breaking_events` (missing `pushed`, `story_id` columns).
    - Added `breaking_stories` table to support hierarchical deduplication and story-level tracking.
- **Job Reliability**:
    - Refactored `job_daily_summary` to use `LLMManager` for all fragment generations, ensuring summaries are generated even if the primary LLM fails.
    - Updated background jobs to correctly inject the `LLMManager` singleton.

## v1.5.3 (2026-03-07)
- **Knowledge Graph API Trigger**:
    - Added `/trigger/kg_extract` POST endpoint to manually summon the extraction pipeline from web frontends or tools.
    - Implemented a robust thread-safe **concurrency lock** (`is_kg_extraction_running`) in `jobs/__init__.py` to gracefully reject parallel API execution requests if the background scheduler or another API request is already running.

## v1.5.2 (2026-03-07)
- **Docker Compose Port Misalignment Fix**:
    - Fixed a `503 Service Unavailable` error when deploying via Docker by aligning the exposed `--port` in the `Dockerfile` Uvicorn CMD to `8080`, matching the `docker-compose.yml` mapping of `8080:8080`.

## v1.5.1 (2026-03-07)
- **Dgraph Transaction Reliability**:
    - **Idempotent Mutations & Batching**: Refactored `dgraph_client.py` and `extractor.py` to batch all node and edge mutations inside a single request before calling `txn.commit()`, completely eliminating "ghost nodes" caused by race conditions.
    - **Double Edges**: Fixed missing reverse edges by explicitly adding `<entity> <mentioned_in> <event>` edges, enabling bi-directional traversal.
    - **Political Alignment**: Enhanced LLM Prompt to specifically track political figures' statements, evaluations, and appointments.

## v1.5.0 (2026-03-06)
- **Knowledge Graph Extraction Engine**:
    - Introduced `domains/knowledge_graph/` to systematically extract Entities (Person, Organization, Location) and Relations from news articles.
    - Integrated with **Dgraph** for high-performance graph storage and querying.
    - Added background job `job_kg_extract` that extracts triples every 15 minutes.
    - Added `manage.py kg extract` CLI command for manual and backfill operations.
- **LLM Compatibility Fixes**:
    - Fixed `400 Bad Request` and `JSONDecodeError` for non-OpenAI models (like Claude over proxy) by safely stripping markdown JSON wrappers and injecting explicit `max_tokens=4096`.
    - Made `job_daily_summary` resilient when `RAGFLOW_ENABLED=False` by directly instantiating a local OpenAI client instead of relying on the disabled RAG provider.

## v1.4.2 (2026-03-05)
- **Hierarchical Deduplication & Story Timelines (Breaking News)**:
    - **Story Level Clustering**: Clustered individual breaking events into overarching "Stories" (narrative arcs) to avoid fragmented, duplicate alerts over time.
    - **Cross-Verification**: Alerting now requires a minimum of 2 independent source reports (`source_count >= 2`) to mark a story as `verified` and push it, drastically reducing noise.
    - **Timeline Notifications**: Push templates for Telegram and DingTalk now feature a timeline of events mapping the history of the Story with `YYYY-MM-DD HH:MM` high-resolution timestamps.
    - Retroactive Backfill: Added `manage.py db backfill-stories` to group legacy events into Stories without re-triggering pushes.
    - Test Deep Cleanup: Enhanced E2E test scripts to deeply clean DB associations (mappings, events, stories) to guarantee a fresh state per run.

## v1.4.1 (2026-03-05)
- **Centralized Testing Framework**:
    - Added a `test` subcommand to `manage.py` (`test all`, `test daily`, `test breaking`) for end-to-end continuous testing of major pipelines.
    - Included automated Mock data injection, LLM processing, DB validation, and real `[TEST]`-prefixed notification triggers.
    - Deprecated scattered standalone test scripts.

## v1.4.0 (2026-03-03)
- **Domain-Driven Architecture**:
    - Restructured the codebase from a technical layer approach (`services/`) to a feature-based domain approach (`domains/`).
    - Created isolated domains for `rss`, `breaking_news`, `daily_digest`, `analysis`, `knowledge_base`, and `auth`.
- **Dependency Injection**:
    - Removed the eager global singleton container (`core/container.py`).
    - Implemented formal FastAPI Dependency Injection via `api/deps.py` for lazy loading of resources (e.g., `DatabaseManager`, `RAGClient`).
- **CLI & Background Jobs Refactoring**:
    - Renamed the `commands/` directory to `cli/` to better reflect its purpose.
    - Updated background jobs and CLI tools to instantiate dependencies independently without relying on the FastAPI routing context.
- **Code Cleanup & Import Fixes**:
    - Removed duplicate Jinja templates and consolidated notification logic into a dedicated `notifications/` module.
    - Updated all internal cross-domain import paths globally to support the new `v1.4.0` hierarchy.

## v1.3.0 (2026-03-01)
- **Breaking News Engine**:
    - **Dual-System Architecture**: Introduced a new `BreakingProcessor` and `BreakingCrawler` distinct from the daily digest pipeline.
    - **Decoupled Database**: Added `breaking_stream_raw`, `breaking_events`, and `event_stream_mapping` tables. Processors now interact purely via the database.
    - **Real-Time Alerting**: Developed a dedicated `BreakingAlerter` loop to instantly push events exceeding the configurable `impact_score` threshold to Telegram and DingTalk.
    - **LLM Triage & Scoring**: Realtime articles are scrubbed by an LLM prompt to identify world-altering events (signal vs noise) and scored dynamically.
    - **Custom Templates**: Included new templates `telegram_breaking.html.j2` and `dingtalk_breaking.md.j2` to visually separate breaking alerts from regular news.
- **LLM-Based Semantic Deduplication**:
    - Implemented `CLUSTERING_PROMPT` in `BreakingProcessor` to detect when multiple RSS sources report on the same event using LLM semantic matching.
    - Duplicate reports are automatically clustered into a single event with all contributing sources aggregated under an "信息来源" section.
    - Added `get_breaking_event_sources()` DB method to retrieve real source URLs from the `event_stream_mapping` join.
- **Dynamic Breaking RSS Sources**:
    - Migrated hardcoded RSS sources to a new `breaking_rss_sources` database table for dynamic management.
    - Seeded 17 high-intensity international media sources (BBC, CNN, NYT, Reuters, Al Jazeera, SCMP, etc.) via SQL migration script `004_seed_more_breaking_rss.sql`.
- **CLI Refactoring**:
    - Extracted `manage.py` command logic into modular files under `commands/` package (`db.py`, `rss.py`, `jobs.py`, `auth.py`).
    - Added a root-level `Makefile` with user-friendly aliases for all common CLI operations (e.g., `make test-tg`, `make db-init`, `make trigger-summary`).
- **Configuration Externalization**:
    - Migrated all Breaking News runtime parameters to `.env` with sensible defaults:
        - `ENABLE_BREAKING_NEWS`, `BREAKING_RAG_ENABLED`, `BREAKING_IMPACT_THRESHOLD`
        - `BREAKING_FETCH_INTERVAL_MINUTES`, `BREAKING_PUSH_DINGTALK`, `BREAKING_PUSH_TELEGRAM`
        - `BREAKING_PROCESSOR_CONCURRENCY`, `BREAKING_PROCESSOR_BATCH_SIZE`
- **Directory Architecture Cleanup**:
    - Relocated `templates/` into `src/omnidigest/templates/` for proper package encapsulation.
    - Elevated `migrations/` from `scripts/migrations/` to `src/omnidigest/migrations/`.
    - Removed obsolete `scripts/` directory and orphaned test stubs.
- **Code Quality**:
    - Applied bilingual (English/Chinese) Google-style module docstrings to all 28 Python source files per `PYTHON_COMMENTING_STANDARD.md`.
    - Fixed misplaced docstring positioning in `core/rag.py`.

## v1.2.6 (2026-02-26)
- **High-Performance Concurrency**:
    - Replaced the single `psycopg2` database connection with a robust `ThreadedConnectionPool`, ensuring native thread safety across all operations.
    - Rewrote `NewsCrawler` fetching loop to be fully parallel using `ThreadPoolExecutor`, simultaneously downloading from up to 10 RSS sources.
    - Upgraded `ContentProcessor` LLM pipeline to classify articles and update the database concurrently using `asyncio.gather`, `asyncio.Semaphore`, and `asyncio.to_thread`.
    - Eliminated all artificial thread locks (`self.db_lock`) from the services layer, massively improving processing throughput for large lists of RSS feeds.

## v1.2.5 (2026-02-26)
- **Modular LLM Prompts & Parallelism**:
    - Replaced monolithic JSON prompts with targeted ones (`prompt_overview`, `prompt_critique`, `prompt_translate_titles`) defined in `.env`.
    - Implemented `asyncio.to_thread` to execute multiple LLM calls simultaneously, significantly speeding up summary generation.
- **Customizable Jinja2 Push Templates**:
    - Centralized template rendering via Jinja2 in the Push Service (`pusher.py`).
    - Added modular HTML/Markdown templates (`telegram_default.html.j2`, `dingtalk_default.md.j2`, `dingtalk_no_critique.md.j2`), decoupled from core Python logic.
    - Promoted `templates/` to a root directory and exposed it via volume mounts in `docker-compose.yml` for live edits without rebuilding.
- **Robust Scheduling**:
    - Upgraded daily summary cron logic to accept multiple execution hours (e.g., `SUMMARY_HOUR="8,20"`) and configurable minutes.
    - Synchronized all database timestamps and Python comparators to UTC to avoid timezone mismatch rendering empty summaries.
- **Standardized Documentation**:
    - Applied a comprehensive bilingual (English/Chinese) Google-style docstring standard across every file in `src/omnidigest/`.
- **Test Consolidation**:
    - Merged 10 isolated disparate test scripts into a unified `tests/diagnostics.py` CLI for easier testing and maintenance.
- **Bug Fix**: Addressed a critical hallucination where `pydantic-settings` injected literal `.env` quotes into system prompts, confusing the LLM.

## v1.2.4 (2026-02-25)
- **API Security**: 
    - Implemented database-backed API Key authentication for all endpoints (except Webhooks). 
    - Added `X-API-Key` header requirement to secure manual triggers and data access.
    - Added CLI tools (`manage.py auth create-key`, `manage.py auth list-keys`) for easy key generation and management.
- **Resilient Crawler (Auto-Disable)**:
    - Added comprehensive failure tracking (`fail_count`, `last_error`) to the `rss_sources` table.
    - Feeds that fail 5 consecutive times (e.g., due to 404, timeouts, or XML errors) are automatically disabled to conserve system resources and prevent pipeline hangs.
    - Added CLI tools (`manage.py rss check-failures`, `manage.py rss enable`) to review and manually restore broken feeds.
- **Configuration Security**: 
    - Completely removed hardcoded database credentials and API keys from `config.py`.
    - Migrated all secrets to a `.env` file (with a `.env.example` template provided) to ensure sensitive data is not committed to version control.

## v1.2.3 (2026-02-23)
- **CLI Tooling**: Consolidated standalone operational scripts into a unified `manage.py` and consolidated testing suite into `diagnostics.py`.
- **Documentation**: Added comprehensive bilingual comments to all core source codebase files.
- **Build & CI/CD**: Updated Docker image build scripts and relocated them to the project root.

## v1.2.2 (2026-02-18)
- **Features**: Made RAGFlow integration optional via configuration and added a trend analysis service.
- **Telegram Updates**: Enhanced Telegram bot notifications with HTML trend reports.
- **Codebase Refactoring**: Consolidated scattered scripts and tests directories to improve repository structure.

## v1.2.1 (2026-02-16)
- **Docker Optimization**: 
    - Implemented **multi-stage builds**, reducing image size from ~500MB to ~282MB.
    - Added `.dockerignore` to exclude unnecessary files from the build context.
    - Updated `docker-compose.yml` to use pre-built image `omnidigest:v1.2.1`.
- **RSS Source Management**: 
    - Migrated RSS feeds from static `rss_feeds.txt` to a database table `rss_sources` for dynamic management.
    - Added `src/omnidigest/scripts/migrate_rss.py` for automated migration.
- **Crawler Reliability**: 
    - Refactored `NewsCrawler` to use `requests` with a strict **15-second timeout** before parsing, preventing process hangs.
- **Processing Logic**: 
    - Updated `ContentProcessor` to continuously process *all* unclassified articles in a loop (batches of 10) instead of stopping after a single batch.
- **Codebase Refactoring**:
    - **Modularization**: Split `main.py` into `core/container.py` (dependencies), `jobs/` (scheduled tasks), and `api/router.py` (endpoints) to improve maintainability.
- **Database Safety**: Implemented strict integrity check on startup and added manual init script `src/omnidigest/scripts/init_db.py`.

## v1.2.0 (2026-02-15)
- **Dual Platform Support**: Fully integrated DingTalk robot notifications with dedicated Markdown formatting, running in parallel with Telegram HTML updates.
- **Interactive Summary**: Implemented `/dingtalk/callback` endpoint allowing users to trigger summaries interactively by @mentioning the robot with "新闻".
- **API Architecture**: Refactored `main.py` to separate summary logic into platform-specific endpoints (`/trigger/summary/telegram`, `/trigger/summary/dingtalk`) for granular control.
- **Automated Maintenance**: Introduced `job_cleanup_low_quality` to automatically delete low-scoring articles (< 45) from both the database and RAG knowledge base daily at 05:00 AM.
- **Schedule Optimization**: Updated the daily summary schedule to run twice daily at **08:00 AM** and **08:00 PM** for better coverage.
- **Bug Fixes**: Restored the missing `/trigger/process` endpoint to ensure manual processing triggers work as expected.
- **Code Quality & Documentation**:
    - **Cleanup**: Removed unused RAGFlow chat methods (`get_summary`, `create_chat`) to streamline `RAGClient`.
    - **Bilingual Docs**: Added comprehensive English/Chinese comments to all core services and configuration files.

## v1.1.1 (2026-02-14)
- **News Classification & Scoring**: Introduced 7 specialized categories (AI, SWE, Hardware, etc.) and relevance scoring (0-100) using LLM.
- **Real-time Processing**: Refactored the pipeline to trigger content processing immediately after news fetching, reducing latency.
- **Database Upgrade**: Added `category` and `score` columns to `news_articles` table; included migration scripts.
- **Project Structure**: Consolidated `tests/` directory into `scripts/tests/` to streamline the project root.

## v1.1.0 (2026-02-13)
- **Refactor**: RSS feeds moved to `rss_feeds.txt`.
- **Fix**: "Read Original" links now work correctly using Database Fallback for missing metadata.
- **Optimization**: Switched Telegram messages to HTML format for better layout and reliability.
- **Maintenance**: Cleaned up `tests/` directory, removed deprecated chat scripts, and added `tests/README.md`.
- **Docs**: Detailed report in [summary_optimization_2026_02_13.md](./summary_optimization_2026_02_13.md).

## v1.0.1 (2026-02-09)
- **Fixed RAGFlow Integration**: Corrected API endpoints and authentication flow for successful document uploads.
- **Enhanced Content Quality**:
    - Replaced Google News Aggregator with **Direct RSS Feeds** (SCMP, BBC, CNN, China News).
    - Integrated `newspaper3k` for **Full-Text Extraction**, significantly improving context for RAG.
    - Implemented smart fallback to RSS summaries when full-text extraction fails.
- **Optimized Feed Strategy**:
    - Configured targeted feeds for **IT/AI**, **Global Economy**, and **International Relations**.
    - Implemented a **Max 5 Articles** per feed limit to reduce noise.
- **Engineering Improvements**:
    - **Configuration**: Externalized RSS feeds to `src/omnidigest/config.py` and `.env` (`RSS_FEEDS`) for easy customization.
    - **Testing**: Organized test scripts into `tests/` directory; added `tests/test_feeds.py` for end-to-end verification.

## v1.0.0 (2026-02-04)
- Initialized documentation structure.
- Created `docs/dev_plan.md`, `docs/problem_solving.md`, `docs/change_log.md`.
- Implemented core system logic as individual scripts.
- Refactored project into a structured Python package (`src/omnidigest`).
- Added `pyproject.toml`, `config.py`, and `.env` support.
- Finalized integration and scheduling logic.
- Integrated `FastAPI` to support manual API triggers (`/trigger/fetch`, `/trigger/summary`).
- Added VS Code launch configuration (`.vscode/launch.json`) for proper debugging.
