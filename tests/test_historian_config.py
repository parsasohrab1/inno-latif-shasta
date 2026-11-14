"""تست‌های برای historian و config."""

import pytest
import time
import sys
sys.path.insert(0, "/home/z/my-project/inno-latif-shasta")

from app.core.historian import Historian, SensorSample


def make_sample(ts=None, **overrides):
    defaults = dict(
        timestamp=ts or time.time(),
        shift=0,
        hood_temp_c=400.0, yankee_surface_c=100.0,
        steam_pressure_bar=5.2, hot_air_temp_c=420.0,
        moisture_in_pct=68.0, moisture_out_pct=5.0,
        basis_weight_gm2=15.0, machine_speed_mmin=1500.0,
        steam_flow_th=7.2, gas_flow_nm3h=320.0,
        production_th=7.3, thermal_energy_intensity_kWht=2593.0,
        softness_1_10=8.0, capillary_rise_mm=85.0,
        out_of_spec_flag=0, is_peak_hour=0,
    )
    defaults.update(overrides)
    return SensorSample(**defaults)


class TestHistorianMemory:

    def test_append_and_latest(self):
        h = Historian(backend="memory")
        h.append(make_sample(timestamp=1.0))
        h.append(make_sample(timestamp=2.0))
        latest = h.latest()
        assert latest is not None
        assert latest.timestamp == 2.0

    def test_count(self):
        h = Historian(backend="memory")
        assert h.count() == 0
        h.append(make_sample())
        h.append(make_sample())
        assert h.count() == 2

    def test_history_returns_n_samples(self):
        h = Historian(backend="memory")
        for i in range(10):
            h.append(make_sample(timestamp=float(i)))
        # تاریخچه ۵ نمونه آخر
        result = h.history(5)
        assert len(result) == 5
        # باید به ترتیب زمانی صعودی
        assert result[0].timestamp == 5.0
        assert result[4].timestamp == 9.0

    def test_latest_returns_none_when_empty(self):
        h = Historian(backend="memory")
        assert h.latest() is None

    def test_history_returns_empty_when_empty(self):
        h = Historian(backend="memory")
        assert h.history(10) == []

    def test_buffer_capped(self):
        """بافر memory نباید از max_samples بیشتر شود."""
        h = Historian(backend="memory", max_samples=5)
        for i in range(20):
            h.append(make_sample(timestamp=float(i)))
        assert h.count() == 5
        # آخرین باید نمونه شماره ۱۹ باشد
        assert h.latest().timestamp == 19.0


class TestSensorSample:

    def test_all_required_fields(self):
        s = make_sample()
        for attr in ("timestamp", "shift", "hood_temp_c", "yankee_surface_c",
                     "steam_pressure_bar", "hot_air_temp_c", "moisture_in_pct",
                     "moisture_out_pct", "basis_weight_gm2", "machine_speed_mmin",
                     "steam_flow_th", "gas_flow_nm3h", "production_th",
                     "thermal_energy_intensity_kWht", "softness_1_10",
                     "capillary_rise_mm", "out_of_spec_flag",
                     "moisture_out_target_pct", "is_peak_hour",
                     "production_status"):
            assert hasattr(s, attr), f"missing field: {attr}"

    def test_defaults(self):
        s = make_sample()
        assert s.moisture_out_target_pct == 5.0
        assert s.is_peak_hour == 0
        assert s.production_status == "RUN"


class TestConfig:

    def test_default_settings(self):
        from app.core.config import settings
        assert settings.app_name  # non-empty
        assert settings.port > 0
        assert settings.baseline_thermal_intensity_kWht == 2593.0
        assert settings.target_thermal_reduction_pct == 10.0

    def test_env_overrides(self, monkeypatch):
        """متغیرهای محیطی باید پیش‌فرض‌ها را override کنند."""
        monkeypatch.setenv("LATIF_PORT", "9999")
        monkeypatch.setenv("LATIF_OPCUA_INTERVAL_SEC", "30")
        # reimport برای اعمال env جدید
        import importlib
        from app.core import config
        importlib.reload(config)
        assert config.settings.port == 9999
        assert config.settings.opcua_interval_sec == 30
        # بازگرداندن
        monkeypatch.delenv("LATIF_PORT", raising=False)
        monkeypatch.delenv("LATIF_OPCUA_INTERVAL_SEC", raising=False)
        importlib.reload(config)
