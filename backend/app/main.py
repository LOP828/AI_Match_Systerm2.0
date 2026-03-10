import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.audit import configure_application_logging
from app.config import get_settings
from app.db import verify_database_connection

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_application_logging()
    settings = get_settings()
    settings.validate_runtime_requirements()
    verify_database_connection()

    if settings.ai_extraction_enabled and not settings.deepseek_api_key:
        logger.warning("AI extraction enabled but DEEPSEEK_API_KEY is missing; AI trigger endpoint will be unavailable")

    yield

app = FastAPI(
    title="AI 辅助红娘筛选系统 API",
    version="0.1.0",
    description="MVP：两阶段推荐、禁忌管理、反馈与 AI 抽取等接口。",
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-Id", "X-Role"],
)

app.include_router(api_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error", extra={"path": str(request.url.path)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """简单健康检查，用于存活探测。"""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"message": "AI Match System MVP Backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

