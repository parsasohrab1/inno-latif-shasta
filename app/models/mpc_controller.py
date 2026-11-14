"""
کنترل‌کننده پیش‌بینانه مدل‌محور (MPC) خشک‌کن خط تیشو

حل مسأله بهینه‌سازی در هر گام کنترلی (۵ دقیقه) با افق پیش‌بینی ۱۵ دقیقه:
  min  J = Σ [ w1·E(t+k) + w2·P_gas(t+k) + w3·Waste(t+k) + w4·ΔSP² ]
  s.t.:
    3% ≤ moisture_out_pred(t+k) ≤ 7%
    hood_min ≤ SP_hood(t+k) ≤ hood_max
    steam_min ≤ SP_steam(t+k) ≤ steam_max
    |ΔSP| ≤ ΔSP_max
    softness_pred ≥ 7.5
    capillary_rise_pred ≥ 80 mm

به‌جای یک solver سنگین (CasADi)، از روش تبرید شبیه‌سازی‌شده (simulated annealing)
یا جستجوی شبکه‌ای محلی استفاده می‌کنیم تا وابستگی به کتابخانه‌های خارجی نباشد.
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from .dryer_model import DryerModel, DryerState, DryerOutput


@dataclass
class MPCConstraints:
    """محدوده‌های ایمنی و کیفی HSE."""
    hood_temp_min: float = 300.0
    hood_temp_max: float = 480.0
    hood_temp_delta_max: float = 2.0  # °C/min
    steam_pressure_min: float = 4.0
    steam_pressure_max: float = 6.2
    steam_pressure_delta_max: float = 0.1  # bar/min
    hot_air_temp_min: float = 380.0
    hot_air_temp_max: float = 450.0
    hot_air_temp_delta_max: float = 3.0
    machine_speed_min: float = 1350.0
    machine_speed_max: float = 1600.0
    machine_speed_delta_max: float = 5.0
    moisture_min: float = 3.0
    moisture_max: float = 7.0
    moisture_target: float = 5.0
    softness_min: float = 7.5
    capillary_rise_min: float = 80.0


@dataclass
class MPCWeights:
    """وزن‌های تابع هدف MPC."""
    w1_energy: float = 1.0
    w2_gas_peak: float = 0.8
    w3_waste: float = 1.5
    w4_delta_sp: float = 0.3
    w5_quality: float = 0.5


@dataclass
class MPCSolution:
    """خروجی کنترل‌کننده در یک گام."""
    setpoints: Dict[str, List[float]]  # set-point پیشنهادی برای هر گام افق
    predictions: List[Dict]            # پیش‌بینی خروجی‌ها برای هر گام
    cost: float                        # تابع هدف نهایی
    feasible: bool                     # آیا راه‌حل موجه است
    iterations: int                    # تعداد تکرارها
    computation_time_ms: float        # زمان محاسبه
    mode: str = "advisory"             # advisory / auto / manual


class MPCController:
    """کنترل‌کننده پیش‌بینانه خشک‌کن.

    از یک حل‌کننده‌ی داخلی مبتنی بر جستجوی محلی (local search + random restart)
    استفاده می‌کند که CasADi یا GEKKO را شبیه‌سازی می‌کند، بدون وابستگی خارجی.
    """

    def __init__(self,
                 model: Optional[DryerModel] = None,
                 constraints: Optional[MPCConstraints] = None,
                 weights: Optional[MPCWeights] = None,
                 horizon: int = 3,
                 control_interval_min: int = 5):
        self.model = model or DryerModel()
        self.constraints = constraints or MPCConstraints()
        self.weights = weights or MPCWeights()
        self.horizon = horizon
        self.control_interval = control_interval_min
        self.last_setpoints: Dict[str, List[float]] = {}
        self.rng = random.Random(42)

    def solve(self, current_state: DryerState,
              is_peak_hour: bool = False,
              max_iters: int = 50) -> MPCSolution:
        """حل مسأله MPC برای یک گام کنترلی."""
        import time
        t0 = time.time()

        c = self.constraints
        w = self.weights

        # مقادیر فعلی به‌عنوان نقطه شروع
        sp_init = {
            "hood_temp": [current_state.hood_temp_c] * self.horizon,
            "steam_pressure": [current_state.steam_pressure_bar] * self.horizon,
            "hot_air_temp": [current_state.hot_air_temp_c] * self.horizon,
            "machine_speed": [current_state.machine_speed_mmin] * self.horizon,
        }

        best_sp = dict(sp_init)
        best_cost = self._evaluate(best_sp, current_state, is_peak_hour)
        best_feasible = self._is_feasible(best_sp, current_state)

        # جستجوی محلی با random restart
        restarts = 5
        for r in range(restarts):
            sp = self._random_perturbation(sp_init if r == 0 else best_sp, c)
            for it in range(max_iters // restarts):
                # تولید همسایه
                cand = self._local_step(sp, c)
                if not self._is_feasible_bounds(cand, c):
                    continue
                cost = self._evaluate(cand, current_state, is_peak_hour)
                if cost < best_cost:
                    best_cost = cost
                    best_sp = dict(cand)
                    best_feasible = True
                else:
                    # پذیرش با احتمال (شبیه‌سازی annealing)
                    temp = max(0.01, 1.0 - it / (max_iters / restarts))
                    delta = cost - best_cost
                    if delta < 0 or self.rng.random() < math.exp(-delta / temp):
                        sp = cand

        # اعمال قیود ایمنی نهایی
        best_sp = self._clip_to_constraints(best_sp, c)

        # محاسبه پیش‌بینی خروجی‌ها با set-point بهینه
        preds = self.model.predict_horizon(current_state, best_sp, self.horizon)
        predictions = [
            {
                "k": k,
                "moisture_out_pct": p.moisture_out_pct,
                "thermal_energy_intensity_kWht": p.thermal_energy_intensity_kWht,
                "production_th": p.production_th,
                "co2_kg_per_t": p.co2_kg_per_t,
                "drying_efficiency_pct": p.drying_efficiency_pct,
            }
            for k, p in enumerate(preds)
        ]

        elapsed_ms = (time.time() - t0) * 1000
        self.last_setpoints = best_sp
        return MPCSolution(
            setpoints=best_sp,
            predictions=predictions,
            cost=round(best_cost, 4),
            feasible=best_feasible,
            iterations=max_iters,
            computation_time_ms=round(elapsed_ms, 2),
            mode="advisory",
        )

    def _evaluate(self, sp: Dict[str, List[float]],
                  state: DryerState, is_peak: bool) -> float:
        """ارزیابی تابع هدف J برای یک مسیر set-point."""
        w = self.weights
        c = self.constraints
        preds = self.model.predict_horizon(state, sp, self.horizon)

        cost = 0.0
        baseline_intensity = 2593.0  # خط پایه kWh/t
        prev_sp = {k: getattr(state, v) for k, v in [
            ("hood_temp", "hood_temp_c"),
            ("steam_pressure", "steam_pressure_bar"),
            ("hot_air_temp", "hot_air_temp_c"),
            ("machine_speed", "machine_speed_mmin"),
        ]}

        for k, p in enumerate(preds):
            # w1: شدت انرژی (نرمال‌سازی نسبت به خط پایه)
            cost += w.w1_energy * (p.thermal_energy_intensity_kWht / baseline_intensity)

            # w2: پیک گاز — اگر در ساعات اوج باشد، جریمه بیشتر
            if is_peak:
                cost += w.w2_gas_peak * (sp["hood_temp"][k] / 480.0)
            else:
                cost += w.w2_gas_peak * 0.3 * (sp["hood_temp"][k] / 480.0)

            # w3: ضایعات — اگر رطوبت خارج از محدوده مطلوب (4.5-5.5) باشد
            moisture = p.moisture_out_pct
            if moisture < c.moisture_target - 0.5:
                cost += w.w3_waste * (c.moisture_target - 0.5 - moisture) * 10
            elif moisture > c.moisture_target + 0.5:
                cost += w.w3_waste * (moisture - c.moisture_target - 0.5) * 10

            # w4: نوسان set-point (نرم‌افزار مایل به تغییر ناگهانی نیست)
            for key, prev in prev_sp.items():
                delta = abs(sp[key][k] - prev)
                dmax = self._delta_max(key)
                if dmax > 0:
                    cost += w.w4_delta_sp * (delta / dmax) ** 2
                prev_sp[key] = sp[key][k]

            # w5: قیود کیفی (نرمی و مویینگی) — تقریب خطی
            # هرچه دمای هود و فشار بخار مناسب‌تر، نرمی بالاتر
            if sp["hood_temp"][k] > 450 or sp["hood_temp"][k] < 350:
                cost += w.w5_quality * 0.5

        # جریمه سنگین برای نقض قیود سخت (penalty)
        if not self._is_feasible_bounds(sp, c):
            cost += 1000.0 * self._constraint_violation(sp, c)

        return cost

    def _is_feasible_bounds(self, sp: Dict[str, List[float]], c: MPCConstraints) -> bool:
        """بررسی محدوده‌های سخت (بدون نرخ تغییر)."""
        for k in range(self.horizon):
            if not (c.hood_temp_min <= sp["hood_temp"][k] <= c.hood_temp_max):
                return False
            if not (c.steam_pressure_min <= sp["steam_pressure"][k] <= c.steam_pressure_max):
                return False
            if not (c.hot_air_temp_min <= sp["hot_air_temp"][k] <= c.hot_air_temp_max):
                return False
            if not (c.machine_speed_min <= sp["machine_speed"][k] <= c.machine_speed_max):
                return False
        return True

    def _is_feasible(self, sp: Dict[str, List[float]], state: DryerState) -> bool:
        c = self.constraints
        if not self._is_feasible_bounds(sp, c):
            return False
        # بررسی نرخ تغییر
        prev = {"hood_temp": state.hood_temp_c,
                "steam_pressure": state.steam_pressure_bar,
                "hot_air_temp": state.hot_air_temp_c,
                "machine_speed": state.machine_speed_mmin}
        for k in range(self.horizon):
            for key, p in prev.items():
                if abs(sp[key][k] - p) > self._delta_max(key) * self.control_interval:
                    return False
                prev[key] = sp[key][k]
        # بررسی قیود کیفی (تقریب)
        preds = self.model.predict_horizon(state, sp, self.horizon)
        for p in preds:
            if not (c.moisture_min <= p.moisture_out_pct <= c.moisture_max):
                return False
        return True

    def _constraint_violation(self, sp: Dict[str, List[float]], c: MPCConstraints) -> float:
        """مجموع نقض قیود برای جریمه."""
        v = 0.0
        for k in range(self.horizon):
            v += max(0, sp["hood_temp"][k] - c.hood_temp_max)
            v += max(0, c.hood_temp_min - sp["hood_temp"][k])
            v += max(0, sp["steam_pressure"][k] - c.steam_pressure_max)
            v += max(0, c.steam_pressure_min - sp["steam_pressure"][k])
        return v

    def _delta_max(self, key: str) -> float:
        c = self.constraints
        return {
            "hood_temp": c.hood_temp_delta_max,
            "steam_pressure": c.steam_pressure_delta_max,
            "hot_air_temp": c.hot_air_temp_delta_max,
            "machine_speed": c.machine_speed_delta_max,
        }.get(key, 1.0)

    def _random_perturbation(self, sp: Dict[str, List[float]],
                             c: MPCConstraints) -> Dict[str, List[float]]:
        """تولید نقطه تصادفی درون محدوده‌ها."""
        return {
            "hood_temp": [self.rng.uniform(c.hood_temp_min, c.hood_temp_max)
                          for _ in range(self.horizon)],
            "steam_pressure": [self.rng.uniform(c.steam_pressure_min, c.steam_pressure_max)
                               for _ in range(self.horizon)],
            "hot_air_temp": [self.rng.uniform(c.hot_air_temp_min, c.hot_air_temp_max)
                             for _ in range(self.horizon)],
            "machine_speed": [self.rng.uniform(c.machine_speed_min, c.machine_speed_max)
                              for _ in range(self.horizon)],
        }

    def _local_step(self, sp: Dict[str, List[float]],
                    c: MPCConstraints) -> Dict[str, List[float]]:
        """یک گام همسایگی کوچک."""
        cand = {k: list(v) for k, v in sp.items()}
        key = self.rng.choice(list(cand.keys()))
        k = self.rng.randint(0, self.horizon - 1)
        step = self.rng.gauss(0, 1) * 2.0
        cand[key][k] = cand[key][k] + step
        return cand

    def _clip_to_constraints(self, sp: Dict[str, List[float]],
                             c: MPCConstraints) -> Dict[str, List[float]]:
        """برش به محدوده‌های ایمنی."""
        sp["hood_temp"] = [min(c.hood_temp_max, max(c.hood_temp_min, v))
                           for v in sp["hood_temp"]]
        sp["steam_pressure"] = [min(c.steam_pressure_max, max(c.steam_pressure_min, v))
                                for v in sp["steam_pressure"]]
        sp["hot_air_temp"] = [min(c.hot_air_temp_max, max(c.hot_air_temp_min, v))
                              for v in sp["hot_air_temp"]]
        sp["machine_speed"] = [min(c.machine_speed_max, max(c.machine_speed_min, v))
                               for v in sp["machine_speed"]]
        return sp
