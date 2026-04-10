# temi_api.py
# Wrapper for Temi robot using pytemi.
# pytemi sends HTTP REST requests to TemiMiddleware (Android app on Temi, port 8080).
# Graceful fallback: if pytemi is not installed or Temi is unreachable, methods
# log warnings instead of crashing the orchestrator.

from config import TEMI_IP, ROBOT_TIMEOUT


class TemiRobot:
    def __init__(self):
        print(f"[TEMI] Connecting to {TEMI_IP} for real execution...")
        self.connected = False
        self.robot = None
        try:
            from pytemi import TemiRobot as Temi
            self.robot = Temi(TEMI_IP)
            self.connected = True
            print(f"[TEMI] Connected at {TEMI_IP}")
        except ImportError:
            print("[TEMI ERROR] pytemi not installed. Temi commands will be logged only.")
        except Exception as e:
            print(f"[TEMI ERROR] Could not connect to Temi at {TEMI_IP}: {e}")
            print("[TEMI] Temi commands will be logged only.")

    def goto(self, location_name):
        """
        Navigate Temi to a saved location.
        Blocks until Temi arrives.
        Location names must match what's saved on Temi's map.
        """
        if not self.connected or not self.robot:
            print(f"[TEMI MOCK] goto({location_name})")
            return True
        try:
            self.robot.goto(location_name)
            return True
        except Exception as e:
            print(f"[TEMI ERROR] goto({location_name}) failed: {e}")
            return False

    def say(self, text):
        """Make Temi speak through its speaker. Blocks until done."""
        if not self.connected or not self.robot:
            print(f"[TEMI MOCK] say: {text}")
            return
        try:
            self.robot.say(text)
        except Exception as e:
            print(f"[TEMI ERROR] say() failed: {e}")

    def go_home(self):
        """Send Temi back to home base / charging station."""
        self.goto("home base")
