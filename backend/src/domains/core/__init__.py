"""
Core domain components for OmniDigest.
OmniDigest 的核心领域组件。

This module provides reusable components like the generic One-Pass processor framework.
此模块提供可重用组件，如通用 One-Pass 处理器框架。
"""
from .onepass import OnePassProcessor, OnePassConfig, ContextProvider, RecentEventsProvider, ActiveStoriesProvider, RAGProvider

__all__ = [
    "OnePassProcessor",
    "OnePassConfig",
    "ContextProvider",
    "RecentEventsProvider",
    "ActiveStoriesProvider",
    "RAGProvider",
]
