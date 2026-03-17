# pepper_api.py
# Wrapper for Pepper robot using pypepper.
# Falls back to console output on macOS (pypepper is Linux-only).
#
# pypepper connects directly to Pepper's NAOqi runtime (port 9559).
# It also starts a local HTTP server to serve images/text to Pepper's tablet.
# Repo: https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/pypepper.git

import platform
from config import PEPPER_IP, LOCAL_IP


class PepperRobot:
    def __init__(self):
        self.connected = False
        self.robot = None
        self._try_connect()

    def _try_connect(self):
        if platform.system() != "Linux":
            print("[PEPPER] Not on Linux — mock mode (commands print to console)")
            return

        try:
            from pypepper import PepperRobot as PypepperRobot
            self.robot = PypepperRobot(PEPPER_IP, local_ip=LOCAL_IP)
            self.connected = True
            print(f"[PEPPER] Connected at {PEPPER_IP}")
        except ImportError:
            print("[PEPPER] pypepper not installed — mock mode")
        except Exception as e:
            print(f"[PEPPER] Connection failed: {e} — mock mode")

    def say(self, text, language="english"):
        """Make Pepper speak."""
        if self.connected:
            try:
                self.robot.say(text, language=language)
            except Exception as e:
                print(f"[PEPPER ERROR] say: {e}")
        else:
            print(f"  [PEPPER] ({language}): {text}")

    def gesture(self, name):
        """
        Trigger a gesture animation on Pepper.
        Names are mapped to NAOqi animation paths.
        TODO: verify these paths work on our Pepper in the lab.
        """
        animations = {
            "wave": "animations/Stand/Gestures/Hey_1",
            "point_left": "animations/Stand/Gestures/ShowTablet_1",
            "point_right": "animations/Stand/Gestures/ShowTablet_2",
            "nod": "animations/Stand/Gestures/Yes_1",
            "bow": "animations/Stand/Gestures/BowShort_1",
        }
        if self.connected:
            try:
                anim = animations.get(name)
                if anim:
                    self.robot.animate(anim)
                else:
                    print(f"[PEPPER] Unknown gesture: {name}")
            except Exception as e:
                print(f"[PEPPER ERROR] gesture: {e}")
        else:
            print(f"  [PEPPER GESTURE]: {name}")

    def show_on_tablet(self, text):
        """Show text on Pepper's tablet screen."""
        if self.connected:
            try:
                self.robot.show_text(text)
            except Exception as e:
                print(f"[PEPPER ERROR] tablet: {e}")
        else:
            print(f"  [PEPPER TABLET TEXT]: {text}")

    def show_image(self, url):
        """Show image on Pepper's tablet screen."""
        if self.connected:
            try:
                self.robot.show_image(url)
            except Exception as e:
                print(f"[PEPPER ERROR] show_image: {e}")
        else:
            print(f"  [PEPPER TABLET IMAGE]: {url}")

    def wait(self, seconds):
        """Wait for a certain amount of time."""
        if self.connected:
            try:
                self.robot.wait(seconds)
            except Exception as e:
                print(f"[PEPPER ERROR] wait: {e}")
        else:
            import time
            time.sleep(seconds)

    def clear_tablet(self):
        """Clear Pepper's tablet screen."""
        if self.connected:
            try:
                self.robot.clear_tablet()
            except Exception as e:
                print(f"[PEPPER ERROR] clear_tablet: {e}")
        else:
            print(f"  [PEPPER TABLET CLEARED]")

    def listen(self):
        """
        Listen for speech and return transcribed text.
        Returns None in mock mode (text input used instead).
        TODO: check exact pypepper speech recognition method in lab.
        """
        if self.connected:
            try:
                return self.robot.listen()
            except Exception as e:
                print(f"[PEPPER ERROR] listen: {e}")
                return None
        return None
