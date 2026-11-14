"""تنظیمات pytest — مسیرها و fixture های سراسری."""

import sys
import os
import pytest
from pathlib import Path

# افزودن مسیر ریشه‌ی پروژه به sys.path (برای import app)
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# متغیرهای محیطی برای تست (بدون نیاز به اینترنت)
os.environ.setdefault("LATIF_OPCUA_INTERVAL_SEC", "1")
os.environ.setdefault("LATIF_HISTORIAN_BACKEND", "memory")


@pytest.fixture
def app_client():
    """TestClient برای FastAPI بدون اجرای شبیه‌ساز (/disable)."""
    from fastapi.testclient import TestClient
    # جلوگیری از شروع خودکار شبیه‌ساز
    os.environ["LATIF_OPCUA_SIM_ENABLED"] = "false"
    # import مجدد تا تنظیمات اعمال شود
    import importlib
    from app.core import config
    importlib.reload(config)
    from app.services import opcua_sim
    importlib.reload(opcua_sim)
    from app.core import historian
    importlib.reload(historian)
    from app.api import routes
    importlib.reload(routes)
    from app import main
    importlib.reload(main)
    with TestClient(main.app) as client:
        yield client


@pytest.fixture
def app_client_with_sim():
    """TestClient با شبیه‌ساز فعال (تولید داده)."""
    from fastapi.testclient import TestClient
    os.environ["LATIF_OPCUA_SIM_ENABLED"] = "true"
    os.environ["LATIF_OPCUA_INTERVAL_SEC"] = "1"
    import importlib
    from app.core import config
    importlib.reload(config)
    from app.services import opcua_sim
    importlib.reload(opcua_sim)
    from app.core import historian
    importlib.reload(historian)
    from app.api import routes
    importlib.reload(routes)
    from app import main
    importlib.reload(main)
    with TestClient(main.app) as client:
        import time
        time.sleep(2.5)  # صبر برای تولید چند نمونه
        yield client
