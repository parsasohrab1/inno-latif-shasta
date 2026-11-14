"""احراز هویت و امنیت API.

در فاز Pilot با SSO/OAuth2 (مطابق IEC 62443) جایگزین می‌شود.
فعلاً: API Key ساده از header X-API-Key یا query parameter api_key.

استثناها (بدون احراز هویت):
  - /api/health  (heartbeat)
  - /metrics     (Prometheus scrape — با شبکه‌ی داخلی)
  - /docs, /openapi.json  (مستندات)
  - /            (داشبورد استاتیک)
"""

from __future__ import annotations
import os
import secrets
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader, APIKeyQuery

# کلید پیش‌فرض از env؛ اگر تنظیم نشده باشد، در هر بار راه‌اندازی یک کلید
# موقت تولید می‌شود (در فاز Pilot حتماً LATIF_API_KEY در env تنظیم شود)
DEFAULT_KEY = os.environ.get("LATIF_API_KEY") or "dev-only-key-" + secrets.token_hex(8)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
API_KEY_QUERY = APIKeyQuery(name="api_key", auto_error=False)

# مسیرهای مستثنی
PUBLIC_PATHS = {"/", "/api/health", "/metrics",
                "/docs", "/redoc", "/openapi.json",
                "/docs/oauth2-redirect", "/dashboard"}


async def verify_api_key(request: Request,
                          header_key: str = Security(API_KEY_HEADER),
                          query_key: str = Security(API_KEY_QUERY)) -> str:
    """برای هر request (به‌جز PUBLIC_PATHS) کلید را بررسی می‌کند."""
    path = request.url.path
    # مسیرهای استاتیک و WebSocket نیز مجاز
    if path in PUBLIC_PATHS or path.startswith("/static") or path.startswith("/api/ws"):
        return "anonymous"

    # اگر کلید تنظیم نشده (dev) دسترسی آزاد است
    if not os.environ.get("LATIF_API_KEY"):
        return "dev"

    provided = header_key or query_key
    if not provided or not secrets.compare_digest(provided, DEFAULT_KEY):
        raise HTTPException(
            status_code=401,
            detail="invalid or missing API key (X-API-Key header or api_key query)",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return "authenticated"


def get_current_api_key() -> str:
    """برای نمایش در داشبورد لاگ‌ها."""
    return DEFAULT_KEY
