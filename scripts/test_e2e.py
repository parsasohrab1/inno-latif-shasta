#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست end-to-end سرور FastAPI و یکپارچه‌سازی با MPC و داشبورد.

روش:
  ۱) سرور uvicorn را در process جدا با PYTHONPATH اجرا می‌کند
  ۲) ۸ ثانیه صبر می‌کند تا شبیه‌ساز OPC-UA چند نمونه تولید کند
  ۳) API ها را با urllib فرا می‌خواند و خروجی را تأیید می‌کند
  ۴) سرور را متوقف می‌کند
"""

import sys
import os
import time
import json
import subprocess
import urllib.request
import urllib.error
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "127.0.0.1"
PORT = 8765
BASE = f"http://{HOST}:{PORT}"


def fetch(path, method="GET", data=None, timeout=5):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if body:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    env = os.environ.copy()
    env["PYTHONPATH"] = REPO
    env["LATIF_PORT"] = str(PORT)
    env["LATIF_OPCUA_SIM_ENABLED"] = "true"
    env["LATIF_OPCUA_INTERVAL_SEC"] = "1"  # سریع‌تر برای تست

    print("→ Starting uvicorn on port", PORT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", HOST, "--port", str(PORT), "--log-level", "warning"],
        cwd=REPO, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )

    failures = []
    try:
        # صبر برای بالا آمدن سرور
        for i in range(15):
            time.sleep(1)
            try:
                h = fetch("/api/health", timeout=2)
                if h.get("status") == "ok":
                    print(f"✅ Server up after {i+1}s: {h['name']} v{h['version']}")
                    break
            except Exception:
                continue
        else:
            print("❌ Server did not come up")
            failures.append("server_start")
            return

        # صبر برای تولید داده
        print("→ Waiting 5s for OPC-UA simulator to produce data...")
        time.sleep(5)

        # تست ۱: /api/status
        print("\n[1] GET /api/status")
        s = fetch("/api/status")
        print(f"    historian count: {s['historian']['count']}")
        print(f"    opcua step: {s['opcua']['step']}")
        if s['historian']['count'] == 0:
            failures.append("status_no_data")
        else:
            print("    ✅ data being produced")

        # تست ۲: /api/sensors/latest
        print("\n[2] GET /api/sensors/latest")
        sl = fetch("/api/sensors/latest")
        print(f"    hood_temp: {sl.get('hood_temp_c')} °C")
        print(f"    moisture_out: {sl.get('moisture_out_pct')} %")
        print(f"    production: {sl.get('production_th')} t/h")
        print(f"    energy_intensity: {sl.get('thermal_energy_intensity_kWht')} kWh/t")
        if not sl or sl.get('error'):
            failures.append("sensors_latest")

        # تست ۳: /api/sensors/history
        print("\n[3] GET /api/sensors/history?n=10")
        h = fetch("/api/sensors/history?n=10")
        print(f"    samples: {h['count']}")
        if h['count'] == 0:
            failures.append("history_empty")

        # تست ۴: POST /api/mpc/solve
        print("\n[4] POST /api/mpc/solve")
        r = fetch("/api/mpc/solve", method="POST", data={"operator": "test"})
        if r.get('error'):
            print(f"    ❌ {r.get('error')}: {r.get('message')}")
            failures.append("mpc_solve")
        else:
            sol = r['solution']
            print(f"    cost: {sol['cost']}")
            print(f"    feasible: {sol['feasible']}")
            print(f"    ms: {sol['computation_time_ms']}")
            print(f"    setpoint hood[0]: {sol['setpoints']['hood_temp'][0]:.1f}")
            print(f"    setpoint steam[0]: {sol['setpoints']['steam_pressure'][0]:.2f}")
            print(f"    moisture pred t+15: {r['moisture_prediction']['pred_pct'][2]}")
            if not sol['feasible']:
                failures.append("mpc_infeasible")

        # تست ۵: POST /api/mpc/mode
        print("\n[5] POST /api/mpc/mode (advisory)")
        m = fetch("/api/mpc/mode", method="POST", data={"mode": "advisory", "operator": "test"})
        print(f"    from: {m.get('from')} → to: {m.get('to')}")
        if m.get('to') != 'advisory':
            failures.append("mode_change")

        # تست ۶: POST /api/mpc/apply
        print("\n[6] POST /api/mpc/apply (approved=true)")
        a = fetch("/api/mpc/apply", method="POST", data={"approved": True, "operator": "test"})
        print(f"    applied: {a.get('applied')}")
        print(f"    setpoint: {a.get('setpoint')}")
        if not a.get('applied'):
            failures.append("apply_failed")

        # تست ۷: GET /api/kpi
        print("\n[7] GET /api/kpi")
        k = fetch("/api/kpi")
        print(f"    energy: {k.get('thermal_intensity_kWht')} kWh/t (base {k.get('thermal_baseline_kWht')})")
        print(f"    reduction: {k.get('thermal_reduction_pct')}% (target {k.get('thermal_target_reduction_pct')}%)")
        print(f"    gas peak: {k.get('gas_peak_nm3h')} (base {k.get('gas_peak_baseline_nm3h')})")
        print(f"    waste: {k.get('waste_pct')}%")
        if k.get('error'):
            failures.append("kpi")

        # تست ۸: GET /api/audit
        print("\n[8] GET /api/audit?n=10")
        al = fetch("/api/audit?n=10")
        print(f"    entries: {len(al.get('entries', []))}")
        for e in al.get('entries', [])[-3:]:
            print(f"    - {e['event_type']} by {e['operator']}")
        if not al.get('entries'):
            failures.append("audit_empty")

        # تست ۹: GET / (root - dashboard)
        print("\n[9] GET / (dashboard)")
        try:
            with urllib.request.urlopen(BASE + "/", timeout=5) as resp:
                ct = resp.headers.get('content-type', '')
                content = resp.read().decode()
                if 'text/html' in ct and 'دوقلوی دیجیتال' in content:
                    print(f"    ✅ dashboard HTML served ({len(content)} bytes)")
                else:
                    print(f"    ⚠ content-type: {ct}")
                    failures.append("dashboard_not_html")
        except Exception as e:
            print(f"    ❌ {e}")
            failures.append("dashboard_fetch")

        # تست ۱۰: GET /api/mpc/solution
        print("\n[10] GET /api/mpc/solution")
        sol2 = fetch("/api/mpc/solution")
        print(f"    cost: {sol2.get('cost')}")
        print(f"    mode: {sol2.get('mode')}")
        if sol2.get('error'):
            failures.append("solution_persist")

    finally:
        print("\n→ Stopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print("    stopped")

    print("\n" + "="*50)
    if failures:
        print(f"❌ {len(failures)} failure(s): {failures}")
        sys.exit(1)
    else:
        print("✅ همه تست‌ها موفق بودند (۱۰/۱۰)")
        sys.exit(0)


if __name__ == "__main__":
    main()
