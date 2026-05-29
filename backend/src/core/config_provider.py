"""
ConfigProvider - Database-first configuration provider with environment variable fallback.
ConfigProvider - 数据库优先的配置提供程序，支持环境变量回退。

This module provides a unified config access mechanism that:
1. Checks database overrides first
2. Falls back to environment variables and defaults
3. Caches values for performance
4. Supports runtime hot-reload
"""
import logging
import time
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ConfigProvider:
    """
    Unified config provider that checks database overrides first,
    then falls back to environment variables and defaults.

    Features:
    - Database-first configuration with env fallback
    - Simple in-memory cache with TTL
    - Thread-safe access
    - Hot-reload capability
    """

    def __init__(self, db, settings):
        """
        Initialize ConfigProvider.

        Args:
            db: DatabaseManager instance
            settings: Pydantic Settings instance (for defaults)
        """
        self._db = db
        self._settings = settings
        self._cache = {}
        self._cache_timestamps = {}
        self._cache_ttl = 60  # seconds
        self._lock = threading.Lock()
        self._initialized = False

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid."""
        if key not in self._cache_timestamps:
            return False
        return time.time() - self._cache_timestamps[key] < self._cache_ttl

    def get(self, key: str, default: Any = None, value_type: str = "string") -> Any:
        """
        Get config value with DB override support.

        Resolution order:
        1. Check in-memory cache
        2. Check database override
        3. Fall back to settings default
        4. Return provided default

        Args:
            key: Config key (case-insensitive)
            default: Default value if not found anywhere
            value_type: Expected type for conversion (string, int, bool, json, float)

        Returns:
            Config value converted to appropriate type
        """
        cache_key = key.upper()

        # 1. Check cache first
        with self._lock:
            if self._is_cache_valid(cache_key):
                return self._cache[cache_key]

        # 2. Check database override
        db_value = self._get_from_db(cache_key)
        if db_value is not None:
            result = self._convert_value(db_value, value_type)
            with self._lock:
                self._cache[cache_key] = result
                self._cache_timestamps[cache_key] = time.time()
            return result

        # 3. Fall back to settings default (env var or pydantic default)
        settings_value = self._get_from_settings(cache_key)
        if settings_value is not None:
            result = self._convert_value(settings_value, value_type)
            with self._lock:
                self._cache[cache_key] = result
                self._cache_timestamps[cache_key] = time.time()
            return result

        # 4. Return default
        logger.debug(f"Config key '{key}' not found, using default: {default}")
        return default

    def _get_from_db(self, key: str) -> Optional[str]:
        """
        Get config value from database.
        Searches all sections for the key.

        Args:
            key: Uppercase config key

        Returns:
            Raw string value or None if not found
        """
        try:
            all_config = self._db.get_all_config()
            for entry in all_config:
                if entry.get("key", "").upper() == key:
                    return entry.get("value")
            return None
        except Exception as e:
            logger.warning(f"Failed to get config from DB for '{key}': {e}")
            return None

    def _get_from_settings(self, key: str) -> Any:
        """
        Get config value from settings (environment or pydantic defaults).

        Args:
            key: Uppercase config key

        Returns:
            Value from settings or None
        """
        # Convert key to snake_case for settings access
        # e.g., BREAKING_IMPACT_THRESHOLD -> breaking_impact_threshold
        setting_key = key.lower()

        # Try direct attribute access
        if hasattr(self._settings, setting_key):
            return getattr(self._settings, setting_key)

        # Try with underscores removed
        # e.g., BREAKINGIMPACTTHRESHOLD -> breakingimpactthreshold
        setting_key_nounders = setting_key.replace("_", "")
        for attr in dir(self._settings):
            if attr.lower().replace("_", "") == setting_key_nounders:
                return getattr(self._settings, attr)

        return None

    def _convert_value(self, value: Any, value_type: str) -> Any:
        """
        Convert value to specified type.

        Args:
            value: Raw value (usually string from DB or any from settings)
            value_type: Target type (string, int, bool, json, float)

        Returns:
            Converted value
        """
        if value is None:
            return None

        # If already the correct type, return as-is
        if value_type == "string":
            return str(value)
        elif value_type == "int":
            try:
                return int(value)
            except (ValueError, TypeError):
                # Handle string "true"/"false" as bool for int
                if isinstance(value, str):
                    if value.lower() == "true":
                        return 1
                    elif value.lower() == "false":
                        return 0
                return int(float(value))
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on")
            return bool(value)
        elif value_type == "json":
            import json
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON for config: {value}")
                    return value
            return value

        return value

    def set(self, key: str, value: str, value_type: str = "string",
            section: str = "general", description: str = "",
            is_editable: bool = True) -> bool:
        """
        Set config value in database.

        Args:
            key: Config key
            value: Config value (will be stored as string)
            value_type: Type hint (string, int, bool, json, float)
            section: Config section
            description: Description of this config
            is_editable: Whether this can be edited via API

        Returns:
            True if successful
        """
        try:
            success = self._db.set_config(
                section=section,
                key=key,
                value=str(value),
                value_type=value_type,
                description=description,
                is_editable=is_editable
            )
            if success:
                # Invalidate cache for this key
                with self._lock:
                    cache_key = key.upper()
                    if cache_key in self._cache:
                        del self._cache[cache_key]
                    if cache_key in self._cache_timestamps:
                        del self._cache_timestamps[cache_key]
            return success
        except Exception as e:
            logger.error(f"Failed to set config '{key}': {e}")
            return False

    def reload(self, key: Optional[str] = None):
        """
        Clear cache and reload from DB.

        Args:
            key: Specific key to reload, or None to reload all
        """
        with self._lock:
            if key:
                cache_key = key.upper()
                if cache_key in self._cache:
                    del self._cache[cache_key]
                if cache_key in self._cache_timestamps:
                    del self._cache_timestamps[cache_key]
            else:
                self._cache.clear()
                self._cache_timestamps.clear()
        logger.info(f"Config cache cleared for: {'all' if key is None else key}")

    def get_all(self) -> dict:
        """
        Get all config as a dict, with DB values overriding env defaults.

        Returns:
            Dict mapping keys to their resolved values
        """
        result = {}

        # Get all env/settings defaults
        for attr in dir(self._settings):
            if attr.startswith("_"):
                continue
            try:
                value = getattr(self._settings, attr)
                if not callable(value):
                    result[attr.upper()] = value
            except AttributeError:
                continue

        # Override with DB values
        try:
            db_config = self._db.get_all_config()
            for entry in db_config:
                key = entry.get("key", "").upper()
                value = entry.get("value")
                value_type = entry.get("value_type", "string")
                if key:
                    result[key] = self._convert_value(value, value_type)
        except Exception as e:
            logger.warning(f"Failed to get DB config: {e}")

        return result

    def get_all_with_metadata(self) -> list:
        """
        Get all config entries with full metadata from DB.

        Returns:
            List of dicts with id, section, key, value, value_type, etc.
        """
        try:
            return self._db.get_all_config()
        except Exception as e:
            logger.error(f"Failed to get all config with metadata: {e}")
            return []

    def get_sections(self) -> list:
        """
        Get all available config sections.

        Returns:
            List of unique section names
        """
        try:
            all_config = self._db.get_all_config()
            sections = set(entry.get("section") for entry in all_config if entry.get("section"))
            return sorted(list(sections))
        except Exception as e:
            logger.error(f"Failed to get sections: {e}")
            return []

    def is_db_override(self, key: str) -> bool:
        """
        Check if a key has a database override.

        Args:
            key: Config key to check

        Returns:
            True if key exists in database
        """
        return self._get_from_db(key.upper()) is not None
