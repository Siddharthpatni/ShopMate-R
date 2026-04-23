import paramiko
import time
import config

class PepperRobotSSH:
    """
    Drop-in replacement for PepperRobot that bypasses the x86 `qi` requirement 
    by executing native NAOqi commands directly over SSH to Pepper's internal OS.
    """
    
    def __init__(self, ip: str, local_ip: str = "0.0.0.0", port: int = 9559):
        self.ip = ip
        self.username = "nao"
        self.password = "nao"
        
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        print(f"🔌 Connecting to Pepper brain over SSH ({self.ip})...")
        try:
            self.client.connect(self.ip, username=self.username, password=self.password, timeout=5)
            print("✅ Pepper SSH Connected!")
            
            # Wake up robot and reset posture
            self._exec('qicli call ALMotion.wakeUp')
            self._exec('qicli call ALAudioDevice.setMicrophoneGain 100')
            self._exec(f'qicli call ALAudioDevice.setOutputVolume {config.PEPPER_VOLUME}')
        except Exception as e:
            # Fallback for alternative password
            try:
                self.password = "Pepper"
                self.client.connect(self.ip, username=self.username, password=self.password, timeout=5)
                print("✅ Pepper SSH Connected! (Alt password)")
                self._exec('qicli call ALMotion.wakeUp')
                self._exec('qicli call ALAudioDevice.setMicrophoneGain 100')
                self._exec(f'qicli call ALAudioDevice.setOutputVolume {config.PEPPER_VOLUME}')
            except Exception as e2:
                print(f"⚠️ Pepper SSH failed: {e2}")
                raise ConnectionError(f"Could not SSH into Pepper at {self.ip}")
    
    def _exec(self, cmd: str, timeout: int = 30):
        """Execute a raw shell command on Pepper."""
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd, timeout=timeout)
            stdout.channel.recv_exit_status()  # Block until done
            return stdout.read().decode('utf-8').strip()
        except Exception as e:
            print(f"⚠️ SSH Exec failed: {e}")
            return ""

    def say(self, text: str, language: str = "english"):
        # Escape quotes for bash
        safe_text = text.replace('"', '\\"').replace("'", "\\'")
        self._exec(f'qicli call ALTextToSpeech.say "{safe_text}"')

    def set_system_volume(self, volume: int):
        self._exec(f'qicli call ALAudioDevice.setOutputVolume {volume}')

    def play_animation(self, animation_name: str, wait: bool = False):
        # Map simple names to NAOqi behavior paths
        behaviors = {
            "Wave": "animations/Stand/Gestures/Hey_1",
            "Bow": "animations/Stand/Gestures/BowShort_1",
            "RaiseHands": "animations/Stand/Gestures/Explain_1",
            "Thinking": "animations/Stand/Gestures/Thinking_1"
        }
        
        # If it's a known short name, use the mapped path
        if animation_name in behaviors:
            path = behaviors[animation_name]
        # If it already looks like a path (starts with animations/), use as-is
        elif animation_name.startswith("animations/"):
            path = animation_name
        # Otherwise, assume it's a short gesture name and wrap it
        else:
            path = f"animations/Stand/Gestures/{animation_name}"
            if not path.endswith("_1"):
                path += "_1"

        # Run async by default so we don't block, unless wait=True
        if wait:
            self._exec(f'qicli call ALAnimationPlayer.run "{path}"')
        else:
            self._exec(f'qicli call ALAnimationPlayer.run "{path}" > /dev/null 2>&1 &')

    def show_image(self, url: str):
        # By using loadUrl directly, we support both images and web dashboards
        self._exec(f'qicli call ALTabletService.loadUrl "{url}"')
        self._exec('qicli call ALTabletService.showWebview')

    def show_html(self, html_content: str):
        """Display an HTML string on the tablet using a data URI."""
        import urllib.parse
        encoded = urllib.parse.quote(html_content)
        data_uri = f"data:text/html;charset=utf-8,{encoded}"
        self._exec(f'qicli call ALTabletService.loadUrl "{data_uri}"')
        self._exec('qicli call ALTabletService.showWebview')

    def clear_tablet(self):
        self._exec('qicli call ALTabletService.hideWebview')

    def record_audio(self, duration_sec: float, output_path: str):
        """Record audio from Pepper's front microphone via NAOqi.

        Tries multiple methods:
          1. ALAudioRecorder (NAOqi native — most reliable)
          2. arecord with various ALSA devices
        """
        import time
        remote_tmp = "/tmp/pepper_mic.wav"
        dur = int(duration_sec)
        print(f"🎤 Pepper recording for {dur}s...")

        # Remove old file first
        self._exec(f'rm -f {remote_tmp}', timeout=3)

        recorded = False

        # --- Method 1: NAOqi ALAudioRecorder ---
        # Stop any leftover recording
        self._exec('qicli call ALAudioRecorder.stopMicrophonesRecording', timeout=3)

        # qicli wants bare args, NOT extra-quoted strings
        start_cmd = (
            f'qicli call ALAudioRecorder.startMicrophonesRecording '
            f'{remote_tmp} wav 16000 [0,0,1,0]'
        )
        result = self._exec(start_cmd, timeout=5)
        print(f"   ALAudioRecorder result: {result!r}")

        # Check if file appeared (recording started)
        time.sleep(0.5)
        check = self._exec(f'ls -la {remote_tmp} 2>/dev/null', timeout=3)

        if check and "No such file" not in check:
            # Recording is running — wait for the duration
            time.sleep(dur)
            self._exec('qicli call ALAudioRecorder.stopMicrophonesRecording', timeout=5)
            time.sleep(0.3)
            # Verify file has content
            size_check = self._exec(f'stat -c %s {remote_tmp} 2>/dev/null', timeout=3)
            if size_check and int(size_check) > 1000:
                recorded = True
                print(f"   ALAudioRecorder OK — {size_check} bytes")

        # --- Method 2: arecord with multiple devices ---
        if not recorded:
            self._exec('qicli call ALAudioRecorder.stopMicrophonesRecording', timeout=3)
            print("⚠️ ALAudioRecorder didn't produce audio, trying arecord...")
            self._exec(f'rm -f {remote_tmp}', timeout=3)

            # Try several ALSA device names
            devices = ["default", "plughw:0,0", "hw:0,0", "plughw:0,1", "pulse"]
            for dev in devices:
                self._exec(f'rm -f {remote_tmp}', timeout=3)
                arecord_cmd = (
                    f"arecord -D {dev} -d {dur} -f S16_LE "
                    f"-r 16000 -c 1 {remote_tmp} 2>/dev/null"
                )
                self._exec(arecord_cmd, timeout=dur + 5)

                size_check = self._exec(f'stat -c %s {remote_tmp} 2>/dev/null', timeout=3)
                if size_check and size_check.isdigit() and int(size_check) > 1000:
                    recorded = True
                    print(f"   arecord OK with device '{dev}' — {size_check} bytes")
                    break
                else:
                    print(f"   arecord device '{dev}' failed")

        if not recorded:
            print("❌ All recording methods failed on Pepper")
            return

        # Download the recorded file
        self.download_file(remote_tmp, output_path)

    def download_file(self, remote_path: str, local_path: str):
        """Download a file from Pepper via SCP."""
        try:
            sftp = self.client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
        except Exception as e:
            print(f"⚠️ Failed to download file from Pepper: {e}")

    def close(self):
        try:
            self.client.close()
        except:
            pass
