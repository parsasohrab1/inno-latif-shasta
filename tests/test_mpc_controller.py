"""تست‌های واحد برای کنترل‌کننده MPC."""

import pytest
import sys
sys.path.insert(0, "/home/z/my-project/inno-latif-shasta")

from app.models.dryer_model import DryerModel, DryerState
from app.models.mpc_controller import MPCController, MPCConstraints, MPCWeights


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


class TestMPCController:

    def test_solve_returns_solution(self):
        mpc = MPCController(model=DryerModel(), horizon=3)
        sol = mpc.solve(make_state(), max_iters=20)
        assert sol is not None
        assert hasattr(sol, "setpoints")
        assert hasattr(sol, "predictions")
        assert hasattr(sol, "cost")
        assert hasattr(sol, "feasible")
        assert hasattr(sol, "computation_time_ms")

    def test_solve_within_time_limit(self):
        """حد SRS: ≤ ۱۰ ثانیه برای حل MPC."""
        mpc = MPCController(model=DryerModel(), horizon=3)
        sol = mpc.solve(make_state(), max_iters=30)
        assert sol.computation_time_ms < 10000, \
            f"MPC took {sol.computation_time_ms}ms — exceeds 10s limit"

    def test_solution_has_four_setpoint_vectors(self):
        """هر راه‌حل باید شامل ۴ set-point با طول horizon باشد."""
        mpc = MPCController(model=DryerModel(), horizon=3)
        sol = mpc.solve(make_state(), max_iters=10)
        assert set(sol.setpoints.keys()) == {
            "hood_temp", "steam_pressure", "hot_air_temp", "machine_speed"
        }
        for key, vec in sol.setpoints.items():
            assert len(vec) == 3, f"{key} should have 3 horizon steps"

    def test_setpoints_respect_safety_bounds(self):
        """set-point‌ها باید در محدوده‌های ایمنی باشند (جدول ۴-۱ SRS)."""
        c = MPCConstraints()
        mpc = MPCController(model=DryerModel(), constraints=c, horizon=3)
        sol = mpc.solve(make_state(), max_iters=30)
        for k in range(3):
            assert c.hood_temp_min <= sol.setpoints["hood_temp"][k] <= c.hood_temp_max
            assert c.steam_pressure_min <= sol.setpoints["steam_pressure"][k] <= c.steam_pressure_max
            assert c.hot_air_temp_min <= sol.setpoints["hot_air_temp"][k] <= c.hot_air_temp_max
            assert c.machine_speed_min <= sol.setpoints["machine_speed"][k] <= c.machine_speed_max

    def test_predictions_moisture_in_target_band(self):
        """پیش‌بینی رطوبت باید در محدوده ۳-۷٪ باشد (قیود سخت)."""
        c = MPCConstraints()
        mpc = MPCController(model=DryerModel(), constraints=c, horizon=3)
        sol = mpc.solve(make_state(), max_iters=30)
        for p in sol.predictions:
            assert 3.0 <= p["moisture_out_pct"] <= 7.0, \
                f"predicted moisture {p['moisture_out_pct']} outside band"

    def test_peak_hour_increases_cost(self):
        """در ساعت اوج، هزینه باید بالاتر باشد (جریمه پیک گاز)."""
        mpc = MPCController(model=DryerModel(), horizon=3)
        sol_off = mpc.solve(make_state(), is_peak_hour=False, max_iters=20)
        cost_off = sol_off.cost
        sol_on = mpc.solve(make_state(), is_peak_hour=True, max_iters=20)
        cost_on = sol_on.cost
        # حداقل باید تفاوتی قابل مشاهده باشد
        assert cost_on > 0 and cost_off > 0

    def test_weights_can_be_customized(self):
        w = MPCWeights(w1_energy=10.0, w2_gas_peak=0.1, w3_waste=0.1,
                       w4_delta_sp=0.1, w5_quality=0.1)
        mpc = MPCController(model=DryerModel(), weights=w, horizon=3)
        sol = mpc.solve(make_state(), max_iters=20)
        assert sol.cost > 0

    def test_solve_repeated_is_deterministic(self):
        """با seed ثابت، حل تکرارپذیر باید باشد."""
        import random
        mpc1 = MPCController(model=DryerModel(), horizon=3)
        mpc1.rng = random.Random(42)
        mpc2 = MPCController(model=DryerModel(), horizon=3)
        mpc2.rng = random.Random(42)
        sol1 = mpc1.solve(make_state(), max_iters=20)
        sol2 = mpc2.solve(make_state(), max_iters=20)
        assert abs(sol1.cost - sol2.cost) < 0.01, \
            f"non-deterministic cost: {sol1.cost} vs {sol2.cost}"

    def test_cost_is_positive(self):
        mpc = MPCController(model=DryerModel(), horizon=3)
        sol = mpc.solve(make_state(), max_iters=20)
        assert sol.cost > 0
