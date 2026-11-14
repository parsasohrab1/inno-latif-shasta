"""تست‌های واحد برای پیش‌بینی‌کننده رطوبت (نسخه‌های ۱ و ۲)."""

import pytest
import sys
sys.path.insert(0, "/home/z/my-project/inno-latif-shasta")

from app.models.moisture_predictor import MoisturePredictor
from app.models.moisture_predictor_v2 import MoisturePredictorV2, get_predictor


def make_history(n=6, moisture_out=5.0):
    history = []
    for i in range(n):
        history.append({
            "moisture_in": 68.0 + i * 0.1,
            "moisture_out": moisture_out,
            "hood_temp": 400.0 + i * 2,
            "steam_pressure": 5.2,
            "hot_air_temp": 420.0,
            "basis_weight": 15.0,
            "machine_speed": 1500.0,
            "gas_flow": 320.0,
        })
    return history


class TestMoisturePredictorV1:

    def test_predict_returns_three_horizons(self):
        p = MoisturePredictor()
        r = p.predict(make_history())
        assert len(r.moisture_pred_pct) == 3
        assert r.horizon_min == [5, 10, 15]

    def test_predict_in_physical_bounds(self):
        p = MoisturePredictor()
        r = p.predict(make_history())
        for v in r.moisture_pred_pct:
            assert 1.0 <= v <= 12.0

    def test_predict_with_short_history(self):
        """اگر تاریخچه کوتاه باشد، نباید exception دهد."""
        p = MoisturePredictor()
        r = p.predict(make_history(2))
        assert len(r.moisture_pred_pct) == 3

    def test_update_does_not_crash(self):
        p = MoisturePredictor()
        p.predict(make_history())
        p.update({"moisture_out": 5.2})
        # predict مجدد برای تأیید پایداری
        r = p.predict(make_history())
        assert len(r.moisture_pred_pct) == 3

    def test_confidence_range(self):
        p = MoisturePredictor()
        r = p.predict(make_history())
        assert 0.0 <= r.confidence <= 1.0


class TestMoisturePredictorV2:

    def test_get_predictor_returns_v2(self):
        p = get_predictor()
        assert isinstance(p, MoisturePredictorV2)

    def test_v2_predict_returns_three_horizons(self):
        p = MoisturePredictorV2(prefer_torch=False)
        r = p.predict(make_history())
        assert len(r.moisture_pred_pct) == 3
        assert r.horizon_min == [5, 10, 15]

    def test_v2_in_physical_bounds(self):
        p = MoisturePredictorV2(prefer_torch=False)
        r = p.predict(make_history())
        for v in r.moisture_pred_pct:
            assert 1.0 <= v <= 12.0

    def test_v2_model_type_is_numpy_when_no_torch(self):
        """بدون وزن‌های آموزش‌دیده، باید به numpy fallback کند."""
        p = MoisturePredictorV2(prefer_torch=True)
        # چون وزن‌های LSTM وجود ندارند → fallback
        assert p.model_type in ("numpy", "torch_lstm")
        r = p.predict(make_history())
        assert r.model_type in ("numpy", "torch_lstm")

    def test_v2_update_works_in_numpy_mode(self):
        p = MoisturePredictorV2(prefer_torch=False)
        p.predict(make_history())
        p.update({"moisture_out": 5.1})
        r = p.predict(make_history())
        assert len(r.moisture_pred_pct) == 3
