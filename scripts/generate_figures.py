#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تولید نمودارهای معماری و تحلیلی برای پروژه دوقلوی دیجیتال لطیف
محصولات کاغذی لطیف - 2026-11-14
"""

import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
fm.fontManager.addfont('/home/z/.local/share/fonts/Vazirmatn-Regular.ttf')
fm.fontManager.addfont('/home/z/.local/share/fonts/Vazirmatn-Bold.ttf')
fm.fontManager.addfont('/home/z/.local/share/fonts/Vazirmatn-Medium.ttf')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle

import arabic_reshaper
from bidi.algorithm import get_display

plt.rcParams['font.sans-serif'] = ['Vazirmatn', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def fa(text):
    """شکل‌دهی متن فارسی برای نمایش صحیح RTL در matplotlib."""
    if text is None:
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))

def fa_lines(text):
    """شکل‌دهی متن چند خطی فارسی."""
    return "\n".join(fa(line) for line in str(text).split("\n"))

DATA = "/home/z/my-project/inno-latif-shasta/data/synthetic"
OUT = "/home/z/my-project/inno-latif-shasta/docs/figures"
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(DATA, "summary_stats.json"), encoding="utf-8") as f:
    S = json.load(f)

# ---------------------------------------------------------------------------
# 1) معماری ۵ لایه‌ای دوقلوی دیجیتال
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(14, 9), constrained_layout=True)
ax.set_xlim(0, 14); ax.set_ylim(0, 10); ax.axis("off")
ax.set_title(fa("معماری ۵ لایه‌ای دوقلوی دیجیتال خط تیشو - لطیف"),
             fontsize=16, fontweight="bold", pad=12)

layers = [
    (8.5, fa("لایه ۱: لایه فیزیکی (Physical Layer)"), "#34495e",
        [fa("ماشین تیشو (5.4m, 1500 m/min)"), fa("خشک‌کن هیبریدی: Yankee + Hood"),
         fa("سنسورها: دما/رطوبت/فشار/جریان"), fa("PLC + DCS (Profinet)")]),
    (6.7, fa("لایه ۲: لایه داده (Data Layer)"), "#2980b9",
        [fa("OPC-UA Gateway + Edge Node"), fa("Historian (PI System / TimescaleDB)"),
         fa("کش‌داده ۵ دقیقه‌ای (۲۰۱۶ نقطه/هفته)"), fa("Data Quality & Validation")]),
    (4.9, fa("لایه ۳: لایه مدل (Model Layer)"), "#8e44ad",
        [fa("مدل ترمودینامیکی خشک‌کن (Mass+Energy Balance)"),
         fa("مدل یادگیری ماشین رطوبت (LSTM/XGBoost)"),
         fa("کنترل پیش‌بینانه (MPC) با افق ۱۵ دقیقه"),
         fa("هم‌زمان‌سازی با پی‌رشته‌ای (Bayesian Update)")]),
    (3.1, fa("لایه ۴: لایه بینش (Insight Layer)"), "#c0392b",
        [fa("داشبورد زنده (Grafana/PowerBI)"), fa("هشدار انحراف از KPI"),
         fa("گزارش صرفه‌جویی انرژی (هفتگی/ماهانه)"),
         fa("تحلیل ریشه‌ای اختلالات")]),
    (1.3, fa("لایه ۵: لایه اقدام (Action Layer)"), "#16a085",
        [fa("تنظیم خودکار set-point دما و رطوبت"),
         fa("محدودسازی پیک گاز در ساعات اوج"),
         fa("توصیه به اپراتور + تأیید/رد دستی"),
         fa("نوشتن دستور به DCS (Safe Write)")]),
]
for y, title, color, items in layers:
    box = FancyBboxPatch((0.5, y), 13, 1.5, boxstyle="round,pad=0.06",
                         linewidth=1.8, edgecolor=color, facecolor=color + "22")
    ax.add_patch(box)
    ax.text(0.8, y + 1.1, title, fontsize=12, fontweight="bold", color=color)
    for i, it in enumerate(items):
        col = i % 2
        row = i // 2
        ax.text(0.9 + col * 6.4, y + 0.55 - row * 0.35, f"• {it}",
                fontsize=9.2, color="#2c3e50", va="top")

for y in [8.5, 6.7, 4.9, 3.1]:
    ax.annotate("", xy=(11.5, y), xytext=(11.5, y + 0.0),
                arrowprops=dict(arrowstyle="->", color="#27ae60", lw=2.2))
    ax.annotate("", xy=(2.5, y - 0.05), xytext=(2.5, y + 1.45),
                arrowprops=dict(arrowstyle="->", color="#e67e22", lw=2.2))
ax.text(11.5, 10.0, fa("داده (بالا)"), fontsize=10, color="#27ae60", ha="center", fontweight="bold")
ax.text(2.5, 10.0, fa("دستور (پایین)"), fontsize=10, color="#e67e22", ha="center", fontweight="bold")
ax.text(7.0, 0.3, fa("حلقه بسته کنترل پیش‌بینانه — افق ۱۵ دقیقه — نرخ به‌روزرسانی ۵ دقیقه"),
        fontsize=11, ha="center", style="italic", color="#555")
plt.savefig(os.path.join(OUT, "fig_architecture.png"), dpi=150)
plt.close()
print("✓ fig_architecture.png")

# ---------------------------------------------------------------------------
# 2) جریان داده و حلقه کنترل پیش‌بینانه
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(15, 7), constrained_layout=True)
ax.set_xlim(0, 15); ax.set_ylim(0, 7); ax.axis("off")
ax.set_title(fa("حلقه جریان داده و کنترل پیش‌بینانه (MPC) — افق ۱۵ دقیقه"),
             fontsize=14, fontweight="bold", pad=8)

nodes = {
    "machine":  (1.0, 5.5, fa_lines("ماشین تیشو\n+ سنسورها")),
    "edge":     (4.0, 5.5, fa_lines("Edge Node\n(OPC-UA)")),
    "historian":(7.0, 5.5, fa_lines("Historian\nDB")),
    "model":    (10.0,5.5, fa_lines("مدل دوقلو\n(LSTM+Thermo)")),
    "mpc":      (13.0,5.5, fa_lines("MPC\nController")),
    "dcplc":    (13.0,2.0, fa_lines("DCS/PLC")),
    "dryer":    (1.0, 2.0, fa_lines("خشک‌کن\n(Yankee+Hood)")),
}
for k, (x, y, t) in nodes.items():
    c = {"machine":"#34495e","edge":"#2980b9","historian":"#2980b9",
         "model":"#8e44ad","mpc":"#c0392b","dcplc":"#16a085","dryer":"#34495e"}[k]
    box = FancyBboxPatch((x-0.8, y-0.55), 1.6, 1.1, boxstyle="round,pad=0.06",
                         linewidth=1.6, edgecolor=c, facecolor=c+"22")
    ax.add_patch(box)
    ax.text(x, y, t, ha="center", va="center", fontsize=9.5, fontweight="bold")

def arrow(a, b, label, color, ls="-"):
    x1, y1, _ = nodes[a]; x2, y2, _ = nodes[b]
    if y2 == y1:
        sx = x1 + (0.85 if x2 > x1 else -0.85)
        ex = x2 - (0.85 if x2 > x1 else -0.85)
        sy = ey = y1
    else:
        sx, ex = x1, x2
        sy = y1 + (0.6 if y2 > y1 else -0.6)
        ey = y2 - (0.6 if y2 > y1 else -0.6)
    ax.annotate("", xy=(ex, ey), xytext=(sx, sy),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.8, linestyle=ls))
    mx, my = (x1+x2)/2, (y1+y2)/2 + 0.18
    ax.text(mx, my, label, fontsize=8.5, ha="center", color=color, fontweight="bold")

arrow("machine","edge",fa_lines("داده زنده\n(5 min)"), "#27ae60")
arrow("edge","historian","ETL", "#27ae60")
arrow("historian","model",fa_lines("آموزش\n+ هم‌زمان‌سازی"), "#27ae60")
arrow("model","mpc",fa_lines("پیش‌بینی\nرطوبت/انرژی"), "#8e44ad")
arrow("mpc","dcplc",fa_lines("set-point\nبهینه"), "#c0392b")
arrow("dcplc","dryer",fa_lines("دستور\nکنترلی"), "#e67e22")
arrow("dryer","machine",fa("تبدیل فیزیکی"), "#34495e", ls="--")
arrow("machine","dryer",fa("جریان وب"), "#7f8c8d", ls=":")

ax.text(7.5, 0.7,
        fa("هدف: حداقل‌سازی (w1·انرژی_حرارتی + w2·پیک_گاز + w3·ضایعات + w4·جرم_کیفیت)  با  قیود ایمنی و کیفی"),
        ha="center", fontsize=10, style="italic", color="#555",
        bbox=dict(boxstyle="round,pad=0.4", fc="#f8f9fa", ec="#ccc"))
plt.savefig(os.path.join(OUT, "fig_dataflow.png"), dpi=150)
plt.close()
print("✓ fig_dataflow.png")

# ---------------------------------------------------------------------------
# 3) شماتیک خشک‌کن هیبریدی
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(13, 6.5), constrained_layout=True)
ax.set_xlim(0, 13); ax.set_ylim(0, 6.5); ax.axis("off")
ax.set_title(fa("خشک‌کن هیبریدی خط تیشو — سیلندر یانکی + هود هوای گرم"),
             fontsize=14, fontweight="bold")

# سیلندر یانکی (دایره بزرگ)
yankee = Circle((5.0, 3.0), 2.0, fill=False, lw=2.5, ec="#34495e")
ax.add_patch(yankee)
ax.text(5.0, 3.0, fa_lines("سیلندر یانکی\nقطر 5.5 m\nسطح 90-110°C\nبخار 4.5-6 bar"),
        ha="center", va="center", fontsize=9.5, fontweight="bold")

# ورودی وب (رطوبت بالا)
ax.annotate("", xy=(2.0, 3.0), xytext=(0.4, 3.0),
            arrowprops=dict(arrowstyle="->", color="#3498db", lw=2.5))
ax.text(0.4, 3.4, fa_lines("وب ورودی\nرطوبت 60-75%\nگرماژ 15 g/m²"), fontsize=8.5, ha="left", color="#3498db")

# مسیر وب روی یانکی
theta = np.linspace(180, 0, 50)
ax.plot(5.0 + 2.0*np.cos(np.radians(theta)), 3.0 + 2.0*np.sin(np.radians(theta)),
        color="#e67e22", lw=3, ls="--")

# خروجی وب (رطوبت پایین)
ax.annotate("", xy=(12.6, 3.6), xytext=(7.0, 3.6),
            arrowprops=dict(arrowstyle="->", color="#27ae60", lw=2.5))
ax.text(12.6, 4.0, fa_lines("وب خروجی\nرطوبت 5% ± 0.5%"), fontsize=8.5, ha="right", color="#27ae60")

# هود هوای گرم (طاق بالای یانکی)
hood = FancyBboxPatch((2.5, 5.0), 5.0, 1.2, boxstyle="round,pad=0.1",
                     lw=2.2, ec="#c0392b", facecolor="#c0392b22")
ax.add_patch(hood)
ax.text(5.0, 5.6, fa_lines("هود هیبریدی — هوای گرم + بازتاب تابشی\nدمای هود 350-450°C"),
        ha="center", va="center", fontsize=10, fontweight="bold", color="#c0392b")

# ورودی بخار
ax.annotate("", xy=(3.5, 1.2), xytext=(3.5, 0.3),
            arrowprops=dict(arrowstyle="->", color="#7f8c8d", lw=2.0))
ax.text(3.5, 0.1, fa_lines("بخار\n5.2 bar"), ha="center", fontsize=9, color="#7f8c8d")
# خروجی کندانس
ax.annotate("", xy=(6.5, 0.3), xytext=(6.5, 1.2),
            arrowprops=dict(arrowstyle="->", color="#7f8c8d", lw=2.0))
ax.text(6.5, 0.1, fa("کندانس"), ha="center", fontsize=9, color="#7f8c8d")

# مشاور گاز به هود
ax.annotate("", xy=(4.0, 5.0), xytext=(1.0, 5.6),
            arrowprops=dict(arrowstyle="->", color="#e67e22", lw=2.0))
ax.text(0.8, 6.0, fa_lines("گاز\n320 Nm³/h"), fontsize=9, color="#e67e22")
# خروجی هوای خنک
ax.annotate("", xy=(12.4, 5.6), xytext=(7.5, 5.6),
            arrowprops=dict(arrowstyle="->", color="#e74c3c", lw=2.0))
ax.text(12.5, 5.6, fa_lines("هوای\nخروجی"), fontsize=9, color="#e74c3c", ha="right")

# سنسورها (نقاط قرمز)
sensors = [(7.3, 3.8, fa("رطوبت نهایی")),
           (1.2, 2.4, fa("رطوبت ورودی")),
           (5.0, 5.0, fa("دمای هود")),
           (3.0, 3.0, fa("T سطح")),
           (3.5, 0.6, fa("فشار بخار"))]
for x, y, lbl in sensors:
    ax.plot(x, y, "o", color="#c0392b", ms=10, zorder=5)
    ax.text(x + 0.15, y + 0.25, lbl, fontsize=8.5, color="#c0392b")

ax.text(6.5, 0.0, fa("نقطه تنظیم دما و رطوبت توسط MPC تصحیح می‌شود تا کمترین بخار/گاز با حفظ کیفیت نرمی و جذب"),
        ha="center", fontsize=9.5, style="italic", color="#555")
plt.savefig(os.path.join(OUT, "fig_dryer.png"), dpi=150)
plt.close()
print("✓ fig_dryer.png")

# ---------------------------------------------------------------------------
# 4) شدت انرژی پایه vs بهینه‌شده (۱۲ ماه)
# ---------------------------------------------------------------------------
df_e = pd.read_csv(os.path.join(DATA, "thermal_energy_monthly.csv"))
fig, ax = plt.subplots(figsize=(12, 6.5), constrained_layout=True)
x = np.arange(len(df_e))
w = 0.38
ax.bar(x - w/2, df_e["thermal_energy_baseline_kWht"], w,
       label=fa("خط پایه (بدون دوقلو)"), color="#95a5a6", edgecolor="#7f8c8d")
ax.bar(x + w/2, df_e["thermal_energy_optimized_kWht"], w,
       label=fa("با دوقلوی دیجیتال"), color="#27ae60", edgecolor="#1e8449")
for i in range(len(df_e)):
    ax.text(x[i] - w/2, df_e["thermal_energy_baseline_kWht"][i] + 10,
            f"{df_e['thermal_energy_baseline_kWht'][i]:.0f}", ha="center", fontsize=8, color="#555")
    ax.text(x[i] + w/2, df_e["thermal_energy_optimized_kWht"][i] + 10,
            f"{df_e['thermal_energy_optimized_kWht'][i]:.0f}", ha="center", fontsize=8, color="#1e8449")
    ax.text(x[i], max(df_e["thermal_energy_baseline_kWht"][i], df_e["thermal_energy_optimized_kWht"][i]) + 90,
            f"-{df_e['saving_pct'][i]:.1f}%", ha="center", fontsize=9, color="#c0392b", fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(df_e["month"], rotation=30, ha="right")
ax.set_ylabel(fa("شدت انرژی حرارتی (kWh/تن)"))
ax.set_title(fa("شدت انرژی حرارتی به ازای هر تن محصول — پایه vs بهینه‌شده (هدف ۱۰٪ الگو FOREST)"),
             fontsize=13, fontweight="bold")
ax.legend(loc="upper right")
ax.grid(True, axis="y", alpha=0.3)
ax.set_ylim(0, df_e["thermal_energy_baseline_kWht"].max() * 1.18)
plt.savefig(os.path.join(OUT, "fig_energy_saving.png"), dpi=150)
plt.close()
print("✓ fig_energy_saving.png")

# ---------------------------------------------------------------------------
# 5) پروفایل پیک مصرف گاز ۲۴ ساعته
# ---------------------------------------------------------------------------
df_p = pd.read_csv(os.path.join(DATA, "gas_peak_profile_24h.csv"))
fig, ax = plt.subplots(figsize=(12, 5.5), constrained_layout=True)
ax.fill_between(df_p["hour"], 0, df_p["gas_baseline_nm3h"],
                color="#e67e22", alpha=0.25, label=fa("ناحیه پیک پایه"))
ax.plot(df_p["hour"], df_p["gas_baseline_nm3h"], "-o", color="#e67e22",
        ms=5, label=fa("مصرف گاز پایه (Nm³/h)"))
ax.plot(df_p["hour"], df_p["gas_optimized_nm3h"], "-s", color="#27ae60",
        ms=5, label=fa("مصرف گاز با دوقلو (Nm³/h)"))
# سایه‌زنی پیک‌ها
ax.axvspan(8, 11, color="#c0392b", alpha=0.08)
ax.axvspan(18, 21, color="#c0392b", alpha=0.08)
ymax = df_p["gas_baseline_nm3h"].max()
ax.text(9.5, ymax*0.92, fa("پیک صبح"), ha="center", color="#c0392b", fontweight="bold")
ax.text(19.5, ymax*0.92, fa("پیک عصر"), ha="center", color="#c0392b", fontweight="bold")
ax.set_xlabel(fa("ساعت روز")); ax.set_ylabel(fa("مصرف گاز (Nm³/h)"))
ax.set_title(fa("پروفایل ۲۴ ساعته مصرف گاز — هدف: کاهش پیک در ساعات اوج"),
             fontsize=13, fontweight="bold")
ax.set_xticks(range(0, 24, 2))
ax.legend(loc="upper left"); ax.grid(True, alpha=0.3)
plt.savefig(os.path.join(OUT, "fig_gas_peak.png"), dpi=150)
plt.close()
print("✓ fig_gas_peak.png")

# ---------------------------------------------------------------------------
# 6) سری زمانی گپ رطوبت
# ---------------------------------------------------------------------------
df_g = pd.read_csv(os.path.join(DATA, "moisture_gap_timeseries.csv"))
df_g["timestamp"] = pd.to_datetime(df_g["timestamp"])
fig, ax = plt.subplots(figsize=(13, 5), constrained_layout=True)
ax.plot(df_g["timestamp"], df_g["moisture_gap_baseline_pct"], color="#7f8c8d",
        lw=0.8, alpha=0.7, label=fa(f"گپ پایه (std={df_g['moisture_gap_baseline_pct'].std():.3f})"))
ax.plot(df_g["timestamp"], df_g["moisture_gap_optimized_pct"], color="#27ae60",
        lw=0.8, alpha=0.85, label=fa(f"گپ با MPC (std={df_g['moisture_gap_optimized_pct'].std():.3f})"))
ax.axhline(0, color="#34495e", lw=1, ls="-")
ax.axhline(0.5, color="#c0392b", lw=1, ls=":", label=fa("حد مطلوب ±0.5%"))
ax.axhline(-0.5, color="#c0392b", lw=1, ls=":")
ax.set_ylabel(fa("گپ رطوبت از نقطه تنظیم (%)"))
ax.set_title(fa("سری زمانی گپ رطوبت محصول — کاهش پراکندگی توسط کنترل پیش‌بینانه"),
             fontsize=13, fontweight="bold")
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)
plt.savefig(os.path.join(OUT, "fig_moisture_gap.png"), dpi=150)
plt.close()
print("✓ fig_moisture_gap.png")

# ---------------------------------------------------------------------------
# 7) ضایعات هفتگی
# ---------------------------------------------------------------------------
df_w = pd.read_csv(os.path.join(DATA, "moisture_waste_weekly.csv"))
fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
x = np.arange(len(df_w)); w = 0.38
ax.bar(x - w/2, df_w["waste_tons_baseline"], w, label=fa("ضایعات پایه (تن/هفته)"), color="#95a5a6")
ax.bar(x + w/2, df_w["waste_tons_optimized"], w, label=fa("ضایعات با دوقلو (تن/هفته)"), color="#27ae60")
for i in range(len(df_w)):
    ax.text(x[i], df_w["waste_tons_baseline"][i] + 0.4,
            f"-{((1-df_w['waste_optimized_pct'][i]/df_w['waste_baseline_pct'][i])*100):.0f}%",
            ha="center", fontsize=8.5, color="#c0392b", fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(df_w["week"], rotation=30, ha="right")
ax.set_ylabel(fa("ضایعات ناشی از رطوبت (تن/هفته)"))
ax.set_title(fa("ضایعات ناشی از خارج‌از‌محدوده‌شدن رطوبت — کاهش هدف ≥۵۵٪"),
             fontsize=13, fontweight="bold")
ax.legend(loc="upper right"); ax.grid(True, axis="y", alpha=0.3)
plt.savefig(os.path.join(OUT, "fig_waste.png"), dpi=150)
plt.close()
print("✓ fig_waste.png")

# ---------------------------------------------------------------------------
# 8) داشبورد KPI های هدف
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), constrained_layout=True)
fig.suptitle(fa("داشبورد شاخص‌های هدف دوقلوی دیجیتال — لطیف"), fontsize=14, fontweight="bold")

# KPI 1: شدت انرژی
base_e = S["thermal_energy_baseline_kWht"]; opt_e = base_e * 0.90
ax = axes[0]
ax.bar([fa("پایه"), fa("هدف")], [base_e, opt_e], color=["#95a5a6", "#27ae60"])
for i, v in enumerate([base_e, opt_e]):
    ax.text(i, v + 30, f"{v:.0f}\nkWh/t", ha="center", fontsize=10, fontweight="bold")
ax.set_title(fa("شدت انرژی حرارتی"), fontsize=11, fontweight="bold")
ax.set_ylabel(fa("kWh/تن"))
ax.text(0.5, 0.15, fa("هدف کاهش ۱۰٪\n(الگوی FOREST)"), transform=ax.transAxes,
        ha="center", fontsize=9, color="#c0392b", fontweight="bold")
ax.set_ylim(0, base_e*1.25)

# KPI 2: پیک گاز
ax = axes[1]
peak_base = df_p["gas_baseline_nm3h"].max(); peak_opt = df_p["gas_optimized_nm3h"].max()
ax.bar([fa("پایه"), fa("هدف")], [peak_base, peak_opt], color=["#95a5a6", "#27ae60"])
for i, v in enumerate([peak_base, peak_opt]):
    ax.text(i, v + 6, f"{v:.0f}\nNm³/h", ha="center", fontsize=10, fontweight="bold")
ax.set_title(fa("پیک مصرف گاز در اوج"), fontsize=11, fontweight="bold")
ax.set_ylabel(fa("Nm³/h"))
ax.text(0.5, 0.15, fa(f"هدف کاهش پیک\n{(1-peak_opt/peak_base)*100:.0f}%"), transform=ax.transAxes,
        ha="center", fontsize=9, color="#c0392b", fontweight="bold")
ax.set_ylim(0, peak_base*1.25)

# KPI 3: ضایعات رطوبت
ax = axes[2]
waste_base = df_w["waste_baseline_pct"].mean(); waste_opt = df_w["waste_optimized_pct"].mean()
ax.bar([fa("پایه"), fa("هدف")], [waste_base, waste_opt], color=["#95a5a6", "#27ae60"])
for i, v in enumerate([waste_base, waste_opt]):
    ax.text(i, v + 0.05, f"{v:.2f}\n%", ha="center", fontsize=10, fontweight="bold")
ax.set_title(fa("نرخ ضایعات رطوبت"), fontsize=11, fontweight="bold")
ax.set_ylabel(fa("٪ از تولید"))
ax.text(0.5, 0.15, fa(f"هدف کاهش ≥۵۵٪\n({(1-waste_opt/waste_base)*100:.0f}%)"), transform=ax.transAxes,
        ha="center", fontsize=9, color="#c0392b", fontweight="bold")
ax.set_ylim(0, waste_base*1.25)
plt.savefig(os.path.join(OUT, "fig_kpi_dashboard.png"), dpi=150)
plt.close()
print("✓ fig_kpi_dashboard.png")

print("\n✓ همه نمودارها در docs/figures/ ذخیره شدند.")
