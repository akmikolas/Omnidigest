"""
API Key authentication CLI command handlers.
API 密钥认证 CLI 命令处理器。

Provides functions for creating, listing, and revoking API keys
used to authenticate external clients against the OmniDigest REST API.
提供创建、列出和吊销用于外部客户端认证 OmniDigest REST API 的 API 密钥的函数。
"""
import sys
import logging
from src.omnidigest.core.database import DatabaseManager
from src.omnidigest.cli.db import override_db_settings

logger = logging.getLogger("manage.auth")

def auth_create_key(args):
    """
    CLI handler to generate and store a new API key for a client.
    CLI 处理器，用于为客户端生成并存储一个新的 API 密钥。
    
    Args:
        args (argparse.Namespace): Arguments containing 'client_name'. / 包含 'client_name' 的参数。
    """
    from src.omnidigest.api.auth import generate_api_key, hash_api_key
    override_db_settings(args)
    client_name = args.client_name
    
    raw_key = generate_api_key()
    hashed_key = hash_api_key(raw_key)
    
    db = DatabaseManager()
    if db.create_api_key(client_name, hashed_key):
        print("\n" + "="*50)
        print("✅ API Key Generated Successfully!")
        print("="*50)
        print(f"Client Name: {client_name}")
        print(f"Raw API Key: {client_name}:{raw_key}")
        print("="*50)
        print("⚠️ IMPORTANT: Copy this key now. It provides full access to the API.")
        print("The raw key will NOT be shown again. It is stored securely as a hash.")
        print("="*50 + "\n")
    else:
        logger.error("Failed to generate API Key.")
        sys.exit(1)

def auth_list_keys(args):
    """
    CLI handler to list all registered API keys and their statuses.
    CLI 处理器，用于列出所有已注册的 API 密钥及其状态。
    
    Args:
        args (argparse.Namespace): CLI arguments. / CLI 参数。
    """
    override_db_settings(args)
    db = DatabaseManager()
    keys = db.list_api_keys()
    print("\n" + "-"*60)
    print(f"{'ID':<5} | {'Client Name':<25} | {'Active?':<10} | {'Created At'}")
    print("-" * 60)
    for k in keys:
         status_str = "Yes" if k['is_active'] else "No/Revoked"
         print(f"{k['id']:<5} | {k['client_name']:<25} | {status_str:<10} | {k['created_at']}")
    print("-" * 60 + "\n")

def auth_revoke_key(args):
    """
    CLI handler to revoke (deactivate) an existing API key by client name.
    CLI 处理器，用于通过客户端名称吊销（禁用）现有的 API 密钥。
    
    Args:
        args (argparse.Namespace): Arguments containing 'client_name'. / 包含 'client_name' 的参数。
    """
    override_db_settings(args)
    client_name = args.client_name
    db = DatabaseManager()
    if db.revoke_api_key(client_name):
        logger.info(f"✅ Successfully revoked API key for client: {client_name}")
    else:
        logger.error(f"Failed to revoke key for {client_name}. Does it exist?")
        sys.exit(1)
