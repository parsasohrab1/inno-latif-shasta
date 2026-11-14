"""
بسته FastAPI backend دوقلوی دیجیتال خشک‌کن خط تیشو

معماری:
  - core/config.py    : تنظیمات (Pydantic Settings)
  - core/historian.py  : پایگاه داده سری‌زمانی در حافظه/SQLite
  - services/opcua_sim.py  : شبیه‌ساز OPC-UA (تولید داده سنسور)
  - services/mpc_service.py : سرویس کنترل‌کننده MPC
  - api/routes.py     : مسیرهای REST + WebSocket
  - main.py           : نقطه ورود FastAPI
"""

__version__ = "0.1.0"
