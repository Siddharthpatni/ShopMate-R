# temi_api.py
# Wrapper for Temi robot using pytemi.
# pytemi sends HTTP REST requests to TemiMiddleware (Android app on Temi, port 8080).
# All calls are blocking — they return after the action completes.
# Works on any OS (it's just HTTP).
#
# IMPORTANT: TemiMiddleware must be running on Temi before connecting.
# Repo: https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/pytemi.git
# Middleware: https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/temi-middleware.git

from config import TEMI_IP


class TemiRobot:
    def __init__(self):
        self.connected = False
        self.robot = None
        self._try_connect()

    def _try_connect(self):
        try:
            from pytemi import TemiRobot as Temi
            self.robot = Temi(TEMI_IP)
            self.connected = True
            print(f"[TEMI] Connected at {TEMI_IP}")
        except ImportError:
            print("[TEMI] pytemi not installed — mock mode")
        except Exception as e:
            print(f"[TEMI] Connection failed: {e} — mock mode")

    def goto(self, location_name):
        """
        Navigate Temi to a saved location.
        Blocks until Temi arrives.
        Location names must match what's saved on Temi's map.
        """
        if self.connected:
            try:
                self.robot.goto(location_name)
                return True
            except Exception as e:
                print(f"[TEMI ERROR] goto: {e}")
                return False
        else:
            print(f"  [TEMI GOTO]: {location_name}")
            return True

    def say(self, text, language="english", animation=False):
        """Make Temi speak through its speaker. Blocks until done."""
        if self.connected:
            try:
                self.robot.say(text, language=language, animation=animation)
            except Exception as e:
                print(f"[TEMI ERROR] say: {e}")
        else:
            print(f"  [TEMI SAYS] ({language}): {text}")

    def show_image(self, url):
        """Show image on Temi's screen."""
        if self.connected:
            try:
                self.robot.show_image(url)
            except Exception as e:
                print(f"[TEMI ERROR] show_image: {e}")
        else:
            print(f"  [TEMI SCREEN IMAGE]: {url}")

    def wait(self, seconds):
        """Wait for a certain amount of time."""
        if self.connected:
            try:
                self.robot.wait(seconds)
            except Exception as e:
                print(f"[TEMI ERROR] wait: {e}")
        else:
            import time
            time.sleep(seconds)

    def clear_tablet(self):
        """Clear Temi's screen."""
        if self.connected:
            try:
                self.robot.clear_tablet()
            except Exception as e:
                print(f"[TEMI ERROR] clear_tablet: {e}")
        else:
            print(f"  [TEMI SCREEN CLEARED]")

    def go_home(self):
        """Send Temi back to home base / charging station."""
        self.goto("home base")
