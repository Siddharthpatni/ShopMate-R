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
)
from temi_api import (
    temi_mic_active,
    temi_prompt_listen,
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

def listen_from_microphone() -> str:
    try:
        import speech_recognition as sr
    except ImportError:
        print("[main] speech_recognition not installed — falling back to text input")
        return input("👤 You: ")

    owner = "Pepper" if pepper_mic_active() else ("Temi" if temi_mic_active() else "PC")
    print(f"🎙️  Listening via {owner}...")

    if pepper_mic_active():
        pepper_prompt_listen("I'm listening, what do you need?")
    elif temi_mic_active():
        temi_prompt_listen("Tell me what you need.")

    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=6, phrase_time_limit=8)
        text = r.recognize_google(audio)
        print(f"👤 ({owner} mic) Customer: {text}")
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

def serve_one_customer():
    """Handle a single customer from greeting to goodbye.

    Pepper greets, then we accept requests until the orchestrator
    signals the conversation has ended (which happens automatically
    after Temi delivers an item, or if the customer says goodbye).
    """
    orchestrator.reset()
    orchestrator.run_turn("hello")

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

    try:
        while True:
            result = serve_one_customer()
            if result == "SHUTDOWN":
                break
            # Short pause between customers
            print("\n⏳ Waiting for next customer...\n")
            time.sleep(1.5)
    except KeyboardInterrupt:
        print("\n[main] Interrupted.")
    finally:
        pepper_say("Store closing. Goodbye.", gesture=True)
        pepper_close()
        print("👋 ShopMate-R shut down cleanly.")


if __name__ == "__main__":
    main()
