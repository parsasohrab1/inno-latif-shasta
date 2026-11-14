#!/usr/bin/env bash
# اجرای همه تست‌های pytest برای دوقلوی دیجیتال لطیف
# استفاده: bash scripts/run_tests.sh [--cov]

set -e
cd "$(dirname "$0")/.."

echo "===================="
echo "Latif Digital Twin — Test Suite"
echo "===================="
echo ""

# متغیرهای محیطی تست (بدون نیاز به اینترنت یا سرویس‌های خارجی)
export LATIF_OPCUA_SIM_ENABLED=true
export LATIF_OPCUA_INTERVAL_SEC=1
export LATIF_HISTORIAN_BACKEND=memory
export LATIF_LOG_LEVEL=warning
export PYTHONPATH="$(pwd)"

if [[ "$1" == "--cov" ]]; then
  pytest --cov=app --cov-report=term-missing --cov-report=html:htmlcov tests/
else
  pytest tests/ "$@"
fi

echo ""
echo "===================="
echo "Test run complete"
echo "===================="
