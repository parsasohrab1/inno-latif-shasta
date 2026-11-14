"""متریک‌های Prometheus برای دوقلوی دیجیتال لطیف.

متریک‌ها بر اساس KPI های SRS (P-1 تا P-17) تعریف شده‌اند.
 endpoint /metrics برای scrape توسط Prometheus.

مدل متریک‌ها:
  - Counter   : شمارنده‌ی رویدادها (تعداد حل MPC، تعداد apply، تعداد خطا)
  - Gauge     : مقدار لحظه‌ای (رطوبت، شدت انرژی، دبی گاز)
  - Histogram  : توزیع زمان (زمان حل MPC)
"""

from __future__ import annotations
import time
from prometheus_client import (
    Counter, Gauge, Histogram, Info, CollectorRegistry, generate_latest,
)

# رجیستری اختصاصی (از رجیستری پیش‌فرض برای کنترل کامل استفاده می‌کنیم)
registry = CollectorRegistry()

# ---- Info: اطلاعات ثابت سرویس ----
info = Info("latif", "Latif Digital Twin service info", registry=registry)
info.info({
    "version": "0.2.0",
    "service": "digital-twin",
    "component": "dryer-mpc",
})

# ---- Counters ----
MPC_SOLVE_TOTAL = Counter(
    "latif_mpc_solve_total", "Total MPC solves",
    ["feasible", "mode"], registry=registry
)
MPC_APPLY_TOTAL = Counter(
    "latif_mpc_apply_total", "Total set-point apply/reject",
    ["action"], registry=registry  # action: applied/rejected
)
AUDIT_EVENTS_TOTAL = Counter(
    "latif_audit_events_total", "Total audit log entries",
    ["event_type"], registry=registry
)
OPCUA_SAMPLES_TOTAL = Counter(
    "latif_opcua_samples_total", "Total OPC-UA samples received", registry=registry
)
API_REQUESTS_TOTAL = Counter(
    "latif_api_requests_total", "Total API requests",
    ["endpoint", "method", "status"], registry=registry
)

# ---- Gauges (مقادیر لحظه‌ای KPI) ----
MOISTURE_OUT_PCT = Gauge("latif_moisture_out_pct",
    "Moisture output percent", ["shift"], registry=registry)
MOISTURE_GAP_PCT = Gauge("latif_moisture_gap_pct",
    "Moisture gap from target percent", registry=registry)
THERMAL_INTENSITY_KWHT = Gauge("latif_thermal_intensity_kWht",
    "Thermal energy intensity kWh/ton", registry=registry)
GAS_FLOW_NM3H = Gauge("latif_gas_flow_nm3h",
    "Gas flow Nm3/h", registry=registry)
GAS_PEAK_FLAG = Gauge("latif_gas_peak_flag",
    "Peak hour flag (1 if peak)", registry=registry)
STEAM_FLOW_TH = Gauge("latif_steam_flow_th",
    "Steam flow t/h", registry=registry)
PRODUCTION_TH = Gauge("latif_production_th",
    "Production t/h", registry=registry)
OUT_OF_SPEC = Gauge("latif_out_of_spec",
    "Out of spec flag (1 if out)", registry=registry)
MPC_MODE = Gauge("latif_mpc_mode",
    "MPC mode (0=manual, 1=advisory, 2=auto)", registry=registry)
HISTORIAN_COUNT = Gauge("latif_historian_count",
    "Historian sample count", registry=registry)
PRED_CONFIDENCE = Gauge("latif_pred_confidence",
    "Moisture prediction confidence 0-1", registry=registry)

# ---- Histograms ----
MPC_SOLVE_MS = Histogram(
    "latif_mpc_solve_ms", "MPC solve time in milliseconds",
    buckets=(1, 5, 10, 50, 100, 500, 1000, 5000, 10000), registry=registry
)
API_LATENCY_S = Histogram(
    "latif_api_latency_seconds", "API request latency in seconds",
    ["endpoint"], registry=registry
)


def record_sample(sample) -> None:
    """ثبت یک نمونه سنسور در متریک‌ها (از SensorSample)."""
    try:
        MOISTURE_OUT_PCT.labels(shift=str(sample.shift)).set(sample.moisture_out_pct)
        MOISTURE_GAP_PCT.set(abs(sample.moisture_out_pct - sample.moisture_out_target_pct))
        THERMAL_INTENSITY_KWHT.set(sample.thermal_energy_intensity_kWht)
        GAS_FLOW_NM3H.set(sample.gas_flow_nm3h)
        GAS_PEAK_FLAG.set(sample.is_peak_hour)
        STEAM_FLOW_TH.set(sample.steam_flow_th)
        PRODUCTION_TH.set(sample.production_th)
        OUT_OF_SPEC.set(sample.out_of_spec_flag)
        HISTORIAN_COUNT.set(1)
        OPCUA_SAMPLES_TOTAL.inc()
    except Exception:
        pass


def record_mpc(sol, mode: str = "advisory") -> None:
    """ثبت یک راه‌حل MPC."""
    try:
        MPC_SOLVE_TOTAL.labels(feasible=str(sol.feasible).lower(), mode=mode).inc()
        MPC_SOLVE_MS.observe(sol.computation_time_ms)
        if mode == "auto":
            MPC_MODE.set(2)
        elif mode == "advisory":
            MPC_MODE.set(1)
        else:
            MPC_MODE.set(0)
    except Exception:
        pass


def record_apply(approved: bool) -> None:
    try:
        MPC_APPLY_TOTAL.labels(action="applied" if approved else "rejected").inc()
    except Exception:
        pass


def record_audit(event_type: str) -> None:
    try:
        AUDIT_EVENTS_TOTAL.labels(event_type=event_type).inc()
    except Exception:
        pass


def record_api(endpoint: str, method: str, status: int, duration_s: float) -> None:
    try:
        API_REQUESTS_TOTAL.labels(endpoint=endpoint, method=method,
                                    status=str(status)).inc()
        API_LATENCY_S.labels(endpoint=endpoint).observe(duration_s)
    except Exception:
        pass


def render_metrics() -> bytes:
    """خروجی متنی برای endpoint /metrics."""
    return generate_latest(registry)
