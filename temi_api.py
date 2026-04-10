# temi_api.py
# Wrapper for Temi robot. Uses pytemi for real interaction.

import time
import requests
from config import TEMI_IP, ROBOT_TIMEOUT, DISPLAY_PORT, LOCAL_IP

class TemiRobot:
    def __init__(self):
        self.ip = TEMI_IP
        self.connected = False
        self.robot = None
        
        print(f"[TEMI] Connecting to {self.ip} for real execution...")
        try:
            from pytemi import TemiRobot as Temi
            self.robot = Temi(self.ip)
            self.connected = True
            print(f"[TEMI] Connected at {self.ip}")
        except Exception as e:
            print(f"[TEMI ERROR] Could not connect to Temi at {self.ip}: {e}")
            print("[TEMI] Running in MOCK MODE.")

    def _sync_display(self, **kwargs):
        """Helper to sync Temi status with the orchestrator's display server."""
        try:
            # We call the local display API since it's merged into orchestrator
            # If orchestrator is running, this will work.
            requests.post(f"http://127.0.0.1:{DISPLAY_PORT}/api/display", json=kwargs, timeout=0.5)
        except:
            pass

    def goto(self, location_name):
        """Navigate Temi to a saved location."""
        self._sync_display(temi_status="fetching", temi_destination=location_name)
        if not self.connected:
            print(f"[TEMI MOCK] goto({location_name})")
            time.sleep(2)
            self._sync_display(temi_status="idle", temi_destination="")
            return True
        try:
            self.robot.goto(location_name)
            self._sync_display(temi_status="idle", temi_destination="")
            return True
        except Exception as e:
            print(f"[TEMI ERROR] goto({location_name}) failed: {e}")
            self._sync_display(temi_status="idle")
            return False

    def say(self, text):
        """Make Temi speak."""
        if not self.connected:
            print(f"[TEMI MOCK] say: {text}")
            return
        try:
            self.robot.say(text)
        except Exception as e:
            print(f"[TEMI ERROR] say() failed: {e}")

    def show_url(self, url):
        """Show a URL on Temi's screen."""
        if not self.connected:
            print(f"[TEMI MOCK] show_url: {url}")
            return
        try:
            self.robot.show_image(url)
        except Exception as e:
            print(f"[TEMI ERROR] show_url() failed: {e}")

    def go_home(self):
        """Send Temi back to home base."""
        self.goto("home base")
