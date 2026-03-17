"""
Database mixin for daily news article CRUD operations.
每日新闻文章 CRUD 操作的数据库 Mixin。

Provides methods for adding, querying, classifying, and deleting
news articles, as well as retrieving articles for RAG syncing.
提供添加、查询、分类和删除新闻文章的方法，以及检索用于 RAG 同步的文章。
"""
import logging
import uuid
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class DailyNewsMixin:
    """
    Mixin for managing daily news articles and classification data.
    用于管理每日新闻文章和分类数据的 Mixin。
    """
    def check_exists(self, source_url):
        """
        Checks if an article with the given URL already exists in the database.
        检查具有给定 URL 的文章是否已存在于数据库中。
        
        Args:
            source_url (str): The URL of the article to check. / 要检查的文章的 URL。
            
        Returns:
            bool: True if it exists, False otherwise. / 如果存在则返回 True，否则返回 False。
        """
        query = "SELECT 1 FROM news_articles WHERE source_url = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Execute select with URL parameter to prevent SQL injection
                    # 使用 URL 参数执行 select 以防止 SQL 注入
                    cur.execute(query, (source_url,))
                    return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking existence: {e}")
            return False

    def add_article(self, title, content, source_url, source_name, publish_time):
        """
        Adds a new article to the database if the URL doesn't exist. Generates a new UUID for the article.
        如果 URL 不存在，则将新文章添加到数据库。为文章生成一个新的 UUID。
        
        Args:
            title (str): Article title. / 文章标题。
            content (str): Full article text. / 文章全文。
            source_url (str): Original URL of the article. / 文章的原始 URL。
            source_name (str): Name of the publisher/RSS feed. / 发布者/RSS 源的名称。
            publish_time (datetime): Publication timestamp. / 发布时间戳。
            
        Returns:
            str | None: The new article's UUID if inserted, or None if skipped (on conflict) or error. / 如果插入则返回新文章的 UUID，如果跳过（发生冲突）或出错则返回 None。
        """
        query = """
        INSERT INTO news_articles (id, title, content, source_url, source_name, publish_time)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_url) DO NOTHING
        RETURNING id;
        """
        article_id = str(uuid.uuid4())
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (article_id, title, content, source_url, source_name, publish_time))
                    result = cur.fetchone()
                conn.commit()
                # Return the ID only if the row was actually inserted
                # 仅在实际插入行时才返回 ID
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error adding article: {e}")
            return None

    def update_status(self, article_id, status, ragflow_id=None):
        """
        Updates the processing status of an article, and optionally associates a RAGFlow document ID.
        更新文章的处理状态，并可选地关联一个 RAGFlow 文档 ID。
        
        Args:
            article_id (str): The UUID of the article. / 文章的 UUID。
            status (int): The new status code. / 新的状态代码。
            ragflow_id (str, optional): The corresponding document ID in RAGFlow. Defaults to None. / RAGFlow 中相应的文档 ID。默认为 None。
        """
        if ragflow_id:
            query = "UPDATE news_articles SET status = %s, ragflow_id = %s WHERE id = %s"
            params = (status, ragflow_id, article_id)
        else:
            query = "UPDATE news_articles SET status = %s WHERE id = %s"
            params = (status, article_id)
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating article status: {e}")

    def get_url_search(self, partial_title: str):
        """
        Retrieves the source_url of an article using a partial title match. Useful for finding the original URL when only a truncated title is known.
        使用部分标题匹配检索文章的 source_url。当只知道截断的标题时，用于查找原始 URL 很有用。
        
        Args:
            partial_title (str): The partial title to search for. / 要搜索的部分标题。
            
        Returns:
            str | None: The found source_url, or None if no match is found. / 找到的 source_url，如果没有找到匹配项则返回 None。
        """
        # Try finding a title that starts with the filename title (handling potential truncation)
        # 尝试查找以文件名标题开头的标题（处理潜在的截断）
        query = "SELECT source_url FROM news_articles WHERE title LIKE %s LIMIT 1"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Match beginning of title
                    # 匹配标题的开头
                    cur.execute(query, (partial_title + '%',))
                    result = cur.fetchone()
                    if result:
                        return result[0]
                    
                    # Fallback: Try containment (if filename was middle-truncated?)
                    # 后备：尝试包含匹配（如果文件名是中间截断的？）
                    cur.execute(query, ('%' + partial_title + '%',))
                    result = cur.fetchone()
                    if result:
                        return result[0]
                    return None
        except Exception as e:
            logger.error(f"Error searching URL by title: {e}")
            return None

    def get_unclassified_articles(self, limit=50):
        """
        Retrieves a list of articles that have not yet been assigned a category.
        检索尚未分配类别的文章列表。
        
        Args:
            limit (int, optional): Maximum number of articles to retrieve. Defaults to 50. / 要检索的最大文章数。默认为 50。
            
        Returns:
            list[dict]: A list of article dictionaries containing id, title, content, etc. / 包含 id、title、content 等的文章字典列表。
        """
        query = """
        SELECT id, title, content, source_url, source_name, publish_time 
        FROM news_articles 
        WHERE category IS NULL 
        ORDER BY publish_time DESC 
        LIMIT %s
        """
        try:
            with self._get_connection() as conn:
                # Use RealDictCursor to return rows as dictionaries
                # 使用 RealDictCursor 将行作为字典返回
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (limit,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching unclassified articles: {e}")
            return []

    def update_classification(self, article_id, category, score, summary_raw=None):
        """
        Updates an article with LLM classification and scoring results.
        更新文章的 LLM 分类和评分结果。
        
        Args:
            article_id (str): The UUID of the article to update. / 要更新的文章的 UUID。
            category (str): The determined category (e.g., 'AI & LLMs'). / 确定的类别（例如，'AI & LLMs'）。
            score (int): The relevance score (0-100). / 相关性评分（0-100）。
            summary_raw (str, optional): A short LLM-generated summary. Defaults to None. / 简短的 LLM 生成总结。默认为 None。
        """
        query = """
        UPDATE news_articles 
        SET category = %s, score = %s, summary_raw = %s
        WHERE id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (category, score, summary_raw, article_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating classification: {e}")

    def get_high_score_articles(self, hours=24, min_score=60):
        """
        Retrieves high-scoring articles within a specified recent time window. Useful for generating daily or periodic summaries of important news.
        检索指定最近时间窗口内的高分文章。用于生成重要新闻的每日或定期总结很有用。
        
        Args:
            hours (int, optional): The time window in hours to look back. Defaults to 24. / 要回顾的时间窗口（小时数）。默认为 24。
            min_score (int, optional): The minimum score threshold. Defaults to 60. / 最低分数阈值。默认为 60。
            
        Returns:
            list[dict]: A list of high-scoring article dictionaries. / 高分文章字典的列表。
        """
        # Safely inject the hours interval using string concatenation in query
        # 注意：此处使用字符串拼接，但是由代码内部控制的整数转换，是安全的
        query = """
        SELECT id, title, content, source_url, source_name, publish_time, category, score, summary_raw
        FROM news_articles 
        WHERE publish_time > (CURRENT_TIMESTAMP AT TIME ZONE 'UTC') - (%s || ' hours')::INTERVAL
          AND score >= %s
        ORDER BY category, score DESC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (str(hours), min_score))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching high score articles: {e}")
            return []

    def get_low_score_articles(self, threshold=45):
        """
        Retrieves articles with a score strictly less than the given threshold. Useful for scheduled cleanup of low-value content to save database space.
        检索分数严格低于给定阈值的文章。用于定期清理低价值内容以节省数据库空间时很有用。
        
        Args:
            threshold (int, optional): The score threshold. defaults to 45. / 分数阈值。默认为 45。
            
        Returns:
            list[dict]: A list of low-scoring article dictionaries containing at least id, title, and ragflow_id. / 低分文章字典列表，至少包含 id、title 和 ragflow_id。
        """
        query = """
        SELECT id, title, ragflow_id 
        FROM news_articles 
        WHERE score < %s AND score IS NOT NULL
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (threshold,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching low score articles: {e}")
            return []

    def delete_article(self, article_id):
        """
        Deletes a specific article from the database by its UUID.
        根据其 UUID 从数据库中删除特定文章。
        
        Args:
            article_id (str): The UUID of the article to delete. / 要删除的文章的 UUID。
        """
        query = "DELETE FROM news_articles WHERE id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (article_id,))
                conn.commit()
            logger.info(f"Deleted article {article_id} from database.")
        except Exception as e:
            logger.error(f"Error deleting article {article_id}: {e}")


    def get_articles_without_rag_id(self, limit=100):
        """
        Retrieves articles that have not yet been uploaded to RAGFlow (ragflow_id IS NULL). Used by the RAG sync background job.
        检索尚未上传至 RAGFlow 的文章（ragflow_id 为 NULL）。由 RAG 同步后台任务使用。
        
        Args:
            limit (int, optional): The maximum number of articles to retrieve per batch. Defaults to 100. / 每批检索的最大文章数。默认为 100。
            
        Returns:
            list[dict]: A list of article dictionaries containing id, title, content, source_url, publish_time. / 包含 id、title、content、source_url、publish_time 的文章字典列表。
        """
        query = """
        SELECT id, title, content, source_url, publish_time 
        FROM news_articles 
        WHERE ragflow_id IS NULL 
        ORDER BY publish_time DESC 
        LIMIT %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (limit,))
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching articles for RAG sync: {e}")
            return []

    def get_articles_by_date_range(self, days: int = 30):
        """
        Retrieves article metadata for the specified past number of days. Useful for generating analytics, charts, or broader trend reports.
        检索指定过去天数的文章元数据。对于生成分析、图表或更广泛的趋势报告很有用。
        
        Args:
            days (int, optional): The number of days to look back. Defaults to 30. / 要回顾的天数。默认为 30。
            
        Returns:
            list[dict]: Article metadata including id, title, summary, score, url, time, and category. / 文章元数据，包括 id、标题、摘要、评分、url、时间 和 category。
        """
        # Safely inject the days interval using string concatenation in query
        # 注意：此处使用字符串拼接，但是由代码内部控制的整数转换，是安全的
        query = """
        SELECT id, title, summary_raw, score, source_url, publish_time, category
        FROM news_articles 
        WHERE publish_time > NOW() - (%s || ' days')::INTERVAL
        ORDER BY score DESC, publish_time DESC
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, (str(days),))
                    return cur.fetchall()
        except Exception as e:
            return []

