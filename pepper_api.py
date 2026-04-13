"""
pepper_api.py — Pepper robot control for ShopMate-R.

Pepper is the stationary humanoid at the store entrance. It greets
customers, holds the conversation, uses expressive hand gestures while
talking, shows product cards on its tablet, and says goodbye when the
interaction ends.

There is NO mock mode — this module always tries to drive the real
Pepper over SSH. If the connection drops at runtime, individual calls
log the error and continue rather than crashing the whole app.
"""

import random
import config
from pypepper_ssh import PepperRobotSSH

# -------------------------------------------------------------------------
# Connect to the real Pepper once at import time.
# -------------------------------------------------------------------------
_pepper = PepperRobotSSH(ip=config.PEPPER_IP)


# =========================================================================
# SPEECH
# =========================================================================

def pepper_say(text: str, gesture: bool = True):
    """Make Pepper speak `text`. By default Pepper also plays a small
    conversational hand gesture while talking, so it looks alive."""
    print(f"🤖 Pepper says: {text}")
    try:
        if gesture:
            pepper_talk_gesture()
        _pepper.say(text)
    except Exception as e:
        print(f"[pepper_api] say() failed: {e}")


def pepper_set_volume(level: int):
    """Set Pepper speaker volume 0–100."""
    try:
        _pepper.set_system_volume(level)
    except Exception as e:
        print(f"[pepper_api] set_volume failed: {e}")


# =========================================================================
# HAND GESTURES
# =========================================================================
# Pepper should always feel conversational, so every `say` triggers a
# small hand gesture picked at random from this pool. Bigger named
# gestures (wave, bow, point) are still available for specific moments.

TALK_GESTURES = [
    "animations/Stand/Gestures/Explain_1",
    "animations/Stand/Gestures/Explain_2",
    "animations/Stand/Gestures/Explain_3",
    "animations/Stand/Gestures/Explain_4",
    "animations/Stand/Gestures/Enthusiastic_4",
    "animations/Stand/Gestures/YouKnowWhat_1",
    "animations/Stand/Gestures/ShowSky_1",
]


def pepper_gesture(path: str):
    print(f"💃 Pepper gesture: {path}")
    try:
        _pepper.play_animation(path)
    except Exception as e:
        print(f"[pepper_api] gesture failed: {e}")


def pepper_talk_gesture():
    """Random conversational hand gesture played while Pepper talks."""
    pepper_gesture(random.choice(TALK_GESTURES))


def pepper_wave_hello():
    pepper_gesture("animations/Stand/Gestures/Hey_1")


def pepper_wave_goodbye():
    pepper_gesture("animations/Stand/Gestures/BowShort_1")


def pepper_bow():
    pepper_gesture("animations/Stand/Gestures/BowShort_1")


def pepper_point_to_aisle():
    """Point in the direction of the aisle where Temi is heading."""
    pepper_gesture("animations/Stand/Gestures/ShowSky_1")


def pepper_raise_hands():
    pepper_gesture("animations/Stand/Gestures/Enthusiastic_4")


def pepper_thinking():
    """Small 'hmm, let me think' gesture while the LLM is parsing."""
    pepper_gesture("animations/Stand/Gestures/Thinking_1")


# =========================================================================
# DISPLAY MODE  — tablet output
# =========================================================================

def _display_enabled() -> bool:
    return config.DISPLAY_MODE and config.PEPPER_DISPLAY_MODE


def pepper_show_image(url: str):
    if not _display_enabled():
        print("📵 Pepper display mode OFF — skipping show_image")
        return
    print(f"📺 Pepper tablet shows image: {url}")
    try:
        _pepper.show_image(url)
    except Exception as e:
        print(f"[pepper_api] show_image failed: {e}")


def pepper_show_product(product: dict):
    """Show a product card on Pepper's tablet."""
    if not _display_enabled():
        print(f"📵 Pepper display mode OFF — would have shown {product.get('name')}")
        return
    label = f"{product.get('name')} — €{product.get('price'):.2f} — {product.get('aisle','?')}"
    print(f"📺 Pepper tablet shows product card:\n    {label}")
    try:
        html = _product_card_html(product)
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_product failed: {e}")


def _product_card_html(product: dict) -> str:
    """Generate a self-contained HTML product card for Pepper's tablet."""
    name  = product.get("name", "Item")
    price = product.get("price", 0)
    aisle = product.get("aisle", "?").replace("_", " ").title()
    stock = product.get("stock", "?")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: Arial, sans-serif;
    background: linear-gradient(135deg, #667eea, #764ba2);
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; color: #fff;
  }}
  .card {{
    background: rgba(255,255,255,0.15);
    backdrop-filter: blur(10px);
    border-radius: 24px; padding: 40px 48px;
    text-align: center; min-width: 420px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
  }}
  .icon {{ font-size: 64px; margin-bottom: 12px; }}
  .name {{ font-size: 36px; font-weight: bold; margin-bottom: 8px; }}
  .price {{ font-size: 48px; font-weight: bold; color: #ffd700; margin: 12px 0; }}
  .detail {{ font-size: 22px; opacity: 0.9; margin: 6px 0; }}
  .badge {{
    display: inline-block; margin-top: 16px;
    padding: 8px 24px; border-radius: 999px;
    background: rgba(255,255,255,0.25); font-size: 18px;
  }}
</style></head><body>
<div class="card">
  <div class="icon">
    <svg width="80" height="80" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M6 2L3 6V20C3 20.5304 3.21071 21.0391 3.58579 21.4142C3.96086 21.7893 4.46957 22 5 22H19C19.5304 22 20.0391 21.7893 20.4142 21.4142C20.7893 21.0391 21 20.5304 21 20V6L18 2H6Z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M3 6H21" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M16 10C16 11.0609 15.5786 12.0783 14.8284 12.8284C14.0783 13.5786 13.0609 14 12 14C10.9391 14 9.92172 13.5786 9.17157 12.8284C8.42143 12.0783 8 11.0609 8 10" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </div>
  <div class="name">{name}</div>
  <div class="price">EUR {price:.2f}</div>
  <div class="detail">Aisle: {aisle}</div>
  <div class="detail">In stock: {stock}</div>
  <div class="badge">ShopMate-R</div>
</div>
</body></html>"""


def pepper_show_welcome():
    """Show a friendly welcome screen on Pepper's tablet."""
    if not _display_enabled(): return
    print("📺 Pepper tablet shows welcome screen")
    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
      body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #00b4db, #0083b0); display: flex; align-items: center; justify-content: center; min-height: 100vh; color: #fff; margin:0; }
      .card { background: rgba(255,255,255,0.15); backdrop-filter: blur(10px); border-radius: 24px; padding: 60px; text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
      .title { font-size: 54px; font-weight: bold; margin-bottom: 20px; }
      .subtitle { font-size: 28px; opacity: 0.9; }
    </style></head><body>
    <div class="card">
      <div class="title">Welcome! 👋</div>
      <div class="subtitle">How can I help you today?</div>
    </div>
    </body></html>"""
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_welcome failed: {e}")


def pepper_show_goodbye():
    """Show a goodbye screen on Pepper's tablet."""
    if not _display_enabled(): return
    print("📺 Pepper tablet shows goodbye screen")
    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
      body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #11998e, #38ef7d); display: flex; align-items: center; justify-content: center; min-height: 100vh; color: #fff; margin:0; }
      .card { background: rgba(255,255,255,0.15); backdrop-filter: blur(10px); border-radius: 24px; padding: 60px; text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
      .title { font-size: 54px; font-weight: bold; margin-bottom: 20px; }
      .subtitle { font-size: 28px; opacity: 0.9; }
    </style></head><body>
    <div class="card">
      <div class="title">Goodbye! ✨</div>
      <div class="subtitle">Have a wonderful day!</div>
    </div>
    </body></html>"""
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_goodbye failed: {e}")


def pepper_clear_tablet():
    if not _display_enabled():
        return
    print("📺 Pepper tablet cleared")
    try:
        _pepper.clear_tablet()
    except Exception as e:
        print(f"[pepper_api] clear_tablet failed: {e}")


# =========================================================================
# MIC MODE
# =========================================================================

def pepper_mic_active() -> bool:
    """Does Pepper currently own the voice input channel?"""
    return config.MIC_MODE and config.PEPPER_MIC_MODE


def pepper_prompt_listen(prompt: str = "I'm listening."):
    """Speak a prompt to the customer if Pepper's mic is the active one."""
    if not pepper_mic_active():
        return
    pepper_say(prompt)


def pepper_listen(timeout: float = 6.0) -> str:
    """Record from Pepper's mic, download, and transcribe. Returns text."""
    if not pepper_mic_active():
        return ""
    
    local_path = "tmp_pepper_audio.wav"
    try:
        # 1. Record on robot and pull back to PC
        _pepper.record_audio(timeout, local_path)
        
        # 2. Transcribe locally using speech_recognition
        import speech_recognition as sr
        import os, sys
        
        # Suppress ALSA/PortAudio noise during import/init
        stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        try:
            r = sr.Recognizer()
            with sr.AudioFile(local_path) as source:
                audio = r.record(source)
            text = r.recognize_google(audio)
        finally:
            sys.stderr = stderr

        # 3. Keyword matching (item names)
        # We try to find items from the database in the text
        from grocery_db import get_all_items
        all_items = [item['name'].lower() for item in get_all_items()]
        
        words = text.lower().split()
        for it in all_items:
            if it in text.lower():
                print(f"🎯 Keyword detected: {it}")
                return it

        print(f"👂 Pepper heard: {text}")
        return text
    except Exception as e:
        # Check if it was just silence
        if "recognition connection error" not in str(e).lower():
            print(f"[pepper_api] listen failed or no speech: {e}")
        return ""


# =========================================================================
# LIFECYCLE
# =========================================================================

def pepper_close():
    try:
        _pepper.close()
        print("🤖 Pepper connection closed")
    except Exception as e:
        print(f"[pepper_api] close failed: {e}")
