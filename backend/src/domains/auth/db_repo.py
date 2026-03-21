"""
Database mixin for API key authentication operations.
API 密钥认证操作的数据库 Mixin。

Provides CRUD methods for managing API keys including creation,
retrieval, listing, and revocation.
提供管理 API 密钥的 CRUD 方法，包括创建、检索、列出和吊销。
"""
import logging
import uuid
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class AuthMixin:
    """
    Mixin for managing API keys and client authentication in the database.
    在数据库中管理 API 密钥和客户端认证的 Mixin。
    """
    def create_api_key(self, client_name: str, key_hash: str):
        """
        Stores a new API key hash for a client, or updates it if it exists and was revoked.
        为客户端存储新的 API 密钥哈希，如果已存在且被撤销则更新它。
        
        Args:
            client_name (str): The name of the client. / 客户端名称。
            key_hash (str): The hashed API key. / 散列的 API 密钥。
            
        Returns:
            int | None: The ID of the API key record, or None on error. / API 密钥记录的 ID，出错时返回 None。
        """
        query = """
        INSERT INTO omnidigest.api_keys (client_name, key_hash, is_active)
        VALUES (%s, %s, TRUE)
        ON CONFLICT (client_name) DO UPDATE
        SET key_hash = EXCLUDED.key_hash, is_active = TRUE, "created_at" = NOW()
        RETURNING id;
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (client_name, key_hash))
                    result = cur.fetchone()
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return None

    def get_api_key_hash(self, client_name: str):
        """
        Retrieves the active API key hash for a given client_name.
        检索给定客户端名称的活动 API 密钥哈希。
        
        Args:
            client_name (str): The name of the client. / 客户端名称。
            
        Returns:
            str | None: The hashed API key if found and active, otherwise None. / 如果找到且处于活动状态，则返回散列的 API 密钥，否则返回 None。
        """
        query = "SELECT key_hash FROM omnidigest.api_keys WHERE client_name = %s AND is_active = TRUE"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (client_name,))
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting API key hash: {e}")
            return None

    def list_api_keys(self):
        """
        Retrieves a list of all API keys (client names, active status, creation dates), excluding the actual hashes for security.
        检索所有 API 密钥的列表（客户端名称、活动状态、创建日期），排除实际哈希以确保安全。
        
        Returns:
            list[dict]: A list of dictionary records containing id, client_name, is_active, and created_at. / 包含 id、client_name、is_active 和 created_at 的字典记录列表。
        """
        query = 'SELECT id, client_name, is_active, "created_at" FROM omnidigest.api_keys ORDER BY "created_at" DESC'
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            logger.error(f"Error listing API keys: {e}")
            return []

    def revoke_api_key(self, client_name: str):
        """
        Revokes an API key.
        撤销 API 密钥。
        
        Args:
            client_name (str): The name of the client whose key will be revoked. / 将被撤销其密钥的客户端名称。
            
        Returns:
            bool: True if successful, False otherwise. / 如果成功则返回 True，否则返回 False。
        """
        query = "UPDATE omnidigest.api_keys SET is_active = FALSE WHERE client_name = %s RETURNING id"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (client_name,))
                    result = cur.fetchone()
                conn.commit()
                return result[0] is not None
        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return False
