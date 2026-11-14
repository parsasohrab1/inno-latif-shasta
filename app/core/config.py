"""تنظیمات سرور FastAPI و سرویس‌ها."""

from __future__ import annotations
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # سرور
    app_name: str = "Latif Digital Twin API"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]

    # شبیه‌ساز OPC-UA
    opcua_sim_enabled: bool = True
    opcua_interval_sec: int = 5      # هر گام ۵ ثانیه (شبیه‌سازی فشرده‌تر)
    opcua_seed: int = 42

    # Historian
    historian_backend: str = "memory"  # memory | sqlite
    historian_path: str = "/tmp/latif_historian.sqlite"
    historian_retention_hours: int = 24

    # MPC
    mpc_horizon: int = 3
    mpc_max_iters: int = 30
    mpc_auto_apply: bool = False  # False = Advisory, True = Auto

    # KPI های خط پایه (از BRS/SRS)
    baseline_thermal_intensity_kWht: float = 2593.0
    baseline_gas_peak_nm3h: float = 460.0
    baseline_waste_pct: float = 2.6

    # اهداف
    target_thermal_reduction_pct: float = 10.0
    target_gas_peak_reduction_pct: float = 9.0
    target_waste_reduction_pct: float = 55.0

    class Config:
        env_prefix = "LATIF_"
        env_file = ".env"


settings = Settings()
