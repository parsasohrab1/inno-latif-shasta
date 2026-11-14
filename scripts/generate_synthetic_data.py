#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تولید داده سنتتیک سنسور خشک‌کن خط تیشو (Yankee Dryer + Hood)
برای پروژه دوقلوی دیجیتال محصولات کاغذی لطیف
محصولات کاغذی لطیف - تولید کاغذ بهداشتی/تیشو
 تاریخ تولید: 2026-11-14

مجموعه‌های داده تولیدشده:
  1) سری زمانی سنسورهای خشک‌کن (5 دقیقه‌ای، ۷ روز = ۲۰۱۶ نقطه)
  2) پروفایل پیک مصرف گاز در ساعات اوج
  3) سری زمانی رطوبت محصول و گپ از نقطه تنظیم
  4) مدل مصرف انرژی حرارتی به ازای هر تن (kWh/t) baseline vs optimized
  5) ضایعات ناشی از خارج‌از‌محدوده‌شدن رطوبت (out-of-spec)
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RNG = np.random.default_rng(seed=42)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(_REPO_ROOT, "data", "synthetic")
os.makedirs(OUT_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# 1) سری زمانی سنسورهای خشک‌کن (۵ دقیقه‌ای، ۷ روز)
#    ماشین تیشو: سرعت ماشین 1500 m/min، گرماژ 15 g/m²، عرض 5.4 m
# ----------------------------------------------------------------------------
N_DAYS = 7
SAMPLES_PER_DAY = 288  # 24h * 60min / 5min
N = N_DAYS * SAMPLES_PER_DAY
start = datetime(2026, 11, 7, 0, 0, 0)
ts = pd.date_range(start=start, periods=N, freq="5min")

# بسط پایه نوسانات روزانه (_SHIFT 3 شیفت ۸ ساعته)
minute_of_day = np.array(ts.hour * 60 + ts.minute, dtype=float)
shift = np.array((ts.hour // 8) % 3)  # 0,1,2

# دمای هود (Hood Temperature) - بین 350-450 °C با نوسان شیفت
hood_temp_base = 400.0 + 20.0 * np.sin(2 * np.pi * minute_of_day / 1440)
hood_temp = hood_temp_base + RNG.normal(0, 3.5, N)

# دمای سطح سیلندر یانکی (Yankee Cylinder Surface) - 90-110 °C
yankee_surface = 100.0 + 5.0 * np.sin(2 * np.pi * minute_of_day / 1440 + 0.5) + RNG.normal(0, 1.2, N)

# فشار بخار سیلندر یانکی (bar) - 4.5-6.0
steam_pressure = 5.2 + 0.3 * np.sin(2 * np.pi * minute_of_day / 1440 + 1.0) + RNG.normal(0, 0.08, N)

# دمای هوای گرم ورودی به هود (°C)
hot_air_temp = 420.0 + 15.0 * np.sin(2 * np.pi * minute_of_day / 1440 + 0.2) + RNG.normal(0, 4.0, N)

# رطوبت ورودی به خشک‌کن (Moisture In) - درصد - 60-75%
moisture_in = 68.0 + 4.0 * np.sin(2 * np.pi * minute_of_day / 1440 + 1.5) + RNG.normal(0, 1.0, N)

# رطوبت خروجی محصول (Final Moisture) - هدف 5.0% ± 0.5%
moisture_out_target = 5.0
# نوسان طبیعی + اختلال گاه‌گاهی
disturbance = np.zeros(N)
for i in range(N):
    if RNG.random() < 0.02:  # 2% احتمال اختلال
        disturbance[i] = RNG.normal(0, 1.2)
moisture_out = moisture_out_target + 0.6 * np.sin(2 * np.pi * minute_of_day / 1440 + 0.8) + \
               RNG.normal(0, 0.25, N) + disturbance

# جرم ویکی محصول (Basis Weight) g/m²
basis_weight = 15.0 + 0.3 * np.sin(2 * np.pi * minute_of_day / 1440 + 2.0) + RNG.normal(0, 0.08, N)

# سرعت ماشین (m/min)
machine_speed = 1500 + 50 * np.sin(2 * np.pi * minute_of_day / 1440 + 1.2) + RNG.normal(0, 8, N)

# مصرف بخار (t/h) - تابع پایه از رطوبت ورودی و سرعت
steam_flow = 7.2 + 0.012 * (moisture_in - 68) + 0.001 * (machine_speed - 1500) + RNG.normal(0, 0.15, N)

# مصرف گاز هود (Nm³/h) - تابع از دمای هود و سرعت
gas_flow = 320 + 0.8 * (hood_temp - 400) + 0.05 * (machine_speed - 1500) + RNG.normal(0, 6, N)

# تولید (t/h) = basis_weight(g/m²) * speed(m/min) * width(m) * 60(min/h) / 1e6 (g → t)
production = basis_weight * machine_speed * 5.4 * 60 / 1e6

# شدت انرژی حرارتی (kWh/t) = (steam*2200 + gas*9.5) / production
thermal_energy_intensity = (steam_flow * 2200 + gas_flow * 9.5) / production

# کیفیت: نرمی (Softness, 1-10) و جذب (Capillary Rise, mm)
softness = 8.0 + 0.4 * np.sin(2 * np.pi * minute_of_day / 1440 + 2.5) + RNG.normal(0, 0.15, N)
softness = np.clip(softness, 6.5, 9.5)
capillary_rise = 85.0 + 3.0 * np.sin(2 * np.pi * minute_of_day / 1440 + 3.0) + RNG.normal(0, 1.0, N)

# پرچم خارج‌از‌محدوده بودن رطوبت (3% < moisture_out < 7%)
out_of_spec = ((moisture_out < 3.0) | (moisture_out > 7.0)).astype(int)

df_sensors = pd.DataFrame({
    "timestamp": ts,
    "shift": shift,
    "hood_temp_C": np.round(hood_temp, 2),
    "yankee_surface_C": np.round(yankee_surface, 2),
    "steam_pressure_bar": np.round(steam_pressure, 3),
    "hot_air_temp_C": np.round(hot_air_temp, 2),
    "moisture_in_pct": np.round(moisture_in, 3),
    "moisture_out_pct": np.round(moisture_out, 4),
    "moisture_out_target_pct": moisture_out_target,
    "basis_weight_gm2": np.round(basis_weight, 3),
    "machine_speed_mmin": np.round(machine_speed, 1),
    "steam_flow_th": np.round(steam_flow, 3),
    "gas_flow_nm3h": np.round(gas_flow, 2),
    "production_th": np.round(production, 4),
    "thermal_energy_intensity_kWht": np.round(thermal_energy_intensity, 2),
    "softness_1_10": np.round(softness, 2),
    "capillary_rise_mm": np.round(capillary_rise, 2),
    "out_of_spec_flag": out_of_spec,
})
df_sensors.to_csv(os.path.join(OUT_DIR, "dryer_sensors_timeseries.csv"), index=False)
print(f"[1] Dryer sensor timeseries: {df_sensors.shape} -> dryer_sensors_timeseries.csv")

# ----------------------------------------------------------------------------
# 2) پروفایل پیک مصرف گاز در ساعات اوج (۲۴ ساعت، میانگین ۳۰ روز)
# ----------------------------------------------------------------------------
hours = np.arange(24)
# پیک صبح ۸-۱۱ و عصر ۱۸-۲۱
gas_profile = 280 + 80 * np.exp(-((hours - 9.5) / 2.5) ** 2) + \
              100 * np.exp(-((hours - 19.5) / 2.0) ** 2) + \
              30 * np.exp(-((hours - 14) / 3.0) ** 2) + RNG.normal(0, 6, 24)
# مصرف پس از بهینه‌سازی دوقلو
gas_profile_opt = gas_profile * 0.91 + RNG.normal(0, 4, 24)

df_peak = pd.DataFrame({
    "hour": hours,
    "gas_baseline_nm3h": np.round(gas_profile, 2),
    "gas_optimized_nm3h": np.round(gas_profile_opt, 2),
    "reduction_pct": np.round((1 - gas_profile_opt / gas_profile) * 100, 2),
})
df_peak.to_csv(os.path.join(OUT_DIR, "gas_peak_profile_24h.csv"), index=False)
print(f"[2] Gas peak profile: {df_peak.shape} -> gas_peak_profile_24h.csv")

# ----------------------------------------------------------------------------
# 3) سری زمانی گپ رطوبت از نقطه تنظیم (Bias + MSE)
# ----------------------------------------------------------------------------
gap_baseline = (moisture_out - moisture_out_target)
# شبیه‌سازی کنترل پیش‌بینانه: کاهش ۴۰٪ MSE
gap_optimized = gap_baseline * 0.6 + RNG.normal(0, 0.05, N)

df_gap = pd.DataFrame({
    "timestamp": ts,
    "moisture_gap_baseline_pct": np.round(gap_baseline, 4),
    "moisture_gap_optimized_pct": np.round(gap_optimized, 4),
})
df_gap.to_csv(os.path.join(OUT_DIR, "moisture_gap_timeseries.csv"), index=False)
print(f"[3] Moisture gap: {df_gap.shape} -> moisture_gap_timeseries.csv")

# ----------------------------------------------------------------------------
# 4) شدت انرژی حرارتی به ازای هر تن (kWh/t) - مقایسه ۱۲ ماه
# ----------------------------------------------------------------------------
months = pd.date_range("2026-01-01", periods=12, freq="MS")
month_labels = [m.strftime("%Y-%m") for m in months]
# خط پایه: نوسان فصلی ۱۱۵۰-۱۳۲۰ kWh/t
baseline_energy = 1230 + 70 * np.sin(2 * np.pi * np.arange(12) / 12 + 1) + RNG.normal(0, 12, 12)
# پس از استقرار دوقلو: کاهش ۸-۱۲٪ به سمت ۱۰٪ (الگو گرفته از پروژه FOREST)
reduction_factor = 1 - (0.08 + 0.04 * np.arange(12) / 12)  # شروع ۸٪ و رسیدن به ۱۲٪
optimized_energy = baseline_energy * reduction_factor + RNG.normal(0, 8, 12)

df_energy = pd.DataFrame({
    "month": month_labels,
    "thermal_energy_baseline_kWht": np.round(baseline_energy, 1),
    "thermal_energy_optimized_kWht": np.round(optimized_energy, 1),
    "saving_kWht": np.round(baseline_energy - optimized_energy, 1),
    "saving_pct": np.round((1 - optimized_energy / baseline_energy) * 100, 2),
})
df_energy.to_csv(os.path.join(OUT_DIR, "thermal_energy_monthly.csv"), index=False)
print(f"[4] Monthly thermal energy: {df_energy.shape} -> thermal_energy_monthly.csv")

# ----------------------------------------------------------------------------
# 5) ضایعات ناشی از خارج‌از‌محدوده‌شدن رطوبت (هفتگی)
# ----------------------------------------------------------------------------
weeks = pd.date_range("2025-12-01", periods=12, freq="W")
week_labels = [w.strftime("%Y-%W") for w in weeks]
# ضایعات پایه: 2.0-3.2٪ از تولید
waste_baseline = 2.6 + 0.5 * np.sin(2 * np.pi * np.arange(12) / 12) + RNG.normal(0, 0.15, 12)
# پس از کنترل پیش‌بینانه: کاهش ۵۰-۶۰٪
waste_optimized = waste_baseline * 0.42 + RNG.normal(0, 0.05, 12)
# تولید هفتگی (تن)
weekly_production = 5 * 24 * 7 * 0.85  # تقریبی
waste_tons_baseline = weekly_production * waste_baseline / 100
waste_tons_optimized = weekly_production * waste_optimized / 100

df_waste = pd.DataFrame({
    "week": week_labels,
    "waste_baseline_pct": np.round(waste_baseline, 3),
    "waste_optimized_pct": np.round(waste_optimized, 3),
    "weekly_production_t": round(weekly_production, 1),
    "waste_tons_baseline": np.round(waste_tons_baseline, 2),
    "waste_tons_optimized": np.round(waste_tons_optimized, 2),
    "saving_tons": np.round(waste_tons_baseline - waste_tons_optimized, 2),
})
df_waste.to_csv(os.path.join(OUT_DIR, "moisture_waste_weekly.csv"), index=False)
print(f"[5] Weekly moisture waste: {df_waste.shape} -> moisture_waste_weekly.csv")

# ----------------------------------------------------------------------------
# خلاصه آماری برای مستندات
# ----------------------------------------------------------------------------
summary = {
    "sampling_period": "2026-11-07 to 2026-11-13 (7 days, 5-min interval)",
    "total_samples": int(N),
    "machine_speed_avg_mmin": round(float(machine_speed.mean()), 1),
    "basis_weight_avg_gm2": round(float(basis_weight.mean()), 2),
    "moisture_in_avg_pct": round(float(moisture_in.mean()), 2),
    "moisture_out_avg_pct": round(float(moisture_out.mean()), 3),
    "moisture_out_std_pct": round(float(moisture_out.std()), 3),
    "thermal_energy_baseline_kWht": round(float(thermal_energy_intensity.mean()), 1),
    "out_of_spec_events": int(out_of_spec.sum()),
    "out_of_spec_rate_pct": round(float(out_of_spec.mean() * 100), 3),
    "hood_temp_avg_C": round(float(hood_temp.mean()), 1),
    "yankee_surface_avg_C": round(float(yankee_surface.mean()), 1),
    "steam_pressure_avg_bar": round(float(steam_pressure.mean()), 2),
    "gas_flow_avg_nm3h": round(float(gas_flow.mean()), 1),
    "steam_flow_avg_th": round(float(steam_flow.mean()), 2),
    "production_avg_th": round(float(production.mean()), 3),
    "softness_avg": round(float(softness.mean()), 2),
    "capillary_rise_avg_mm": round(float(capillary_rise.mean()), 1),
    "monthly_energy_saving_pct_target": 10.0,
    "weekly_waste_reduction_pct_target": 55.0,
}
import json
with open(os.path.join(OUT_DIR, "summary_stats.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print("\n[Summary]", json.dumps(summary, ensure_ascii=False, indent=2))

print("\n✓ تمام داده‌های سنتتیک با موفقیت تولید شد.")
