"""
Configuration and settings management for OmniDigest. Uses pydantic_settings to load variables from environment or .env files.
OmniDigest 的配置和设置管理。使用 pydantic_settings 从环境变量或 .env 文件加载变量。
"""
import os
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class DingRobotConfig(BaseModel):
    """
    Configuration for a single DingTalk robot.
    单个钉钉机器人的配置。
    """
    token: str
    secret: str = ""
    keyword: str = ""  # 安全关键词，消息内容必须包含此关键词
    enable_daily: bool = True
    daily_template: str = "dingtalk_default.md.j2"
    enable_breaking: bool = True
    breaking_template: str = "dingtalk_breaking.md.j2"
    enable_twitter: bool = True
    twitter_template: str = "dingtalk_twitter_alert.md.j2"
    enable_astock: bool = True
    astock_template: str = "dingtalk_astock_pre_market.md.j2"

class TgRobotConfig(BaseModel):
    """
    Configuration for a single Telegram robot.
    单个 Telegram 机器人的配置。
    """
    bot_token: str  # Telegram bot token (merged from tg_bot_token)
    chat_id: str
    enable_daily: bool = True
    daily_template: str = "telegram_default.html.j2"
    enable_breaking: bool = True
    breaking_template: str = "telegram_breaking.html.j2"
    enable_twitter: bool = True
    twitter_template: str = "telegram_twitter_alert.html.j2"
    enable_astock: bool = True
    astock_template: str = "telegram_astock_pre_market.html.j2"


class FeishuRobotConfig(BaseModel):
    """
    Configuration for a single Feishu (飞书) robot.
    单个飞书机器人的配置。
    """
    webhook_url: str  # Full webhook URL, e.g. https://open.feishu.cn/open-apis/bot/v2/hook/xxx
    secret: str = ""  # HMAC-SHA256 signing secret
    enable_daily: bool = True
    daily_template: str = "feishu_default.md.j2"
    enable_breaking: bool = True
    breaking_template: str = "feishu_breaking.md.j2"
    enable_twitter: bool = True
    twitter_template: str = "feishu_twitter_alert.md.j2"
    enable_astock: bool = True
    astock_template: str = "feishu_astock.md.j2"

class Settings(BaseSettings):
    """
    Global configuration settings for OmniDigest using pydantic_settings.
    OmniDigest 的全局配置设置。
    """
    
    # ==========================
    # Database Configuration
    # 数据库配置
    # ==========================
    db_host: str = Field(default="localhost", env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")
    db_user: str = Field(default="", env="DB_USER")
    db_password: str = Field(default="", env="DB_PASSWORD")
    db_name: str = Field(default="omnidigest", env="DB_NAME")

    # ==========================
    # RAGFlow Configuration
    # RAGFlow 配置
    # ==========================
    ragflow_enabled: bool = Field(default=False, env="RAGFLOW_ENABLED")
    ragflow_api_url: str = Field(default="", env="RAGFLOW_API_URL")
    ragflow_api_key: str = Field(default="", env="RAGFLOW_API_KEY")
    ragflow_dataset_id: str = Field(default="", env="RAGFLOW_DATASET_ID")

    # ==========================
    # Notifications
    # 通知配置
    # ==========================
    ding_robots: list[DingRobotConfig] = Field(default_factory=list, env="DING_ROBOTS")
    tg_robots: list[TgRobotConfig] = Field(default_factory=list, env="TG_ROBOTS")
    feishu_robots: list[FeishuRobotConfig] = Field(default_factory=list, env="FEISHU_ROBOTS")

    # Twitter Alerts Control
    enable_twitter_alerts: bool = Field(default=True, env="ENABLE_TWITTER_ALERTS")
    twitter_push_dingtalk: bool = Field(default=True, env="TWITTER_PUSH_DINGTALK")
    twitter_push_telegram: bool = Field(default=True, env="TWITTER_PUSH_TELEGRAM")
    twitter_impact_threshold: int = Field(default=80, env="TWITTER_IMPACT_THRESHOLD")
    twitter_event_lookback_minutes: int = Field(default=10, env="TWITTER_EVENT_LOOKBACK_MINUTES")
    twitter_event_push_threshold: int = Field(default=2, env="TWITTER_EVENT_PUSH_THRESHOLD")
    twitter_account_cooling_minutes: int = Field(default=15, env="TWITTER_ACCOUNT_COOLING_MINUTES")
    twitter_request_delay_seconds: float = Field(default=1.0, env="TWITTER_REQUEST_DELAY_SECONDS")

    template_dir: str = Field(default="templates", env="TEMPLATE_DIR")

    # ==========================
    # Scheduler & Jobs
    # 定时任务及抓取配置
    # ==========================
    fetch_interval_hours: int = Field(default=1, env="FETCH_INTERVAL_HOURS")
    summary_hour: str = Field(default="8", env="SUMMARY_HOUR")
    summary_minute: int = Field(default=0, env="SUMMARY_MINUTE")

    # ==========================
    # Breaking News Subsystem
    # 突发新闻子系统配置
    # ==========================
    enable_breaking_news: bool = Field(default=True, env="ENABLE_BREAKING_NEWS")
    breaking_rag_enabled: bool = Field(default=False, env="BREAKING_RAG_ENABLED")
    breaking_rag_dataset_name: str = Field(default="OmniDigest Breaking Events", env="BREAKING_RAG_DATASET_NAME")
    breaking_rag_dataset_id: str = Field(default="", env="BREAKING_RAG_DATASET_ID")
    breaking_embedding_model: str = Field(default="text-embedding-v4@Tongyi-Qianwen", env="BREAKING_EMBEDDING_MODEL")
    breaking_rag_similarity_threshold: float = Field(default=0.85, env="BREAKING_RAG_SIMILARITY_THRESHOLD")
    breaking_impact_threshold: int = Field(default=80, env="BREAKING_IMPACT_THRESHOLD")
    breaking_fetch_interval_minutes: int = Field(default=5, env="BREAKING_FETCH_INTERVAL_MINUTES")
    breaking_push_dingtalk: bool = Field(default=True, env="BREAKING_PUSH_DINGTALK")
    breaking_push_telegram: bool = Field(default=True, env="BREAKING_PUSH_TELEGRAM")
    breaking_story_lookback_days: int = Field(default=10, env="BREAKING_STORY_LOOKBACK_DAYS")
    breaking_processor_concurrency: int = Field(default=6, env="BREAKING_PROCESSOR_CONCURRENCY")
    breaking_processor_batch_size: int = Field(default=10, env="BREAKING_PROCESSOR_BATCH_SIZE")
    breaking_context_recent_events: int = Field(default=3, env="BREAKING_CONTEXT_RECENT_EVENTS")  # Number of recent events to include in context
    breaking_context_active_stories: int = Field(default=10, env="BREAKING_CONTEXT_ACTIVE_STORIES")  # Number of active stories to include in context

    # ==========================
    # Breaking News 质量控制配置
    # ==========================
    breaking_min_content_length: int = Field(default=500, env="BREAKING_MIN_CONTENT_LENGTH")  # Content 最小长度，太短则跳过
    breaking_max_title_retries: int = Field(default=1, env="BREAKING_MAX_TITLE_RETRIES")  # 空标题重试次数

    # Prompt templates for One-Pass processors (支持环境变量覆盖)
    prompt_breaking_onepass: str = Field(
        default="""You are a senior news editor and intelligence analyst. Your task is to analyze a new, raw intelligence stream and perform triage, scoring, clustering, and story matching SIMULTANEOUSLY.

    ### INSTRUCTIONS:
    1. **Triage**: Determine if this text describes a significant, explosive, or breaking news event (e.g., wars, major political shifts, massive economic crashes, disasters). If it is just normal news, opinion, chatter, or minor updates, set "is_breaking" to false and you may leave other fields null.
    2. **Analysis & Scoring**: If it IS breaking, assign an `impact_score` (0-100).
    - >90: world-altering events
    - 80-89: major international crises OR catastrophic national-level emergencies
    - 70-79: significant regional events
    - <70: routine news.
    Provide a concise 1-2 sentence summary and a short, punchy headline in CHINESE. Assign a category from: [War & Conflict, International Relations, Macro Economics, Emergency/Disaster, Major Tech/Science, Other]
    3. **Event Clustering**: Determine if this stream describes the EXACT SAME specific event as any of the `Recent Events`. If so, extract its Event ID into `matched_event_id`.
    4. **Story Matching**: Determine if this event belongs to the SAME BROADER NARRATIVE ARC as any of the `Active Stories`. If so, extract its Story ID into `matched_story_id`.

    ### INPUT DATA:
    【New Raw Stream】:
    {input_data}

    【Recent Events (For Clustering)】:
    {recent_events}

    【Active Stories (For Narrative Trajectory)】:
    {active_stories}

    ### OUTPUT (JSON ONLY - no other text):
    Output ONLY valid JSON matching this exact format:
    {{"is_breaking": true/false, "event_title": "Chinese headline (5-15 chars) or null", "summary": "1-2 sentence Chinese summary or null", "category": "category name or null", "impact_score": 0-100 or null, "matched_event_id": "UUID or null", "matched_story_id": "UUID or null"}}

    DO NOT include any explanatory text. Output only the JSON.""",
            env="PROMPT_BREAKING_ONEPASS"
        )

    # 英文内容专用 prompt - 强调翻译而非提取
    prompt_breaking_onepass_english: str = Field(
        default="""You are a senior news translator and editor. Your primary task is to TRANSLATE English news into accurate Chinese.

### IMPORTANT RULES:
1. ALWAYS translate the English content to Chinese first
2. Extract a meaningful Chinese headline (5-15 characters) from the TRANSLATED content
3. NEVER use "Breaking News" as a headline - it provides no information value
4. If the content is too short to extract meaning, set is_breaking=false

### INPUT DATA:
【New Raw Stream】:
{input_data}

### OUTPUT (JSON):
Return valid JSON with:
- is_breaking: true if this is significant breaking news
- event_title: Chinese headline (5-15 chars, NEVER "Breaking News")
- summary: 1-2 sentence Chinese summary
- category: [War & Conflict, International Relations, Macro Economics, Emergency/Disaster, Major Tech/Science, Other]
- impact_score: 0-100
- matched_event_id: UUID or null
- matched_story_id: UUID or null""",
            env="PROMPT_BREAKING_ONEPASS_ENGLISH"
        )

    # 空标题重试 prompt - 专门用于翻译和提取
    prompt_breaking_onepass_retry: str = Field(
        default="""You are a translator. Extract a meaningful Chinese title from this news content.

### TASK:
1. If the content is in English, translate it to Chinese first
2. Then extract a concise Chinese headline (5-15 characters)
3. IMPORTANT: Never output "Breaking News" as the title - this is forbidden

### INPUT DATA:
{input_data}

### OUTPUT (JSON ONLY - no other text):
Output ONLY valid JSON matching this exact format:
{{"is_breaking": true, "event_title": "actual Chinese headline (5-15 chars)", "summary": "Chinese summary", "category": "category name", "impact_score": 0-100, "matched_event_id": null, "matched_story_id": null}}

DO NOT include any explanatory text. Output only the JSON.""",
            env="PROMPT_BREAKING_ONEPASS_RETRY"
        )

    prompt_twitter_onepass: str = Field(
        default="""You are a senior intelligence analyst. Your task is to analyze tweets and perform triage, scoring, and event matching SIMULTANEOUSLY.

    ### TASKS:
    1. **Triage**: Determine if each tweet is significant intelligence or noise.
    2. **Scoring**: Assign impact score (0-100, >80=critical intelligence).
    3. **Summary**: Provide concise Chinese summary for significant tweets.
    4. **Event Matching**: Does this belong to any of the 'Recent Twitter Events' listed below?
    - If it matches an existing event, set 'matched_event_id' to that event's ID.
    - If it's significant but no match exists, set 'should_create_event' to true.

    ### INPUT DATA:
    【Recent Twitter Events (For Matching)】:
    {recent_events}

    【Tweets to Analyze】:
    {input_data}

    ### OUTPUT (JSON):
    Return a list of results, one per tweet, with fields:
    - tweet_id: The original tweet ID
    - is_significant: true/false
    - impact_score: 0-100
    - summary_zh: Chinese summary (if significant)
    - category: [Politics, Macro Economy, Tech, Finance, Crisis, Other]
    - is_thread_start: true/false
    - matched_event_id: UUID of existing event to link (null if no match)
    - should_create_event: true if significant and no matching event exists
    - reasoning: Brief reason for the decision""",
            env="PROMPT_TWITTER_ONEPASS"
        )

    prompt_daily_onepass: str = Field(
        default="""You are a tech news analyzer. Analyze each article and provide classification, relevance score, and summary.

    ### CATEGORIES:
    [AI & LLMs, Software Engineering, Hardware & Semiconductors, Cybersecurity, Frontier Tech & Startups, Web3, Other]

    ### SCORING CRITERIA:
    - 90-100: Breaking news, major releases (e.g. GPT-5), critical vulnerabilities.
    - 70-89: Important updates, significant funding, widely used tool updates.
    - 40-69: Minor updates, niche news, rumors.
    - 0-39: Irrelevant, PR fluff, advertisements.

    ### INPUT DATA:
    【Articles to Analyze】:
    {input_data}

    ### OUTPUT (JSON):
    Return ONLY valid JSON with this exact structure:
    {{
      "results": [
        {{
          "article_id": "original article ID",
          "category": "category from the list above",
          "score": 0-100,
          "summary": "One-sentence summary (max 50 words)"
        }},
        ...
      ]
    }}
    Each article in the input must have exactly one result in the array.""",
            env="PROMPT_DAILY_ONEPASS"
        )

    # ==========================
    # Knowledge Graph (Dgraph)
    # 知识图谱配置
    # ==========================
    kg_enabled: bool = Field(default=False, env="KG_ENABLED")
    dgraph_alpha_url: str = Field(default="localhost:9080", env="DGRAPH_ALPHA_URL")

    # ==========================
    # Prompt Engineering
    # 提示词工程
    # ==========================
    prompt_overview: str = Field(default="""Current Date: {current_date}
    请基于以下提供的今天的所有新闻标题，生成一段短短两三句话的“科技圈核心动态概括”。
    要求：仅返回纯文本概述，不要包含任何标题、Markdown 或格式符号。
    
    Titles:
    {context}""", env="PROMPT_OVERVIEW")

    prompt_critique: str = Field(default="""请根据以下提供的一个特定分类下的新闻内容，生成一段极度辛辣、刻薄、甚至带点粗鄙的“喷子式”一句话锐评。
    要求：
    1. 尺度放开，大胆使用网络梗、阴阳怪气、歇后语，甚至是“文明脏话/垃圾话”来拉满嘲讽拉满节目效果。
    2. 必须高频率、高密度地穿插和堆砌强情绪的 Emoji 表情包（如 🤡、💀、💊、🍋、🙄、🚬、🤡💩、🤮 等），让文字看起来充满了攻击性和不屑。不要端着，越犀利越好。
    3. 仅返回纯文本锐评本身，不要带任何前缀（如“锐评：”）。
    
    News Context:
    {context}""", env="PROMPT_CRITIQUE")

    prompt_translate_titles: str = Field(default="""请将以下用换行符分隔的多条英文新闻标题，严格逐字、逐行地翻译成准确、流畅的中文。
    要求：
    1. 必须原路返回，即**输入共有多少行，输出必须有多少行**。
    2. 仅返回翻译后的中文标题文本本身，不要添加任何编号、项目符号（如 - 或 1.）或任何其他额外说明。
    3. 每行对应原文的翻译，保持顺序绝对一致。
    
    Titles to translate:
    {context}""", env="PROMPT_TRANSLATE_TITLES")

    prompt_twitter_batch_triage: str = Field(default="""你是一位资深的社交媒体情报分析师。你的任务是分析以下这一组推特（Twitter/X），并进行批量过滤、打分和分类。

    ### 指令：
    对于列表中的每一条推文，请执行：
    1. **重要性判定 (is_significant)**：包含高价值情报、政策宣布、重大突破或突发新闻。日常闲聊、无评价转推、琐碎回复设为 false。
    2. **打分 (impact_score)**：0-100。
    3. **中文摘要 (summary_zh)**：如果重要，提供一段简练中文摘要。
    4. **类别 (category)**：[Politics, Macro Economy, Tech, Finance, Crisis, Other]。
    5. **Thread检测 (is_thread_start)**：是否为系列推文开始。

    ### 输入数据 (Batch)：
    {context}

    请严格按照指定的结构化输出返回结果列表，并确保 `tweet_id` 与输入一一对应。
    """, env="PROMPT_TWITTER_BATCH_TRIAGE")

    # ==========================
    # A股分析配置
    # ==========================
    enable_astock_analysis: bool = Field(default=True, env="ENABLE_ASTOCK_ANALYSIS")
    astock_pre_market_hour: int = Field(default=8, env="ASTOCK_PRE_MARKET_HOUR")
    astock_pre_market_minute: int = Field(default=30, env="ASTOCK_PRE_MARKET_MINUTE")
    astock_intraday_hour: int = Field(default=14, env="ASTOCK_INTRADAY_HOUR")
    astock_intraday_minute: int = Field(default=30, env="ASTOCK_INTRADAY_MINUTE")
    astock_post_market_hour: int = Field(default=15, env="ASTOCK_POST_MARKET_HOUR")
    astock_post_market_minute: int = Field(default=30, env="ASTOCK_POST_MARKET_MINUTE")
    astock_push_telegram: bool = Field(default=True, env="ASTOCK_PUSH_TELEGRAM")
    astock_push_dingtalk: bool = Field(default=True, env="ASTOCK_PUSH_DINGTALK")
    astock_semantic_threshold: float = Field(default=0.7, env="ASTOCK_SEMANTIC_THRESHOLD")
    astock_query_template: str = Field(
        default="A股 股市 大盘 指数 宏观经济 货币政策 财政政策 行业政策 美联储 央行 房地产 新能源 半导体",
        env="ASTOCK_QUERY_TEMPLATE"
    )
    astock_news_hours: int = Field(default=24, env="ASTOCK_NEWS_HOURS")

    # ==========================
    # A股异常波动推送配置
    # ==========================
    enable_astock_alert: bool = Field(default=True, env="ENABLE_ASTOCK_ALERT")
    astock_alert_threshold: float = Field(default=3.0, env="ASTOCK_ALERT_THRESHOLD")  # 涨跌幅阈值 %
    astock_alert_volume_multiplier: float = Field(default=2.0, env="ASTOCK_ALERT_VOLUME_MULTIPLIER")  # 成交量倍数
    astock_alert_check_interval: int = Field(default=30, env="ASTOCK_ALERT_CHECK_INTERVAL")  # 检查间隔（分钟）
    astock_alert_push_telegram: bool = Field(default=True, env="ASTOCK_ALERT_PUSH_TELEGRAM")
    astock_alert_push_dingtalk: bool = Field(default=True, env="ASTOCK_ALERT_PUSH_DINGTALK")

    # ==========================
    # External LLM Configuration
    # 外部大语言模型配置
    # ==========================
    llm_api_key: str = Field(default="", env="LLM_API_KEY")
    llm_base_url: str = Field(default="https://api.openai.com/v1", env="LLM_BASE_URL")
    llm_model_name: str = Field(default="gpt-4o-mini", env="LLM_MODEL_NAME")

    # ==========================
    # Redis Cache Configuration
    # Redis 缓存配置
    # ==========================
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: str = Field(default="", env="REDIS_PASSWORD")
    redis_enabled: bool = Field(default=False, env="REDIS_ENABLED")

    # Determine environment config file dynamically
    _env_name = os.getenv("OMNIDIGEST_ENV")
    _env_file = f".env.{_env_name}" if _env_name else ".env"

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        env_file_parse_booleans=True,
        extra="ignore"
    )

settings = Settings()
