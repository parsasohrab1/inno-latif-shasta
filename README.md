# دوقلوی دیجیتال خط تیشو با کنترل پیش‌بینانه خشک‌کن — لطیف

<div dir="rtl">

مخزن مستندات پروژه **دوقلوی دیجیتال خط تیشو با کنترل پیش‌بینانه خشک‌کن** برای **محصولات کاغذی لطیف** (تولید کاغذ بهداشتی/تیشو).

این پروژه با الهام از نمونه آلمانی **FOREST**، یک دوقلوی دیجیتال از ماشین تیشو می‌سازد که جریان انرژی، جرم و CO₂ را شبیه‌سازی می‌کند و با کنترل پیش‌بینانه مدل‌محور (MPC)، نقطه تنظیم دما و رطوبت را به‌صورت خودکار بهینه می‌کند تا ضمن حفظ کیفیت نرمی و جذب، کمترین بخار و گاز مصرف شود.

> ✅ **الگوی موفقیت FOREST:** صرفه‌جویی تا ۱۰٪ در هزینه‌های انرژی روی یک ماشین تیشوی آلمانی.

</div>

---

## 📑 فهرست

- [معرفی پروژه](#-معرفی-پروژه)
- [ساختار مخزن](#-ساختار-مخزن)
- [مستندات اصلی](#-مستندات-اصلی)
- [داده‌های سنتتیک](#-دادههای-سنتتیک)
- [نمودارها](#-نمودارها)
- [شاخص‌های هدف (KPI)](#-شاخصهای-هدف-kpi)
- [نرم‌افزار دوقلوی دیجیتال](#-نرمافزار-دوقلوی-دیجیتال)
- [نحوه اجرای اسکریپت‌ها و سرور](#-نحوه-اجرای-اسکریپتها-و-سرور)
- [استقرار با Docker](#-استقرار-با-docker)
- [تست‌ها و CI](#-تستها-و-ci)
- [امنیت و مانیتورینگ](#-امنیت-و-مانیتورینگ)
- [معماری سیستم](#-معماری-سیستم)
- [توسعه و مشارکت](#-توسعه-و-مشارکت)

---

## 📖 معرفی پروژه

<div dir="rtl">

محصولات کاغذی لطیف یک تولیدکننده کاغذ بهداشتی و تیشو در ایران است. خط تولید اصلی شامل یک ماشین تیشو با مشخصات زیر است:

| پارامتر | مقدار |
|---|---|
| عرض وب | ۵.۴ m |
| سرعت ماشین | ۱۵۰۰ m/min |
| گرماژ اسمی | ۱۵ g/m² |
| رطوبت هدف خروجی | ۵.۰٪ ± ۰.۵٪ |
| تولید متوسط | حدود ۷.۳ t/h |

**چالش فعلی:** کنترل خشک‌کن به‌صورت واکنشی و توسط اپراتور انجام می‌شود که باعث بیش‌مصرفی انرژی، پیک مصرف گاز و ضایعات ناشی از رطوبت خارج از محدوده می‌شود.

**راه‌حل:** ساخت دوقلوی دیجیتال با ۵ لایه (فیزیکی، داده، مدل، بینش، اقدام) و استقرار کنترل پیش‌بینانه MPC با افق ۱۵ دقیقه و نرخ به‌روزرسانی ۵ دقیقه‌ای.

</div>

---

## 🗂️ ساختار مخزن

```
inno-latif-shasta/
├── README.md                    # این فایل
├── CONTRIBUTING.md              # راهنمای مشارکت
├── requirements.txt              # وابستگی‌های Python
├── pytest.ini                    # تنظیمات pytest
├── Dockerfile                    # image تکی (multi-stage)
├── docker-compose.yml            # stack کامل: API + Prometheus + Grafana + TimescaleDB
├── .dockerignore
├── .github/
│   └── workflows/
│       └── ci.yml                # CI: lint + test + Docker build + scripts test
├── docs/                         # مستندات
│   ├── BRS.md                    # سند نیازمندی‌های کسب‌وکار (جامع)
│   ├── SRS.md                    # سند نیازمندی‌های نرم‌افزار (IEEE 830)
│   └── figures/                  # نمودارها (PNG)
│       ├── fig_architecture.png
│       ├── fig_dataflow.png
│       ├── fig_dryer.png
│       ├── fig_energy_saving.png
│       ├── fig_gas_peak.png
│       ├── fig_moisture_gap.png
│       ├── fig_waste.png
│       ├── fig_kpi_dashboard.png
│       └── fig_mpc_simulation.png
├── app/                          # نرم‌افزار دوقلوی دیجیتال (FastAPI)
│   ├── __init__.py
│   ├── main.py                   # نقطه ورود FastAPI + middleware متریک
│   ├── .env.example              # نمونه‌ی تنظیمات محیطی
│   ├── api/
│   │   └── routes.py             # مسیرهای REST + WebSocket + /metrics
│   ├── core/
│   │   ├── config.py             # تنظیمات (Pydantic Settings)
│   │   ├── historian.py           # پایگاه داده سری‌زمانی (memory/sqlite)
│   │   ├── security.py           # احراز هویت API Key
│   │   └── logging_setup.py      # logging ساختاریافته (JSON)
│   ├── models/                   # مدل‌های دوقلوی دیجیتال
│   │   ├── dryer_model.py        # مدل ترمودینامیکی خشک‌کن
│   │   ├── moisture_predictor.py # پیش‌بینی‌کننده رطوبت (numpy)
│   │   ├── moisture_predictor_v2.py # پیش‌بینی‌کننده LSTM (با fallback numpy)
│   │   └── mpc_controller.py     # کنترل‌کننده پیش‌بینانه MPC
│   ├── services/
│   │   ├── opcua_sim.py          # شبیه‌ساز OPC-UA (تولید داده سنسور)
│   │   ├── opcua_client.py       # کلاینت OPC-UA واقعی (asyncua + fallback)
│   │   └── mpc_service.py        # سرویس MPC + Audit Log
│   ├── monitoring/
│   │   └── metrics.py            # متریک‌های Prometheus
│   └── static/
│       └── index.html            # داشبورد HTML/JS (Chart.js)
├── monitoring/
│   └── prometheus.yml             # پیکربندی Prometheus scrape
├── tests/                        # تست‌های pytest (۵۶ تست)
│   ├── conftest.py
│   ├── test_dryer_model.py       # مدل ترمودینامیکی
│   ├── test_mpc_controller.py    # MPC
│   ├── test_moisture_predictor.py # پیش‌بینی‌کننده
│   ├── test_historian_config.py  # پایگاه داده + تنظیمات
│   └── test_api.py               # API + امنیت + KPI + audit
├── data/
│   ├── synthetic/                # داده‌های سنتتیک تولیدشده
│   │   ├── dryer_sensors_timeseries.csv
│   │   ├── gas_peak_profile_24h.csv
│   │   ├── moisture_gap_timeseries.csv
│   │   ├── thermal_energy_monthly.csv
│   │   ├── moisture_waste_weekly.csv
│   │   ├── mpc_simulation.csv
│   │   └── summary_stats.json
│   └── models/                    # وزن‌های LSTM (در فاز Pilot)
└── scripts/                      # اسکریپت‌های تولید داده/نمودار و تست
    ├── generate_synthetic_data.py
    ├── generate_figures.py
    ├── test_mpc.py               # شبیه‌سازی MPC
    ├── test_e2e.py               # تست end-to-end سرور
    └── run_tests.sh              # اجرای pytest
```

---

## 📚 مستندات اصلی

<div dir="rtl">

دو سند اصلی این مخزن:

| سند | شرح | الگو | شناسه |
|---|---|---|---|
| [`docs/BRS.md`](docs/BRS.md) | سند نیازمندی‌های کسب‌وکار (Business Requirements Specification) — شامل زمینه کسب‌وکار، اهداف، ذی‌نفعان، مورد تجاری، شاخص‌های هدف، فازبندی و ریسک‌ها | BRS جامع (Volere-inspired + Business Case) | LATIF-BRS-2026-001 |
| [`docs/SRS.md`](docs/SRS.md) | سند نیازمندی‌های نرم‌افزار (Software Requirements Specification) — شامل ۲۵ نیازمندی عملکردی تست‌پذیر، رابط‌ها، عملکرد، محدودیت‌های طراحی، ویژگی‌های نرم‌افزاری و ماتریس ردیابی | IEEE Std 830-1998 | LATIF-SRS-2026-001 |

</div>

---

## 📊 داده‌های سنتتیک

<div dir="rtl">

به‌دلیل عدم دسترسی به داده واقعی ماشین در فاز طراحی، مجموعه داده سنتتیک با اسکریپت [`scripts/generate_synthetic_data.py`](scripts/generate_synthetic_data.py) تولید شده است. این داده‌ها بر اساس مدل‌های فیزیکی (نوسان روزانه، شیفت‌بندی ۸ ساعته، نویز سنسور، اختلال گاه‌گاهی) ساخته شده‌اند.

| فایل | شرح | حجم |
|---|---|---|
| `dryer_sensors_timeseries.csv` | سری زمانی ۵ دقیقه‌ای ۱۸ سنسور خشک‌کن در ۷ روز | ۲۰۱۶ نقطه |
| `gas_peak_profile_24h.csv` | پروفایل ۲۴ ساعته مصرف گاز پایه و بهینه‌شده | ۲۴ نقطه |
| `moisture_gap_timeseries.csv` | سری زمانی گپ رطوبت از نقطه تنظیم (پایه و MPC) | ۲۰۱۶ نقطه |
| `thermal_energy_monthly.csv` | شدت انرژی ماهانه (پایه/بهینه/صرفه‌جویی) | ۱۲ نقطه |
| `moisture_waste_weekly.csv` | ضایعات هفتگی ناشی از رطوبت (پایه/بهینه) | ۱۲ نقطه |
| `mpc_simulation.csv` | خروجی شبیه‌سازی ۲ ساعته MPC (۲۴ گام) | ۲۴ نقطه |
| `summary_stats.json` | خلاصه آماری کل مجموعه‌ها | — |

### خلاصه آماری خط پایه

| شاخص | مقدار |
|---|---|
| دوره نمونه‌برداری | ۲۰۲۶-۱۱-۰۷ تا ۲۰۲۶-۱۱-۱۳ |
| تعداد نمونه | ۲۰۱۶ |
| سرعت ماشین میانگین | ۱۵۰۰.۶ m/min |
| گرماژ میانگین | ۱۵.۰ g/m² |
| رطوبت ورودی میانگین | ۶۸.۰٪ |
| رطوبت خروجی میانگین | ۵.۰٪ (σ=۰.۵۱٪) |
| شدت انرژی حرارتی پایه | ۲۵۹۳ kWh/t |
| تعداد رویداد خارج از محدوده | ۶ (نرخ ۰.۳۰٪) |
| دمای هود میانگین | ۴۰۰°C |
| دبی گاز میانگین | ۳۲۰ Nm³/h |
| دبی بخار میانگین | ۷.۲ t/h |
| تولید میانگین | ۷.۳ t/h |

</div>

---

## 📈 نمودارها

<div dir="rtl">

همه نمودارها با اسکریپت [`scripts/generate_figures.py`](scripts/generate_figures.py) تولید شده‌اند. فونت فارسی Vazirmatn به‌همراه arabic-reshaper و python-bidi برای شکل‌دهی صحیح متن RTL استفاده شده است.

| فایل | شرح |
|---|---|
| [`fig_architecture.png`](docs/figures/fig_architecture.png) | معماری ۵ لایه‌ای دوقلوی دیجیتال |
| [`fig_dataflow.png`](docs/figures/fig_dataflow.png) | حلقه جریان داده و کنترل پیش‌بینانه |
| [`fig_dryer.png`](docs/figures/fig_dryer.png) | شماتیک خشک‌کن هیبریدی (یانکی + هود) |
| [`fig_energy_saving.png`](docs/figures/fig_energy_saving.png) | شدت انرژی پایه vs بهینه‌شده (۱۲ ماه) |
| [`fig_gas_peak.png`](docs/figures/fig_gas_peak.png) | پروفایل ۲۴ ساعته مصرف گاز |
| [`fig_moisture_gap.png`](docs/figures/fig_moisture_gap.png) | سری زمانی گپ رطوبت |
| [`fig_waste.png`](docs/figures/fig_waste.png) | ضایعات هفتگی پایه vs بهینه‌شده |
| [`fig_kpi_dashboard.png`](docs/figures/fig_kpi_dashboard.png) | داشبورد KPI های هدف |
| [`fig_mpc_simulation.png`](docs/figures/fig_mpc_simulation.png) | نتایج شبیه‌سازی ۲ ساعته MPC (خروجی `test_mpc.py`) |

</div>

---

## 🎯 شاخص‌های هدف (KPI)

<div dir="rtl">

سه شاخص اصلی پروژه (بر اساس عنوان پروژه و BRS):

| # | شاخص | خط پایه | هدف | افق |
|---|---|---|---|---|
| ۱ | شدت انرژی حرارتی (kWh/t) | ۲۵۹۳ | ≤۲۳۳۷ (کاهش ≥۱۰٪) | ۱۲ ماه |
| ۲ | پیک مصرف گاز در اوج (Nm³/h) | ۴۶۰ | ≤۴۲۰ (کاهش ≥۹٪) | ۹ ماه |
| ۳ | نرخ ضایعات رطوبت (٪ تولید) | ۲.۶٪ | ≤۱.۲٪ (کاهش ≥۵۵٪) | ۱۲ ماه |

شاخص‌های مکمل: حفظ نرمی ≥۷.۵، مویینگی ≥۸۰ mm، انحراف معیار رطوبت ≤۰.۳٪، نرخ Auto Mode ≥۸۰٪.

</div>

---

## 🖥️ نرم‌افزار دوقلوی دیجیتال

<div dir="rtl">

نرم‌افزار اجرایی در فولدر `app/` پیاده‌سازی شده و شامل سه مؤلفه اصلی است:

### ۱. مدل‌ها (`app/models/`)

- **`dryer_model.py`** — مدل ترمودینامیکی خشک‌کن هیبریدی بر اساس تراز جرم و انرژی. جریان انرژی، رطوبت خروجی، شدت انرژی حرارتی و CO₂ را محاسبه می‌کند. قابلیت پیش‌بینی در افق چند گام ۵ دقیقه‌ای دارد.
- **`moisture_predictor.py`** — پیش‌بینی‌کننده رطوبت نهایی با مدل شبکه‌ی عصبی ساده (پیاده‌سازی numpy، بدون وابستگی به PyTorch/TensorFlow). ورودی: ۶ گام گذشته ۸ ویژگی. خروجی: پیش‌بینی در t+5، t+10، t+15. پشتیبانی از آموزش تدریجی (online learning).
- **`mpc_controller.py`** — کنترل‌کننده پیش‌بینانه MPC با حل‌کننده‌ی داخلی مبتنی بر جستجوی محلی + شبیه‌سازی annealing (بدون وابستگی به CasADi). تابع هدف چندمتغیره با قیود ایمنی و کیفی. میانگین زمان حل در تست: **۲.۱۶ ms** (حد SRS: ۱۰ ثانیه).

### ۲. سرور FastAPI (`app/api/`, `app/core/`, `app/services/`)

| مسیر | متد | شرح |
|---|---|---|
| `/api/health` | GET | سلامت سرور |
| `/api/status` | GET | وضعیت شبیه‌ساز + historian |
| `/api/sensors/latest` | GET | آخرین نمونه سنسور |
| `/api/sensors/history` | GET | تاریخچه (پارامتر `n`) |
| `/api/kpi` | GET | KPI های زنده (شدت انرژی، پیک گاز، ضایعات) |
| `/api/mpc/solve` | POST | حل MPC با آخرین داده |
| `/api/mpc/apply` | POST | اعمال/رد set-point پیشنهادی |
| `/api/mpc/mode` | POST | تغییر مد (advisory/auto/manual) |
| `/api/mpc/solution` | GET | آخرین راه‌حل MPC |
| `/api/audit` | GET | audit log |
| `/api/ws/sensors` | WS | stream زنده سنسورها |
| `/api/ws/mpc` | WS | stream زنده راه‌حل‌های MPC |

- **شبیه‌ساز OPC-UA** (`opcua_sim.py`): داده سنسور را با مدل فیزیکی همانند اسکریپت `generate_synthetic_data.py` تولید و در historian ذخیره می‌کند (در فاز Pilot با OPC-UA واقعی DCS جایگزین می‌شود).
- **Historian** (`historian.py`): پایگاه داده سری‌زمانی با دو backend: memory (آزمایشی) و sqlite (پایدار). در فاز Pilot با TimescaleDB جایگزین می‌شود.
- **MPC Service** (`mpc_service.py`): لایه‌ی سرویس با Audit Log، مدیریت مد (advisory/auto/manual)، fallback ایمنی.

### ۳. داشبورد (`app/static/index.html`)

داشبورد HTML/JS تک‌صفحه‌ای با:
- ۴ کارت KPI زنده (شدت انرژی، پیک گاز، ضایعات رطوبت، میانگین رطوبت)
- نمودار سری زمانی ۶۰ نمونه اخیر (رطوبت، دمای هود، دبی گاز)
- جدول حالت خشک‌کن با ۱۵ پارامتر زنده
- پنل کنترل MPC با سه مد (Advisory/Auto/Manual)، set-point پیشنهادی و دکمه‌های تأیید/رد
- نمودار پیش‌بینی رطوبت در افق ۱۵ دقیقه با باندهای حد
- نمودار پیش‌بینی MPC (شدت انرژی و تولید در ۳ گام)
- Audit Log زنده
- فونت Vazirmatn و راست‌چین کامل

</div>

---

## 🚀 نحوه اجرای اسکریپت‌ها

### پیش‌نیازها

```bash
pip install numpy pandas matplotlib arabic-reshaper python-bidi
```

### ۱) تولید داده سنتتیک

```bash
python scripts/generate_synthetic_data.py
```

خروجی: فایل‌های CSV و `summary_stats.json` در `data/synthetic/`.

### ۲) تولید نمودارها

```bash
python scripts/generate_figures.py
```

خروجی: ۸ فایل PNG در `docs/figures/`.

> **نکته:** برای رندر صحیح متن فارسی، فونت Vazirmatn باید نصب باشد. فایل‌های فونت به‌صورت خودکار از `~/.local/share/fonts/Vazirmatn-Regular.ttf` خوانده می‌شوند. برای نصب:
>
> ```bash
> curl -sL -o /tmp/vazirmatn.zip "https://github.com/rastikerdar/vazirmatn/releases/download/v33.003/Vazirmatn-v33.003.zip"
> unzip -q /tmp/vazirmatn.zip -d /tmp/vazirmatn_extract
> cp /tmp/vazirmatn_extract/fonts/ttf/Vazirmatn-*.ttf ~/.local/share/fonts/
> fc-cache -f ~/.local/share/fonts/
> ```

### ۳) نصب وابستگی‌ها و اجرای سرور

```bash
# نصب وابستگی‌ها
pip install -r requirements.txt

# اجرای سرور FastAPI (با شبیه‌ساز OPC-UA فعال)
cd /home/z/my-project/inno-latif-shasta
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

پس از بالا آمدن سرور:
- داشبورد: http://localhost:8000/ یا http://localhost:8000/dashboard
- مستندات API (Swagger): http://localhost:8000/docs
- مستندات ReDoc: http://localhost:8000/redoc
- نمونه API: http://localhost:8000/api/kpi

### ۴) تست‌ها

```bash
# تست و شبیه‌سازی مدل MPC (۲۴ گام = ۲ ساعت)
python scripts/test_mpc.py
# خروجی: data/synthetic/mpc_simulation.csv و docs/figures/fig_mpc_simulation.png

# تست end-to-end سرور (۱۰ مورد، شامل: health, status, sensors, MPC, KPI, audit, dashboard)
python scripts/test_e2e.py
# خروجی: ✅ همه تست‌ها موفق بودند (۱۰/۱۰)
```

### ۵) متغیرهای محیط قابل تنظیم

| متغیر | پیش‌فرض | شرح |
|---|---|---|
| `LATIF_HOST` | `0.0.0.0` | آدرس bind |
| `LATIF_PORT` | `8000` | پورت سرور |
| `LATIF_OPCUA_SIM_ENABLED` | `true` | فعال/غیرفعال کردن شبیه‌ساز |
| `LATIF_OPCUA_INTERVAL_SEC` | `5` | فاصله تولید داده (ثانیه) |
| `LATIF_HISTORIAN_BACKEND` | `memory` | `memory` یا `sqlite` |
| `LATIF_HISTORIAN_PATH` | `/tmp/latif_historian.sqlite` | مسیر SQLite |
| `LATIF_MPC_AUTO_APPLY` | `false` | `false`=Advisory، `true`=Auto |
| `LATIF_MPC_MAX_ITERS` | `30` | حداکثر تکرار حل MPC |

---

## 🐳 استقرار با Docker

<div dir="rtl">

سه روش استقرار با Docker پشتیبانی می‌شود:

### ۱) Image تکی (سریع‌ترین)

```bash
docker build -t latif-digital-twin .
docker run -p 8000:8000 latif-digital-twin
```

سپس باز کنید: http://localhost:8000/

### ۲) Docker Compose (توصیه‌شده — با Prometheus + Grafana)

```bash
# راه‌اندازی سرویس‌های اصلی
docker compose up -d

# با TimescaleDB برای فاز Pilot (اختیاری)
docker compose --profile pilot up -d
```

سرویس‌ها:

| سرویس | پورت | توضیح |
|---|---|---|
| `latif-api` | 8000 | سرور FastAPI اصلی |
| `prometheus` | 9090 | جمع‌آوری متریک‌ها |
| `grafana` | 3000 | داشبورد عملیاتی (admin / `$GRAFANA_ADMIN_PASSWORD`) |
| `timescaledb` | 5432 | پایگاه داده سری‌زمانی (فقط با `--profile pilot`) |

### ۳) ساخت image در CI

GitHub Actions به‌صورت خودکار در هر push به `main`، image را می‌سازد و سلامت `/api/health` را بررسی می‌کند (`.github/workflows/ci.yml`).

### متغیرهای محیط Docker

| متغیر | پیش‌فرض | توضیح |
|---|---|---|
| `LATIF_API_KEY` | `changeme` | کلید API (در production حتماً تنظیم شود) |
| `LATIF_OPCUA_URL` | — | URL سرور OPC-UA واقعی (در صورت تنظیم، حالت واقعی فعال می‌شود) |
| `LATIF_OPCUA_USERNAME` | — | نام کاربری OPC-UA |
| `LATIF_OPCUA_PASSWORD` | — | گذرواژه OPC-UA |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | گذرواژه Grafana |
| `TS_PASSWORD` | `latif_secret` | گذرواژه TimescaleDB |

</div>

---

## 🧪 تست‌ها و CI

<div dir="rtl">

### مجموعه تست (pytest)

۵۶ تست در ۵ فایل، شامل:

| فایل | تعداد | پوشش |
|---|---|---|
| `tests/test_dryer_model.py` | ۸ | مدل ترمودینامیکی خشک‌کن |
| `tests/test_mpc_controller.py` | ۹ | کنترل‌کننده MPC (قیود، زمان، تکرارپذیری) |
| `tests/test_moisture_predictor.py` | ۱۰ | پیش‌بینی‌کننده V1 و V2 |
| `tests/test_historian_config.py` | ۱۰ | پایگاه داده و تنظیمات |
| `tests/test_api.py` | ۱۹ | API + احراز هویت + KPI + MPC + audit |

اجرای تست‌ها:

```bash
# تمام تست‌ها
bash scripts/run_tests.sh

# با پوشش کد
bash scripts/run_tests.sh --cov

# فقط یک فایل
pytest tests/test_mpc_controller.py -v
```

### GitHub Actions CI

در هر push و PR (به‌جز فایل‌های docs):

1. **Lint با ruff** — warning غیر-blocking
2. **تست Python ۳.۱۱ و ۳.۱۲** — matrix build با پوشش کد
3. **ساخت Docker image** (فقط در `main`) — با cache و تست سلامت
4. **تست اسکریپت‌های داده/نمودار** — تولید داده و نمودار MPC

نتیجه‌ی CI در badge بالای README نمایش داده می‌شود.

</div>

---

## 🔐 امنیت و مانیتورینگ

<div dir="rtl">

### احراز هویت API Key

- در dev (بدون `LATIF_API_KEY`): دسترسی آزاد
- در production (با `LATIF_API_KEY`): تمام مسیرهای `/api/*` نیاز به header `X-API-Key` دارند
- مسیرهای عمومی: `/`, `/api/health`, `/metrics`, `/docs`, `/static/*`, `/api/ws/*`
- مقایسه با `secrets.compare_digest` (ضد timing attack)
- در فاز Pilot با OAuth2/SSO (IEC 62443) جایگزین می‌شود

### Logging ساختاریافته

- فرمت JSON line (هر خط یک رکورد) برای ارسال به ELK/Loki
- فیلدها: `ts`, `level`, `logger`, `msg`, `extra`
- قابل تنظیم با `LATIF_LOG_LEVEL` (debug/info/warning/error)

### متریک‌های Prometheus

endpoint: `/metrics` (در فرمت Prometheus استاندارد)

| متریک | نوع | توضیح |
|---|---|---|
| `latif_mpc_solve_total` | Counter | تعداد حل MPC (با برچسب feasible/mode) |
| `latif_mpc_apply_total` | Counter | تعداد apply/reject set-point |
| `latif_mpc_solve_ms` | Histogram | توزیع زمان حل MPC |
| `latif_moisture_out_pct` | Gauge | رطوبت خروجی لحظه‌ای |
| `latif_thermal_intensity_kWht` | Gauge | شدت انرژی حرارتی |
| `latif_gas_flow_nm3h` | Gauge | دبی گاز |
| `latif_api_requests_total` | Counter | تعداد درخواست‌ها (endpoint/method/status) |
| `latif_api_latency_seconds` | Histogram | تاخیر API |

### OPC-UA Client واقعی (فاز Pilot)

ماژول `app/services/opcua_client.py` به‌صورت خودکار بین دو حالت سوییچ می‌کند:

- اگر `asyncua` نصب باشد و `LATIF_OPCUA_URL` تنظیم شده باشد → **حالت واقعی** (اتصال به DCS)
- در غیر این صورت → **حالت شبیه‌سازی** (fallback)

ویژگی‌های حالت واقعی:
- اتصال خودکار با retry (با exponential backoff)
- fallback به شبیه‌ساز در صورت قطع شدن دائمی
- پشتیبانی از احراز هویت OPC-UA (username/password)
- خواندن مقادیر از Node ID های استاندارد (ns=2;s=Latif.Dryer.*)

### LSTM پیش‌بینی رطوبت (فاز Pilot)

`app/models/moisture_predictor_v2.py`:

- اگر `torch` نصب باشد و وزن‌ها در `data/models/lstm_moisture.pt` موجود باشد → **LSTM واقعی**
- در غیر این صورت → fallback به مدل numpy (نسخه ۰.۱)
- پشتیبانی از ذخیره/بارگذاری وزن‌ها با `save()`
- آموزش تدریجی با `update()`

</div>

---

## 🏗️ معماری سیستم

<div dir="rtl">

معماری ۵ لایه‌ای دوقلوی دیجیتال (مشاهده کامل در [`docs/figures/fig_architecture.png`](docs/figures/fig_architecture.png)):

1. **لایه فیزیکی:** ماشین تیشو، خشک‌کن هیبریدی، سنسورها، DCS/PLC.
2. **لایه داده:** Edge Node + OPC-UA Gateway، Historian (TimescaleDB).
3. **لایه مدل:** مدل ترمودینامیکی + LSTM رطوبت + MPC + هم‌زمان‌سازی بیزی.
4. **لایه بینش:** داشبورد زنده، هشدارها، گزارش‌ها، تحلیل ریشه‌ای.
5. **لایه اقدام:** تنظیم خودکار set-point، محدودسازی پیک گاز، نوشتن به DCS (Safe Write).

**حلقه کنترل پیش‌بینانه:**
- افق پیش‌بینی: ۱۵ دقیقه (۳ گام ۵ دقیقه‌ای).
- نرخ به‌روزرسانی: هر ۵ دقیقه.
- تابع هدف: حداقل‌سازی (انرژی حرارتی + پیک گاز + ضایعات + نوسان set-point) با قیود ایمنی و کیفی.

</div>

---

## 🔧 توسعه و مشارکت

<div dir="rtl">

### فازبندی پروژه

| فاز | مدت | خروجی کلیدی |
|---|---|---|
| فاز ۰ — آماده‌سازی | ۱ ماه | سنسورها کالیبره، Edge Node نصب، OPC-UA برقرار |
| فاز ۱ — پایه داده | ۲ ماه | Historian راه‌اندازی، داده ۳۰ روزه |
| فاز ۲ — ساخت مدل | ۳ ماه | مدل ترمودینامیکی + LSTM + MPC |
| فاز ۳ — Pilot سرد | ۲ ماه | MPC در حالت Advisory |
| فاز ۴ — Pilot گرم | ۱ ماه | MPC در حالت Auto (Safe Write) |
| فاز ۵ — بهره‌برداری کامل | ۱۲ ماه | عملکرد پایدار و گزارش‌داه |

### الگوی مستندسازی

- **BRS** الگوی Volere-inspired + Business Case جامع.
- **SRS** الگوی IEEE Std 830-1998.

### زبان و استانداردها

- زبان مستندات: **فارسی**.
- استانداردهای مرجع: IEC 62443, IEC 61511, ISO 50001, IEEE 830, OPC UA.

### اعتبار

- شناسه BRS: `LATIF-BRS-2026-001 v1.0`
- شناسه SRS: `LATIF-SRS-2026-001 v1.0`
- تاریخ انتشار: ۲۰۲۶-۱۱-۱۴ (۱۴۰۵/۰۸/۲۴)

</div>

---

## 📄 لایسنس

<div dir="rtl">

این پروژه متعلق به **محصولات کاغذی لطیف** است و به‌صورت داخلی نگه‌داری می‌شود. استفاده و توزیع خارج از سازمان بدون تأیید کتبی ممنوع است.

</div>

---

## 📞 تماس

<div dir="rtl">

- **مالک کسب‌وکار:** مدیرعامل محصولات کاغذی لطیف
- **مالک فنی:** مدیر فناوری اطلاعات و اتوماسیون (CTO)
- **ریپو:** https://github.com/parsasohrab1/inno-latif-shasta.git

</div>

---

<div dir="rtl">

*نسخه README: ۱.۰ — ۲۰۲۶-۱۱-۱۴*

</div>
