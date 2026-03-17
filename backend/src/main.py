"""
Main entry point for the OmniDigest backend service. Provides the FastAPI application lifecycle and API router, and starts the background job scheduler.
OmniDigest 后端服务的主入口。提供 FastAPI 应用程序生命周期和 API 路由，并启动后台任务调度器。
"""
import logging
import sys
import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.deps import get_db
from .jobs.scheduler import scheduler
from .jobs import setup_scheduler, job_cleanup_low_quality
from .api.router import router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the lifecycle events of the FastAPI application (startup and shutdown).
    This function acts as an async context manager. Whatever is before 'yield' runs on startup, and whatever is after 'yield' runs on shutdown.
    管理 FastAPI 应用程序的生命周期事件（启动和关闭）。这个函数作为一个异步上下文管理器。'yield' 之前的内容在启动时运行，'yield' 之后的内容在关闭时运行。
    
    Args:
        app (FastAPI): The FastAPI application instance. / FastAPI 应用程序实例。
    """
    # Startup phase: Initialize necessary services and checks
    # 启动阶段：初始化必要的服务和检查
    import os
    env_name = os.getenv("OMNIDIGEST_ENV", "dev")
    logger.info(f"OmniDigest starting up in [{env_name}] mode, loading config from [.env.{env_name} if env is set, else .env]...")
    
    # Strict Database Integrity Check: Ensure tables exist before starting
    # 严格的数据库完整性检查：确保在启动服务之前表已经存在（会自动创建）
    if not get_db().check_integrity():
        error_msg = "Database integrity check failed. Please check database connection and try again."
        logger.critical(error_msg)
        raise RuntimeError(error_msg)
    
    # Run cleanup immediately on startup
    # 启动时立即运行清理
    asyncio.create_task(job_cleanup_low_quality())

    # Schedule jobs (skip if DISABLE_SCHEDULER is set)
    # 调度任务（如果设置了 DISABLE_SCHEDULER 则跳过）
    import os
    if os.getenv("DISABLE_SCHEDULER", "").lower() != "true":
        setup_scheduler()
    else:
        logger.info("Scheduler disabled via DISABLE_SCHEDULER environment variable")
    
    yield
    # Shutdown
    # 关闭
    logger.info("OmniDigest shutting down...")
    scheduler.shutdown()

app = FastAPI(title="OmniDigest API", lifespan=lifespan)
app.include_router(router)

def main():
    """
    The main entry point function to run the uvicorn ASGI server. Configures host bind and port settings.
    运行 uvicorn ASGI 服务器的主入口函数。配置主机绑定和端口设置。
    """
    # Start the server listening on all interfaces at port 8080
    # 启动服务器，在端口 8080 监听所有网络接口
    uvicorn.run("omnidigest.main:app", host="0.0.0.0", port=8080, reload=False)

if __name__ == "__main__":
    main()
