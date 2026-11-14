# Contribution Guidelines — دوقلوی دیجیتال لطیف

<div dir="rtl">

## گزارش باگ و پیشنهاد

لطفاً قبل از گزارش باگ، issue های موجود را بررسی کنید. باگ‌ها را با قالب زیر گزارش کنید:

- توضیح کوتاه مشکل
- مراحل بازتولید
- رفتار مورد انتظار
- رفتار واقعی
- نسخه Python و کتابخانه‌ها (`pip freeze`)

## شاخه‌ها

- `main` — شاخه‌ی پایدار (محصول آماده‌ی release)
- `develop` — شاخه‌ی توسعه (تجمیع feature ها)
- `feature/<name>` — برای هر قابلیت جدید
- `fix/<name>` — برای رفع باگ
- `hotfix/<name>` — رفع فوری در main

## commit message

از قالب Conventional Commits استفاده کنید:

```
type(scope): subject

[optional body]
```

نوع‌ها: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`
scope: `model`, `api`, `dashboard`, `docker`, `tests`, `docs`, `ci`

مثال: `feat(api): افزودن endpoint /api/mpc/history`

## پیش‌نیازها

```bash
pip install -r requirements.txt
pip install pytest pytest-cov ruff
```

## اجرای تست‌ها قبل از PR

```bash
bash scripts/run_tests.sh --cov
ruff check app/ tests/
```

## روند PR

۱. یک شاخه‌ی feature بسازید: `git checkout -b feature/my-feature`
۲. تغییرات را با commit message استاندارد ثبت کنید
۳. تست‌ها را اجرا و همه‌چیز را سبز نگه دارید
۴. PR به `develop` بزنید (نه مستقیم به `main`)
۵. حداقل یک code review لازم است
۶. بعد از merge، CI به‌صورت خودکار build را اجرا می‌کند

## استانداردهای کد

- Python 3.11+
- Type hints در همه‌ی توابع
- Docstring برای توابع عمومی
- طول خط: ۱۰۰ کاراکتر
- import مرتب (alphabetical، standard → third-party → local)
- تست برای هر قابلیت جدید (coverage ≥ ۸۰٪)

## ساختار فولدر

```
app/          # کد نرم‌افزار
tests/        # تست‌های pytest
scripts/      # اسکریپت‌های کمکی
docs/         # مستندات (BRS, SRS, figures)
data/         # داده‌های سنتتیک
monitoring/   # پیکربندی Prometheus/Grafana
.github/      # CI workflows
```

## موارد مهم برای فاز Pilot

اگر روی مؤلفه‌ای کار می‌کنید که در فاز Pilot به‌کار می‌آید (OPC-UA واقعی، TimescaleDB، SSO)، حتماً:
- با fallback به حالت شبیه‌سازی کار کند
- تست‌ها بدون نیاز به سرویس خارجی اجرا شوند
- در README توضیح داده شود که چطور فعال می‌شود

</div>
