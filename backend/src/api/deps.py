"""
FastAPI dependency injection utilities for OmniDigest.
OmniDigest 的 FastAPI 依赖注入实用程序。

Provides database connections, RAG clients, and domain services.
提供数据库连接、RAG 客户端和领域服务。
"""
from typing import Generator
from fastapi import Depends
from ..core.database import DatabaseManager
from ..domains.knowledge_base.rag_client import RAGClient
from ..notifications.pusher import NotificationService
from ..domains.daily_digest.processor import ContentProcessor
from ..domains.analysis.trend_analyzer import AnalysisService
from ..domains.analysis.astock_analyzer import AStockAnalyzer
from ..domains.ingestion.rss.fast_crawler import BreakingCrawler
from ..domains.breaking_news.processor import BreakingProcessor
from ..domains.breaking_news.alerter import BreakingAlerter
from ..core.llm_manager import LLMManager

# Cache singleton instances to mimic the old container per-worker lifecycle but injected nicely
_db_instance = None
_rag_instance = None
_pusher_instance = None
_processor_instance = None
_analyzer_instance = None
_astock_analyzer_instance = None
_llm_manager_instance = None

def get_db() -> DatabaseManager:
    """
    Returns a singleton instance of the DatabaseManager.
    返回 DatabaseManager 的单例实例。
    
    Returns:
        DatabaseManager: The active database manager. / 活跃的数据库管理器。
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance

def get_rag() -> RAGClient:
    """
    Returns a singleton instance of the RAGClient.
    返回 RAGClient 的单例实例。
    
    Returns:
        RAGClient: The active RAG client. / 活跃的 RAG 客户端。
    """
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGClient(get_db())
    return _rag_instance

def get_pusher() -> NotificationService:
    """
    Returns a singleton instance of the NotificationService.
    返回 NotificationService 的单例实例。
    
    Returns:
        NotificationService: The active notification service. / 活跃的通知服务。
    """
    global _pusher_instance
    if _pusher_instance is None:
        _pusher_instance = NotificationService()
    return _pusher_instance

def get_llm_manager() -> LLMManager:
    """
    Returns a singleton instance of the LLMManager.
    返回 LLMManager 的单例实例。
    
    Returns:
        LLMManager: The active LLM manager. / 活跃的 LLM 管理器。
    """
    global _llm_manager_instance
    if _llm_manager_instance is None:
        _llm_manager_instance = LLMManager(get_db())
    return _llm_manager_instance

def get_processor() -> ContentProcessor:
    """
    Returns a singleton instance of the ContentProcessor.
    返回 ContentProcessor 的单例实例。
    
    Returns:
        ContentProcessor: The active content processor. / 活跃的内容处理器。
    """
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = ContentProcessor(get_db(), get_llm_manager())
    return _processor_instance

def get_analyzer() -> AnalysisService:
    """
    Returns a singleton instance of the AnalysisService.
    返回 AnalysisService 的单例实例。
    
    Returns:
        AnalysisService: The active analysis service. / 活跃的分析服务。
    """
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AnalysisService(get_db(), get_llm_manager())
    return _analyzer_instance

def get_astock_analyzer() -> AStockAnalyzer:
    """
    Returns a singleton instance of the AStockAnalyzer.
    返回 AStockAnalyzer 的单例实例。

    Returns:
        AStockAnalyzer: The active A股 analysis service. / 活跃的A股分析服务。
    """
    global _astock_analyzer_instance
    if _astock_analyzer_instance is None:
        _astock_analyzer_instance = AStockAnalyzer(get_db(), get_llm_manager())
    return _astock_analyzer_instance

_breaking_crawler_instance = None
_breaking_processor_instance = None
_breaking_alerter_instance = None

def get_breaking_crawler() -> BreakingCrawler:
    """
    Returns a singleton instance of the BreakingCrawler.
    返回 BreakingCrawler 的单例实例。
    
    Returns:
        BreakingCrawler: The active breaking news crawler. / 活跃的突发新闻抓取器。
    """
    global _breaking_crawler_instance
    if _breaking_crawler_instance is None:
        _breaking_crawler_instance = BreakingCrawler(get_db())
    return _breaking_crawler_instance

def get_breaking_processor() -> BreakingProcessor:
    """
    Returns a singleton instance of the BreakingProcessor.
    返回 BreakingProcessor 的单例实例。
    
    Returns:
        BreakingProcessor: The active breaking news processor. / 活跃的突发新闻处理器。
    """
    global _breaking_processor_instance
    if _breaking_processor_instance is None:
        _breaking_processor_instance = BreakingProcessor(get_db(), get_llm_manager(), get_rag())
    return _breaking_processor_instance

def get_breaking_alerter() -> BreakingAlerter:
    """
    Returns a singleton instance of the BreakingAlerter.
    返回 BreakingAlerter 的单例实例。
    
    Returns:
        BreakingAlerter: The active breaking news alerter. / 活跃的突发新闻警报器。
    """
    global _breaking_alerter_instance
    if _breaking_alerter_instance is None:
        _breaking_alerter_instance = BreakingAlerter(get_db(), get_pusher())
    return _breaking_alerter_instance
