"""
pepper_api.py — Pepper robot control for ShopMate-R.

Pepper is the stationary humanoid at the store entrance. It greets
customers, holds the conversation, uses expressive hand gestures while
talking, shows product cards on its tablet, and says goodbye when the
interaction ends.

There is NO mock mode — this module always tries to drive the real
Pepper over SSH. If the connection drops at runtime, individual calls
log the error and continue rather than crashing the whole app.

Tablet visuals follow a single Apple-inspired glassmorphism system
defined in `_UI_CSS_BASE`, `_CAT_COLORS`, `_CAT_SVG`, and `_AURORA_BG`
below. Every screen pulls from those tokens so all views feel like
one product.
"""

import random
import config
from pypepper_ssh import PepperRobotSSH

# -------------------------------------------------------------------------
# Connect to the real Pepper once at import time.  (DO NOT MODIFY.)
# -------------------------------------------------------------------------
_pepper = PepperRobotSSH(ip=config.PEPPER_IP)


# =========================================================================
# DESIGN TOKENS  — Apple-style glassmorphism
# =========================================================================
# Pepper's tablet runs a Chromium-based Android WebView on recent
# firmware and supports `backdrop-filter`. For older WebViews we also
# emit `-webkit-backdrop-filter` and keep the translucent background
# opaque enough that cards still read clearly even if blur is missing.

_UI_CSS_BASE = """
  *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display',
                 'SF Pro Text', 'Roboto', 'Segoe UI',
                 'Helvetica Neue', Arial, sans-serif;
    color: #1c1c1e;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
    line-height: 1.4;
    letter-spacing: -0.01em;
  }
"""

# Apple-inspired vivid palette (close to SF Symbols accent hues).
_CAT_COLORS = {
    "dairy":     {"base": "#0A84FF", "container": "#CCE5FF", "on": "#003D80"},
    "milk":      {"base": "#30B0C7", "container": "#CFF2F7", "on": "#0F5869"},
    "bakery":    {"base": "#FF9F0A", "container": "#FFE5B8", "on": "#8A4F00"},
    "produce":   {"base": "#34C759", "container": "#CBEFD3", "on": "#0F5D23"},
    "beverages": {"base": "#AF52DE", "container": "#ECD6F7", "on": "#4C1F73"},
    "pantry":    {"base": "#FF6B35", "container": "#FFD3BD", "on": "#7A2A07"},
    "snacks":    {"base": "#FF375F", "container": "#FFC9D4", "on": "#7A0D27"},
    "frozen":    {"base": "#5AC8FA", "container": "#D1EFFC", "on": "#0B5878"},
}
_CAT_DEFAULT = {"base": "#8E8E93", "container": "#E5E5EA", "on": "#3A3A3C"}

_CAT_SVG = {
    "dairy":     '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><ellipse cx="12" cy="12" rx="8" ry="9"/><path d="M8 8c1 2 5 2 8 0"/><path d="M9 14c.5 1 4.5 1 6 0"/></svg>',
    "milk":      '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M8 2h8v4l2 3v11a2 2 0 01-2 2H8a2 2 0 01-2-2V9l2-3V2z"/><path d="M6 9h12"/></svg>',
    "bakery":    '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M5 18h14a2 2 0 002-2c0-2-3-3-3-6 0-2-1-4-4-4h-4c-3 0-4 2-4 4 0 3-3 4-3 6a2 2 0 002 2z"/><path d="M9 18v2a1 1 0 001 1h4a1 1 0 001-1v-2"/></svg>',
    "produce":   '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="14" r="7"/><path d="M12 7V3"/><path d="M15 5c-1 1-3 1.5-5 .5"/></svg>',
    "beverages": '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M18 8h1a4 4 0 010 8h-1"/><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/><path d="M6 1v3"/><path d="M10 1v3"/><path d="M14 1v3"/></svg>',
    "pantry":    '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4H6z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 01-8 0"/></svg>',
    "snacks":    '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 12h18"/><path d="M9 4v16"/><path d="M15 4v16"/></svg>',
    "frozen":    '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M12 2v20M2 12h20"/><path d="M20 16l-4-4 4-4"/><path d="M4 8l4 4-4 4"/><path d="M16 4l-4 4-4-4"/><path d="M8 20l4-4 4 4"/></svg>',
}


def _cat(category: str) -> dict:
    return _CAT_COLORS.get((category or "").lower(), _CAT_DEFAULT)


def _icon(category: str, color: str = None) -> str:
    tpl = _CAT_SVG.get((category or "").lower(), _CAT_SVG["pantry"])
    return tpl.replace("{c}", color or _cat(category)["base"])


# Vibrant multi-light aurora backdrop — the thing that makes the glass
# actually feel like glass. Used behind every dark-mode screen.
_AURORA_BG = """
    background:
      radial-gradient(1200px 800px at 10% 10%,
                      rgba(175, 82, 222, 0.45) 0%, transparent 55%),
      radial-gradient(1000px 700px at 95% 20%,
                      rgba(10, 132, 255, 0.50) 0%, transparent 55%),
      radial-gradient(900px 700px at 20% 100%,
                      rgba(255, 55, 95, 0.40) 0%, transparent 55%),
      radial-gradient(900px 700px at 100% 100%,
                      rgba(255, 159, 10, 0.35) 0%, transparent 55%),
      linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%);
"""


# =========================================================================
# SPEECH
# =========================================================================

def pepper_say(text: str, gesture: bool = True):
    print(f"🤖 Pepper says: {text}")
    try:
        if gesture:
            pepper_talk_gesture()
        _pepper.say(text)
    except Exception as e:
        print(f"[pepper_api] say() failed: {e}")


def pepper_set_volume(level: int):
    try:
        _pepper.set_system_volume(level)
    except Exception as e:
        print(f"[pepper_api] set_volume failed: {e}")


# =========================================================================
# HAND GESTURES
# =========================================================================

TALK_GESTURES = [
    "animations/Stand/Gestures/Explain_1",
    "animations/Stand/Gestures/Explain_2",
    "animations/Stand/Gestures/Explain_3",
    "animations/Stand/Gestures/Explain_4",
    "animations/Stand/Gestures/Explain_8",
    "animations/Stand/Gestures/Enthusiastic_4",
    "animations/Stand/Gestures/Enthusiastic_5",
    "animations/Stand/Gestures/YouKnowWhat_1",
    "animations/Stand/Gestures/YouKnowWhat_3",
]


def pepper_gesture(path: str, wait: bool = False):
    print(f"💃 Pepper gesture: {path}")
    try:
        _pepper.play_animation(path, wait=wait)
    except Exception as e:
        print(f"[pepper_api] gesture failed: {e}")


def pepper_talk_gesture():
    pepper_gesture(random.choice(TALK_GESTURES))


def pepper_wave_hello(wait: bool = False):
    pepper_gesture("animations/Stand/Gestures/Hey_1", wait=wait)


def pepper_wave_goodbye(wait: bool = False):
    """Actual goodbye wave — Bye_1, not the previous BowShort_1."""
    pepper_gesture("animations/Stand/Gestures/Bye_1", wait=wait)


def pepper_bow():
    pepper_gesture("animations/Stand/Gestures/BowShort_1")


def pepper_point_to_aisle():
    """Forward/lateral point (Show_1), not the upward ShowSky_1."""
    pepper_gesture("animations/Stand/Gestures/Show_1")


def pepper_raise_hands():
    pepper_gesture("animations/Stand/Gestures/Enthusiastic_4")


def pepper_thinking():
    pepper_gesture("animations/Stand/Gestures/Thinking_1")


def pepper_nod_yes():
    pepper_gesture("animations/Stand/Gestures/Yes_1")


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


def _stock_pill(stock) -> tuple:
    try:
        n = int(stock)
    except (TypeError, ValueError):
        n = 0
    if n > 10:
        return (f"{n} in stock", "rgba(52,199,89,0.18)",  "#1E7A3A")
    if n > 0:
        return (f"Only {n} left", "rgba(255,149,0,0.18)", "#8A4B00")
    return ("Out of stock",       "rgba(255,59,48,0.18)", "#8A1A13")


# -------------------------------------------------------------------------
# SINGLE PRODUCT CARD (glass, light)
# -------------------------------------------------------------------------

def _product_card_html(product: dict) -> str:
    name     = product.get("name", "Item")
    price    = product.get("price", 0)
    aisle    = product.get("aisle", "?").replace("_", " ").title()
    stock    = product.get("stock", "?")
    category = (product.get("category") or "pantry").lower()

    swatch = _cat(category)
    svg    = _icon(category, swatch["base"])
    pill_label, pill_bg, pill_fg = _stock_pill(stock)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
{_UI_CSS_BASE}
  body {{
    {_AURORA_BG}
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
  }}
  .card {{
    width: 100%; max-width: 560px;
    padding: 40px 44px;
    text-align: center;
    border-radius: 32px;
    background: rgba(255,255,255,0.72);
    -webkit-backdrop-filter: blur(30px) saturate(200%);
            backdrop-filter: blur(30px) saturate(200%);
    border: 1px solid rgba(255,255,255,0.85);
    box-shadow:
      0 1px 0 rgba(255,255,255,0.9) inset,
      0 -1px 0 rgba(255,255,255,0.3) inset,
      0 16px 40px rgba(16,24,40,0.18),
      0 32px 80px rgba(16,24,40,0.14);
    position: relative; overflow: hidden;
  }}
  .card::before {{
    content: ""; position: absolute; top: 0; right: 0; left: 0; height: 5px;
    background: linear-gradient(90deg, {swatch['base']} 0%, {swatch['on']} 100%);
    opacity: 0.95;
  }}
  .icon-wrap {{
    width: 108px; height: 108px;
    margin: 14px auto 24px;
    border-radius: 28px;
    background: linear-gradient(135deg, {swatch['container']} 0%, rgba(255,255,255,0.6) 100%);
    border: 1px solid rgba(255,255,255,0.8);
    display: flex; align-items: center; justify-content: center;
    box-shadow:
      0 1px 0 rgba(255,255,255,0.9) inset,
      0 8px 24px {swatch['base']}33;
  }}
  .icon-wrap svg {{ width: 56px; height: 56px; }}
  .tag {{
    display: inline-block;
    padding: 6px 14px; border-radius: 999px;
    background: rgba(255,255,255,0.6);
    -webkit-backdrop-filter: blur(12px);
            backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.8);
    color: {swatch['on']};
    font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1.6px;
    margin-bottom: 16px;
  }}
  .name  {{ font-size: 32px; font-weight: 700; color: #1c1c1e;
            margin-bottom: 24px; letter-spacing: -0.8px; line-height: 1.1; }}
  .price {{ font-size: 60px; font-weight: 700; color: #1c1c1e;
            letter-spacing: -2px; line-height: 1; margin-bottom: 8px; }}
  .price .cur {{ font-size: 22px; vertical-align: top; color: #8E8E93;
                 margin-right: 6px; font-weight: 600; }}
  .meta {{ display: -webkit-flex; display: flex; -webkit-justify-content: center; justify-content: center; margin: 26px 0 22px; }}
  .meta > * + * {{ margin-left: 10px; }}
  .chip {{
    display: -webkit-flex; display: flex; -webkit-align-items: center; align-items: center;
    padding: 10px 18px; border-radius: 999px;
    background: rgba(255,255,255,0.5);
    -webkit-backdrop-filter: blur(14px);
            backdrop-filter: blur(14px);
    border: 1px solid rgba(255,255,255,0.8);
    color: #1c1c1e; font-size: 14px; font-weight: 600;
  }}
  .chip svg {{ width: 16px; height: 16px; stroke: {swatch['base']}; margin-right: 8px; }}
  .pill {{
    display: inline-block;
    padding: 10px 24px; border-radius: 999px;
    background: {pill_bg};
    -webkit-backdrop-filter: blur(12px);
            backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.4);
    color: {pill_fg};
    font-size: 14px; font-weight: 700; letter-spacing: 0.3px;
  }}
</style></head><body>
  <div class="card">
    <div class="icon-wrap">{svg}</div>
    <div class="tag">{category.title()}</div>
    <div class="name">{name}</div>
    <div class="price"><span class="cur">EUR</span>{price:.2f}</div>
    <div class="meta">
      <div class="chip">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/>
        </svg>
        <span>{aisle}</span>
      </div>
      <div class="chip">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 7l-8-4-8 4v10l8 4 8-4V7z"/><path d="M4 7l8 4 8-4"/><path d="M12 11v10"/>
        </svg>
        <span>{stock} units</span>
      </div>
    </div>
    <div class="pill">{pill_label}</div>
  </div>
</body></html>"""


# -------------------------------------------------------------------------
# WELCOME (glass on aurora)
# -------------------------------------------------------------------------

def pepper_show_welcome():
    if not _display_enabled(): return
    print("📺 Pepper tablet shows welcome screen")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      @keyframes floaty {{ 0%,100%{{transform:translateY(0);}} 50%{{transform:translateY(-10px);}} }}
      body {{
        {_AURORA_BG}
        color: #fff;
        display: flex; align-items: center; justify-content: center;
      }}
      .card {{
        text-align: center; padding: 56px 72px; max-width: 680px;
        border-radius: 40px;
        background: rgba(255,255,255,0.12);
        -webkit-backdrop-filter: blur(40px) saturate(180%);
                backdrop-filter: blur(40px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.22);
        box-shadow:
          0 1px 0 rgba(255,255,255,0.3) inset,
          0 20px 50px rgba(0,0,0,0.35),
          0 40px 100px rgba(0,0,0,0.25);
      }}
      .mark {{
        width: 112px; height: 112px;
        background: rgba(255,255,255,0.18);
        -webkit-backdrop-filter: blur(20px);
                backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.35);
        border-radius: 32px;
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 32px;
        animation: floaty 4s ease-in-out infinite;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset, 0 16px 40px rgba(0,0,0,0.3);
      }}
      .mark svg {{ width: 56px; height: 56px; stroke: #fff; }}
      .brand {{
        font-size: 13px; font-weight: 700; letter-spacing: 4px;
        text-transform: uppercase; color: rgba(255,255,255,0.78);
        margin-bottom: 16px;
      }}
      .title    {{ font-size: 64px; font-weight: 700; margin-bottom: 14px;
                   letter-spacing: -2px; line-height: 1.05; }}
      .subtitle {{ font-size: 22px; font-weight: 400;
                   color: rgba(255,255,255,0.88); margin-bottom: 32px; }}
      .chips    {{ display: -webkit-flex; display: flex; -webkit-justify-content: center; justify-content: center; -webkit-flex-wrap: wrap; flex-wrap: wrap; }}
      .chip {{ margin: 0 5px 10px; }}
      .chip {{
        padding: 10px 18px;
        background: rgba(255,255,255,0.14);
        -webkit-backdrop-filter: blur(16px);
                backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.26);
        border-radius: 999px;
        font-size: 14px; font-weight: 600;
        color: rgba(255,255,255,0.95);
      }}
    </style></head><body>
    <div class="card">
      <div class="mark">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round">
          <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
          <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
        </svg>
      </div>
      <div class="brand">ShopMate Assistant</div>
      <div class="title">Welcome</div>
      <div class="subtitle">How can I help you shop today?</div>
      <div class="chips">
        <div class="chip">Voice-guided</div>
        <div class="chip">Powered by Pepper &amp; Temi</div>
      </div>
    </div>
    </body></html>"""
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_welcome failed: {e}")


# -------------------------------------------------------------------------
# GOODBYE (glass on green aurora)
# -------------------------------------------------------------------------

def pepper_show_goodbye():
    if not _display_enabled(): return
    print("📺 Pepper tablet shows goodbye screen")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      body {{
        background:
          radial-gradient(900px 700px at 15% 15%, rgba(52,199,89,0.55) 0%, transparent 55%),
          radial-gradient(900px 700px at 85% 85%, rgba(48,176,199,0.55) 0%, transparent 55%),
          radial-gradient(700px 500px at 50% 50%, rgba(10,132,255,0.30) 0%, transparent 55%),
          linear-gradient(135deg, #0a3d2e 0%, #0b2a3b 50%, #062632 100%);
        color: #fff;
        display: flex; align-items: center; justify-content: center;
      }}
      .card {{
        text-align: center; padding: 56px 72px; max-width: 640px;
        border-radius: 40px;
        background: rgba(255,255,255,0.14);
        -webkit-backdrop-filter: blur(40px) saturate(180%);
                backdrop-filter: blur(40px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.24);
        box-shadow:
          0 1px 0 rgba(255,255,255,0.3) inset,
          0 20px 50px rgba(0,0,0,0.35),
          0 40px 100px rgba(0,0,0,0.22);
      }}
      .mark {{
        width: 112px; height: 112px;
        background: rgba(255,255,255,0.2);
        -webkit-backdrop-filter: blur(20px);
                backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.38);
        border-radius: 32px;
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 32px;
        box-shadow: 0 1px 0 rgba(255,255,255,0.45) inset, 0 16px 40px rgba(0,0,0,0.3);
      }}
      .mark svg {{ width: 56px; height: 56px; stroke: #fff; }}
      .brand {{
        font-size: 13px; font-weight: 700; letter-spacing: 4px;
        text-transform: uppercase; color: rgba(255,255,255,0.78);
        margin-bottom: 16px;
      }}
      .title    {{ font-size: 64px; font-weight: 700; margin-bottom: 14px;
                   letter-spacing: -2px; }}
      .subtitle {{ font-size: 22px; color: rgba(255,255,255,0.88);
                   font-weight: 400; }}
    </style></head><body>
    <div class="card">
      <div class="mark">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2.5"
             stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
      </div>
      <div class="brand">Thank You</div>
      <div class="title">Goodbye</div>
      <div class="subtitle">Have a wonderful day!</div>
    </div>
    </body></html>"""
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_goodbye failed: {e}")


# -------------------------------------------------------------------------
# IDLE (glass on aurora)
# -------------------------------------------------------------------------

def pepper_show_idle():
    if not _display_enabled(): return
    print("📺 Pepper tablet shows idle screen (waiting for hello)")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      @keyframes pulse {{ 0%,100%{{transform:scale(1);opacity:1;}} 50%{{transform:scale(1.05);opacity:0.92;}} }}
      @keyframes float {{ 0%,100%{{transform:translateY(0);}} 50%{{transform:translateY(-8px);}} }}
      body {{
        {_AURORA_BG}
        color: #fff;
        display: flex; align-items: center; justify-content: center;
      }}
      .card {{
        text-align: center; padding: 56px 72px; max-width: 620px;
        border-radius: 40px;
        background: rgba(255,255,255,0.10);
        -webkit-backdrop-filter: blur(40px) saturate(180%);
                backdrop-filter: blur(40px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.20);
        box-shadow:
          0 1px 0 rgba(255,255,255,0.25) inset,
          0 20px 50px rgba(0,0,0,0.4),
          0 40px 100px rgba(0,0,0,0.25);
      }}
      .mark {{
        width: 116px; height: 116px;
        background: rgba(255,255,255,0.12);
        -webkit-backdrop-filter: blur(20px);
                backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.24);
        border-radius: 32px;
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 32px;
        animation: float 3.2s ease-in-out infinite;
        box-shadow: 0 1px 0 rgba(255,255,255,0.3) inset, 0 16px 40px rgba(0,0,0,0.35);
      }}
      .mark svg {{ width: 56px; height: 56px; stroke: #FFB340; }}
      .brand {{
        font-size: 13px; font-weight: 700; letter-spacing: 4px;
        text-transform: uppercase; color: rgba(255,255,255,0.65);
        margin-bottom: 16px;
      }}
      .title    {{ font-size: 54px; font-weight: 700; margin-bottom: 14px;
                   letter-spacing: -1.5px; color: #fff; }}
      .subtitle {{ font-size: 20px; color: rgba(255,255,255,0.75);
                   font-weight: 400; margin-bottom: 36px; }}
      .cta {{
        display: inline-block; padding: 14px 32px;
        border-radius: 999px;
        background: linear-gradient(135deg, #FFB340 0%, #FF6B35 100%);
        color: #1a1a2e;
        font-size: 16px; font-weight: 700; letter-spacing: 0.4px;
        animation: pulse 2.6s ease-in-out infinite;
        border: 1px solid rgba(255,255,255,0.3);
        box-shadow: 0 1px 0 rgba(255,255,255,0.5) inset, 0 8px 24px rgba(255,107,53,0.4);
      }}
    </style></head><body>
    <div class="card">
      <div class="mark">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8"
             stroke-linecap="round" stroke-linejoin="round">
          <path d="M7 11V7a5 5 0 0110 0v4"/>
          <path d="M4 15.5C4 12.5 6 11 8 11h8c2 0 4 1.5 4 4.5 0 4-3 7.5-8 7.5s-8-3.5-8-7.5z"/>
          <path d="M16 11V5a2 2 0 00-4 0"/>
          <path d="M12 11V4a2 2 0 00-4 0v7"/>
        </svg>
      </div>
      <div class="brand">ShopMate Assistant</div>
      <div class="title">Ready to help</div>
      <div class="subtitle">Your personal grocery assistant</div>
      <div class="cta">Wave or say &ldquo;Hello&rdquo; to begin</div>
    </div>
    </body></html>"""
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_idle failed: {e}")


# -------------------------------------------------------------------------
# CATEGORIES DASHBOARD  — 2 columns × rich glass tiles
# -------------------------------------------------------------------------

def pepper_show_categories():
    """Category dashboard with a 2-column glass-tile grid. Each tile
    shows the category header plus a 2-column mini-preview of its
    products so the customer sees options at a glance."""
    if not _display_enabled(): return
    print("📺 Pepper tablet shows product category dashboard")

    from grocery_db import get_all_items
    items = get_all_items()

    cats: dict[str, list] = {}
    for it in items:
        cats.setdefault(it["category"], []).append(it)

    tiles_html = ""
    for cat_name, products in cats.items():
        sw   = _cat(cat_name)
        icon = _icon(cat_name, "#ffffff")
        in_stock = sum(1 for p in products if p["stock"] > 0)

        # Preview up to 4 products — fills the 2×2 sub-grid nicely
        preview = sorted(products, key=lambda p: -p["stock"])[:4]
        preview_html = ""
        for p in preview:
            is_out = p["stock"] <= 0
            preview_html += f'''
            <div class="mini{' out' if is_out else ''}">
              <div class="mini-name">{p["name"]}</div>
              <div class="mini-price">€{p["price"]:.2f}</div>
            </div>'''

        extra = len(products) - len(preview)
        more_html = (f'<div class="more">+{extra} more</div>'
                     if extra > 0 else "")

        tiles_html += f'''
        <div class="tile">
          <div class="tile-bar" style="background: linear-gradient(90deg, {sw['base']} 0%, {sw['on']} 100%);"></div>
          <div class="tile-head">
            <div class="t-icon" style="background: linear-gradient(135deg, {sw['base']} 0%, {sw['on']} 100%);">{icon}</div>
            <div>
              <div class="t-name">{cat_name.title()}</div>
              <div class="t-count">{in_stock} of {len(products)} in stock</div>
            </div>
          </div>
          <div class="mini-grid">
            {preview_html}
          </div>
          {more_html}
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    {_UI_CSS_BASE}
      body {{
        {_AURORA_BG}
        padding: 20px 24px;
        color: #fff;
      }}

      /* ---- Top bar ---- */
      .topbar {{
        display: -webkit-flex; display: flex; -webkit-align-items: center; align-items: center;
        -webkit-justify-content: space-between; justify-content: space-between;
        padding: 14px 20px;
        border-radius: 20px; margin-bottom: 18px;
        background: rgba(255,255,255,0.12);
        -webkit-backdrop-filter: blur(28px) saturate(180%);
                backdrop-filter: blur(28px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.22);
        box-shadow: 0 1px 0 rgba(255,255,255,0.3) inset, 0 8px 24px rgba(0,0,0,0.2);
      }}
      .logo {{ display: -webkit-flex; display: flex; -webkit-align-items: center; align-items: center; }}
      .logo > * + * {{ margin-left: 14px; }}
      .logo-mark {{
        width: 44px; height: 44px;
        background: linear-gradient(135deg, #AF52DE 0%, #FF375F 100%);
        border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.3);
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset, 0 8px 20px rgba(175,82,222,0.4);
      }}
      .logo-mark svg {{ width: 22px; height: 22px; stroke: #fff; }}
      .logo-text {{ font-size: 20px; font-weight: 700; color: #fff;
                    letter-spacing: -0.3px; line-height: 1.1; }}
      .logo-sub  {{ font-size: 11px; font-weight: 700; color: rgba(255,255,255,0.7);
                    text-transform: uppercase; letter-spacing: 1.4px; margin-top: 2px; }}

      .search {{ flex: 1; max-width: 380px; position: relative; }}
      .search svg {{ position: absolute; left: 16px; top: 50%;
                     transform: translateY(-50%); width: 18px; height: 18px;
                     stroke: rgba(255,255,255,0.6); }}
      .search input {{
        width: 100%; padding: 11px 16px 11px 44px;
        border: 1px solid rgba(255,255,255,0.25); border-radius: 999px;
        background: rgba(255,255,255,0.1);
        -webkit-backdrop-filter: blur(16px);
                backdrop-filter: blur(16px);
        color: #fff; font-size: 15px; font-weight: 500; outline: none;
      }}
      .search input::placeholder {{ color: rgba(255,255,255,0.55); }}

      .status {{
        display: -webkit-flex; display: flex; -webkit-align-items: center; align-items: center;
        padding: 6px 14px;
        background: rgba(52,199,89,0.2);
        border: 1px solid rgba(52,199,89,0.4);
        color: #6EEA90; border-radius: 999px;
        font-size: 12px; font-weight: 700;
      }}
      .status-dot {{ width: 8px; height: 8px; border-radius: 50%;
                     background: #34C759; box-shadow: 0 0 0 3px rgba(52,199,89,0.25);
                     margin-right: 8px; }}

      /* ---- Hint banner ---- */
      .banner {{
        padding: 14px 20px; border-radius: 18px; margin-bottom: 18px;
        display: -webkit-flex; display: flex; -webkit-align-items: center; align-items: center;
        background: rgba(255,255,255,0.10);
        -webkit-backdrop-filter: blur(24px) saturate(180%);
                backdrop-filter: blur(24px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.18);
        box-shadow: 0 1px 0 rgba(255,255,255,0.2) inset;
      }}
      .banner-ic {{
        width: 38px; height: 38px; flex-shrink: 0;
        background: linear-gradient(135deg, #FFB340 0%, #FF6B35 100%);
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.3);
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset, 0 4px 12px rgba(255,107,53,0.35);
      }}
      .banner-ic svg {{ width: 20px; height: 20px; stroke: #fff; }}
      .banner-ic {{ margin-right: 14px; }}
      .banner-text {{ font-size: 15px; color: rgba(255,255,255,0.95); }}
      .banner-text strong {{ color: #fff; font-weight: 700; }}

      /* ---- 2-column category grid ---- */
      .section-title {{
        font-size: 12px; font-weight: 700;
        color: rgba(255,255,255,0.65); text-transform: uppercase;
        letter-spacing: 1.8px; margin-bottom: 12px; padding-left: 4px;
      }}
      .grid {{
        display: -webkit-flex;
        display: flex;
        -webkit-flex-wrap: wrap;
        flex-wrap: wrap;
      }}
      .tile {{
        width: 48.5%;
        margin-right: 3%;
        margin-bottom: 14px;
        border-radius: 22px;
        padding: 18px 18px 16px;
        position: relative; overflow: hidden;
        background: rgba(255,255,255,0.14);
        -webkit-backdrop-filter: blur(26px) saturate(180%);
                backdrop-filter: blur(26px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.22);
        box-shadow:
          0 1px 0 rgba(255,255,255,0.3) inset,
          0 8px 24px rgba(0,0,0,0.2),
          0 16px 40px rgba(0,0,0,0.12);
      }}
      .tile:nth-child(2n) {{ margin-right: 0; }}
      .tile-bar {{
        position: absolute; top: 0; right: 0; left: 0; height: 3px;
        border-radius: 22px 22px 0 0; opacity: 0.9;
      }}
      .tile-head {{
        display: -webkit-flex; display: flex;
        -webkit-align-items: center; align-items: center;
        margin-bottom: 12px;
      }}
      .tile-head > *:first-child {{ margin-right: 12px; }}
      .t-icon {{
        width: 48px; height: 48px;
        -webkit-flex-shrink: 0; flex-shrink: 0;
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 14px;
        display: -webkit-flex; display: flex;
        -webkit-align-items: center; align-items: center;
        -webkit-justify-content: center; justify-content: center;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset, 0 4px 10px rgba(0,0,0,0.25);
      }}
      .t-icon svg {{ width: 26px; height: 26px; stroke: #fff; }}
      .t-name  {{ font-size: 18px; font-weight: 700; color: #fff;
                  margin-bottom: 2px; letter-spacing: -0.3px; }}
      .t-count {{ font-size: 11px; font-weight: 700; color: rgba(255,255,255,0.7);
                  text-transform: uppercase; letter-spacing: 1px; }}

      /* ---- mini 2-col product preview inside each tile ---- */
      .mini-grid {{
        display: -webkit-flex;
        display: flex;
        -webkit-flex-wrap: wrap;
        flex-wrap: wrap;
      }}
      .mini {{
        width: 48%;
        margin-right: 4%;
        margin-bottom: 6px;
        padding: 8px 10px; border-radius: 10px;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.18);
        display: -webkit-flex; display: flex;
        -webkit-align-items: center; align-items: center;
        -webkit-justify-content: space-between; justify-content: space-between;
        min-width: 0;
      }}
      .mini:nth-child(2n) {{ margin-right: 0; }}
      .mini.out {{ opacity: 0.45; }}
      .mini-name {{
        font-size: 12px; font-weight: 600;
        color: rgba(255,255,255,0.95);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        min-width: 0;
        -webkit-flex: 1; flex: 1;
        margin-right: 6px;
      }}
      .mini-price {{ font-size: 12px; font-weight: 700; color: #fff;
                     white-space: nowrap; }}
      .more {{
        margin-top: 8px; text-align: center;
        padding: 6px 12px;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.16);
        border-radius: 999px;
        font-size: 11px; font-weight: 700;
        color: rgba(255,255,255,0.7);
        text-transform: uppercase; letter-spacing: 0.8px;
      }}

      .footer {{ text-align: center; margin-top: 18px;
                 font-size: 12px; font-weight: 600;
                 color: rgba(255,255,255,0.55); letter-spacing: 0.4px; }}
    </style></head><body>

    <div class="topbar">
      <div class="logo">
        <div class="logo-mark">
          <svg viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round">
            <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
            <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
          </svg>
        </div>
        <div>
          <div class="logo-text">ShopMate</div>
          <div class="logo-sub">Grocery Assistant</div>
        </div>
      </div>
      <div class="search">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round">
          <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
        </svg>
        <input type="text" placeholder="Listening..." readonly>
      </div>
      <div class="status">
        <div class="status-dot"></div>
        <span>Online</span>
      </div>
    </div>

    <div class="banner">
      <div class="banner-ic">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2a3 3 0 00-3 3v7a3 3 0 006 0V5a3 3 0 00-3-3z"/>
          <path d="M19 10v2a7 7 0 01-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="22"/>
        </svg>
      </div>
      <div class="banner-text">
        <strong>Tell me what you need</strong> &mdash; for example, &ldquo;I need milk&rdquo; or &ldquo;Where are the snacks?&rdquo;
      </div>
    </div>

    <div class="section-title">Browse by category</div>
    <div class="grid">{tiles_html}</div>

    <div class="footer">Say &ldquo;help&rdquo; or &ldquo;goodbye&rdquo; at any time</div>

    </body></html>'''
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_categories failed: {e}")


# -------------------------------------------------------------------------
# CATEGORY → PRODUCT GRID  (2 columns)
# -------------------------------------------------------------------------

def pepper_show_category_products(category: str, products: list):
    if not _display_enabled(): return
    print(f"📺 Pepper tablet shows {category} products ({len(products)} items)")

    sw   = _cat(category)
    icon = _icon(category, "#ffffff")

    rows = ""
    for p in products:
        pill_label, pill_bg, pill_fg = _stock_pill(p.get("stock", 0))
        aisle = p["aisle"].replace("_", " ").title()
        rows += f'''
        <div class="product">
          <div class="p-head">
            <div class="p-name">{p["name"]}</div>
            <div class="p-price">€{p["price"]:.2f}</div>
          </div>
          <div class="p-meta">
            <div class="p-aisle">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2"
                   stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>
                <circle cx="12" cy="10" r="3"/>
              </svg>
              <span>{aisle}</span>
            </div>
            <div class="p-stock" style="background:{pill_bg}; color:{pill_fg};">{pill_label}</div>
          </div>
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      body {{
        background:
          radial-gradient(1100px 800px at 10% 10%, {sw['base']}66 0%, transparent 55%),
          radial-gradient(900px 700px at 90% 90%, {sw['on']}55 0%, transparent 55%),
          radial-gradient(800px 600px at 50% 50%, rgba(175,82,222,0.25) 0%, transparent 55%),
          linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%);
        padding: 22px;
        color: #fff;
      }}

      .header {{
        border-radius: 24px; padding: 20px 24px; margin-bottom: 18px;
        display: -webkit-flex; display: flex; -webkit-align-items: center; align-items: center;
        position: relative; overflow: hidden;
        background: rgba(255,255,255,0.14);
        -webkit-backdrop-filter: blur(30px) saturate(180%);
                backdrop-filter: blur(30px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.25);
        box-shadow: 0 1px 0 rgba(255,255,255,0.35) inset, 0 12px 32px rgba(0,0,0,0.25);
      }}
      .header::before {{
        content: ""; position: absolute; top: 0; right: 0; left: 0; height: 4px;
        background: linear-gradient(90deg, {sw['base']} 0%, {sw['on']} 100%);
      }}
      .h-icon {{
        width: 60px; height: 60px;
        background: linear-gradient(135deg, {sw['base']} 0%, {sw['on']} 100%);
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.3);
        display: -webkit-flex; display: flex;
        -webkit-align-items: center; align-items: center;
        -webkit-justify-content: center; justify-content: center;
        -webkit-flex-shrink: 0; flex-shrink: 0;
        margin-right: 16px;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset, 0 8px 20px {sw['base']}55;
      }}
      .h-icon svg {{ width: 32px; height: 32px; }}
      .h-title {{ font-size: 28px; font-weight: 700; color: #fff;
                  letter-spacing: -0.6px; line-height: 1.1; }}
      .h-sub   {{ font-size: 12px; font-weight: 700; color: rgba(255,255,255,0.7);
                  text-transform: uppercase; letter-spacing: 1.2px; margin-top: 4px; }}

      .grid {{
        display: -webkit-flex;
        display: flex;
        -webkit-flex-wrap: wrap;
        flex-wrap: wrap;
      }}
      .product {{
        width: 48.5%;
        margin-right: 3%;
        margin-bottom: 12px;
        border-radius: 18px; padding: 16px 18px;
        background: rgba(255,255,255,0.14);
        -webkit-backdrop-filter: blur(24px) saturate(180%);
                backdrop-filter: blur(24px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.22);
        border-left: 3px solid {sw['base']};
        box-shadow: 0 1px 0 rgba(255,255,255,0.25) inset, 0 6px 16px rgba(0,0,0,0.2);
      }}
      .product:nth-child(2n) {{ margin-right: 0; }}
      .p-head {{ display: -webkit-flex; display: flex;
                 -webkit-justify-content: space-between; justify-content: space-between;
                 -webkit-align-items: baseline; align-items: baseline;
                 margin-bottom: 12px; }}
      .p-name {{ margin-right: 12px; }}
      .p-name  {{ font-size: 17px; font-weight: 700; color: #fff; letter-spacing: -0.2px; }}
      .p-price {{ font-size: 18px; font-weight: 700; color: #fff; white-space: nowrap; }}
      .p-meta  {{ display: -webkit-flex; display: flex;
                   -webkit-justify-content: space-between; justify-content: space-between;
                   -webkit-align-items: center; align-items: center; }}
      .p-aisle {{
        display: -webkit-flex; display: flex;
        -webkit-align-items: center; align-items: center;
        font-size: 11px; font-weight: 700;
        color: rgba(255,255,255,0.7); text-transform: uppercase;
        letter-spacing: 0.6px;
      }}
      .p-aisle svg {{ width: 13px; height: 13px; stroke: rgba(255,255,255,0.7); margin-right: 6px; }}
      .p-stock {{
        font-size: 11px; font-weight: 700;
        padding: 5px 12px; border-radius: 999px;
        letter-spacing: 0.3px;
        border: 1px solid rgba(255,255,255,0.25);
        -webkit-backdrop-filter: blur(10px);
                backdrop-filter: blur(10px);
      }}

      .hint {{
        margin-top: 18px; padding: 14px 20px;
        border-radius: 18px;
        display: -webkit-flex; display: flex; -webkit-align-items: center; align-items: center;
        font-size: 14px; color: rgba(255,255,255,0.95);
        background: rgba(255,255,255,0.10);
        -webkit-backdrop-filter: blur(24px);
                backdrop-filter: blur(24px);
        border: 1px solid rgba(255,255,255,0.2);
      }}
      .hint svg {{ width: 20px; height: 20px; stroke: #FFB340; -webkit-flex-shrink: 0; flex-shrink: 0; margin-right: 12px; }}
      .hint strong {{ color: #fff; font-weight: 700; }}
    </style></head><body>

    <div class="header">
      <div class="h-icon">{icon}</div>
      <div>
        <div class="h-title">{category.title()}</div>
        <div class="h-sub">{len(products)} product{"s" if len(products) != 1 else ""} available</div>
      </div>
    </div>

    <div class="grid">{rows}</div>

    <div class="hint">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 2a3 3 0 00-3 3v7a3 3 0 006 0V5a3 3 0 00-3-3z"/>
        <path d="M19 10v2a7 7 0 01-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="22"/>
      </svg>
      <div><strong>Say the product name</strong> to add it to your cart &mdash; e.g. &ldquo;I want milk&rdquo;</div>
    </div>

    </body></html>'''
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_category_products failed: {e}")


# -------------------------------------------------------------------------
# CART  (glass receipt)
# -------------------------------------------------------------------------

def pepper_show_cart(cart: list):
    if not _display_enabled(): return
    if not cart:
        return
    print(f"📺 Pepper tablet shows cart ({len(cart)} items)")

    total = sum(p["price"] for p in cart)
    item_count = len(cart)

    items_html = ""
    for p in cart:
        category = (p.get("category") or "pantry").lower()
        sw   = _cat(category)
        icon = _icon(category, "#ffffff")
        aisle = p.get("aisle", "").replace("_", " ").title()
        items_html += f'''
        <div class="line">
          <div class="l-icon" style="background: linear-gradient(135deg, {sw['base']} 0%, {sw['on']} 100%);">{icon}</div>
          <div class="l-info">
            <div class="l-name">{p["name"]}</div>
            <div class="l-aisle">{aisle}</div>
          </div>
          <div class="l-price">€{p["price"]:.2f}</div>
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      body {{
        {_AURORA_BG}
        padding: 24px;
        display: flex; align-items: center; justify-content: center;
      }}
      .receipt {{
        width: 100%; max-width: 600px;
        border-radius: 32px; overflow: hidden;
        background: rgba(255,255,255,0.72);
        -webkit-backdrop-filter: blur(36px) saturate(200%);
                backdrop-filter: blur(36px) saturate(200%);
        border: 1px solid rgba(255,255,255,0.85);
        box-shadow:
          0 1px 0 rgba(255,255,255,0.9) inset,
          0 -1px 0 rgba(255,255,255,0.3) inset,
          0 20px 50px rgba(16,24,40,0.2),
          0 40px 100px rgba(16,24,40,0.15);
      }}
      .r-head {{
        padding: 24px 28px;
        background: linear-gradient(135deg, #AF52DE 0%, #FF375F 100%);
        color: #fff;
        display: flex; align-items: center; justify-content: space-between;
        border-bottom: 1px solid rgba(255,255,255,0.2);
      }}
      .r-head-left {{ display: -webkit-flex; display: flex; -webkit-align-items: center; align-items: center; }}
      .r-head-left > * + * {{ margin-left: 14px; }}
      .r-head-icon {{
        width: 44px; height: 44px;
        background: rgba(255,255,255,0.22);
        -webkit-backdrop-filter: blur(16px);
                backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 14px;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset;
      }}
      .r-head-icon svg {{ width: 22px; height: 22px; stroke: #fff; }}
      .r-title {{ font-size: 20px; font-weight: 700; letter-spacing: -0.3px; }}
      .r-sub   {{ font-size: 11px; font-weight: 700; color: rgba(255,255,255,0.85);
                  text-transform: uppercase; letter-spacing: 1.4px; margin-top: 4px; }}
      .r-count {{
        padding: 8px 14px;
        background: rgba(255,255,255,0.22);
        -webkit-backdrop-filter: blur(16px);
                backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.35);
        border-radius: 999px;
        font-size: 12px; font-weight: 700; letter-spacing: 0.6px;
      }}

      .r-body {{ padding: 12px 20px; }}
      .line {{
        display: -webkit-flex; display: flex; -webkit-align-items: center; align-items: center;
        padding: 14px 8px;
        border-bottom: 1px solid rgba(0,0,0,0.06);
      }}
      .line:last-child {{ border-bottom: none; }}
      .l-icon {{
        width: 44px; height: 44px; border-radius: 14px;
        border: 1px solid rgba(255,255,255,0.3);
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
        box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset, 0 4px 10px rgba(0,0,0,0.15);
      }}
      .l-icon svg {{ width: 22px; height: 22px; stroke: #fff; }}
      .l-icon {{ margin-right: 14px; }}
      .l-info {{ flex: 1; }}
      .l-name  {{ font-size: 16px; font-weight: 600; color: #1c1c1e;
                  letter-spacing: -0.1px; }}
      .l-aisle {{ font-size: 11px; font-weight: 700; color: #8E8E93;
                  text-transform: uppercase; letter-spacing: 0.8px; margin-top: 3px; }}
      .l-price {{ font-size: 16px; font-weight: 700; color: #1c1c1e;
                  white-space: nowrap; }}

      .r-total {{
        padding: 20px 28px;
        background: rgba(175,82,222,0.08);
        border-top: 2px dashed rgba(175,82,222,0.3);
        display: flex; justify-content: space-between; align-items: center;
      }}
      .t-label {{ font-size: 12px; font-weight: 700; color: #5E1B90;
                  text-transform: uppercase; letter-spacing: 1.4px; }}
      .t-value {{ font-size: 32px; font-weight: 700; color: #1c1c1e;
                  letter-spacing: -0.8px; }}

      .r-hint {{
        padding: 16px 28px;
        background: rgba(255,255,255,0.5);
        border-top: 1px solid rgba(0,0,0,0.05);
        font-size: 14px; color: #3A3A3C; text-align: center;
      }}
      .r-hint strong {{ color: #AF52DE; font-weight: 700; }}
    </style></head><body>

    <div class="receipt">
      <div class="r-head">
        <div class="r-head-left">
          <div class="r-head-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round">
              <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
              <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
            </svg>
          </div>
          <div>
            <div class="r-title">Your Cart</div>
            <div class="r-sub">ShopMate Session</div>
          </div>
        </div>
        <div class="r-count">{item_count} item{"s" if item_count != 1 else ""}</div>
      </div>

      <div class="r-body">
        {items_html}
      </div>

      <div class="r-total">
        <div class="t-label">Total</div>
        <div class="t-value">€{total:.2f}</div>
      </div>

      <div class="r-hint">
        Say <strong>&ldquo;done&rdquo;</strong> or <strong>&ldquo;that&rsquo;s all&rdquo;</strong> when ready, or add more items
      </div>
    </div>

    </body></html>'''
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_cart failed: {e}")


def pepper_clear_tablet():
    if not _display_enabled():
        return
    print("📺 Pepper tablet cleared")
    try:
        _pepper.clear_tablet()
    except Exception as e:
        print(f"[pepper_api] clear_tablet failed: {e}")


# =========================================================================
# MIC MODE  (DO NOT MODIFY — real speech I/O)
# =========================================================================

def pepper_mic_active() -> bool:
    return config.MIC_MODE and config.PEPPER_MIC_MODE


def pepper_prompt_listen(prompt: str = "I'm listening."):
    if not pepper_mic_active():
        return
    pepper_say(prompt)


def pepper_listen(timeout: float = 6.0) -> str:
    """Record from Pepper's mic, download, and transcribe. Returns text."""
    if not pepper_mic_active():
        return ""
    
    import os
    local_path = "tmp_pepper_audio.wav"

    try:
        # 1. Record on robot and pull back to PC
        _pepper.record_audio(timeout, local_path)
        
        # 2. Check the file actually exists and has content
        if not os.path.exists(local_path):
            print("[pepper_api] No audio file downloaded from Pepper")
            return ""
        fsize = os.path.getsize(local_path)
        if fsize < 1000:  # too small = silence or error
            print(f"[pepper_api] Audio file too small ({fsize}B) — likely silence")
            return ""
        print(f"🎤 Audio file: {fsize} bytes")

        # 3. Transcribe locally using speech_recognition
        import speech_recognition as sr
        import sys
        
        # Suppress ALSA/PortAudio noise
        stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        text = ""
        try:
            r = sr.Recognizer()
            with sr.AudioFile(local_path) as source:
                audio = r.record(source)

            # Try Whisper first, then Google as fallback
            try:
                text = r.recognize_whisper(audio, model="base")
            except Exception as e:
                print(f"[pepper_api] Whisper failed: {e}")
                # Try Google as fallback
                try:
                    text = r.recognize_google(audio)
                except sr.UnknownValueError:
                    print("[pepper_api] Google couldn't understand audio")
                except sr.RequestError as ge:
                    print(f"[pepper_api] Google API error: {ge}")
        finally:
            sys.stderr = stderr

        if not text:
            print("[pepper_api] No speech detected")
            return ""

        # 4. Keyword matching against DB keys and product names
        from grocery_db import get_all_items
        items = get_all_items()
        text_lower = text.lower()

        # Check DB keys first (e.g. "milk", "eggs", "chips")
        for item in items:
            key = item["key"]
            if key in text_lower:
                print(f"🎯 Keyword detected: {key}")
                return key

        # Then check display names
        for item in items:
            name = item["name"].lower()
            if name in text_lower:
                print(f"🎯 Product name detected: {item['name']}")
                return item["key"]

        print(f"👂 Pepper heard: {text}")
        return text
    except Exception as e:
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
 
