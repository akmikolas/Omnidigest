"""
Authentication layer for OmniDigest API endpoints. Provides FastAPI dependencies for verifying API keys.
OmniDigest API 端点的身份验证层。提供用于验证 API 密钥的 FastAPI 依赖项。
"""
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from .deps import get_db
import secrets
import logging
import bcrypt

logger = logging.getLogger(__name__)

# Header configuration: We will look for X-API-Key in the request header
X_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

def hash_api_key(api_key: str) -> str:
    """
    Hashes an API key before storing it in the database using bcrypt.
    在将 API 密钥存储到数据库之前，使用 bcrypt 对其进行哈希处理。
    
    Args:
        api_key (str): The raw API key string. / 原始 API 密钥字符串。
        
    Returns:
        str: The bcrypt hashed API key string.
        字符串: bcrypt 哈希处理后的 API 密钥字符串。
    """
    # Ensure key is bytes, hash it, then decode to string for db storage
    # 确保密钥是字节，进行哈希处理，然后解码为字符串以进行数据库存储
    salt = bcrypt.gensalt()
    # It is safe to use raw api_key here since secrets.token_urlsafe(32) generates ~43 chars (< 72 limit)
    # 在此处使用原始 api_key 是安全的，因为 secrets.token_urlsafe(32) 会生成约 43 个字符（低于 72 的限制）
    hashed_bytes = bcrypt.hashpw(api_key.encode('utf-8'), salt)
    return hashed_bytes.decode('utf-8')

def verify_api_key_hash(plain_api_key: str, hashed_key: str) -> bool:
    """
    Verifies a plain API key against the stored hash.
    验证明文 API 密钥与存储的哈希值是否匹配。
    
    Args:
        plain_api_key (str): The provided plain text API key. / 提供的明文 API 密钥。
        hashed_key (str): The correct hashed key from the database. / 数据库中正确的哈希密钥。
        
    Returns:
        bool: True if the key matches the hash, False otherwise.
        布尔值: 如果密钥与哈希匹配，则返回 True，否则返回 False。
    """
    try:
        return bcrypt.checkpw(plain_api_key.encode('utf-8'), hashed_key.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying bcrypt hash: {e}")
        return False

def generate_api_key() -> str:
    """
    Generates a secure random URL-safe API key.
    生成一个安全的、URL安全的随机 API 密钥。
    
    Returns:
        str: A generated API key string.
        字符串: 生成的 API 密钥字符串。
    """
    return secrets.token_urlsafe(32)

async def verify_api_key(header_key: str = Security(X_API_KEY_HEADER)):
    """
    FastAPI Dependency to verify the incoming API Key.
    用于验证传入 API 密钥的 FastAPI 依赖项。

    Supports two formats:
    1. 'client_name:raw_key_string' - Full format with client name
    2. 'raw_key_string' - Direct key format (tries to match first active key)

    Args:
        header_key (str, optional): The API key extracted from request headers. / 从请求标头中提取的 API 密钥。

    Returns:
        str: The verified client name.
        字符串: 经验证的客户端名称。

    Raises:
        HTTPException: If the token is missing, malformed, or invalid. / 如果令牌丢失、格式错误或无效时引发。
    """
    if not header_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key header",
            headers={"WWW-Authenticate": "APIKey"},
        )

    # Check if it's the full format 'client_name:key'
    parts = header_key.split(":", 1)
    if len(parts) == 2:
        client_name, raw_key = parts

        # Retrieve the hash from the database
        key_hash = get_db().get_api_key_hash(client_name)
        if not key_hash:
            logger.warning(f"Unauthorized API access attempt for unknown or revoked client: {client_name}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API Key",
                headers={"WWW-Authenticate": "APIKey"},
            )

        # Verify the hash
        if not verify_api_key_hash(raw_key, key_hash):
            logger.warning(f"Unauthorized API access attempt for client: {client_name} (Invalid Key)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API Key",
                headers={"WWW-Authenticate": "APIKey"},
            )

        return client_name

    # Try direct key format - iterate through all active keys
    # 尝试直接密钥格式 - 遍历所有活跃密钥
    raw_key = header_key
    all_keys = get_db().list_api_keys()

    for key_entry in all_keys:
        if key_entry.get('is_active'):
            key_hash = get_db().get_api_key_hash(key_entry['client_name'])
            if key_hash and verify_api_key_hash(raw_key, key_hash):
                logger.info(f"Authenticated via direct key for client: {key_entry['client_name']}")
                return key_entry['client_name']

    # No match found
    logger.warning(f"Unauthorized API access attempt with direct key")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or revoked API Key",
        headers={"WWW-Authenticate": "APIKey"},
    )
