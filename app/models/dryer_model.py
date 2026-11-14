"""
مدل ترمودینامیکی خشک‌کن هیبریدی خط تیشو (Yankee + Hood)

مدل بر اساس تراز جرم و انرژی:
  - خشک‌کردن با بخار (Yankee) و هوای گرم + تابش (Hood)
  - محاسبه رطوبت خروجی، شدت انرژی حرارتی، انتشار CO2
  - قابلیت پیش‌بینی حالت داخلی در افق کوتاه

پارامترها از داده سنتتیک خط پایه (data/synthetic/summary_stats.json) تنظیم شده‌اند.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict

# ثابت‌های فیزیکی و انرژی
STEAM_ENERGY_KWH_PER_TON = 2200.0  # kWh حرارتی به ازای هر تن بخار (تبدیل از MJ/t)
GAS_ENERGY_KWH_PER_NM3 = 9.5       # kWh حرارتی به ازای هر Nm3 گاز طبیعی
GAS_CO2_KG_PER_NM3 = 2.04         # kg CO2 به ازای هر Nm3 گاز (IPCC)
WATER_LATENT_HEAT_KWH_PER_T = 627.0  # kWh لازم برای تبخیر هر تن آب (حدود 2260 MJ/t / 3.6)
WEB_WIDTH_M = 5.4                  # عرض وب خط لطیف
DENSITY_TISSUE_KG_PER_M3 = 300.0  # چگالی تقریبی تیشوی خشک‌شده


@dataclass
class DryerState:
    """حالت لحظه‌ای خشک‌کن (ورودی‌های مدل)."""
    hood_temp_c: float           # دمای هود (C)
    yankee_surface_c: float      # دمای سطح سیلندر یانکی (C)
    steam_pressure_bar: float   # فشار بخار یانکی (bar)
    hot_air_temp_c: float       # دمای هوای گرم ورودی هود (C)
    moisture_in_pct: float      # رطوبت ورودی (%)
    basis_weight_gm2: float     # گرماژ (g/m2)
    machine_speed_mmin: float   # سرعت ماشین (m/min)
    steam_flow_th: float        # دبی بخار (t/h)
    gas_flow_nm3h: float        # دبی گاز (Nm3/h)


@dataclass
class DryerOutput:
    """خروجی‌های مدل ترمودینامیکی."""
    moisture_out_pct: float     # رطوبت نهایی پیش‌بینی‌شده (%)
    production_th: float       # تولید (t/h)
    thermal_energy_intensity_kWht: float  # شدت انرژی حرارتی (kWh/t)
    energy_kwh: float          # انرژی حرارتی کل (kW)
    co2_kg_per_t: float        # انتشار CO2 به ازای هر تن (kg/t)
    evaporation_rate_th: float # نرخ تبخیر آب (t/h)
    drying_efficiency_pct: float  # بازده خشک‌کردن (نسبت انرژی مفید به کل)


class DryerModel:
    """مدل ترمودینامیکی خشک‌کن هیبریدی.

    از مدل ساده‌شده‌ی تراز انرژی استفاده می‌کند:
      - انرژی کل در دسترس = انرژی بخار + انرژی گاز هود
      - آب قابل تبخیر = min(آب ورودی، انرژی / گرمای نهانی)
      - رطوبت خروجی = max(هدف، رطوبت ورودی - آب تبخیرشده / جرم خشک)
    """

    def __init__(self,
                 hood_efficiency: float = 0.65,
                 yankee_efficiency: float = 0.70,
                 moisture_target_pct: float = 5.0,
                 moisture_min_pct: float = 3.0,
                 moisture_max_pct: float = 7.0):
        self.hood_eff = hood_efficiency
        self.yankee_eff = yankee_efficiency
        self.moisture_target = moisture_target_pct
        self.moisture_min = moisture_min_pct
        self.moisture_max = moisture_max_pct

    def step(self, s: DryerState) -> DryerOutput:
        """محاسبه خروجی خشک‌کن برای یک گام."""
        # تولید (t/h): basis_weight (g/m2) × speed (m/min) × width (m) × 60 / 1e6
        production_th = s.basis_weight_gm2 * s.machine_speed_mmin * WEB_WIDTH_M * 60.0 / 1e6
        production_th = max(production_th, 1e-6)

        # انرژی حرارتی کل موجود (kW)
        steam_energy_kw = s.steam_flow_th * STEAM_ENERGY_KWH_PER_TON  # t/h × kWh/t = kW
        gas_energy_kw = s.gas_flow_nm3h * GAS_ENERGY_KWH_PER_NM3
        total_energy_kw = steam_energy_kw + gas_energy_kw

        # انرژی مفید (با ضرب در بازده)
        useful_energy_kw = (steam_energy_kw * self.yankee_eff
                            + gas_energy_kw * self.hood_eff)

        # نرخ تبخیر آب (t/h) از انرژی مفید
        # آب ورودی به خشک‌کن (t/h) = production × moisture_in / (100 - moisture_in)
        dry_fiber_th = production_th * (1 - s.moisture_in_pct / 100.0)
        water_in_th = production_th - dry_fiber_th

        # حداکثر آبی که می‌توان تبخیر کرد (t/h) = useful_energy / latent_heat
        max_evap_th = useful_energy_kw / WATER_LATENT_HEAT_KWH_PER_T

        # آب تبخیرشده واقعی = min(آب ورودی - آب هدف, حداکثر تبخیر ممکن)
        target_water_th = dry_fiber_th * self.moisture_target / (100.0 - self.moisture_target)
        water_evap_th = min(water_in_th - target_water_th, max_evap_th)
        water_evap_th = max(water_evap_th, 0.0)

        # رطوبت خروجی
        water_out_th = max(water_in_th - water_evap_th, 0.0)
        if dry_fiber_th > 0:
            moisture_out = water_out_th / (dry_fiber_th + water_out_th) * 100.0
        else:
            moisture_out = self.moisture_target
        moisture_out = max(self.moisture_min, min(self.moisture_max, moisture_out))

        # شدت انرژی حرارتی (kWh/t)
        thermal_intensity = total_energy_kw / production_th if production_th > 0 else 0.0

        # CO2 (kg/t) — فقط از گاز (بخار فرض می‌شود از بویلر کارخانه است و جدا حساب می‌شود)
        co2_kg_per_t = (s.gas_flow_nm3h * GAS_CO2_KG_PER_NM3) / production_th

        # بازده خشک‌کردن = انرژی مفید تبخیر / انرژی کل
        evap_energy_kw = water_evap_th * WATER_LATENT_HEAT_KWH_PER_T
        drying_eff = evap_energy_kw / total_energy_kw if total_energy_kw > 0 else 0.0

        return DryerOutput(
            moisture_out_pct=round(moisture_out, 4),
            production_th=round(production_th, 4),
            thermal_energy_intensity_kWht=round(thermal_intensity, 2),
            energy_kwh=round(total_energy_kw, 2),
            co2_kg_per_t=round(co2_kg_per_t, 2),
            evaporation_rate_th=round(water_evap_th, 4),
            drying_efficiency_pct=round(drying_eff * 100, 2),
        )

    def predict_horizon(self, current: DryerState, setpoints: Dict[str, list],
                        horizon: int = 3) -> list:
        """پیش‌بینی خروجی در افق 'horizon' گام ۵ دقیقه‌ای.

        setpoints: لیست تنظیمات برای هر گام شامل:
          - hood_temp: لیست دمای هود در هر گام
          - steam_pressure: لیست فشار بخار در هر گام
          - hot_air_temp: لیست دمای هوای گرم در هر گام
          - machine_speed: لیست سرعت ماشین در هر گام
        """
        results = []
        s = DryerState(
            hood_temp_c=current.hood_temp_c,
            yankee_surface_c=current.yankee_surface_c,
            steam_pressure_bar=current.steam_pressure_bar,
            hot_air_temp_c=current.hot_air_temp_c,
            moisture_in_pct=current.moisture_in_pct,
            basis_weight_gm2=current.basis_weight_gm2,
            machine_speed_mmin=current.machine_speed_mmin,
            steam_flow_th=current.steam_flow_th,
            gas_flow_nm3h=current.gas_flow_nm3h,
        )
        for k in range(horizon):
            # اعمال set-point‌های گام k
            if k < len(setpoints.get("hood_temp", [])):
                s.hood_temp_c = setpoints["hood_temp"][k]
            if k < len(setpoints.get("steam_pressure", [])):
                s.steam_pressure_bar = setpoints["steam_pressure"][k]
            if k < len(setpoints.get("hot_air_temp", [])):
                s.hot_air_temp_c = setpoints["hot_air_temp"][k]
            if k < len(setpoints.get("machine_speed", [])):
                s.machine_speed_mmin = setpoints["machine_speed"][k]
            # برآورد دبی بخار و گاز از set-point‌ها (مدل ساده)
            s.steam_flow_th = self._estimate_steam_flow(s)
            s.gas_flow_nm3h = self._estimate_gas_flow(s)
            out = self.step(s)
            results.append(out)
            # به‌روزرسانی رطوبت ورودی گام بعد (با تأخیر اندک)
            s.moisture_in_pct = current.moisture_in_pct  # فرض: ثابت در افق کوتاه
        return results

    def _estimate_steam_flow(self, s: DryerState) -> float:
        """برآورد دبی بخار از فشار و سرعت (مدل تقریبی)."""
        base = 7.2  # t/h baseline
        d_pressure = (s.steam_pressure_bar - 5.2) * 0.8
        d_speed = (s.machine_speed_mmin - 1500.0) * 0.001
        return max(2.0, base + d_pressure + d_speed)

    def _estimate_gas_flow(self, s: DryerState) -> float:
        """برآورد دبی گاز از دمای هود و سرعت."""
        base = 320.0
        d_hood = (s.hood_temp_c - 400.0) * 0.8
        d_speed = (s.machine_speed_mmin - 1500.0) * 0.05
        return max(150.0, base + d_hood + d_speed)
