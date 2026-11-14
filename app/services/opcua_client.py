"""کلاینت OPC-UA واقعی برای خواندن سنسورهای خشک‌کن.

در فاز Pilot از این ماژول به جای opcua_sim.py استفاده می‌شود.
اگر کتابخانه asyncua نصب نباشد یا اتصال قطع باشد، به‌صورت خودکار
به شبیه‌ساز fallback می‌کند تا سرویس متوقف نشود.

Node IDs (نمونه — مطابق با DCS متفاوت خواهد بود):
  ns=2;s=Latif.Dryer.HoodTemp
  ns=2;s=Latif.Dryer.YankeeSurface
  ns=2;s=Latif.Dryer.SteamPressure
  ns=2;s=Latif.Dryer.HotAirTemp
  ns=2;s=Latif.Dryer.MoistureIn
  ns=2;s=Latif.Dryer.MoistureOut
  ns=2;s=Latif.Dryer.BasisWeight
  ns=2;s=Latif.Dryer.MachineSpeed
  ns=2;s=Latif.Dryer.SteamFlow
  ns=2;s=Latif.Dryer.GasFlow
"""

from __future__ import annotations
import os
import asyncio
import threading
import logging
from typing import Optional

from app.core.config import settings
from app.core.historian import historian, SensorSample
from app.services.opcua_sim import OPCUASimulator

logger = logging.getLogger("latif.opcua_client")

# تلاش برای import asyncua (اختیاری)
try:
    from asyncua import Client
    ASYNCUA_AVAILABLE = True
except ImportError:
    ASYNCUA_AVAILABLE = False
    logger.warning("asyncua not installed; OPC-UA real mode disabled, falling back to simulator")


class OPCUAClient:
    """کلاینت OPC-UA با fallback خودکار به شبیه‌ساز.

    حالت‌ها:
      1) asyncua نصب است و LATIF_OPCUA_URL تنظیم شده → حالت واقعی
      2) در غیر این صورت → حالت شبیه‌سازی (مثل opcua_sim)
    """

    NODE_MAP = {
        "hood_temp": "ns=2;s=Latif.Dryer.HoodTemp",
        "yankee_surface": "ns=2;s=Latif.Dryer.YankeeSurface",
        "steam_pressure": "ns=2;s=Latif.Dryer.SteamPressure",
        "hot_air_temp": "ns=2;s=Latif.Dryer.HotAirTemp",
        "moisture_in": "ns=2;s=Latif.Dryer.MoistureIn",
        "moisture_out": "ns=2;s=Latif.Dryer.MoistureOut",
        "basis_weight": "ns=2;s=Latif.Dryer.BasisWeight",
        "machine_speed": "ns=2;s=Latif.Dryer.MachineSpeed",
        "steam_flow": "ns=2;s=Latif.Dryer.SteamFlow",
        "gas_flow": "ns=2;s=Latif.Dryer.GasFlow",
    }

    def __init__(self, url: Optional[str] = None, username: Optional[str] = None,
                 password: Optional[str] = None):
        self.url = url or os.environ.get("LATIF_OPCUA_URL")
        self.username = username or os.environ.get("LATIF_OPCUA_USERNAME")
        self.password = password or os.environ.get("LATIF_OPCUA_PASSWORD")
        self.mode = "real" if (ASYNCUA_AVAILABLE and self.url) else "simulator"
        self._sim = OPCUASimulator() if self.mode == "simulator" else None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._client: Optional["Client"] = None
        self._nodes: dict = {}
        self._step = 0

    def start(self):
        if self._running:
            return
        self._running = True
        if self.mode == "simulator":
            self._sim.start()
            logger.info("OPC-UA client started in SIMULATOR mode")
            return
        # حالت واقعی: در thread جدا با event loop خود
        self._thread = threading.Thread(target=self._run_async, daemon=True)
        self._thread.start()
        logger.info("OPC-UA client started in REAL mode (url=%s)", self.url)

    def stop(self):
        self._running = False
        if self._sim:
            self._sim.stop()
        if self._thread and self._loop:
            self._loop.call_soon_threadsafe(self._cancel)
            self._thread.join(timeout=2)

    def _cancel(self):
        if self._task and not self._task.done():
            self._task.cancel()

    def _run_async(self):
        """اجرای event loop برای کلاینت asyncua."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_loop())
        except Exception as e:
            logger.error("OPC-UA client error: %s — falling back to simulator", e)
            # fallback به شبیه‌ساز
            self.mode = "simulator"
            self._sim = OPCUASimulator()
            self._sim.start()
        finally:
            self._loop.close()

    async def _async_loop(self):
        """حلقه اصلی اتصال و خواندن OPC-UA."""
        reconnect_delay = 2
        while self._running:
            try:
                async with Client(url=self.url) as client:
                    if self.username:
                        await client.set_user(self.username)
                    if self.password:
                        await client.set_password(self.password)
                    logger.info("Connected to OPC-UA server: %s", self.url)
                    # دریافت node ها
                    self._nodes = {
                        k: await client.get_node(v)
                        for k, v in self.NODE_MAP.items()
                    }
                    reconnect_delay = 2  # reset پس از اتصال موفق
                    while self._running:
                        await self._read_and_store()
                        await asyncio.sleep(settings.opcua_interval_sec)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("OPC-UA connection lost: %s — retry in %ss", e, reconnect_delay)
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)

    async def _read_and_store(self):
        """خواندن مقادیر و ذخیره در historian."""
        try:
            values = {}
            for k, node in self._nodes.items():
                try:
                    v = await node.read_value()
                    values[k] = float(v)
                except Exception:
                    values[k] = 0.0
            sample = self._build_sample(values)
            historian.append(sample)
            self._step += 1
        except Exception as e:
            logger.error("Error reading OPC-UA values: %s", e)

    def _build_sample(self, v: dict) -> SensorSample:
        """ساخت SensorSample از مقادیر خوانده‌شده."""
        import time as _time
        # اگر moisture_out خوانده شد از DCS؛ در غیر این صورت از مدل محاسبه
        from app.models.dryer_model import DryerModel, DryerState
        state = DryerState(
            hood_temp_c=v.get("hood_temp", 400.0),
            yankee_surface_c=v.get("yankee_surface", 100.0),
            steam_pressure_bar=v.get("steam_pressure", 5.2),
            hot_air_temp_c=v.get("hot_air_temp", 420.0),
            moisture_in_pct=v.get("moisture_in", 68.0),
            basis_weight_gm2=v.get("basis_weight", 15.0),
            machine_speed_mmin=v.get("machine_speed", 1500.0),
            steam_flow_th=v.get("steam_flow", 7.2),
            gas_flow_nm3h=v.get("gas_flow", 320.0),
        )
        out = DryerModel().step(state)
        hour = int(_time.strftime("%H", _time.localtime()))
        return SensorSample(
            timestamp=_time.time(),
            shift=hour // 8 % 3,
            hood_temp_c=state.hood_temp_c,
            yankee_surface_c=state.yankee_surface_c,
            steam_pressure_bar=state.steam_pressure_bar,
            hot_air_temp_c=state.hot_air_temp_c,
            moisture_in_pct=state.moisture_in_pct,
            moisture_out_pct=v.get("moisture_out", out.moisture_out_pct),
            basis_weight_gm2=state.basis_weight_gm2,
            machine_speed_mmin=state.machine_speed_mmin,
            steam_flow_th=state.steam_flow_th,
            gas_flow_nm3h=state.gas_flow_nm3h,
            production_th=out.production_th,
            thermal_energy_intensity_kWht=out.thermal_energy_intensity_kWht,
            softness_1_10=8.0,
            capillary_rise_mm=85.0,
            out_of_spec_flag=0,
            is_peak_hour=1 if (8 <= hour <= 11) or (18 <= hour <= 21) else 0,
        )

    def status(self) -> dict:
        return {
            "running": self._running,
            "mode": self.mode,
            "step": self._step,
            "samples_in_historian": historian.count(),
            "interval_sec": settings.opcua_interval_sec,
            "asyncua_available": ASYNCUA_AVAILABLE,
            "url": self.url if self.mode == "real" else None,
        }


# انتخاب نمونه‌ی سراسری: اگر LATIF_OPCUA_URL تنظیم باشد، واقعی، وگرنه شبیه‌ساز
opcua_client = OPCUAClient()
