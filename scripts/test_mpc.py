#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست و شبیه‌سازی مدل MPC خشک‌کن خط تیشو

این اسکریپت:
  - یک سناریوی شبیه‌سازی ۲۴ گامی (۲ ساعت) اجرا می‌کند
  - در هر گام، حالت خشک‌کن را تولید، مدل را اجرا، و MPC را حل می‌کند
  - نتیجه را در یک CSV و نمودار ذخیره می‌کند
"""

import sys
import os
# مسیر پروژه و scripts را به‌صورت نسبی از محل این اسکریپت محاسبه کن (نه hard-code)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _SCRIPT_DIR)  # برای import _font_util

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
from _font_util import setup_vazirmatn
setup_vazirmatn()
import matplotlib.pyplot as plt
import arabic_reshaper
from bidi.algorithm import get_display

def fa(t):
    return get_display(arabic_reshaper.reshape(str(t)))

from app.models.dryer_model import DryerModel, DryerState
from app.models.moisture_predictor import MoisturePredictor
from app.models.mpc_controller import MPCController, MPCConstraints, MPCWeights


def make_state(t: int, peak: bool = False) -> DryerState:
    """تولید حالت شبیه‌سازی گام t."""
    rng = np.random.default_rng(t)
    # نوسان روزانه
    minute_of_day = (t * 5) % 1440
    hood_temp = 400 + 20 * np.sin(2 * np.pi * minute_of_day / 1440) + rng.normal(0, 3)
    yankee_surface = 100 + 5 * np.sin(2 * np.pi * minute_of_day / 1440 + 0.5) + rng.normal(0, 1)
    steam_pressure = 5.2 + 0.3 * np.sin(2 * np.pi * minute_of_day / 1440 + 1.0) + rng.normal(0, 0.08)
    hot_air_temp = 420 + 15 * np.sin(2 * np.pi * minute_of_day / 1440 + 0.2) + rng.normal(0, 4)
    moisture_in = 68 + 4 * np.sin(2 * np.pi * minute_of_day / 1440 + 1.5) + rng.normal(0, 1)
    basis_weight = 15 + 0.3 * np.sin(2 * np.pi * minute_of_day / 1440 + 2.0) + rng.normal(0, 0.08)
    machine_speed = 1500 + 50 * np.sin(2 * np.pi * minute_of_day / 1440 + 1.2) + rng.normal(0, 8)
    steam_flow = 7.2 + 0.012 * (moisture_in - 68) + 0.001 * (machine_speed - 1500) + rng.normal(0, 0.15)
    gas_flow = 320 + 0.8 * (hood_temp - 400) + 0.05 * (machine_speed - 1500) + rng.normal(0, 6)
    return DryerState(
        hood_temp_c=hood_temp, yankee_surface_c=yankee_surface,
        steam_pressure_bar=steam_pressure, hot_air_temp_c=hot_air_temp,
        moisture_in_pct=moisture_in, basis_weight_gm2=basis_weight,
        machine_speed_mmin=machine_speed, steam_flow_th=steam_flow,
        gas_flow_nm3h=gas_flow,
    )


def main():
    N_STEPS = 24
    model = DryerModel()
    predictor = MoisturePredictor()
    mpc = MPCController(model=model, horizon=3)

    rows = []
    history = []
    for t in range(N_STEPS):
        state = make_state(t)
        out = model.step(state)
        # تشخیص پیک گاز (ساعات ۸-۱۱ و ۱۸-۲۱)
        hour = (t * 5) // 60 % 24
        is_peak = (8 <= hour <= 11) or (18 <= hour <= 21)

        # پیش‌بینی رطوبت
        history.append({
            "moisture_in": state.moisture_in_pct,
            "moisture_out": out.moisture_out_pct,
            "hood_temp": state.hood_temp_c,
            "steam_pressure": state.steam_pressure_bar,
            "hot_air_temp": state.hot_air_temp_c,
            "basis_weight": state.basis_weight_gm2,
            "machine_speed": state.machine_speed_mmin,
            "gas_flow": state.gas_flow_nm3h,
        })
        pred = predictor.predict(history[-6:])

        # حل MPC
        sol = mpc.solve(state, is_peak_hour=is_peak, max_iters=30)

        rows.append({
            "step": t,
            "minute": t * 5,
            "hour": hour,
            "is_peak": int(is_peak),
            "moisture_in_pct": state.moisture_in_pct,
            "moisture_out_pct": out.moisture_out_pct,
            "thermal_energy_kWht": out.thermal_energy_intensity_kWht,
            "production_th": out.production_th,
            "gas_flow_nm3h": state.gas_flow_nm3h,
            "steam_flow_th": state.steam_flow_th,
            "moisture_pred_t15_pct": pred.moisture_pred_pct[2],
            "pred_confidence": pred.confidence,
            "sp_hood_temp": sol.setpoints["hood_temp"][0],
            "sp_steam_pressure": sol.setpoints["steam_pressure"][0],
            "sp_hot_air_temp": sol.setpoints["hot_air_temp"][0],
            "mpc_cost": sol.cost,
            "mpc_feasible": int(sol.feasible),
            "mpc_ms": sol.computation_time_ms,
        })
        # به‌روزرسانی پیش‌بینی‌کننده با داده واقعی
        predictor.update({"moisture_out": out.moisture_out_pct})

    df = pd.DataFrame(rows)
    out_csv = os.path.join(_REPO_ROOT, "data", "synthetic", "mpc_simulation.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"✓ Simulation: {df.shape} -> {out_csv}")
    print(df[["minute", "moisture_out_pct", "thermal_energy_kWht",
              "sp_hood_temp", "sp_steam_pressure", "mpc_ms"]].to_string(index=False))

    # نمودار خروجی شبیه‌سازی
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), constrained_layout=True)
    fig.suptitle(fa("نتایج شبیه‌سازی ۲ ساعته MPC خشک‌کن خط تیشو"), fontsize=14, fontweight="bold")

    ax = axes[0]
    ax.plot(df["minute"], df["moisture_out_pct"], "-o", color="#27ae60", ms=4,
            label=fa("رطوبت نهایی"))
    ax.axhline(5, color="#34495e", ls="-", lw=1, label=fa("هدف ۵٪"))
    ax.axhline(3, color="#c0392b", ls=":", label=fa("حد پایین ۳٪"))
    ax.axhline(7, color="#c0392b", ls=":", label=fa("حد بالا ۷٪"))
    ax.set_ylabel(fa("رطوبت (٪)"))
    ax.set_title(fa("رطوبت نهایی محصول"), fontsize=11, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    ax.plot(df["minute"], df["thermal_energy_kWht"], "-s", color="#e67e22", ms=4,
            label=fa("شدت انرژی حرارتی"))
    ax.axhline(2593, color="#95a5a6", ls="--", label=fa("خط پایه ۲۵۹۳"))
    ax.set_ylabel(fa("kWh/تن"))
    ax.set_title(fa("شدت انرژی حرارتی به ازای هر تن"), fontsize=11, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)

    ax = axes[2]
    ax.plot(df["minute"], df["sp_hood_temp"], "-o", color="#c0392b", ms=4,
            label=fa("SP دمای هود (°C)"))
    ax.plot(df["minute"], df["sp_steam_pressure"] * 60, "-s", color="#3498db", ms=4,
            label=fa("SP فشار بخار ×۶۰"))
    ax.set_ylabel(fa("set-point"))
    ax.set_xlabel(fa("دقیقه"))
    ax.set_title(fa("set-point‌های پیشنهادی MPC"), fontsize=11, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)

    out_png = os.path.join(_REPO_ROOT, "docs", "figures", "fig_mpc_simulation.png")
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    plt.savefig(out_png, dpi=150)
    plt.close()
    print(f"✓ Figure: {out_png}")

    # خلاصه
    print("\n=== خلاصه شبیه‌سازی ===")
    print(f"میانگین رطوبت خروجی: {df['moisture_out_pct'].mean():.3f}٪")
    print(f"انحراف معیار رطوبت: {df['moisture_out_pct'].std():.3f}٪")
    print(f"میانگین شدت انرژی: {df['thermal_energy_kWht'].mean():.1f} kWh/t")
    print(f"صرفه‌جویی نسبت به پایه: {(1-df['thermal_energy_kWht'].mean()/2593)*100:.2f}٪")
    print(f"میانگین زمان MPC: {df['mpc_ms'].mean():.2f} ms")
    print(f"درصد راه‌حل موجه: {df['mpc_feasible'].mean()*100:.1f}٪")


if __name__ == "__main__":
    main()
