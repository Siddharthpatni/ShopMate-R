"""
main.py — ShopMate-R entry point.

Runs a multi-customer loop:
  1. Pepper greets a customer.
  2. Customer speaks or types one request at a time.
  3. Orchestrator dispatches Pepper + Temi as needed.
  4. After Temi delivers the cart, Pepper says BYE.
  5. The loop resets and waits for the next customer.

Ctrl-C (or typing "shutdown") exits the program cleanly.
"""

from __future__ import annotations

import subprocess
import sys
import time

import requests

import config
import orchestrator
from pepper_api import (
    pepper_close,
    pepper_listen,
    pepper_mic_active,
    pepper_prompt_listen,
    pepper_say,
    pepper_show_categories,
    pepper_show_goodbye,
    pepper_show_idle,
    pepper_show_welcome,
    pepper_wave_goodbye,
    pepper_wave_hello,
)
from temi_api import (
    temi_mic_active,
    temi_prompt_listen,
    temi_show_message,
)


# =========================================================================
# Stdout → dashboard log mirror
# =========================================================================

class TeeWriter:
    """Wraps sys.stdout so every printed line is also POSTed to the
    dashboard's /api/log endpoint. Failures are swallowed — nothing the
    dashboard does should ever break the main loop."""

    def __init__(self, original):
        self.original = original

    def write(self, text: str) -> None:
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

    def flush(self) -> None:
        self.original.flush()


# =========================================================================
# Dashboard launcher
# =========================================================================

def start_dashboard() -> None:
    print(f"📊 Starting ShopMate-R dashboard on port {config.DASHBOARD_PORT}...")
    try:
        subprocess.Popen(
            [sys.executable, "mock_dashboard.py"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"[main] Could not start dashboard: {e}")
    # Give Flask a moment to bind its socket before we start POSTing logs
    time.sleep(1.5)


# =========================================================================
# Microphone / keyboard input
# =========================================================================

# Unified fail-counter across both input sites. Reset on every successful
# recognition or at the start of a new customer session.
_MIC_FAIL_LIMIT = 3
_mic_fail_count = 0


def _keyboard_fallback(prompt: str = "👤 You (keyboard): ") -> str:
    """Read one line from stdin, returning 'shutdown' on EOF so the main
    loop has a consistent signal to exit."""
    try:
        return input(prompt)
    except EOFError:
        return "shutdown"


def _mic_failed() -> bool:
    """Increment the global mic fail counter; return True once we've
    crossed the fallback threshold."""
    global _mic_fail_count
    _mic_fail_count += 1
    return _mic_fail_count >= _MIC_FAIL_LIMIT


def _mic_succeeded() -> None:
    global _mic_fail_count
    _mic_fail_count = 0


def listen_from_microphone() -> str:
    """One round of speech capture, with automatic fallback to keyboard
    after repeated failures."""
    # --- Pepper mic (preferred, runs over SSH to the robot) ---
    if pepper_mic_active():
        pepper_prompt_listen("I'm listening, what do you need?")
        text = pepper_listen(timeout=6.0)
        if text:
            _mic_succeeded()
            return text
        if _mic_failed():
            print(f"\n⚠️  Mic failed {_mic_fail_count} times — "
                  "switching to keyboard.")
            print("   (Type your request instead)")
            return _keyboard_fallback()
        return ""

    # --- Fallback chain: speech_recognition on local PC / Temi ---
    try:
        import speech_recognition as sr
    except ImportError:
        print("[main] speech_recognition not installed — "
              "falling back to text input")
        return _keyboard_fallback("👤 You: ")

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
        _mic_succeeded()
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
    return _keyboard_fallback("👤 You: ")


# =========================================================================
# Startup banner
# =========================================================================

def print_banner() -> None:
    bar = "=" * 64
    print(bar)
    print("  🛒  ShopMate-R — Multi-Robot Grocery Assistant")
    print("      Pepper (front desk)  +  Temi (mobile shelf runner)")
    print(bar)
    print(f"  MIC_MODE     : {config.MIC_MODE}   "
          f"(Pepper={config.PEPPER_MIC_MODE}, Temi={config.TEMI_MIC_MODE})")
    print(f"  DISPLAY_MODE : {config.DISPLAY_MODE}  "
          f"(Pepper={config.PEPPER_DISPLAY_MODE}, Temi={config.TEMI_DISPLAY_MODE})")
    print(f"  Dashboard    : {config.DASHBOARD_URL}")
    print(bar)


# =========================================================================
# Customer sessions
# =========================================================================

_GREETING_WORDS = (
    "hello", "hi", "hey",
    "good morning", "good afternoon", "good evening",
)
_SHUTDOWN_WORDS = {"shutdown", "exit", "quit"}


def wait_for_hello() -> bool:
    """Block until the user greets Pepper.

    Shows the idle screen while waiting. Returns True on greeting,
    False if the user asked to shut down. Falls back to keyboard
    after repeated mic failures.
    """
    global _mic_fail_count
    _mic_fail_count = 0

    pepper_show_idle()
    temi_show_message("Say Hello to start!")
    print("\n💤 Pepper is idle. Type 'hello' to start a new session.\n")

    while True:
        use_mic = (config.MIC_MODE
                   and pepper_mic_active()
                   and _mic_fail_count < _MIC_FAIL_LIMIT)

        if use_mic:
            text = pepper_listen(timeout=6.0)
            if not text:
                if _mic_failed():
                    print(f"\n⚠️  Mic failed {_mic_fail_count} times — "
                          "switching to keyboard for hello.")
                continue
            _mic_succeeded()
        else:
            text = _keyboard_fallback("👤 You: ")

        if not text:
            continue

        clean = text.strip().lower()
        if clean in _SHUTDOWN_WORDS:
            return False
        if any(w in clean for w in _GREETING_WORDS):
            return True

        print("💤 (Pepper is sleeping — say 'hello' to wake me up)")


def serve_one_customer() -> str:
    """Handle a single customer end-to-end.

    Returns 'SHUTDOWN' if the user asked to exit, 'NEXT' otherwise.
    """
    orchestrator.reset()
    orchestrator.run_turn("hello")

    # After greeting, show category dashboard on Pepper, text on Temi
    pepper_show_categories()
    temi_show_message("How can I help you? Tell me what you need!")

    while not orchestrator.conversation_ended:
        msg = read_customer_input()
        if not msg:
            continue
        if msg.strip().lower() in _SHUTDOWN_WORDS:
            return "SHUTDOWN"
        orchestrator.run_turn(msg)
    return "NEXT"


# =========================================================================
# Main
# =========================================================================

def _shutdown() -> None:
    """Final goodbye + clean SSH teardown."""
    pepper_show_goodbye()
    pepper_wave_goodbye(wait=False)
    pepper_say("Goodbye, See You Soon!", gesture=False)
    # Give the wave animation time to complete before we cut the SSH socket
    time.sleep(2.0)
    pepper_close()
    print("👋 ShopMate-R shut down cleanly.")


def main() -> None:
    print_banner()
    start_dashboard()
    sys.stdout = TeeWriter(sys.stdout)

    print("\nReady. Waiting for customers. "
          "Type 'shutdown' to stop the program entirely.\n")

    # First customer gets a warm welcome without the hello gate
    pepper_show_welcome()
    # Redundant wave removed — orchestrator handles it in the greet loop
    time.sleep(1.0)

    try:
        if serve_one_customer() == "SHUTDOWN":
            raise SystemExit

        # Subsequent customers must greet Pepper to begin
        while True:
            if not wait_for_hello():
                break
            if serve_one_customer() == "SHUTDOWN":
                break
    except (KeyboardInterrupt, SystemExit):
        print("\n[main] Shutting down...")
    finally:
        _shutdown()


if __name__ == "__main__":
    main()
