# pepper_api.py
# Wrapper for Pepper robot using direct SSH (NAOqi fallback) or pypepper.
# Speech recognition: uses OpenAI Whisper via SSH audio capture.

import time
import os
import tempfile
import paramiko
from config import PEPPER_IP, LOCAL_IP, USE_WHISPER, PEPPER_LISTEN_TIMEOUT, OPENAI_API_KEY

class PepperRobot:
    def __init__(self):
        self.ip = PEPPER_IP
        self.username = "nao"
        self.password = "nao"
        self.connected = False
        
        print(f"[PEPPER] Connecting to {self.ip} over SSH...")
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            self.ssh.connect(self.ip, username=self.username, password=self.password, timeout=5)
            self.connected = True
            print(f"[PEPPER] SSH Connected at {self.ip}")
            
            # Initial setup: wake up and set volume
            self._exec("qicli call ALMotion.wakeUp")
            self._exec("qicli call ALAudioDevice.setOutputVolume 50")
        except Exception as e:
            # Try alternative password
            try:
                self.password = "Pepper"
                self.ssh.connect(self.ip, username=self.username, password=self.password, timeout=5)
                self.connected = True
                print(f"[PEPPER] SSH Connected at {self.ip} (Alt password)")
                self._exec("qicli call ALMotion.wakeUp")
                self._exec("qicli call ALAudioDevice.setOutputVolume 50")
            except Exception as e2:
                print(f"[PEPPER ERROR] SSH Connection failed: {e2}")
                print("[PEPPER] Running in MOCK MODE.")

    def _exec(self, cmd):
        """Execute a NAOqi command via SSH."""
        if not self.connected:
            return ""
        try:
            stdin, stdout, stderr = self.ssh.exec_command(cmd)
            # We don't necessarily wait for all commands (e.g. say might take time)
            # but for setup we might want to.
            return stdout.read().decode('utf-8').strip()
        except Exception as e:
            print(f"[PEPPER SSH ERROR] Exec failed: {e}")
            return ""

    def say(self, text, language="english"):
        if not self.connected:
            print(f"[PEPPER MOCK] say: {text}")
            return
        # Escape for shell
        safe_text = text.replace('"', '\\"').replace("'", "\\'")
        # Run in background so it doesn't block the orchestrator
        self._exec(f'qicli call ALTextToSpeech.say "{safe_text}" &')

    def gesture(self, name):
        if not self.connected: return
        animations = {
            "wave": "animations/Stand/Gestures/Hey_1",
            "point_left": "animations/Stand/Gestures/ShowTablet_1",
            "point_right": "animations/Stand/Gestures/ShowTablet_2",
            "nod": "animations/Stand/Gestures/Yes_1",
            "bow": "animations/Stand/Gestures/BowShort_1",
        }
        anim = animations.get(name)
        if anim:
            self._exec(f'qicli call ALAnimationPlayer.run "{anim}" &')

    def show_on_tablet(self, text):
        if not self.connected: return
        # Displaying text on tablet usually requires a specific URL or HTML
        # For simplicity, we can use ALTabletService.showWebview with a data URL if needed
        # but here we target the main concept's display server
        from config import LOCAL_IP, DISPLAY_PORT
        url = f"http://{LOCAL_IP}:{DISPLAY_PORT}/pepper"
        self._exec(f'qicli call ALTabletService.loadUrl "{url}"')
        self._exec('qicli call ALTabletService.showWebview')

    def show_image(self, url):
        if not self.connected: return
        self._exec(f'qicli call ALTabletService.loadUrl "{url}"')
        self._exec('qicli call ALTabletService.showWebview')

    def clear_tablet(self):
        if not self.connected: return
        self._exec('qicli call ALTabletService.hideWebview')

    def listen(self):
        if not self.connected:
            time.sleep(2)
            return ""

        if USE_WHISPER and OPENAI_API_KEY:
            return self._listen_whisper()
            
        time.sleep(2)
        return ""

    def _listen_whisper(self):
        remote_path = "/home/nao/temp_mic.wav"
        local_path = tempfile.mktemp(suffix=".wav")
        try:
            # Use qicli to record
            # ALAudioRecorder.startMicrophonesRecording(filename, type, samplerate, channels)
            # channels is a list of 4 bools: [left, right, front, rear]
            # We'll use a simple shell command to trigger it
            self._exec(f'qicli call ALAudioRecorder.startMicrophonesRecording "{remote_path}" "wav" 16000 "[1,1,1,1]"')
            
            # Show listening on tablet (via the display server if possible, or direct)
            print("[PEPPER] Listening...")
            time.sleep(PEPPER_LISTEN_TIMEOUT)
            
            self._exec('qicli call ALAudioRecorder.stopMicrophonesRecording')
            
            # Fetch via SFTP
            sftp = self.ssh.open_sftp()
            try:
                sftp.get(remote_path, local_path)
                sftp.remove(remote_path)
            except Exception as fe:
                print(f"[PEPPER W] SFTP fetch failed: {fe}")
                return ""
            finally:
                sftp.close()
            
            # Send to OpenAI
            if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                try:
                    with open(local_path, "rb") as audio_file:
                        transcription = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language="en"
                        )
                    text = transcription.text.strip() if transcription.text else ""
                    if len(text) > 2:
                        print(f"[PEPPER] Heard: {text}")
                        return text
                except Exception as api_e:
                    print(f"[PEPPER ERROR] Whisper API failed: {api_e}")
                    return ""
        except Exception as e:
            print(f"[PEPPER ERROR] Whisper process failed: {e}")
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)
        return ""
