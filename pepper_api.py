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
  <div class="icon">🛒</div>
  <div class="name">{name}</div>
  <div class="price">EUR {price:.2f}</div>
  <div class="detail">Aisle: {aisle}</div>
  <div class="detail">In stock: {stock}</div>
  <div class="badge">ShopMate-R</div>
</div>
</body></html>"""


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


# =========================================================================
# LIFECYCLE
# =========================================================================

def pepper_close():
    try:
        _pepper.close()
        print("🤖 Pepper connection closed")
    except Exception as e:
        print(f"[pepper_api] close failed: {e}")
