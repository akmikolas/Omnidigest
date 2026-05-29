"""
LazySettings - Proxy that delegates to ConfigProvider with settings fallback.
LazySettings - 代理类，将配置访问委托给 ConfigProvider，同时回退到 Settings 默认值。

This module provides a transparent proxy that intercepts all settings attribute
access and routes them through ConfigProvider for database override support.

Usage:
    # Old way (no runtime override):
    api_key = settings.llm_api_key

    # New way (with LazySettings):
    # Most code requires NO changes!
    api_key = settings.llm_api_key  # Automatically checks DB first
"""
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LazySettings:
    """
    Proxy that delegates to ConfigProvider, falling back to Settings defaults.

    This class wraps the original settings object and intercepts all attribute
    access. It first checks ConfigProvider (database overrides), then falls
    back to the original settings values.

    Key Principle: Minimal code changes. Most `settings.X` accesses require NO changes!
    """

    def __init__(self, config_provider, settings):
        """
        Initialize LazySettings proxy.

        Args:
            config_provider: ConfigProvider instance
            settings: Original pydantic Settings instance
        """
        self._config = config_provider
        self._settings = settings
        self._locked_keys = {"getattr", "_config", "_settings", "model_config"}

    def __getattr__(self, name: str) -> Any:
        """
        Get attribute with DB override support.

        Resolution order:
        1. Try ConfigProvider (DB override)
        2. Fall back to original settings

        Args:
            name: Attribute name

        Returns:
            Attribute value with DB override applied
        """
        if name in self._locked_keys:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        # Try to get from ConfigProvider first (DB override)
        try:
            value = self._config.get(name)
            if value is not None:
                return value
        except Exception as e:
            logger.debug(f"ConfigProvider lookup failed for '{name}': {e}")

        # Fall back to settings default
        try:
            return getattr(self._settings, name)
        except AttributeError:
            raise AttributeError(f"Settings has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Set attribute - only allowed for internal attributes.

        Direct setting via this proxy is not supported (use ConfigProvider.set() instead).

        Args:
            name: Attribute name
            value: Value to set

        Raises:
            AttributeError: If trying to set a non-internal attribute
        """
        if name.startswith("_") or name in self._locked_keys:
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(
                f"Cannot set '{name}' directly on LazySettings. "
                f"Use ConfigProvider.set('{name}', value) instead."
            )

    def __hasattr__(self, name: str) -> bool:
        """Check if attribute exists in settings."""
        try:
            getattr(self._settings, name)
            return True
        except AttributeError:
            return False

    def __getitem__(self, key: str) -> Any:
        """
        Dict-style access support.

        Args:
            key: Config key

        Returns:
            Config value
        """
        return self.__getattr__(key)

    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return self.__hasattr__(key)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value with default fallback.

        Args:
            key: Config key
            default: Default value if not found

        Returns:
            Config value or default
        """
        try:
            return self.__getattr__(key)
        except AttributeError:
            return default

    def reload(self):
        """Clear config cache and reload from database."""
        self._config.reload()

    @property
    def config(self):
        """Access the underlying ConfigProvider."""
        return self._config
