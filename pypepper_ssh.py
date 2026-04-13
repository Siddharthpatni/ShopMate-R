import paramiko
import time

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
        except Exception as e:
            # Fallback for alternative password
            try:
                self.password = "Pepper"
                self.client.connect(self.ip, username=self.username, password=self.password, timeout=5)
                print("✅ Pepper SSH Connected! (Alt password)")
                self._exec('qicli call ALMotion.wakeUp')
            except Exception as e2:
                print(f"⚠️ Pepper SSH failed: {e2}")
                raise ConnectionError(f"Could not SSH into Pepper at {self.ip}")
    
    def _exec(self, cmd: str):
        """Execute a raw shell command on Pepper."""
        try:
            stdin, stdout, stderr = self.client.exec_command(cmd)
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

    def play_animation(self, animation_name: str):
        # Map simple names to NAOqi behavior paths
        behaviors = {
            "Wave": "animations/Stand/Gestures/Hey_1",
            "Bow": "animations/Stand/Gestures/BowShort_1",
            "RaiseHands": "animations/Stand/Gestures/Explain_1"
        }
        path = behaviors.get(animation_name, f"animations/Stand/Gestures/{animation_name}_1")
        # Run async in background (using &) so python doesn't block forever if it's long
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

    def close(self):
        try:
            self.client.close()
        except:
            pass
