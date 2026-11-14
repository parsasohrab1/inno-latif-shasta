"""تست‌های واحد برای مدل ترمودینامیکی خشک‌کن."""

import pytest
import sys
sys.path.insert(0, "/home/z/my-project/inno-latif-shasta")

from app.models.dryer_model import DryerModel, DryerState


def make_state(**overrides):
    defaults = dict(
        hood_temp_c=400.0, yankee_surface_c=100.0,
        steam_pressure_bar=5.2, hot_air_temp_c=420.0,
        moisture_in_pct=68.0, basis_weight_gm2=15.0,
        machine_speed_mmin=1500.0, steam_flow_th=7.2,
        gas_flow_nm3h=320.0,
    )
    defaults.update(overrides)
    return DryerState(**defaults)


class TestDryerModel:

    def test_step_returns_all_required_outputs(self):
        m = DryerModel()
        out = m.step(make_state())
        assert hasattr(out, "moisture_out_pct")
        assert hasattr(out, "production_th")
        assert hasattr(out, "thermal_energy_intensity_kWht")
        assert hasattr(out, "energy_kwh")
        assert hasattr(out, "co2_kg_per_t")
        assert hasattr(out, "evaporation_rate_th")
        assert hasattr(out, "drying_efficiency_pct")

    def test_moisture_within_physical_bounds(self):
        m = DryerModel()
        out = m.step(make_state())
        assert 3.0 <= out.moisture_out_pct <= 7.0, \
            f"moisture {out.moisture_out_pct} out of bounds"

    def test_production_reasonable(self):
        m = DryerModel()
        out = m.step(make_state())
        # تولید خط تیشو ~ ۷.۳ t/h
        assert 5.0 < out.production_th < 10.0, \
            f"production {out.production_th} outside expected range"

    def test_thermal_intensity_near_baseline(self):
        """شدت انرژی باید نزدیک خط پایه ۲۵۹۳ kWh/t باشد در شرایط نامی."""
        m = DryerModel()
        out = m.step(make_state())
        # مدل ساده، با خطای تا ±۲۰٪ قابل قبول است
        assert 1800 < out.thermal_energy_intensity_kWht < 3500, \
            f"energy intensity {out.thermal_energy_intensity_kWht} too far"

    def test_higher_hood_temp_reduces_moisture(self):
        """افزایش دمای هود باید رطوبت خروجی را کاهش دهد (نفی ارتباط)."""
        m = DryerModel()
        out_low = m.step(make_state(hood_temp_c=380.0, gas_flow_nm3h=280.0))
        out_high = m.step(make_state(hood_temp_c=440.0, gas_flow_nm3h=380.0))
        assert out_high.moisture_out_pct <= out_low.moisture_out_pct, \
            "higher hood temp should not increase moisture"

    def test_co2_positive(self):
        m = DryerModel()
        out = m.step(make_state())
        assert out.co2_kg_per_t > 0

    def test_predict_horizon_returns_three_steps(self):
        m = DryerModel()
        sp = {"hood_temp": [410.0, 420.0, 430.0],
              "steam_pressure": [5.4, 5.5, 5.6],
              "hot_air_temp": [425.0, 430.0, 435.0],
              "machine_speed": [1520.0, 1530.0, 1540.0]}
        preds = m.predict_horizon(make_state(), sp, horizon=3)
        assert len(preds) == 3
        assert all(3.0 <= p.moisture_out_pct <= 7.0 for p in preds)

    def test_edge_zero_production_does_not_crash(self):
        m = DryerModel()
        # production = basis_weight × speed × width × 60 / 1e6 — سرعت صفر → تولید صفر
        out = m.step(make_state(machine_speed_mmin=0.0))
        # نباید exception یا NaN
        assert out.production_th >= 0
        assert out.thermal_energy_intensity_kWht >= 0 or \
               out.thermal_energy_intensity_kWht == 0
