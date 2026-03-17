"""
RAGFlow client integration. Handles connection to the RAGFlow API for uploading, deleting, and searching knowledge base documents.
RAGFlow 客户端集成。处理与 RAGFlow API 的连接，用于上传、删除和搜索知识库文档。
"""
import logging
import time
import datetime
from ragflow_sdk import RAGFlow
from ...config import settings

logger = logging.getLogger(__name__)

class RAGClient:
    """
    Client wrapper for interacting with the RAGFlow API. Handles SDK initialization, dataset retrieval, document uploading, and parsing triggers.
    用于与 RAGFlow API 交互的客户端包装器。处理 SDK 初始化、数据集检索、文档上传和解析触发。
    """
    def __init__(self, db=None):
        """
        Initializes the RAGFlow client and optionally an external LLM client.
        初始化 RAGFlow 客户端以及可选的外部 LLM 客户端。
        
        Args:
            db (DatabaseManager, optional): The database manager instance. Defaults to None. / 数据库管理器实例。默认为 None。
        """
        self.db = db
        self.api_key = settings.ragflow_api_key
        # Ensure the base_url doesn't incorrectly include API version suffixes expected by the SDK
        # 确保 base_url 没有错误地包含 SDK 预期的 API 版本后缀
        base_url = settings.ragflow_api_url
        if base_url.endswith("/api/v1"):
            base_url = base_url.replace("/api/v1", "")
        if base_url.endswith("/v1"):
            base_url = base_url.replace("/v1", "")
        
        self.base_url = base_url
        self.dataset_id = settings.ragflow_dataset_id
        
        # Session Persistence
        # 会话持久化
        self.chat = None
        self.session = None
        
        if settings.ragflow_enabled or settings.breaking_rag_enabled:
            try:
                self.client = RAGFlow(api_key=self.api_key, base_url=self.base_url)
                logger.info(f"Initialized RAGFlow SDK with base_url: {self.base_url}")
            except Exception as e:
                logger.error(f"Failed to initialize RAGFlow SDK: {e}")
                self.client = None
        else:
            logger.info("RAGFlow integration disabled in settings.")
            self.client = None

        # External LLM Client (OpenAI-compatible)
        # 外部 LLM 客户端（兼容 OpenAI）
        self.llm_client = None
        try:
             from openai import OpenAI
             if settings.llm_api_key and settings.llm_api_key.startswith("sk-"):
                 self.llm_client = OpenAI(
                     api_key=settings.llm_api_key,
                     base_url=settings.llm_base_url
                 )
                 logger.info(f"Initialized External LLM Client: {settings.llm_model_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize External LLM Client: {e}")

    def _get_dataset(self, dataset_id: str = None):
        """
        Internal helper method to retrieve the target RAGFlow dataset object based on settings.
        内部辅助方法，根据设置检索目标 RAGFlow 数据集对象。
        
        Args:
            dataset_id (str, optional): The dataset to retrieve. Defaults to self.dataset_id. / 要检索的数据集。如果未提供则使用实例默认。
        
        Returns:
            ragflow_sdk.Dataset | None: The dataset object if found, otherwise None. / 如果找到则返回数据集对象，否则返回 None。
        """
        if not self.client:
            return None
        target_id = dataset_id or self.dataset_id
        if not target_id:
            logger.error("No dataset ID provided or configured.")
            return None
            
        try:
            datasets = self.client.list_datasets(id=target_id)
            if datasets:
                return datasets[0]
            logger.error(f"Dataset {self.dataset_id} not found.")
            return None
        except Exception as e:
            logger.error(f"Error getting dataset: {e}")
            return None

    def list_datasets(self):
        """
        Lists all available datasets in the bound RAGFlow account.
        列出绑定的 RAGFlow 帐户中所有可用的数据集。
        
        Returns:
            list: A list of dataset objects. / 数据集对象列表。
        """
        if not self.client:
            return []
        try:
            return self.client.list_datasets()
        except Exception as e:
            logger.error(f"Error listing datasets: {e}")
            return []

    def upload_document(self, title: str, content: str, metadata: dict = None, dataset_id: str = None) -> str:
        """
        Uploads a text document to the configured RAGFlow dataset and returns its generated ID. Also attaches optional metadata.
        将文本文档上传到配置的 RAGFlow 数据集并返回其生成的 ID。还可以将可选的元数据附加到上传的文档。
        
        Args:
            title (str): The display title/filename of the document. / 文档的显示标题/文件名。
            content (str): The raw text content to upload. / 要上传的原始文本内容。
            metadata (dict, optional): A dictionary of metadata to attach. Defaults to None. / 要附加的元数据字典。默认为 None。
            dataset_id (str, optional): The dataset to upload to. Defaults to None. / 要上传的数据集。默认为 None。
            
        Returns:
            str | None: The generated document ID if successful, or None/error string if failed. / 如果成功则返回生成的文档 ID，如果失败则返回 None 或错误字符串。
        """
        dataset = self._get_dataset(dataset_id)
        if not dataset:
            return None

        # Generate timestamped filename
        # 生成带时间戳的文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{title}.txt"
        
        try:
            logger.info(f"Uploading '{filename}' to dataset {dataset.id}...")
            # SDK expects list of dicts with 'display_name' and 'blob'
            # SDK 期望包含 'display_name' 和 'blob' 的字典列表
            blob = content.encode('utf-8')
            dataset.upload_documents([{"display_name": filename, "blob": blob}])
            
            # SDK upload doesn't return ID, so we must fetch it
            # We filter by the exact filename we just used
            # SDK 上传不返回 ID，所以我们必须获取它
            # 我们根据刚才使用的确切文件名进行过滤
            time.sleep(1) # Slight delay to ensure consistency / 轻微延迟以确保一致性
            docs = dataset.list_documents(keywords=filename, page=1, page_size=5)
            doc_id = None
            for doc in docs:
                if doc.name == filename:
                    doc_id = doc.id
                    logger.info(f"Successfully uploaded: {doc_id}")
                    
                    # Update metadata if provided
                    # 如果提供了元数据，则进行更新
                    if metadata:
                        try:
                            # doc.update expects a dict with meta_fields
                            # doc.update 期望一个包含 meta_fields 的字典
                            doc.update({"meta_fields": metadata})
                            logger.info(f"Updated metadata for {doc_id}: {metadata}")
                        except Exception as e:
                            logger.error(f"Failed to update metadata for {doc_id}: {e}")
                    
                    return doc_id
            
            logger.warning("Upload seemed successful but could not retrieve document ID.")
            return "uploaded_unknown_id"
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            return None

    def delete_document(self, document_id: str) -> bool:
        """
        Deletes a specific document from the RAGFlow dataset using its ID.
        使用其 ID 从 RAGFlow 数据集中删除特定文档。
        
        Args:
            document_id (str): The unique identifier of the document to delete. / 要删除的文档的唯一标识符。
            
        Returns:
            bool: True if the deletion was successful, False otherwise. / 如果删除成功则返回 True，否则返回 False。
        """
        dataset = self._get_dataset()
        if not dataset or not document_id:
            return False
            
        try:
            logger.info(f"Deleting document {document_id} from dataset {self.dataset_id}...")
            # SDK typically takes a list of IDs
            # SDK 通常接受 ID 列表
            dataset.delete_documents(ids=[document_id])
            logger.info(f"Successfully deleted document: {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            return False

    def trigger_parsing(self, document_ids: list[str], dataset_id: str = None) -> bool:
        """
        Triggers the asynchronous parsing process in RAGFlow for a list of recently uploaded documents.
        触发 RAGFlow 中最近上传的文档列表的异步解析过程。
        
        Args:
            document_ids (list[str]): A list of document IDs to parse. / 要解析的文档 ID 列表。
            dataset_id (str, optional): The dataset containing the documents. Defaults to None. / 包含文档的数据集。默认为 None。
            
        Returns:
            bool: True if the parsing trigger command was sent successfully, False otherwise. / 如果成功发送解析触发命令，则返回 True，否则返回 False。
        """
        dataset = self._get_dataset(dataset_id)
        if not dataset or not document_ids:
            return False

        try:
            logger.info(f"Triggering parsing for {len(document_ids)} documents...")
            dataset.async_parse_documents(document_ids)
            logger.info("Parsing triggered successfully.")
            return True
        except Exception as e:
            logger.error(f"Error triggering parsing: {e}")
            return False

    def create_dataset(self, name: str, chunk_method: str = "naive", embedding_model: str = "text-embedding-v4") -> str:
        """
        Creates a new dataset in RAGFlow.
        在 RAGFlow 中创建一个新的数据集。
        
        Args:
            name (str): The name of the dataset. / 数据集的名称。
            chunk_method (str, optional): The chunking method. Defaults to "naive". / 分块方法。默认为 "naive"。
            embedding_model (str, optional): The embedding model to use. / 要使用的嵌入模型。
            
        Returns:
            str | None: The generated dataset ID if successful, otherwise None. / 如果成功则返回生成的数据集 ID，否则返回 None。
        """
        if not self.client:
            logger.error("RAGFlow SDK client is not initialized.")
            return None
        try:
            logger.info(f"Creating new RAGFlow dataset: '{name}' with model '{embedding_model}'...")
            ds = self.client.create_dataset(name=name, chunk_method=chunk_method, embedding_model=embedding_model)
            if ds:
                logger.info(f"Dataset '{name}' created successfully with ID: {ds.id}")
                return ds.id
            return None
        except Exception as e:
            logger.error(f"Error creating dataset '{name}': {e}")
            return None

    def search_chunks(self, question: str, dataset_id: str = None, top_k: int = 3, similarity_threshold: float = 0.5) -> list:
        """
        Searches for similar chunks in the dataset using RAGFlow's retrieve API.
        使用 RAGFlow 的检索 API 在数据集中搜索相似的段落。
        
        Args:
            question (str): The search query text. / 搜索查询文本。
            dataset_id (str, optional): The dataset to search. Defaults to self.dataset_id. / 要搜索的数据集。如果未提供则使用实例默认。
            top_k (int, optional): The maximum number of expected chunks. Defaults to 3. / 预期的最大段落数。默认为 3。
            similarity_threshold (float, optional): Custom similarity threshold. Defaults to 0.5. / 自定义相似度阈值。
            
        Returns:
            list: A list of Chunk objects retrieved. / 检索到的段落（Chunk）对象列表。
        """
        target_dataset_id = dataset_id or self.dataset_id
        if not self.client or not target_dataset_id:
            return []
            
        try:
            chunks = self.client.retrieve(
                question=question,
                dataset_ids=[target_dataset_id],
                page_size=top_k,
                similarity_threshold=similarity_threshold
            )
            return chunks if chunks else []
        except Exception as e:
            logger.error(f"Error searching chunks in RAGFlow: {e}")
            return []
