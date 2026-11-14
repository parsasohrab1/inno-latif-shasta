"""
پیش‌بینی‌کننده رطوبت نهایی (نسخه ۰.۲)

معماری:
  - اگر PyTorch نصب باشد → LSTM واقعی (سه‌لایه)
  - در غیر این صورت → مدل numpy ساده (مثل نسخه ۰.۱)

هر دو نسخه یک رابط یکسان دارند (predict / update / save / load).
مدل‌ها در data/models/ ذخیره می‌شوند.
"""

from __future__ import annotations
import os
import json
import numpy as np
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict


@dataclass
class PredictionResult:
    """نتیجه پیش‌بینی."""
    moisture_pred_pct: list
    horizon_min: list
    confidence: float
    model_type: str = "numpy"  # numpy | torch_lstm


# تلاش برای import torch (اختیاری)
try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


# ----- مدل PyTorch LSTM -----
if TORCH_AVAILABLE:

    class _LSTMModel(nn.Module):
        """مدل LSTM برای پیش‌بینی رطوبت در ۳ افق."""

        def __init__(self, n_features=8, hidden=32, n_layers=2, horizon=3):
            super().__init__()
            self.lstm = nn.LSTM(
                input_size=n_features,
                hidden_size=hidden,
                num_layers=n_layers,
                batch_first=True,
                dropout=0.1 if n_layers > 1 else 0.0,
            )
            self.head = nn.Linear(hidden, horizon)
            # نرمال‌سازی داخلی با BatchNorm روی خروجی LSTM
            self.norm = nn.LayerNorm(hidden)

        def forward(self, x):
            # x: (batch, seq, features)
            out, (h, c) = self.lstm(x)
            out = self.norm(out[:, -1, :])   # فقط گام آخر
            y = self.head(out)
            return torch.clamp(y, 1.0, 12.0)


class MoisturePredictorV2:
    """پیش‌بینی‌کننده رطوبت با ارتقا اختیاری به LSTM.

    اگر PyTorch نصب باشد و فایل وزن‌ها موجود باشد، از LSTM استفاده می‌کند؛
    در غیر این صورت به‌صورت خودکار به مدل numpy (ساده‌تر) برمی‌گردد.
    """

    HORIZON = 3
    INPUT_LAG = 6
    N_FEATURES = 8
    # مسیر پروژه را نسب به این فایل محاسبه می‌کنیم (نه hard-code)
    # app/models/moisture_predictor_v2.py → app/models → app → repo root (3 سطح)
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    @classmethod
    def _model_dir(cls):
        return os.path.join(cls._REPO_ROOT, "data", "models")

    @property
    def MODEL_PATH(self):
        return os.path.join(self._model_dir(), "lstm_moisture.pt")

    @property
    def SCALER_PATH(self):
        return os.path.join(self._model_dir(), "lstm_scaler.json")

    def __init__(self, prefer_torch: bool = True):
        self.prefer_torch = prefer_torch and TORCH_AVAILABLE
        self.model_type = "numpy"
        self._torch_model = None
        self._scaler: Dict[str, list] = {}

        if self.prefer_torch:
            self._init_torch()

        if self.model_type != "torch_lstm":
            # fallback به numpy
            from app.models.moisture_predictor import MoisturePredictor as _V1
            self._numpy_model = _V1()

    def _init_torch(self):
        """ساخت/بارگذاری مدل PyTorch."""
        try:
            os.makedirs(self._model_dir(), exist_ok=True)
            self._torch_model = _LSTMModel(
                n_features=self.N_FEATURES,
                hidden=32,
                n_layers=2,
                horizon=self.HORIZON,
            )
            if os.path.isfile(self.MODEL_PATH):
                state = torch.load(self.MODEL_PATH, map_location="cpu")
                self._torch_model.load_state_dict(state)
                self.model_type = "torch_lstm"
                # بارگذاری scaler
                if os.path.isfile(self.SCALER_PATH):
                    with open(self.SCALER_PATH, "r") as f:
                        self._scaler = json.load(f)
            else:
                # بدون وزن‌های آموزش‌دیده، numpy بهتر از LSTM تصادفی است
                self._torch_model = None
                self.model_type = "numpy"
        except Exception as e:
            # اگر هر مشکلی پیش آمد، به numpy برمی‌گردیم
            self._torch_model = None
            self.model_type = "numpy"

    def predict(self, history: List[Dict]) -> PredictionResult:
        """پیش‌بینی رطوبت نهایی.

        history: لیست حداقل ۶ دیکشنری شامل ۸ ویژگی.
        """
        if self.model_type == "torch_lstm" and self._torch_model is not None:
            return self._predict_torch(history)
        return self._predict_numpy(history)

    def _predict_torch(self, history: List[Dict]) -> PredictionResult:
        x = self._history_to_tensor(history)
        with torch.no_grad():
            y = self._torch_model(x).squeeze(0).numpy()
        return PredictionResult(
            moisture_pred_pct=[round(float(v), 4) for v in y],
            horizon_min=[5, 10, 15],
            confidence=0.85,
            model_type="torch_lstm",
        )

    def _predict_numpy(self, history: List[Dict]) -> PredictionResult:
        r = self._numpy_model.predict(history)
        return PredictionResult(
            moisture_pred_pct=r.moisture_pred_pct,
            horizon_min=r.horizon_min,
            confidence=r.confidence,
            model_type="numpy",
        )

    def update(self, new_sample: Dict, learning_rate: float = 0.01) -> None:
        """به‌روزرسانی تدریجی مدل با داده جدید."""
        if self.model_type == "torch_lstm":
            self._online_torch(new_sample, learning_rate)
        else:
            self._numpy_model.update(new_sample, learning_rate)

    def _online_torch(self, new_sample: Dict, lr: float) -> None:
        """یک گام آموزش online با gradient descent."""
        if "moisture_out" not in new_sample or self._torch_model is None:
            return
        # بدون ذخیره last_input به‌دلیل پیچیدگی — به‌جای آن، به‌روزرسانی دوره‌ای بعد از
        # انباشت N نمونه انجام می‌شود. این یک placeholder است برای فاز Pilot.
        pass

    def save(self) -> None:
        """ذخیره وزن‌ها برای استفاده‌ی بعدی."""
        if self.model_type == "torch_lstm" and self._torch_model is not None:
            os.makedirs(self._model_dir(), exist_ok=True)
            torch.save(self._torch_model.state_dict(), self.MODEL_PATH)
            with open(self.SCALER_PATH, "w") as f:
                json.dump(self._scaler, f)

    def _history_to_tensor(self, history: List[Dict]):
        """تبدیل تاریخچه به tensor (1, seq, features) با نرمال‌سازی."""
        x = np.zeros((self.INPUT_LAG, self.N_FEATURES), dtype=np.float32)
        for k, h in enumerate(history[-self.INPUT_LAG:]):
            x[k, 0] = h.get("moisture_in", 68.0)
            x[k, 1] = h.get("moisture_out", 5.0)
            x[k, 2] = h.get("hood_temp", 400.0)
            x[k, 3] = h.get("steam_pressure", 5.2)
            x[k, 4] = h.get("hot_air_temp", 420.0)
            x[k, 5] = h.get("basis_weight", 15.0)
            x[k, 6] = h.get("machine_speed", 1500.0)
            x[k, 7] = h.get("gas_flow", 320.0)
        # نرمال‌سازی ساده (میانگین صفر)
        mean = np.array([68.0, 5.0, 400.0, 5.2, 420.0, 15.0, 1500.0, 320.0])
        std = np.array([2.0, 0.5, 10.0, 0.1, 8.0, 0.1, 30.0, 10.0])
        x = (x - mean) / std
        return torch.from_numpy(x).unsqueeze(0)


def get_predictor() -> MoisturePredictorV2:
    """کارخانه‌ی پیش‌بینی‌کننده با انتخاب خودکار مدل."""
    return MoisturePredictorV2(prefer_torch=TORCH_AVAILABLE)
