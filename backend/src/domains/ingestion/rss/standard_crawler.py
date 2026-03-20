"""
News crawling service. Fetches articles from RSS feeds, parses content using newspaper3k, and stores them in the database.
新闻抓取服务。从 RSS 订阅源获取文章，使用 newspaper3k 解析内容，并将其存储在数据库中。
"""
import feedparser
import time
import logging
import requests
import calendar
import concurrent.futures
from datetime import datetime, timezone
from ....core.database import DatabaseManager
from ...knowledge_base.rag_client import RAGClient
from ....config import settings
from newspaper import Article, Config

logger = logging.getLogger(__name__)

class NewsCrawler:
    """
    Crawls news from RSS feeds and processes them concurrently.
    并发地从 RSS 订阅源抓取新闻并进行处理。
    """
    def __init__(self, db: DatabaseManager, rag: RAGClient):
        """
        Initializes the NewsCrawler with database, RAG clients, and threading objects.
        使用数据库、RAG 客户端和线程对象初始化 NewsCrawler。
        
        Args:
            db (DatabaseManager): Database manager. / 数据库管理器。
            rag (RAGClient): RAG client. / RAG 客户端。
        """
        self.db = db
        self.rag = rag
        # Configuration for newspaper3k to mimic a real browser to bypass basic anti-scraping
        # newspaper3k 的配置，以模拟真实浏览器以绕过基本反爬虫
        self.news_config = Config()
        self.news_config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        self.news_config.request_timeout = 10
        self.max_workers = 10  # Maximum number of concurrent feeds to process / 最大并发处理的订阅源数量

    def _resolve_url(self, url):
        """
        Attempts to resolve intermediate redirect URLs (like Google News links) to find the actual target article URL.
        尝试解析中间重定向 URL（如 Google News 链接）以找到实际的目标文章 URL。
        
        Args:
            url (str): The original (potentially redirected) URL. / 原始的（可能被重定向的）URL。
            
        Returns:
            str: The resolved final URL, or the original URL if resolution fails. / 解析后的最终 URL，如果解析失败则返回原始 URL。
        """
        try:
            # Google News links might require cookies or specific handling. 
            # Simple requests.head often works for basic redirects.
            # Google News 链接可能需要 Cookie 或特殊处理。
            # 简单的 requests.head 通常适用于基本的重定向。
            response = requests.head(url, allow_redirects=True, timeout=10)
            return response.url
        except Exception as e:
            logger.warning(f"Failed to resolve URL {url}: {e}")
            return url

    def _process_source(self, source):
        """
        Processes a single RSS source: fetching, parsing, and storing articles.
        处理单个 RSS 源：获取、解析并存储文章。
        """
        MAX_FAILURES = 5  # Threshold to automatically disable a feed
        url = source[0]  # source is a tuple (url, name)
        logger.info(f"Fetching RSS feed: {url}")
        try:
            # Add User-Agent to avoid being blocked by some servers
            # 添加 User-Agent 以避免被某些服务器屏蔽
            headers = {'User-Agent': self.news_config.browser_user_agent}
            
            # Fetch content with strict timeout
            # 使用严格的超时获取内容
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            content = response.content

            feed = feedparser.parse(content)
            
            # Check for bozo exception (malformed XML or network error caught by feedparser)
            # 检查 bozo 异常（格式错误的 XML 或 feedparser 捕获的网络错误）
            if feed.bozo:
                error_msg = f"Feedparser bozo error: {feed.bozo_exception}"
                logger.warning(f"{error_msg} for {url}")
                fail_count = self.db.increment_rss_failure(url, error_msg)
                if fail_count >= MAX_FAILURES:
                    logger.error(f"RSS Source {url} reached max failures ({MAX_FAILURES}). Auto-disabling.")
                    self.db.disable_rss_source(url)
                # Return early if no entries are present
                if not getattr(feed, 'entries', False):
                    return

            # If we successfully parsed the feed and have entries, reset the fail_count
            if getattr(feed, 'entries', False):
                self.db.reset_rss_failure(url)

        except Exception as e:
            error_msg = f"Request/Connection error: {e}"
            logger.error(f"Failed to fetch RSS feed {url}: {error_msg}")
            fail_count = self.db.increment_rss_failure(url, error_msg)
            if fail_count >= MAX_FAILURES:
                logger.error(f"RSS Source {url} reached max failures ({MAX_FAILURES}). Auto-disabling.")
                self.db.disable_rss_source(url)
            return

        # Limit to 5 articles per feed as requested
        # 根据要求，每个订阅源限制为 5 篇文章
        feed_entries = getattr(feed, 'entries', [])
        for entry in feed_entries[:5]:
            title = getattr(entry, 'title', 'Untitled')
            link = getattr(entry, 'link', '')
            if not link:
                continue
                
            rss_summary = entry.get('summary', '') or entry.get('description', '')
            source_name = feed.feed.get('title', 'Unknown Source')
            
            # Deduplication check: Skip if URL already exists
            # 去重检查：如果 URL 已存在则跳过
            exists = self.db.check_exists(link)
            if exists:
                logger.info(f"Skipping existing article: {title}")
                continue
            
            # Full text extraction attempt
            # 尝试全文提取
            article_content = rss_summary
            try:
                # Resolve Google News redirect
                # 解析 Google News 重定向
                final_url = self._resolve_url(link)
                if final_url != link:
                    logger.info(f"Resolved URL: {link} -> {final_url}")
                
                article = Article(final_url, config=self.news_config)
                article.download()
                article.parse()
                if article.text and len(article.text) > len(rss_summary):
                    article_content = article.text
                    logger.info(f"Extracted full text for '{title}' ({len(article_content)} chars)")
                else:
                    logger.warning(f"Full text extraction empty or shorter than summary for '{title}', using summary.")
            except Exception as e:
                logger.error(f"Failed to extract full text for '{title}': {e}")
                # Fallback to RSS summary is automatic since article_content was initialized with it
                # 自动回退到 RSS 摘要，因为 article_content 已经初始化为摘要
            
            pub_time = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                # feedparser published_parsed is a struct_time in UTC
                utc_timestamp = calendar.timegm(entry.published_parsed)
                pub_time = datetime.fromtimestamp(utc_timestamp, timezone.utc).replace(tzinfo=None)
            
            article_id = self.db.add_article(title, article_content, link, source_name, pub_time)
            
            if article_id:
                logger.info(f"Processing new article: {title}")
                
                # Prepare metadata
                # 准备元数据
                meta = {
                    "source_url": link,
                    "publish_time": pub_time.timestamp() if pub_time else datetime.now().timestamp()
                }
                
                # Prepare content with Source URL for RAG context
                # 为 RAG 上下文准备包含源 URL 的内容
                content_to_upload = f"{article_content}\n\nSource URL: {link}"
                
                if settings.ragflow_enabled:
                    doc_id = self.rag.upload_document(title, content_to_upload, metadata=meta)
                    if doc_id:
                        # NEW: Trigger parsing immediately
                        # 新增：立即触发解析
                        self.rag.trigger_parsing([doc_id])
                        self.db.update_status(article_id, 1, ragflow_id=doc_id)
                    else:
                        # Handle RAG upload failure - still mark as processed to avoid limbo
                        # 处理 RAG 上传失败 - 仍标记为已处理，避免文章处于不确定状态
                        self.db.update_status(article_id, 1, ragflow_id=None)
                else:
                    logger.info(f"Skipping RAGFlow upload for '{title}' (disabled in config).")
                    self.db.update_status(article_id, 1, ragflow_id=None)

    def run(self):
        """
        Executes the main crawling loop using a thread pool. It retrieves enabled RSS sources 
        from the database and processes them concurrently.
        使用线程池执行主爬取循环。它从数据库中检索启用的 RSS 源并并发处理。
        """
        # Fetch enabled RSS sources from database safely
        # 安全地从数据库获取已启用的 RSS 源
        rss_sources = self.db.get_rss_sources()
            
        if not rss_sources:
            logger.warning("No enabled RSS sources found in database.")
            return

        logger.info(f"Starting concurrent crawl of {len(rss_sources)} RSS sources...")
        
        # Use ThreadPoolExecutor to fetch and process sources concurrently
        # 使用 ThreadPoolExecutor 并发获取和处理资源
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self._process_source, source) for source in rss_sources]
            concurrent.futures.wait(futures)
            
        logger.info("Crawl completed.")
