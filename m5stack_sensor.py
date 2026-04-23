"""
m5stack_sensor.py — CLI simulator for the M5Stack IoT shelf sensors.

Each shelf in the store has an M5Stack unit with a load cell that
detects when an item is picked up or placed back. In the real
deployment the sensor firmware POSTs to the dashboard's /api/sensor
endpoint; this script lets you post the same events from a laptop
so you can demo the system without physical hardware.

Usage:

    python m5stack_sensor.py milk                 # default: taken, 1
    python m5stack_sensor.py bananas taken
    python m5stack_sensor.py milk restocked 3
    python m5stack_sensor.py --list               # show available items
    python m5stack_sensor.py --url http://host:5050 milk

Environment:
    SHOPMATE_DASHBOARD  — overrides the dashboard URL.
"""

from __future__ import annotations
import argparse
import os
import sys

import requests

import config
import grocery_db


DEFAULT_URL = os.environ.get("SHOPMATE_DASHBOARD", config.DASHBOARD_URL)


def post_event(url: str, item: str, event: str, count: int) -> int:
    endpoint = f"{url.rstrip('/')}/api/sensor"
    try:
        r = requests.post(
            endpoint,
            json={"item": item, "event": event, "count": count},
            timeout=3.0,
        )
    except requests.exceptions.RequestException as e:
        print(f"❌ Could not reach dashboard at {endpoint}")
        print(f"   {e}")
        print("   Is mock_dashboard.py running?")
        return 2

    if r.status_code == 200 and r.json().get("ok"):
        body = r.json()
        verb = "TAKEN" if event == "taken" else "RESTOCKED"
        print(f"✅ {verb} {count}× {body['item']}  →  new stock: {body['new_stock']}")
        return 0

    try:
        err = r.json().get("error", r.text)
    except Exception:
        err = r.text
    print(f"❌ Dashboard returned {r.status_code}: {err}")
    return 1


def print_catalogue() -> None:
    print("Available items (use the key on the left):\n")
    for key, data in sorted(grocery_db.GROCERIES.items()):
        print(f"  {key:<20} — {data['name']:<30} "
              f"[{data['category']:<9}] stock={data['stock']}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m5stack_sensor",
        description="Simulate an M5Stack shelf sensor event.",
    )
    p.add_argument("item", nargs="?", help="grocery item key (e.g. 'milk')")
    p.add_argument(
        "event", nargs="?", default="taken",
        choices=["taken", "restocked", "restock", "added"],
        help="event type (default: taken)",
    )
    p.add_argument(
        "count", nargs="?", type=int, default=1,
        help="how many units (default: 1)",
    )
    p.add_argument("--list", action="store_true",
                   help="list available items and exit")
    p.add_argument("--url", default=DEFAULT_URL,
                   help=f"dashboard URL (default: {DEFAULT_URL})")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list or not args.item:
        print_catalogue()
        return 0

    if args.count < 1:
        print("❌ count must be >= 1")
        return 1

    # Normalise alias events to what the dashboard expects
    event = "restocked" if args.event in ("restock", "added") else args.event
    return post_event(args.url, args.item.lower(), event, args.count)


if __name__ == "__main__":
    sys.exit(main())
