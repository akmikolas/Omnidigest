"""
RAGFlow synchronization service. Handles batch uploading of historical database articles to the RAGFlow knowledge base.
RAGFlow 同步服务。处理将历史数据库文章批量上传到 RAGFlow 知识库的操作。
"""
import logging
import time
from datetime import datetime
from ...core.database import DatabaseManager
from .rag_client import RAGClient
from ...config import settings

logger = logging.getLogger(__name__)

class RAGService:
    """
    Service for managing RAGFlow interactions, specifically syncing historical data.
    用于管理 RAGFlow 交互的服务，专门用于同步历史数据。
    """
    def __init__(self, db: DatabaseManager, rag: RAGClient):
        """
        Initializes the RAGService with required dependencies.
        使用所需的依赖项初始化 RAGService。
        
        Args:
            db (DatabaseManager): The database manager instance for querying un-synced articles. / 用于查询未同步文章的数据库管理器实例。
            rag (RAGClient): The core RAG client instance for uploading and parsing. / 用于上传和解析的核心 RAG 客户端实例。
        """
        self.db = db
        self.rag = rag

    def sync_articles_to_rag(self, limit: int = 100) -> int:
        """
        Incrementally synchronizes a batch of un-synced articles from the local database to the remote RAGFlow knowledge base. It uploads the document content, attaches metadata, triggers parsing, and updates the local database with the generated RAGFlow ID.
        将一批未同步的文章从本地数据库增量同步到远程 RAGFlow 知识库。它上传文档内容，附加元数据，触发解析，并使用生成的 RAGFlow ID 更新本地数据库。
        
        Note: This forces initialization of the RAG client even if disabled in the global config, as this represents an explicit manual sync action.
        注意：即使在全局配置中禁用，这也将强制初始化 RAG 客户端，因为这表示明确的手动同步操作。
        
        Args:
            limit (int, optional): The maximum number of articles to sync in this batch. Defaults to 100. / 此批次中要同步的最大文章数。默认为 100。
            
        Returns:
            int: The number of articles successfully synchronized. / 成功同步的文章数量。
        """
        # Force initialization if not present (manual override)
        if not self.rag.client:
            logger.info("RAG client not initialized. Attempting manual initialization for sync...")
            try:
                from ragflow_sdk import RAGFlow
                self.rag.client = RAGFlow(api_key=settings.ragflow_api_key, base_url=self.rag.base_url)
                logger.info("Manual RAG initialization successful.")
            except Exception as e:
                logger.error(f"Failed to manually initialize RAG client: {e}")
                return 0

        # Fetch articles without ragflow_id
        # 获取没有 ragflow_id 的文章
        # We need a new method in DB or use a raw query here for simplicity since it's a specific maintenance task
        # 我们需要在 DB 中添加一个新方法，或者为了简单起见在这里使用原始查询，因为它是一个特定的维护任务
        
        # Adding a temporary helper method to DB via monkey patching or just extending DB class is cleaner.
        # Let's rely on a new DB method `get_articles_without_ragid` that we should add.
        # But to avoid touching DB class again just for this query, let's use the existing connection pattern if possible,
        # or better, add the method to DB class as it's cleaner. 
        # Wait, the plan didn't explicitly say modify DB for this query, but let's do it properly.
        # Actually, let's look at `get_unclassified_articles` structure in database.py and mimic it or add a new one.
        
        # For now, I will assume we should add `get_articles_to_sync` to database.py as it is better practice.
        # But to stick to the plan strictly which didn't mention DB modification for this specific fetch (oops),
        # I will implement the DB fetch logic here if I can't modify DB. 
        # However, modifying DB is safe and correct. I will add `get_articles_without_rag_id` to database.py next.
        
        articles = self.db.get_articles_without_rag_id(limit=limit)
        
        if not articles:
            logger.info("No articles found needing sync.")
            return 0
            
        logger.info(f"Found {len(articles)} articles to sync to RAGFlow...")
        synced_count = 0
        
        for article in articles:
            try:
                # Prepare content with Source URL
                title = article['title']
                content = article['content']
                link = article['source_url']
                pub_time = article['publish_time']
                
                meta = {
                    "source_url": link,
                    "publish_time": pub_time.timestamp() if pub_time else datetime.now().timestamp()
                }
                
                content_to_upload = f"{content}\n\nSource URL: {link}"
                
                doc_id = self.rag.upload_document(title, content_to_upload, metadata=meta)
                
                if doc_id:
                     self.rag.trigger_parsing([doc_id])
                     self.db.update_status(article['id'], 1, ragflow_id=doc_id)
                     synced_count += 1
                     logger.info(f"Synced '{title}' to RAGFlow.")
                     time.sleep(0.5) # Rate limiting
                else:
                    logger.warning(f"Failed to upload '{title}'")
                    
            except Exception as e:
                logger.error(f"Error syncing article {article['id']}: {e}")
                
        return synced_count
