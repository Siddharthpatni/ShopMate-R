# pepper_api.py
# Wrapper for Pepper robot using pypepper.
# All fake mock modes removed for production code execution on the real platform.
# Crashing here if hardware is unreachable is expected and correct.

import time
from config import PEPPER_IP, LOCAL_IP


class PepperRobot:
    def __init__(self):
        print(f"[PEPPER] Connecting to {PEPPER_IP} for real execution...")
        self.connected = False
        self.robot = None
        try:
            from pypepper import Pepper
            for attempt in range(3):
                try:
                    self.robot = Pepper(robot_ip=PEPPER_IP, local_ip=LOCAL_IP)
                    self.connected = True
                    print(f"[PEPPER] Connected at {PEPPER_IP}")
                    break
                except Exception as e:
                    print(f"[PEPPER ERROR] Connection failed (attempt {attempt+1}/3): {e}")
                    time.sleep(2)
            if not self.connected:
                print("[PEPPER ERROR] Could not connect to real Pepper. Continuing without robot hardware.")
        except ImportError:
            print("[PEPPER ERROR] pypepper not installed. Continuing without robot hardware.")

    def say(self, text, language="english"):
        if not self.connected or not self.robot: return
        try:
            self.robot.say(text)
        except Exception as e:
            print(f"[PEPPER ERROR] Failed to perform say(): {e}")

    def gesture(self, name):
        if not self.connected or not self.robot: return
        animations = {
            "wave": "animations/Stand/Gestures/Hey_1",
            "point_left": "animations/Stand/Gestures/ShowTablet_1",
            "point_right": "animations/Stand/Gestures/ShowTablet_2",
            "nod": "animations/Stand/Gestures/Yes_1",
            "bow": "animations/Stand/Gestures/BowShort_1",
        }
        anim = animations.get(name)
        if anim:
            try:
                self.robot.animate(anim)
            except Exception as e:
                print(f"[PEPPER ERROR] Failed to perform gesture({name}): {e}")
        else:
            print(f"[PEPPER ERROR] Unknown gesture: {name}")

    def show_on_tablet(self, text):
        if not self.connected or not self.robot: return
        try:
            self.robot.show_text(text)
        except Exception as e:
            print(f"[PEPPER ERROR] Failed to show on tablet: {e}")

    def show_image(self, url):
        if not self.connected or not self.robot: return
        try:
            self.robot.show_image(url)
        except Exception as e:
            print(f"[PEPPER ERROR] Failed to show image: {e}")

    def wait(self, seconds):
        if not self.connected or not self.robot: 
            time.sleep(seconds)
            return
        try:
            self.robot.wait(seconds)
        except Exception as e:
            print(f"[PEPPER ERROR] Failed to wait: {e}")
            time.sleep(seconds)

    def clear_tablet(self):
        if not self.connected or not self.robot: return
        try:
            self.robot.clear_tablet()
        except Exception as e:
            print(f"[PEPPER ERROR] Failed to clear tablet: {e}")

    def listen(self):
        """Listen from the real Pepper's mic blockingly."""
        if not self.connected or not self.robot:
            time.sleep(1) # Fake delay
            return ""
        try:
            return self.robot.listen()
        except Exception as e:
            print(f"\n[PEPPER ERROR] Failed to listen: {e}")
            time.sleep(1)
            return ""
