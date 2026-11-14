"""شبیه‌ساز OPC-UA برای خشک‌کن خط تیشو.

این سرویس داده سنسور واقعی را (که در فاز Pilot از DCS از طریق OPC-UA می‌آید)
با مدل فیزیکی همانند اسکریپت generate_synthetic_data.py شبیه‌سازی می‌کند.

هر گام (settings.opcua_interval_sec ثانیه) یک نمونه تولید و در historian ذخیره می‌کند.
"""

from __future__ import annotations
import math
import time
import threading
import numpy as np
from datetime import datetime

from app.core.config import settings
from app.core.historian import historian, SensorSample
from app.models.dryer_model import DryerModel, DryerState


class OPCUASimulator:
    """شبیه‌ساز سنسورهای خشک‌کن."""

    def __init__(self, seed: int = None):
        self.rng = np.random.default_rng(seed or settings.opcua_seed)
        self.dryer_model = DryerModel()
        self._running = False
        self._thread = None
        self._step = 0
        self._t0 = time.time()
        # محاسبه shift از ساعت
        self._shift = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        while self._running:
            sample = self._generate_sample()
            historian.append(sample)
            time.sleep(settings.opcua_interval_sec)

    def _generate_sample(self) -> SensorSample:
        """تولید یک نمونه سنسور با نوسان طبیعی."""
        t = self._step
        self._step += 1

        # زمان شبیه‌سازی به دقیقه (نرخ فشرده‌تر، ۱ گام = ۵ دقیقه شبیه‌سازی)
        sim_minute = t * 5
        minute_of_day = sim_minute % 1440
        hour = int((sim_minute // 60) % 24)
        self._shift = hour // 8 % 3

        # نوسان روزانه (مشابه generate_synthetic_data.py)
        hood_temp = 400.0 + 20.0 * math.sin(2 * math.pi * minute_of_day / 1440) \
                    + float(self.rng.normal(0, 3.5))
        yankee_surface = 100.0 + 5.0 * math.sin(2 * math.pi * minute_of_day / 1440 + 0.5) \
                         + float(self.rng.normal(0, 1.2))
        steam_pressure = 5.2 + 0.3 * math.sin(2 * math.pi * minute_of_day / 1440 + 1.0) \
                         + float(self.rng.normal(0, 0.08))
        hot_air_temp = 420.0 + 15.0 * math.sin(2 * math.pi * minute_of_day / 1440 + 0.2) \
                       + float(self.rng.normal(0, 4.0))
        moisture_in = 68.0 + 4.0 * math.sin(2 * math.pi * minute_of_day / 1440 + 1.5) \
                      + float(self.rng.normal(0, 1.0))
        basis_weight = 15.0 + 0.3 * math.sin(2 * math.pi * minute_of_day / 1440 + 2.0) \
                       + float(self.rng.normal(0, 0.08))
        machine_speed = 1500 + 50 * math.sin(2 * math.pi * minute_of_day / 1440 + 1.2) \
                        + float(self.rng.normal(0, 8))
        steam_flow = 7.2 + 0.012 * (moisture_in - 68) + 0.001 * (machine_speed - 1500) \
                     + float(self.rng.normal(0, 0.15))
        gas_flow = 320 + 0.8 * (hood_temp - 400) + 0.05 * (machine_speed - 1500) \
                   + float(self.rng.normal(0, 6))

        # تولید رطوبت خروجی با مدل ترمودینامیکی
        state = DryerState(
            hood_temp_c=hood_temp, yankee_surface_c=yankee_surface,
            steam_pressure_bar=steam_pressure, hot_air_temp_c=hot_air_temp,
            moisture_in_pct=moisture_in, basis_weight_gm2=basis_weight,
            machine_speed_mmin=machine_speed, steam_flow_th=steam_flow,
            gas_flow_nm3h=gas_flow,
        )
        out = self.dryer_model.step(state)

        # اوج گاز
        is_peak = 1 if (8 <= hour <= 11) or (18 <= hour <= 21) else 0

        # کیفیت
        softness = max(7.0, min(9.0, 8.0 + 0.4 * math.sin(2 * math.pi * minute_of_day / 1440 + 2.5)
                                + float(self.rng.normal(0, 0.15))))
        capillary_rise = max(80.0, 85.0 + 3.0 * math.sin(2 * math.pi * minute_of_day / 1440 + 3.0)
                             + float(self.rng.normal(0, 1.0)))

        out_of_spec = 1 if not (3.0 <= out.moisture_out_pct <= 7.0) else 0

        return SensorSample(
            timestamp=time.time(),
            shift=self._shift,
            hood_temp_c=round(hood_temp, 2),
            yankee_surface_c=round(yankee_surface, 2),
            steam_pressure_bar=round(steam_pressure, 3),
            hot_air_temp_c=round(hot_air_temp, 2),
            moisture_in_pct=round(moisture_in, 3),
            moisture_out_pct=out.moisture_out_pct,
            moisture_out_target_pct=5.0,
            basis_weight_gm2=round(basis_weight, 3),
            machine_speed_mmin=round(machine_speed, 1),
            steam_flow_th=round(steam_flow, 3),
            gas_flow_nm3h=round(gas_flow, 2),
            production_th=out.production_th,
            thermal_energy_intensity_kWht=out.thermal_energy_intensity_kWht,
            softness_1_10=round(softness, 2),
            capillary_rise_mm=round(capillary_rise, 2),
            out_of_spec_flag=out_of_spec,
            is_peak_hour=is_peak,
            production_status="RUN",
        )

    def status(self) -> dict:
        return {
            "running": self._running,
            "step": self._step,
            "samples_in_historian": historian.count(),
            "interval_sec": settings.opcua_interval_sec,
        }


opcua_sim = OPCUASimulator()
