"""
Global APScheduler instance.
全局 APScheduler 实例。
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
