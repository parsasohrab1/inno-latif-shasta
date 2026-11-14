"""سرویس کنترل‌کننده MPC.

- آخرین حالت را از historian می‌خواند
- MPC را حل می‌کند
- حالت Advisory/Auto را مدیریت می‌کند
- Audit Log برای هر set-point اعمال‌شده
"""

from __future__ import annotations
import time
from dataclasses import dataclass, asdict
from typing import Optional
import threading

from app.core.config import settings
from app.core.historian import historian, SensorSample
from app.models.dryer_model import DryerModel, DryerState
from app.models.mpc_controller import MPCController, MPCSolution
from app.models.moisture_predictor import MoisturePredictor
from app.monitoring import metrics


@dataclass
class AuditEntry:
    timestamp: float
    event_type: str       # mpc_solve | setpoint_apply | setpoint_reject | mode_change | fallback
    operator: str          # "system" | "operator_x"
    details: dict


class MPCService:
    """سرویس کنترل پیش‌بینانه."""

    def __init__(self):
        self.dryer_model = DryerModel()
        self.predictor = MoisturePredictor()
        self.mpc = MPCController(model=self.dryer_model,
                                horizon=settings.mpc_horizon)
        self.mode = "advisory"   # advisory | auto | manual
        self.last_solution: Optional[MPCSolution] = None
        self.last_solve_time: float = 0
        self._lock = threading.Lock()
        self.audit_log: list[AuditEntry] = []

    def solve(self, operator: str = "system") -> dict:
        """حل MPC با آخرین داده historian."""
        with self._lock:
            sample = historian.latest()
            if sample is None:
                return {"error": "no_data", "message": "هیچ داده‌ای در historian نیست"}

            state = DryerState(
                hood_temp_c=sample.hood_temp_c,
                yankee_surface_c=sample.yankee_surface_c,
                steam_pressure_bar=sample.steam_pressure_bar,
                hot_air_temp_c=sample.hot_air_temp_c,
                moisture_in_pct=sample.moisture_in_pct,
                basis_weight_gm2=sample.basis_weight_gm2,
                machine_speed_mmin=sample.machine_speed_mmin,
                steam_flow_th=sample.steam_flow_th,
                gas_flow_nm3h=sample.gas_flow_nm3h,
            )

            # پیش‌بینی رطوبت از تاریخچه
            history = [self._sample_to_dict(s) for s in historian.history(6)]
            pred = self.predictor.predict(history)

            # حل MPC
            sol = self.mpc.solve(state, is_peak_hour=bool(sample.is_peak_hour),
                                  max_iters=settings.mpc_max_iters)
            sol.mode = self.mode
            self.last_solution = sol
            self.last_solve_time = time.time()

            # ثبت در متریک‌های Prometheus
            try:
                metrics.record_mpc(sol, mode=self.mode)
            except Exception:
                pass

            self.audit_log.append(AuditEntry(
                timestamp=time.time(),
                event_type="mpc_solve",
                operator=operator,
                details={
                    "cost": sol.cost,
                    "feasible": sol.feasible,
                    "ms": sol.computation_time_ms,
                    "mode": sol.mode,
                }
            ))
            try:
                metrics.record_audit("mpc_solve")
            except Exception:
                pass
            # نگه‌داری فقط ۱۰۰۰ مورد آخر
            self.audit_log = self.audit_log[-1000:]

            return {
                "timestamp": time.time(),
                "state": asdict(state),
                "moisture_prediction": {
                    "pred_pct": pred.moisture_pred_pct,
                    "horizon_min": pred.horizon_min,
                    "confidence": pred.confidence,
                },
                "solution": {
                    "setpoints": sol.setpoints,
                    "predictions": sol.predictions,
                    "cost": sol.cost,
                    "feasible": sol.feasible,
                    "iterations": sol.iterations,
                    "computation_time_ms": sol.computation_time_ms,
                    "mode": sol.mode,
                },
            }

    def apply_setpoint(self, operator: str = "operator", approved: bool = True) -> dict:
        """اعمال set-point پیشنهادی MPC.

        - در حالت advisory: اگر approved=True، ثبت در audit
        - در حالت auto: همیشه اعمال می‌شود
        """
        with self._lock:
            if self.last_solution is None:
                return {"error": "no_solution", "message": "ابتدا MPC را حل کنید"}

            if self.mode == "manual":
                return {"error": "manual_mode", "message": "سیستم در حالت دستی است"}

            event = "setpoint_apply" if approved else "setpoint_reject"
            sp = self.last_solution.setpoints
            # فقط گام اول اعمال می‌شود
            applied_sp = {k: v[0] for k, v in sp.items()}

            self.audit_log.append(AuditEntry(
                timestamp=time.time(),
                event_type=event,
                operator=operator,
                details={"setpoint": applied_sp, "mode": self.mode}
            ))
            self.audit_log = self.audit_log[-1000:]

            return {
                "applied": approved,
                "setpoint": applied_sp,
                "mode": self.mode,
                "operator": operator,
                "timestamp": time.time(),
            }

    def set_mode(self, mode: str, operator: str = "operator") -> dict:
        if mode not in ("advisory", "auto", "manual"):
            return {"error": "invalid_mode"}
        old = self.mode
        self.mode = mode
        self.audit_log.append(AuditEntry(
            timestamp=time.time(),
            event_type="mode_change",
            operator=operator,
            details={"from": old, "to": mode}
        ))
        self.audit_log = self.audit_log[-1000:]
        return {"from": old, "to": mode, "operator": operator}

    def get_audit_log(self, n: int = 50) -> list[dict]:
        return [asdict(e) for e in self.audit_log[-n:]]

    def _sample_to_dict(self, s: SensorSample) -> dict:
        return {
            "moisture_in": s.moisture_in_pct,
            "moisture_out": s.moisture_out_pct,
            "hood_temp": s.hood_temp_c,
            "steam_pressure": s.steam_pressure_bar,
            "hot_air_temp": s.hot_air_temp_c,
            "basis_weight": s.basis_weight_gm2,
            "machine_speed": s.machine_speed_mmin,
            "gas_flow": s.gas_flow_nm3h,
        }


mpc_service = MPCService()
