# Dockerfile برای دوقلوی دیجیتال خشک‌کن لطیف
# multi-stage build: builder → runtime (slim)

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

# نصب پیش‌نیازهای سیستم برای فونت‌های CJK (در صورت نیاز برای نمودار)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# اول requirements.txt را کپی تا cache پایدار باشد
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

# نصب فونت DejaVu (پیش‌فرض matplotlib) و fontconfig
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    fonts-dejavu-core \
    libfreetype6 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# کپی وابستگی‌های Python از builder
COPY --from=builder /install /usr/local

# کپی کد برنامه
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY docs/ ./docs/
COPY README.md requirements.txt ./

# متغیرهای محیط پیش‌فرض
ENV LATIF_HOST=0.0.0.0 \
    LATIF_PORT=8000 \
    LATIF_OPCUA_SIM_ENABLED=true \
    LATIF_OPCUA_INTERVAL_SEC=5 \
    LATIF_HISTORIAN_BACKEND=memory \
    LATIF_LOG_LEVEL=info \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# سلامت‌سنجی
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3).status==200 else 1)"

EXPOSE 8000

# کاربر غیر root برای امنیت (IEC 62443)
RUN useradd -r -u 1000 -g users latif && chown -R latif:users /app
USER latif

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
