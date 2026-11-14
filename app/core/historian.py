"""پایگاه داده سری‌زمانی (Historian) برای دوقلوی دیجیتال.

در فاز Pilot با TimescaleDB جایگزین می‌شود؛ در اینجا برای نمونه:
  - backend=memory  : بافر حلقوی در حافظه (سریع، آزمایشی)
  - backend=sqlite : ذخیره روی دیسک (پایدار، قابل آزمایش)
"""

from __future__ import annotations
import time
import sqlite3
import threading
from collections import deque
from typing import Optional
from dataclasses import dataclass, asdict

from .config import settings


@dataclass
class SensorSample:
    """یک نمونه سنسور با برچسب زمان."""
    timestamp: float               # epoch seconds
    shift: int                     # 0, 1, 2
    hood_temp_c: float
    yankee_surface_c: float
    steam_pressure_bar: float
    hot_air_temp_c: float
    moisture_in_pct: float
    moisture_out_pct: float
    basis_weight_gm2: float
    machine_speed_mmin: float
    steam_flow_th: float
    gas_flow_nm3h: float
    production_th: float
    thermal_energy_intensity_kWht: float
    softness_1_10: float
    capillary_rise_mm: float
    out_of_spec_flag: int
    moisture_out_target_pct: float = 5.0
    is_peak_hour: int = 0
    production_status: str = "RUN"


class Historian:
    """ذخیره سری‌زمانی با پشتیبانی memory و sqlite."""

    def __init__(self, backend: str = "memory", max_samples: int = 10000):
        self.backend = backend
        self.max_samples = max_samples
        self._lock = threading.Lock()

        if backend == "memory":
            self._buffer: deque = deque(maxlen=max_samples)
        elif backend == "sqlite":
            self._conn = sqlite3.connect(settings.historian_path, check_same_thread=False)
            self._init_sqlite()
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def _init_sqlite(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                timestamp REAL PRIMARY KEY,
                shift INTEGER,
                hood_temp_c REAL, yankee_surface_c REAL,
                steam_pressure_bar REAL, hot_air_temp_c REAL,
                moisture_in_pct REAL, moisture_out_pct REAL,
                moisture_out_target_pct REAL,
                basis_weight_gm2 REAL, machine_speed_mmin REAL,
                steam_flow_th REAL, gas_flow_nm3h REAL,
                production_th REAL, thermal_energy_intensity_kWht REAL,
                softness_1_10 REAL, capillary_rise_mm REAL,
                out_of_spec_flag INTEGER, is_peak_hour INTEGER,
                production_status TEXT
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON samples(timestamp)")
        self._conn.commit()

    def append(self, sample: SensorSample):
        """افزودن یک نمونه."""
        with self._lock:
            if self.backend == "memory":
                self._buffer.append(sample)
            else:
                self._conn.execute(
                    "INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(asdict(sample).values())
                )
                self._conn.commit()

    def latest(self) -> Optional[SensorSample]:
        """آخرین نمونه."""
        with self._lock:
            if self.backend == "memory":
                return self._buffer[-1] if self._buffer else None
            else:
                cur = self._conn.execute("SELECT * FROM samples ORDER BY timestamp DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    return SensorSample(*row)
                return None

    def history(self, n: int = 100) -> list[SensorSample]:
        """n نمونه آخر به ترتیب زمانی."""
        with self._lock:
            if self.backend == "memory":
                return list(self._buffer)[-n:]
            else:
                cur = self._conn.execute(
                    "SELECT * FROM samples ORDER BY timestamp DESC LIMIT ?", (n,)
                )
                rows = cur.fetchall()
                return [SensorSample(*r) for r in reversed(rows)]

    def count(self) -> int:
        with self._lock:
            if self.backend == "memory":
                return len(self._buffer)
            else:
                cur = self._conn.execute("SELECT COUNT(*) FROM samples")
                return cur.fetchone()[0]

    def close(self):
        if self.backend == "sqlite":
            self._conn.close()


# نمونه سراسری
historian = Historian(backend=settings.historian_backend,
                      max_samples=settings.historian_retention_hours * 288)
