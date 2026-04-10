# pepper_api.py
# Wrapper for Pepper robot using pypepper.
# Speech recognition: uses pypepper's listen() for real hardware,
# with optional OpenAI Whisper fallback (set USE_WHISPER=true in .env).
# When no hardware is available, returns empty so text input works instead.

import time
import os
import tempfile
from config import PEPPER_IP, LOCAL_IP, USE_WHISPER, PEPPER_LISTEN_TIMEOUT, OPENAI_API_KEY


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
        if not self.connected or not self.robot:
            print(f"[PEPPER MOCK] say: {text}")
            return
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
        """
        Listen for customer speech via Pepper's microphone.

        Strategy:
        1. If connected to real Pepper → use pypepper's listen()
        2. If USE_WHISPER is enabled and pypepper listen fails → record audio
           from Pepper's mic, send to OpenAI Whisper for transcription
        3. If no hardware → return empty (text input thread handles input instead)

        Returns transcribed text or empty string.
        """
        if not self.connected or not self.robot:
            # No hardware — let the text input thread handle input
            time.sleep(1)
            return ""

        # --- Primary: pypepper's built-in listen ---
        text = self._listen_pypepper()
        if text and len(text.strip()) > 1:
            return text.strip()

        # --- Fallback: record audio + Whisper ---
        if USE_WHISPER:
            text = self._listen_whisper()
            if text and len(text.strip()) > 1:
                return text.strip()

        return ""

    def _listen_pypepper(self):
        """Use pypepper's native speech recognition (NAOqi-based)."""
        try:
            result = self.robot.listen()
            if result and isinstance(result, str) and len(result.strip()) > 1:
                return result.strip()
            return ""
        except Exception as e:
            print(f"\n[PEPPER ERROR] listen() failed: {e}")
            time.sleep(0.5)
            return ""

    def _listen_whisper(self):
        """
        Record audio from Pepper's microphone, then transcribe with OpenAI Whisper.
        Requires OPENAI_API_KEY set in config.
        """
        if not OPENAI_API_KEY:
            print("[PEPPER] Whisper fallback skipped — no OPENAI_API_KEY")
            return ""

        audio_path = None
        try:
            # Record audio from Pepper's mic to a temp file
            audio_path = tempfile.mktemp(suffix=".wav")
            self.robot.record_audio(audio_path, PEPPER_LISTEN_TIMEOUT)

            # Check file exists and has content
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
                return ""

            # Send to OpenAI Whisper API
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            with open(audio_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"
                )
            text = transcription.text.strip() if transcription.text else ""

            # Filter noise / very short garbage
            if len(text) < 2:
                return ""

            print(f"[PEPPER WHISPER] Transcribed: {text}")
            return text

        except Exception as e:
            print(f"[PEPPER ERROR] Whisper transcription failed: {e}")
            return ""
        finally:
            # Clean up temp audio file
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except OSError:
                    pass
