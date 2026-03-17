"""
Breaking News Crawler Service. 
Fetches "fast lane" breaking news from high-intensity traditional media RSS feeds.
This acts as the MVP ingestion engine for the new decoupled Explosive News system.
All it does is fetch raw text and dump it into `breaking_stream_raw` for the Processor.

突发新闻抓取服务。
从高频传统媒体 RSS 源获取“快车道”突发新闻。
这是作为新解耦的突发新闻系统的 MVP 数据摄取引擎。
它唯一的职责是获取原始文本并将其放入 `breaking_stream_raw` 供处理器使用。
"""
import feedparser
import logging
import requests
import calendar
from newspaper import Article, Config
import concurrent.futures
from datetime import datetime, timezone
from ....core.database import DatabaseManager

logger = logging.getLogger(__name__)

class BreakingCrawler:
    """
    Crawls high-priority breaking news feeds.
    抓取高优先级突发新闻订阅源。
    """
    def __init__(self, db: DatabaseManager):
        """
        Initializes the BreakingCrawler with a database connection and configuration.
        使用数据库连接和配置初始化 BreakingCrawler。
        
        Args:
            db (DatabaseManager): The database manager instance via dependency injection. / 通过依赖注入提供的数据库管理器实例。
        """
        self.db = db
        # Configuration for newspaper3k to fetch full article content
        # newspaper3k 配置，用于抓取文章全文内容
        self.news_config = Config()
        self.news_config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        self.news_config.request_timeout = 8  # Shorter timeout than daily crawler for speed / 比日报爬虫更短的超时以保证速度
        self.max_workers = 15
        self.user_agent = self.news_config.browser_user_agent

    # Full browser-like headers to bypass anti-scraping detection on sites like France24, NYT, WSJ
    # 完整的浏览器请求头，用于绕过 France24、NYT、WSJ 等站点的反爬虫检测
    _BROWSER_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

    def _fetch_article_content(self, url: str, fallback_text: str) -> str:
        """
        Attempts to fetch the full article content. Downloads HTML with full browser-like
        headers via requests (to bypass anti-scraping), then uses newspaper3k for parsing only.
        尝试抓取文章全文。通过 requests 使用完整的浏览器请求头下载 HTML（以绕过反爬虫），
        然后仅使用 newspaper3k 进行内容解析。
        """
        try:
            # Download HTML ourselves with realistic browser headers
            # 使用完整浏览器请求头自行下载 HTML
            response = requests.get(url, headers=self._BROWSER_HEADERS, timeout=8, allow_redirects=True)
            response.raise_for_status()

            # Feed the downloaded HTML to newspaper3k for content extraction only
            # 将下载的 HTML 交给 newspaper3k 仅做内容提取
            # Strip NULL bytes and control characters that break lxml parsing
            # 去除 NULL 字节和控制字符，防止 lxml 解析报错
            import re
            clean_html = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', response.text)
            article = Article(url, config=self.news_config)
            article.set_html(clean_html)
            article.parse()

            if article.text and len(article.text) > len(fallback_text):
                logger.info(f"Extracted full text for '{url}' ({len(article.text)} chars)")
                return article.text
            else:
                logger.warning(f"Full text extraction empty or shorter than summary for '{url}', using fallback.")
        except Exception as e:
            logger.warning(f"Failed to fetch article content for {url}: {e}")
        return fallback_text

    def _process_breaking_source(self, source: dict):
        """
        Processes a single fast-lane RSS source and inserts items into breaking_stream_raw.
        处理单个快车道 RSS 源并将项目插入到 breaking_stream_raw。
        """
        url = source["url"]
        platform = source["platform"]
        logger.info(f"Fetching Breaking RSS feed: {url}")
        
        try:
            headers = {'User-Agent': self.user_agent}
            # Breaking news requires strict thin timeouts (we don't wait for slow servers)
            # 突发新闻需要严格的极短超时（我们不等慢速服务器）
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            content = response.content
            feed = feedparser.parse(content)

            if getattr(feed, 'bozo', False):
                logger.warning(f"Feedparser bozo error for {url}: {feed.bozo_exception}")

            # Process up to 10 latest breaking items per feed
            # 每个数据源最多处理 10 条最新突发项目
            feed_entries = getattr(feed, 'entries', [])
            inserted_count = 0
            
            for entry in feed_entries[:10]:
                link = getattr(entry, 'link', '')
                if not link:
                    continue
                
                title = getattr(entry, 'title', 'Untitled')
                summary = entry.get('summary', '') or entry.get('description', '')
                
                # Fetch full article content, falling back to RSS summary
                # 抓取文章全文，失败则回退到 RSS 摘要
                article_content = self._fetch_article_content(link, summary)
                
                # The raw text includes title and full content for LLM analysis and quant use
                # 原始文本包含标题和全文，供 LLM 分析和量化使用
                raw_text = f"Title: {title}\nContent: {article_content}"
                
                author = entry.get('author', platform)
                
                pub_time = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    utc_timestamp = calendar.timegm(entry.published_parsed)
                    pub_time = datetime.fromtimestamp(utc_timestamp, timezone.utc).replace(tzinfo=None)
                else:
                    pub_time = datetime.now()
                
                # Insert to raw stream. The DB handles duplicates via ON CONFLICT (source_url)
                # 插入原始流。数据库会通过 ON CONFLICT (source_url) 处理重复项
                stream_id = self.db.add_breaking_stream_raw(
                    source_platform=platform,
                    source_url=link,
                    raw_text=raw_text,
                    author=author,
                    publish_time=pub_time
                )
                
                if stream_id:
                    inserted_count += 1
            
            if inserted_count > 0:
                logger.info(f"Ingested {inserted_count} new breaking streams from {platform}.")
            
            # Track successful fetch
            self.db.increment_breaking_rss_success(url)

        except Exception as e:
            logger.error(f"Failed to fetch Breaking RSS feed {url}: {e}")
            self.db.increment_breaking_rss_failure(url, str(e))

    def run(self):
        """
        Executes the main breaking crawl loop.
        执行主突发抓取循环。
        """
        sources = self.db.get_breaking_rss_sources()
        if not sources:
            logger.warning("No enabled breaking RSS sources found in database.")
            return

        logger.info(f"Starting breaking crawl of {len(sources)} fast-lane sources...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self._process_breaking_source, source) for source in sources]
            concurrent.futures.wait(futures)
            
        logger.info("Breaking Crawl completed.")
