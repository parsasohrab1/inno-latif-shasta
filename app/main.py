"""نقطه ورود FastAPI برای دوقلوی دیجیتال خشک‌کن لطیف.

اجرا:
  cd /home/z/my-project/inno-latif-shasta
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

یا:
  python -m app.main
"""

from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.core.config import settings
from app.api.routes import router
from app.services.opcua_sim import opcua_sim

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("latif")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """چرخه‌ی زندگی سرور — استارت/استاپ شبیه‌ساز."""
    logger.info("Starting Latif Digital Twin API %s", settings.app_version)
    if settings.opcua_sim_enabled:
        opcua_sim.start()
        logger.info("OPC-UA simulator started (interval=%ss)",
                    settings.opcua_interval_sec)
    yield
    opcua_sim.stop()
    logger.info("OPC-UA simulator stopped. Bye.")


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

app.include_router(router, tags=["api"])

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
