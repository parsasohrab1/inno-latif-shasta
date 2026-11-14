"""مسیرهای REST و WebSocket برای دوقلوی دیجیتال.

مسیرها:
  GET  /api/health             : سلامت سرور
  GET  /api/status             : وضعیت شبیه‌ساز + historian
  GET  /api/sensors/latest     : آخرین نمونه سنسور
  GET  /api/sensors/history    : تاریخچه (پارامتر n)
  GET  /api/kpi                : KPI های زنده
  POST /api/mpc/solve          : حل MPC
  POST /api/mpc/apply          : اعمال set-point پیشنهادی
  POST /api/mpc/mode           : تغییر مد (advisory/auto/manual)
  GET  /api/mpc/solution       : آخرین راه‌حل MPC
  GET  /api/audit              : audit log
  WS   /ws/sensors             : stream زنده سنسورها
  WS   /ws/mpc                 : stream زنده راه‌حل‌های MPC
"""

from __future__ import annotations
import asyncio
import json
import time
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core.config import settings
from app.core.historian import historian
from app.services.opcua_sim import opcua_sim
from app.services.mpc_service import mpc_service
from dataclasses import asdict

router = APIRouter(prefix="/api")


class ModeRequest(BaseModel):
    mode: str
    operator: str = "operator"


class ApplyRequest(BaseModel):
    approved: bool = True
    operator: str = "operator"


class SolveRequest(BaseModel):
    operator: str = "system"


@router.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version, "name": settings.app_name}


@router.get("/status")
async def status():
    return {
        "opcua": opcua_sim.status(),
        "historian": {"count": historian.count(), "backend": settings.historian_backend},
        "mpc": {"mode": mpc_service.mode,
                 "last_solve_time": mpc_service.last_solve_time},
    }


@router.get("/sensors/latest")
async def sensors_latest():
    s = historian.latest()
    if s is None:
        return {"error": "no_data"}
    return asdict(s)


@router.get("/sensors/history")
async def sensors_history(n: int = 100):
    samples = historian.history(n)
    return {"count": len(samples), "samples": [asdict(s) for s in samples]}


@router.get("/kpi")
async def kpi():
    """محاسبه KPI های زنده از ۶۰ نمونه آخر."""
    samples = historian.history(60)
    if not samples:
        return {"error": "no_data"}

    energy = [s.thermal_energy_intensity_kWht for s in samples]
    gas_peak = max(s.gas_flow_nm3h for s in samples)
    out_of_spec = sum(s.out_of_spec_flag for s in samples)
    avg_moisture = sum(s.moisture_out_pct for s in samples) / len(samples)

    baseline_e = settings.baseline_thermal_intensity_kWht
    baseline_g = settings.baseline_gas_peak_nm3h
    baseline_w = settings.baseline_waste_pct

    avg_energy = sum(energy) / len(energy)
    waste_pct = (out_of_spec / len(samples)) * 100

    return {
        "thermal_intensity_kWht": round(avg_energy, 1),
        "thermal_baseline_kWht": baseline_e,
        "thermal_reduction_pct": round((1 - avg_energy / baseline_e) * 100, 2),
        "thermal_target_reduction_pct": settings.target_thermal_reduction_pct,
        "gas_peak_nm3h": round(gas_peak, 1),
        "gas_peak_baseline_nm3h": baseline_g,
        "gas_peak_reduction_pct": round((1 - gas_peak / baseline_g) * 100, 2),
        "gas_peak_target_reduction_pct": settings.target_gas_peak_reduction_pct,
        "waste_pct": round(waste_pct, 3),
        "waste_baseline_pct": baseline_w,
        "waste_reduction_pct": round((1 - waste_pct / baseline_w) * 100 if baseline_w > 0 else 0, 2),
        "waste_target_reduction_pct": settings.target_waste_reduction_pct,
        "moisture_avg_pct": round(avg_moisture, 4),
        "moisture_target_pct": 5.0,
        "samples_count": len(samples),
        "timestamp": time.time(),
    }


@router.post("/mpc/solve")
async def mpc_solve(req: SolveRequest):
    return mpc_service.solve(operator=req.operator)


@router.post("/mpc/apply")
async def mpc_apply(req: ApplyRequest):
    return mpc_service.apply_setpoint(operator=req.operator, approved=req.approved)


@router.post("/mpc/mode")
async def mpc_mode(req: ModeRequest):
    return mpc_service.set_mode(mode=req.mode, operator=req.operator)


@router.get("/mpc/solution")
async def mpc_solution():
    if mpc_service.last_solution is None:
        return {"error": "no_solution"}
    sol = mpc_service.last_solution
    return {
        "setpoints": sol.setpoints,
        "predictions": sol.predictions,
        "cost": sol.cost,
        "feasible": sol.feasible,
        "iterations": sol.iterations,
        "computation_time_ms": sol.computation_time_ms,
        "mode": sol.mode,
    }


@router.get("/audit")
async def audit(n: int = 50):
    return {"entries": mpc_service.get_audit_log(n)}


# ---- WebSockets ----

@router.websocket("/ws/sensors")
async def ws_sensors(websocket: WebSocket):
    """Stream زنده آخرین نمونه سنسور هر ۱ ثانیه."""
    await websocket.accept()
    try:
        last_ts = 0
        while True:
            s = historian.latest()
            if s and s.timestamp > last_ts:
                await websocket.send_text(json.dumps({
                    "type": "sensor",
                    "data": asdict(s),
                }))
                last_ts = s.timestamp
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@router.websocket("/ws/mpc")
async def ws_mpc(websocket: WebSocket):
    """Stream راه‌حل‌های MPC به‌صورت دوره‌ای (هر ۵ ثانیه یک‌بار حل)."""
    await websocket.accept()
    try:
        while True:
            result = mpc_service.solve(operator="ws")
            await websocket.send_text(json.dumps({"type": "mpc", "data": result}))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
