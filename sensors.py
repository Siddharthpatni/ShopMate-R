# sensors.py
# Reads distance sensor from M5Stack Core2 via REST.
# Detects item pickups: if distance suddenly increases, something was removed.

import requests
from config import M5STACK_URL, PICKUP_DISTANCE_THRESHOLD


class ShelfSensor:
    def __init__(self):
        self.last_distance = None
        self.connected = False

    def read_distance(self):
        """Read current distance in cm from M5Stack. Returns None if unreachable."""
        try:
            r = requests.get(f"{M5STACK_URL}/distance", timeout=3)
            r.raise_for_status()
            self.connected = True
            return r.json().get("distance_cm")
        except requests.RequestException:
            self.connected = False
            return None

    def check_pickup(self):
        """
        Returns True if an item was picked up since last reading.
        Logic: distance increased by more than threshold = something removed.
        """
        current = self.read_distance()
        if current is None:
            return False

        if self.last_distance is not None:
            if current - self.last_distance > PICKUP_DISTANCE_THRESHOLD:
                self.last_distance = current
                return True

        self.last_distance = current
        return False
