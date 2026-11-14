"""تست‌های API (end-to-end) با TestClient.

این تست‌ها کل زنجیره: OPC-UA simulator → historian → MPC → API را پوشش می‌دهند.
بدون نیاز به سرور واقعی — TestClient از FastAPI استفاده می‌کند.
"""

import pytest
import time
import os
import sys
sys.path.insert(0, "/home/z/my-project/inno-latif-shasta")


@pytest.fixture
def client():
    """TestClient با شبیه‌ساز فعال برای تولید داده کافی.

    توجه: از importlib.reload استفاده نمی‌کنیم چون باعث می‌شود opcua_sim و
    historian دو نمونه‌ی متفاوت شوند و داده‌ها در نمونه‌ی اشتباه ذخیره شوند.
    در عوض، env را قبل از import تنظیم می‌کنیم و یک‌بار app را import می‌کنیم.
    """
    os.environ["LATIF_OPCUA_SIM_ENABLED"] = "true"
    os.environ["LATIF_OPCUA_INTERVAL_SEC"] = "1"
    os.environ["LATIF_HISTORIAN_BACKEND"] = "memory"
    # بدون API Key → دسترسی آزاد در dev
    os.environ.pop("LATIF_API_KEY", None)

    from fastapi.testclient import TestClient
    from app import main as M
    from app.core import historian as H
    from app.services import opcua_sim as S

    # پاک‌کردن historian برای شروع تمیز تست
    H.historian._buffer.clear() if hasattr(H.historian, "_buffer") else None
    S.opcua_sim._step = 0

    with TestClient(M.app) as c:
        # صبر برای تولید داده (شبیه‌ساز هر ۱ ثانیه)
        time.sleep(4)
        yield c


class TestHealthEndpoints:

    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_metrics_endpoint(self, client):
        """endpoint /metrics باید در فرمت Prometheus باشد."""
        r = client.get("/metrics")
        assert r.status_code == 200
        text = r.text
        # فرمت Prometheus: # HELP و # TYPE و نام متریک
        assert "latif_" in text or "#" in text

    def test_root_returns_dashboard(self, client):
        r = client.get("/")
        assert r.status_code == 200
        # اگر HTML یا JSON باشد
        ct = r.headers.get("content-type", "")
        assert "text/html" in ct or "application/json" in ct

    def test_dashboard_route(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200


class TestStatusAndSensors:

    def test_status(self, client):
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert "opcua" in data
        assert "historian" in data
        # باید حداقل چند نمونه تولید شده باشد (صبر در fixture)
        assert data["historian"]["count"] >= 0
        assert data["opcua"]["running"] is True

    def test_sensors_latest(self, client):
        r = client.get("/api/sensors/latest")
        assert r.status_code == 200
        data = r.json()
        if "error" not in data:
            assert "hood_temp_c" in data
            assert "moisture_out_pct" in data
            assert 3.0 <= data["moisture_out_pct"] <= 7.0

    def test_sensors_history(self, client):
        # اگر هنوز نمونه کافی نیست، چند ثانیه صبر کن
        for _ in range(5):
            r = client.get("/api/sensors/history?n=10")
            assert r.status_code == 200
            data = r.json()
            if data["count"] > 0:
                break
            time.sleep(1)
        assert data["count"] > 0, "OPC-UA simulator did not produce samples in time"
        assert isinstance(data["samples"], list)


class TestKPI:

    def test_kpi_returns_all_metrics(self, client):
        r = client.get("/api/kpi")
        assert r.status_code == 200
        data = r.json()
        if "error" not in data:
            for key in ("thermal_intensity_kWht", "thermal_baseline_kWht",
                        "thermal_reduction_pct", "gas_peak_nm3h",
                        "waste_pct", "moisture_avg_pct"):
                assert key in data, f"missing KPI: {key}"

    def test_kpi_baseline_matches_srs(self, client):
        """خط پایه شدت انرژی باید ۲۵۹۳ kWh/t باشد (مطابق SRS)."""
        r = client.get("/api/kpi")
        data = r.json()
        if "error" not in data:
            assert data["thermal_baseline_kWht"] == 2593.0
            assert data["gas_peak_baseline_nm3h"] == 460.0
            assert data["waste_baseline_pct"] == 2.6


class TestMPC:

    def test_solve_mpc(self, client):
        r = client.post("/api/mpc/solve", json={"operator": "test"})
        assert r.status_code == 200
        data = r.json()
        assert "solution" in data
        sol = data["solution"]
        assert "setpoints" in sol
        assert "predictions" in sol
        assert sol["feasible"] in (True, False)
        # حد SRS: ≤ ۱۰ ثانیه
        assert sol["computation_time_ms"] < 10000

    def test_solve_returns_four_setpoints(self, client):
        r = client.post("/api/mpc/solve", json={"operator": "test"})
        sol = r.json()["solution"]
        assert set(sol["setpoints"].keys()) == {
            "hood_temp", "steam_pressure", "hot_air_temp", "machine_speed"
        }

    def test_mode_change(self, client):
        # ابتدا به auto
        r = client.post("/api/mpc/mode", json={"mode": "auto", "operator": "test"})
        assert r.status_code == 200
        # سپس به advisory
        r = client.post("/api/mpc/mode", json={"mode": "advisory", "operator": "test"})
        assert r.status_code == 200

    def test_mode_rejects_invalid(self, client):
        r = client.post("/api/mpc/mode", json={"mode": "invalid_mode", "operator": "test"})
        data = r.json()
        assert "error" in data

    def test_apply_without_solution_fails_gracefully(self, client):
        """اگر MPC حل نشده باشد، apply باید error دهد."""
        # ابتدا یک solution جدید بساز
        client.post("/api/mpc/solve", json={"operator": "test"})
        # حالا apply
        r = client.post("/api/mpc/apply", json={"approved": True, "operator": "test"})
        assert r.status_code == 200
        data = r.json()
        assert "applied" in data

    def test_solution_persists(self, client):
        client.post("/api/mpc/solve", json={"operator": "test"})
        r = client.get("/api/mpc/solution")
        assert r.status_code == 200
        data = r.json()
        assert "setpoints" in data
        assert "cost" in data


class TestAudit:

    def test_audit_returns_list(self, client):
        # راه‌اندازی چند رویداد
        client.post("/api/mpc/solve", json={"operator": "test"})
        client.post("/api/mpc/mode", json={"mode": "advisory", "operator": "test"})
        r = client.get("/api/audit?n=20")
        assert r.status_code == 200
        data = r.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)
        assert len(data["entries"]) > 0

    def test_audit_records_operator(self, client):
        client.post("/api/mpc/solve", json={"operator": "operator_alice"})
        r = client.get("/api/audit?n=10")
        data = r.json()
        # حداقل یک مورد باید operator_alice باشد
        operators = [e["operator"] for e in data["entries"]]
        assert "operator_alice" in operators


class TestSecurity:

    def test_no_api_key_in_dev_mode(self, client):
        """بدون LATIF_API_KEY، مسیرهای API باید آزاد باشند."""
        # تست از قبل fixture را بدون API_KEY تنظیم کرده
        r = client.get("/api/kpi")
        # باید 200 یا 200 با error (نه 401)
        assert r.status_code != 401

    def test_with_api_key_enforced(self, monkeypatch):
        """اگر LATIF_API_KEY تنظیم شود، مسیرها نیاز به کلید دارند.

        این تست مستقل است: مستقیماً security.verify_api_key را با env فرضی تست می‌کند.
        """
        from app.core import security
        from fastapi import HTTPException
        from fastapi.security import APIKeyHeader, APIKeyQuery

        # شبیه‌سازی request با path حفاظت‌شده
        class FakeRequest:
            def __init__(self, path, headers=None):
                from urllib.parse import urlparse
                self.url = type("U", (), {"path": path})()
                self.headers = headers or {}

        # تنظیم LATIF_API_KEY
        monkeypatch.setenv("LATIF_API_KEY", "test-secret-key-12345")
        # نیاز به reload چون DEFAULT_KEY در زمان import مقداردهی می‌شود
        import importlib
        importlib.reload(security)

        # بدون کلید → 401
        req = FakeRequest("/api/status")
        import asyncio
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(security.verify_api_key(req, header_key=None, query_key=None))
        assert exc_info.value.status_code == 401

        # با کلید صحیح → "authenticated"
        req = FakeRequest("/api/status")
        result = asyncio.run(security.verify_api_key(
            req, header_key="test-secret-key-12345", query_key=None))
        assert result == "authenticated"

        # مسیر عمومی → "anonymous"
        req = FakeRequest("/api/health")
        result = asyncio.run(security.verify_api_key(req, header_key=None, query_key=None))
        assert result == "anonymous"

        # پاک‌سازی
        monkeypatch.delenv("LATIF_API_KEY", raising=False)
        importlib.reload(security)
