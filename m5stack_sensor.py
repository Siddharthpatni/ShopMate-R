"""
m5stack_sensor.py — simulator for the shelf distance sensors.

The paper describes M5Stack microcontrollers with infrared time-of-flight
modules placed on shelves. When a customer picks up an item the distance
to the shelf increases, and the sensor POSTs an event to the orchestrator
so the stock count is decremented automatically.

This file is a simulator you can run on your laptop to fake those events:

    python m5stack_sensor.py milk
    python m5stack_sensor.py "almond milk"

On real hardware the M5Stack would send the same JSON payload to
   POST http://<dashboard>/api/sensor
"""

import sys
import requests

from config import DASHBOARD_URL


def send_taken(item: str):
    r = requests.post(
        f"{DASHBOARD_URL}/api/sensor",
        json={"item": item, "event": "taken"},
        timeout=2.0,
    )
    print(f"sensor → {item!r} taken:", r.json())


def send_restocked(item: str, n: int = 1):
    r = requests.post(
        f"{DASHBOARD_URL}/api/sensor",
        json={"item": item, "event": "restocked", "n": n},
        timeout=2.0,
    )
    print(f"sensor → {item!r} restocked:", r.json())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python m5stack_sensor.py <item> [taken|restocked]")
        sys.exit(1)
    item = sys.argv[1]
    event = sys.argv[2] if len(sys.argv) > 2 else "taken"
    if event == "restocked":
        send_restocked(item)
    else:
        send_taken(item)
