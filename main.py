"""
main.py — ShopMate-R entry point.

Runs a multi-customer loop:
  • Pepper greets a customer.
  • Customer speaks or types one request.
  • Orchestrator dispatches Pepper + Temi.
  • After Temi delivers the item, Pepper says BYE.
  • The loop resets and waits for the next customer.

Ctrl-C (or typing "shutdown") exits the program completely.
"""

import sys
import time
import subprocess

import requests

import config
import orchestrator
from pepper_api import (
    pepper_mic_active,
    pepper_prompt_listen,
    pepper_close,
    pepper_say,
    pepper_listen,
    pepper_show_welcome,
    pepper_show_goodbye,
    pepper_show_idle,
    pepper_show_categories,
    pepper_wave_hello,
)
from temi_api import (
    temi_mic_active,
    temi_prompt_listen,
    temi_show_message,
)


# =========================================================================
# Mirror stdout to the dashboard /api/log endpoint so staff see logs live
# =========================================================================

class TeeWriter:
    def __init__(self, original):
        self.original = original

    def write(self, text):
        self.original.write(text)
        if text.strip():
            try:
                requests.post(
                    f"{config.DASHBOARD_URL}/api/log",
                    json={"line": text.rstrip()},
                    timeout=0.5,
                )
            except Exception:
                pass

    def flush(self):
        self.original.flush()


# =========================================================================
# Dashboard launcher
# =========================================================================

def start_dashboard():
    print(f"📊 Starting ShopMate-R dashboard on port {config.DASHBOARD_PORT}...")
    try:
        subprocess.Popen(
            [sys.executable, "mock_dashboard.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"[main] Could not start dashboard: {e}")
    time.sleep(1.5)


# =========================================================================
# Microphone input
# =========================================================================

# Track consecutive mic failures so we can fall back to keyboard
_mic_fail_count = 0
_MIC_FAIL_LIMIT = 3


def listen_from_microphone() -> str:
    global _mic_fail_count

    if pepper_mic_active():
        pepper_prompt_listen("I'm listening, what do you need?")
        text = pepper_listen(timeout=6.0)
        if text:
            _mic_fail_count = 0  # reset on success
            return text
        else:
            _mic_fail_count += 1
            if _mic_fail_count >= _MIC_FAIL_LIMIT:
                print(f"\n⚠️  Mic failed {_mic_fail_count} times — switching to keyboard.")
                print("   (Type your request instead)")
                try:
                    return input("👤 You (keyboard): ")
                except EOFError:
                    return "shutdown"
            return ""

    try:
        import speech_recognition as sr
    except ImportError:
        print("[main] speech_recognition not installed — falling back to text input")
        return input("👤 You: ")

    if temi_mic_active():
        temi_prompt_listen("Tell me what you need.")

    owner = "Temi" if temi_mic_active() else "PC"
    print(f"🎙️  Listening via {owner}...")

    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=6, phrase_time_limit=8)
        text = r.recognize_google(audio)
        print(f"👤 ({owner} mic) Customer: {text}")
        _mic_fail_count = 0
        return text
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        print("[mic] Could not understand audio")
        return ""
    except Exception as e:
        print(f"[mic] Error: {e}")
        return ""


def read_customer_input() -> str:
    if config.MIC_MODE and (pepper_mic_active() or temi_mic_active()):
        return listen_from_microphone()
    try:
        return input("👤 You: ")
    except EOFError:
        return "shutdown"


# =========================================================================
# Banner
# =========================================================================

def print_banner():
    print("=" * 64)
    print("  🛒  ShopMate-R — Multi-Robot Grocery Assistant")
    print("      Pepper (front desk)  +  Temi (mobile shelf runner)")
    print("=" * 64)
    print(f"  MIC_MODE     : {config.MIC_MODE}   "
          f"(Pepper={config.PEPPER_MIC_MODE}, Temi={config.TEMI_MIC_MODE})")
    print(f"  DISPLAY_MODE : {config.DISPLAY_MODE}  "
          f"(Pepper={config.PEPPER_DISPLAY_MODE}, Temi={config.TEMI_DISPLAY_MODE})")
    print(f"  Dashboard    : {config.DASHBOARD_URL}")
    print("=" * 64)


# =========================================================================
# Main loop
# =========================================================================

def wait_for_hello() -> bool:
    """Block until the user types 'hello' (or a greeting variant).

    Shows an idle screen on Pepper's tablet prompting the next customer.
    Returns True when hello received, or False on shutdown request.
    Falls back to keyboard after repeated mic failures.
    """
    global _mic_fail_count
    _mic_fail_count = 0  # reset for new session

    pepper_show_idle()
    temi_show_message("Say Hello to start!")
    print("\n💤 Pepper is idle. Type 'hello' to start a new session.\n")

    mic_fails = 0

    while True:
        try:
            use_mic = (config.MIC_MODE and pepper_mic_active()
                       and mic_fails < _MIC_FAIL_LIMIT)
            if use_mic:
                # In mic mode, listen for "hello" via Pepper's mic
                text = pepper_listen(timeout=6.0)
                if not text:
                    mic_fails += 1
                    if mic_fails >= _MIC_FAIL_LIMIT:
                        print(f"\n⚠️  Mic failed {mic_fails} times — "
                              "switching to keyboard for hello.")
                    continue
                mic_fails = 0
            else:
                text = input("👤 You: ")
        except EOFError:
            return False

        if not text:
            continue

        clean = text.strip().lower()
        if clean in {"shutdown", "exit", "quit"}:
            return False

        # Accept greeting variants
        if any(w in clean for w in ["hello", "hi", "hey", "good morning",
                                     "good afternoon", "good evening"]):
            return True

        print("💤 (Pepper is sleeping — say 'hello' to wake me up)")


def serve_one_customer():
    """Handle a single customer from greeting to goodbye.

    Pepper greets, then we accept requests until the orchestrator
    signals the conversation has ended (which happens automatically
    after Temi delivers an item, or if the customer says goodbye).
    """
    orchestrator.reset()
    orchestrator.run_turn("hello")

    # After greeting, show category dashboard on Pepper, simple text on Temi
    pepper_show_categories()
    temi_show_message("How can I help you? Tell me what you need!")

    while not orchestrator.conversation_ended:
        msg = read_customer_input()
        if not msg:
            continue
        if msg.strip().lower() in {"shutdown", "exit", "quit"}:
            return "SHUTDOWN"
        orchestrator.run_turn(msg)
    return "NEXT"


def main():
    print_banner()
    start_dashboard()
    sys.stdout = TeeWriter(sys.stdout)

    print("\nReady. Waiting for customers. "
          "Type 'shutdown' to stop the program entirely.\n")

    # Startup interaction — first customer gets a warm welcome
    pepper_show_welcome()
    pepper_wave_hello()
    import time
    time.sleep(1.0)

    try:
        # --- First customer (no hello-gate needed on startup) ---
        result = serve_one_customer()
        if result == "SHUTDOWN":
            raise SystemExit

        # --- Subsequent customers: wait for "hello" each time ---
        while True:
            if not wait_for_hello():
                break  # shutdown requested
            result = serve_one_customer()
            if result == "SHUTDOWN":
                break
    except (KeyboardInterrupt, SystemExit):
        print("\n[main] Shutting down...")
    finally:
        pepper_show_goodbye()
        from pepper_api import pepper_wave_goodbye
        pepper_wave_goodbye(wait=False)
        pepper_say("Goodbye, See You Soon!", gesture=False)
        
        import time
        time.sleep(2.0)  # Wait for wave to visually complete before cutting SSH
        pepper_close()
        print("👋 ShopMate-R shut down cleanly.")


if __name__ == "__main__":
    main()
