"""
RAGFlow CLI commands. Handles automated dataset initialization and configuration management.
RAGFlow 命令行工具链。处理自动化数据集初始化和配置管理等运维操作。
"""
import logging
from src.omnidigest.domains.knowledge_base.rag_client import RAGClient
from ..config import settings

logger = logging.getLogger(__name__)

def setup_rag_commands(subparsers):
    """
    Sets up the argparser subcommands for rag.
    设置 RAG 相关的 argparse 子命令。
    """
    rag_parser = subparsers.add_parser('rag', help='RAGFlow knowledge base management commands / RAGFlow 知识库管理命令')
    rag_subparsers = rag_parser.add_subparsers(dest='rag_command', required=True)

    # Init Breaking Dataset
    rag_subparsers.add_parser('init-breaking', help='Initialize the Breaking News dataset in RAGFlow / 在 RAGFlow 中初始化用于突发新闻去重的数据集')

def handle_rag_commands(args):
    """
    Route to the correct rag sub-command handler.
    路由到对应的 RAG 子命令处理函数。
    """
    if args.rag_command == 'init-breaking':
        _init_breaking_dataset()

def _init_breaking_dataset():
    """
    Initializes the Breaking News dataset in RAGFlow.
    在 RAGFlow 中初始化用于突发新闻去重的数据集。
    """
    print(f"[*] Connecting to RAGFlow at {settings.ragflow_api_url}...")
    
    # We explicitly instantiate RAGClient here to perform the init action
    # Note: RAGClient reads from settings on init
    rag_client = RAGClient()
    
    if not rag_client.client:
        print("[*] RAGFlow is locally disabled. Forcing initialization for dataset creation...")
        try:
            from ragflow_sdk import RAGFlow
            rag_client.client = RAGFlow(api_key=settings.ragflow_api_key, base_url=rag_client.base_url)
        except Exception as e:
            print(f"[!] FATAL: Could not manually initialize RAGFlow SDK client: {e}")
            return
            
    if not rag_client.client:
        print("[!] FATAL: Could not initialize RAGFlow SDK client. Check your RAGFLOW_API_URL and RAGFLOW_API_KEY in .env.")
        return

    dataset_name = settings.breaking_rag_dataset_name
    model = settings.breaking_embedding_model
    
    print(f"[*] Attempting to create dataset: '{dataset_name}' with embedding model: '{model}'")
    
    try:
        dataset_id = rag_client.create_dataset(
            name=dataset_name, 
            chunk_method="naive", 
            embedding_model=model
        )
        
        if dataset_id:
            print(f"\n[+] SUCCESS: Dataset created successfully!")
            print(f"    --> Dataset ID: {dataset_id}")
            print(f"\n[ACTION REQUIRED] Please add the following line to your .env file:")
            print(f"    BREAKING_RAG_DATASET_ID={dataset_id}")
            print(f"    BREAKING_RAG_ENABLED=True\n")
        else:
            print(f"\n[-] FAILED: Could not create dataset. A dataset with this name might already exist or the embedding model name might be incorrect.")
            print(f"    If the '{model}' model was added custom locally, ensure the name exactly matches what RAGFlow expects.")
    except Exception as e:
        print(f"\n[!] ERROR: Exception occurred while creating dataset:")
        print(f"    {e}")
