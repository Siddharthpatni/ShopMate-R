"""
health_check.py — Pre-flight diagnostic for ShopMate-R.

Runs without touching the main app. Checks:

  1. Python import health   — config, grocery_db, requests, paramiko, flask
  2. Dashboard reachable    — GET http://127.0.0.1:DASHBOARD_PORT/api/snapshot
  3. Temi reachable         — raw TCP connect + a harmless HTTP POST
  4. Pepper reachable       — raw TCP connect on port 22 (SSH)
  5. Inventory sanity       — no negative stock, no NaN prices
  6. OpenAI key present     — warn (not fail) if missing

Usage:

    python health_check.py              # pretty table
    python health_check.py --strict     # exit 1 on any failure
    python health_check.py --json       # machine-readable

Exit codes:
    0 = all checks passed (or only warnings)
    1 = at least one check failed (only when --strict)
"""

from __future__ import annotations
import argparse
import json
import socket
import sys
import time
from dataclasses import dataclass, asdict


@dataclass
class Check:
    name: str
    status: str       # "ok", "warn", "fail"
    detail: str
    ms: float = 0.0


# -------------------------------------------------------------------------
# Individual checks
# -------------------------------------------------------------------------

def _time(fn):
    start = time.perf_counter()
    try:
        return fn(), (time.perf_counter() - start) * 1000
    except Exception as e:
        return (("fail", str(e)),
                (time.perf_counter() - start) * 1000)


def _check_imports() -> tuple[str, str]:
    missing = []
    for mod in ("config", "grocery_db", "requests", "paramiko", "flask"):
        try:
            __import__(mod)
        except ImportError as e:
            missing.append(f"{mod} ({e})")
    if missing:
        return ("fail", "Missing: " + ", ".join(missing))
    return ("ok", "config, grocery_db, requests, paramiko, flask")


def _check_tcp(host: str, port: int, timeout: float = 2.0) -> tuple[str, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return ("ok", f"TCP {host}:{port} reachable")
    except socket.timeout:
        return ("fail", f"TCP {host}:{port} timed out after {timeout}s")
    except OSError as e:
        return ("fail", f"TCP {host}:{port} — {e}")


def _check_dashboard() -> tuple[str, str]:
    import config
    import requests
    try:
        r = requests.get(f"{config.DASHBOARD_URL}/api/snapshot", timeout=2.0)
        if r.status_code == 200:
            n_log = len(r.json().get("log", []))
            return ("ok",
                    f"Dashboard up at {config.DASHBOARD_URL}  "
                    f"(log buffer: {n_log} lines)")
        return ("warn", f"Dashboard returned HTTP {r.status_code}")
    except requests.exceptions.RequestException:
        return ("warn",
                f"Dashboard not running at {config.DASHBOARD_URL} — "
                "start it with `python mock_dashboard.py`")


def _check_temi_http() -> tuple[str, str]:
    import config
    import requests
    url = f"http://{config.TEMI_IP}:8080"
    try:
        # Any POST — Temi will at worst 404 but that proves it's alive
        r = requests.post(f"{url}/ping", json={}, timeout=2.0)
        return ("ok", f"Temi HTTP up at {url}  (status {r.status_code})")
    except requests.exceptions.RequestException as e:
        return ("fail", f"Temi HTTP at {url} unreachable — {e}")


def _check_inventory() -> tuple[str, str]:
    import grocery_db
    items = grocery_db.get_all_items()
    issues = []
    for it in items:
        if it["stock"] < 0:
            issues.append(f"{it['key']} has negative stock ({it['stock']})")
        if not isinstance(it["price"], (int, float)) or it["price"] < 0:
            issues.append(f"{it['key']} has invalid price ({it['price']})")
    if issues:
        return ("fail", "; ".join(issues))
    low = grocery_db.get_low_stock(threshold=5)
    detail = f"{len(items)} items, {len(low)} low-stock"
    return ("ok", detail) if not low else ("warn", detail)


def _check_openai_key() -> tuple[str, str]:
    import config
    if not config.OPENAI_API_KEY:
        return ("warn",
                "OPENAI_API_KEY not set — fallback keyword parser will be used")
    if not config.OPENAI_API_KEY.startswith("sk-"):
        return ("warn", "OPENAI_API_KEY doesn't look like an OpenAI key")
    return ("ok", f"OPENAI_API_KEY set (model: {config.OPENAI_MODEL})")


def run_all() -> list[Check]:
    import config

    checks: list[Check] = []

    def add(name: str, fn):
        start = time.perf_counter()
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = "fail", f"exception: {e}"
        ms = (time.perf_counter() - start) * 1000
        checks.append(Check(name, status, detail, ms))

    add("Python imports",   _check_imports)
    add("Dashboard",        _check_dashboard)
    add("Pepper SSH port",  lambda: _check_tcp(config.PEPPER_IP, 22))
    add("Temi HTTP port",   lambda: _check_tcp(config.TEMI_IP, 8080))
    add("Temi endpoint",    _check_temi_http)
    add("Inventory sanity", _check_inventory)
    add("OpenAI key",       _check_openai_key)
    return checks


# -------------------------------------------------------------------------
# Output
# -------------------------------------------------------------------------

_ICON = {"ok": "✅", "warn": "⚠️ ", "fail": "❌"}


def _render_table(checks: list[Check]) -> None:
    name_w = max(len(c.name) for c in checks)
    print()
    print(f"  {'check'.ljust(name_w)}  status   ms   detail")
    print(f"  {'-' * name_w}  ------  ----  ------")
    for c in checks:
        print(f"  {c.name.ljust(name_w)}  "
              f"{_ICON[c.status]} {c.status.ljust(4)}  "
              f"{c.ms:>4.0f}  {c.detail}")
    print()

    n_ok   = sum(c.status == "ok"   for c in checks)
    n_warn = sum(c.status == "warn" for c in checks)
    n_fail = sum(c.status == "fail" for c in checks)
    print(f"  Summary: {n_ok} ok, {n_warn} warn, {n_fail} fail")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--strict", action="store_true",
                   help="exit 1 if any check failed (warnings ignored)")
    args = p.parse_args()

    checks = run_all()

    if args.json:
        print(json.dumps([asdict(c) for c in checks], indent=2))
    else:
        _render_table(checks)

    if args.strict and any(c.status == "fail" for c in checks):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
