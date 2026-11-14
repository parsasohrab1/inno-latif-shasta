"""نقطه ورود FastAPI برای دوقلوی دیجیتال خشک‌کن لطیف.

اجرا:
  cd /home/z/my-project/inno-latif-shasta
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

یا:
  python -m app.main
"""

from __future__ import annotations
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging_setup import setup_logging
from app.api.routes import router, metrics_router
from app.services.opcua_sim import opcua_sim

logger = setup_logging(settings.log_level if hasattr(settings, "log_level")
                       else os.environ.get("LATIF_LOG_LEVEL", "info"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """چرخه‌ی زندگی سرور — استارت/استاپ شبیه‌ساز."""
    logger.info("starting_api", extra={"version": settings.app_version,
                                         "host": settings.host,
                                         "port": settings.port})
    if settings.opcua_sim_enabled:
        opcua_sim.start()
        logger.info("opcua_started",
                    extra={"interval": settings.opcua_interval_sec})
    yield
    opcua_sim.stop()
    logger.info("opcua_stopped")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API دوقلوی دیجیتال خشک‌کن خط تیشو - محصولات کاغذی لطیف",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """ثبت متریک‌های API (latency + count) برای هر request."""
    import time as _t
    t0 = _t.time()
    response = await call_next(request)
    duration = _t.time() - t0
    # فقط مسیرهای API را ثبت کن (نه /static، /docs و غیره)
    if request.url.path.startswith("/api"):
        from app.monitoring import metrics
        try:
            metrics.record_api(
                endpoint=request.url.path,
                method=request.method,
                status=response.status_code,
                duration_s=duration,
            )
        except Exception:
            pass
    return response


app.include_router(router, tags=["api"])
app.include_router(metrics_router, tags=["monitoring"])

# سرو کردن داشبورد استاتیک
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    """سرو کردن داشبورد اصلی از مسیر static."""
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "Latif Digital Twin API",
            "docs": "/docs",
            "dashboard": "/static/index.html"}


@app.get("/dashboard")
async def dashboard():
    index = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"error": "dashboard not built"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app",
                host=settings.host,
                port=settings.port,
                reload=False)
