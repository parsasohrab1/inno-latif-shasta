"""
پیش‌بینی‌کننده رطوبت نهایی (Moisture Predictor)

مدل ساده‌شده بر اساس رگرسیون خطی با ویژگی‌های تأخیردار (lag features)
به‌جای LSTM — برای محیط بدون PyTorch/TensorFlow کار می‌کند و قابل ارتقا است.

ورودی: پنجره ۳۰ دقیقه گذشته سنسورها (۶ گام ۵ دقیقه‌ای)
خروجی: پیش‌بینی رطوبت نهایی در t+5، t+10، t+15 دقیقه
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass


@dataclass
class PredictionResult:
    """نتیجه پیش‌بینی."""
    moisture_pred_pct: list   # پیش‌بینی برای ۳ افق
    horizon_min: list         # افق‌ها (دقیقه)
    confidence: float         # سطح اطمینان (0-1)


class MoisturePredictor:
    """پیش‌بینی‌کننده رطوبت نهایی.

    مدل: یک شبکه‌ی عصبی ساده (شبکه‌ی کاملاً متصل یک‌لایه‌ای) که با numpy پیاده‌سازی
    شده تا وابستگی به فریم‌ورک‌های سنگین نداشته باشد. ورودی:
      - ۶ گام گذشته ۸ متغیر: رطوبت ورودی، رطوبت خروجی، دمای هود، فشار بخار،
        دمای هوای گرم، گرماژ، سرعت ماشین، دبی گاز
    خروجی: پیش‌بینی رطوبت خروجی در ۳ افق (۵، ۱۰، ۱۵ دقیقه).
    """

    HORIZON = 3
    INPUT_LAG = 6
    N_FEATURES = 8

    def __init__(self):
        # وزن‌ها به‌صورت pre-trained (شبیه‌سازی شده با مقادیر منطقی)
        # ورودی: 6*8 = 48، خروجی: 3
        rng = np.random.default_rng(seed=42)
        # وزن‌ها با مقدار کوچک تصادفی + بایاس
        self.W = rng.normal(0, 0.01, (self.INPUT_LAG * self.N_FEATURES, self.HORIZON))
        self.b = np.array([5.0, 5.0, 5.0])  # بایاس = رطوبت هدف

        # وزن‌های معنادار (دستی) برای ویژگی‌های مهم
        # رطوبت ورودی (هر گام) اثر مثبت
        for k in range(self.INPUT_LAG):
            self.W[k * self.N_FEATURES + 0, :] = 0.08 * (1 - k * 0.1)
            # رطوبت خروجی (lag) اثر مثبت قوی — auto-regressive
            self.W[k * self.N_FEATURES + 1, :] = 0.25 * (1 - k * 0.1)
            # دمای هود اثر منفی (دمای بیشتر = رطوبت کمتر)
            self.W[k * self.N_FEATURES + 2, :] = -0.004
            # فشار بخار اثر منفی
            self.W[k * self.N_FEATURES + 3, :] = -0.02
            # دمای هوای گرم اثر منفی
            self.W[k * self.N_FEATURES + 4, :] = -0.002
            # گرماژ اثر مثبت (محتوای آب بیشتر)
            self.W[k * self.N_FEATURES + 5, :] = 0.05
            # سرعت ماشین اثر مثبت (زمان کمتر در خشک‌کن)
            self.W[k * self.N_FEATURES + 6, :] = 0.0008
            # دبی گاز اثر منفی
            self.W[k * self.N_FEATURES + 7, :] = -0.0005

        self.last_input = None

    def predict(self, history: list) -> PredictionResult:
        """پیش‌بینی رطوبت نهایی.

        history: لیست ۶ دیکشنری، هر کدام شامل ۸ ویژگی:
          moisture_in, moisture_out, hood_temp, steam_pressure,
          hot_air_temp, basis_weight, machine_speed, gas_flow
        """
        if len(history) < self.INPUT_LAG:
            # اگر داده کافی نبود، با مقدار آخر تکرار کن
            history = (history + [history[-1] if history else {}])[-self.INPUT_LAG:]

        x = np.zeros((self.INPUT_LAG, self.N_FEATURES))
        for k, h in enumerate(history[-self.INPUT_LAG:]):
            x[k, 0] = h.get("moisture_in", 68.0)
            x[k, 1] = h.get("moisture_out", 5.0)
            x[k, 2] = h.get("hood_temp", 400.0)
            x[k, 3] = h.get("steam_pressure", 5.2)
            x[k, 4] = h.get("hot_air_temp", 420.0)
            x[k, 5] = h.get("basis_weight", 15.0)
            x[k, 6] = h.get("machine_speed", 1500.0)
            x[k, 7] = h.get("gas_flow", 320.0)

        x_flat = x.flatten()
        self.last_input = x_flat.copy()

        y = x_flat @ self.W + self.b
        # محدودسازی به بازه فیزیکی
        y = np.clip(y, 1.0, 12.0)

        # تخمین اطمینان بر اساس واریانس تاریخچه
        std = float(np.std(history[-self.INPUT_LAG:] and
                           [h.get("moisture_out", 5.0) for h in history[-self.INPUT_LAG:]]
                           or [5.0]))
        confidence = max(0.0, min(1.0, 1.0 - std / 1.5))

        return PredictionResult(
            moisture_pred_pct=[round(float(v), 4) for v in y],
            horizon_min=[5, 10, 15],
            confidence=round(confidence, 3),
        )

    def update(self, new_sample: dict, learning_rate: float = 0.01):
        """به‌روزرسانی تدریجی مدل (online learning) با یک نمونه جدید.

        پس از دریافت مقدار واقعی رطوبت خروجی، خطای پیش‌بینی را محاسبه می‌کند
        و با gradient descent کوچک، وزن‌ها را اصلاح می‌کند.
        """
        if self.last_input is None:
            return
        # فقط اگر مقدار واقعی moisture_out موجود باشد
        actual = new_sample.get("moisture_out")
        if actual is None:
            return
        # پیش‌بینی مجدد برای محاسبه خطا
        y_pred = self.last_input @ self.W + self.b
        err = y_pred - actual
        # به‌روزرسانی وزن با LMS
        grad = np.outer(self.last_input, err)
        self.W -= learning_rate * grad
        # محدودسازی وزن برای پایداری
        self.W = np.clip(self.W, -1.0, 1.0)
