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
# DESIGN TOKENS  — shared across every tablet screen
# =========================================================================
# Keeping these in one place so all screens feel like the same product.
# Pepper's tablet runs an older Android WebView, so we stick to widely
# supported CSS (flex, grid, gradients, basic transitions) and avoid
# emoji — icons are inline SVG instead.

_UI_CSS_BASE = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    background: #f5f7fa;
    color: #1a202c;
    -webkit-font-smoothing: antialiased;
    line-height: 1.4;
  }
  /* Brand colors */
  .brand-primary { color: #2c5282; }
  .brand-accent  { color: #2f855a; }
"""

# Muted, professional category colors (no neon).
_CAT_COLORS = {
    "dairy":     "#3182ce",
    "milk":      "#4299e1",
    "bakery":    "#d69e2e",
    "produce":   "#38a169",
    "beverages": "#805ad5",
    "pantry":    "#c05621",
    "snacks":    "#e53e3e",
    "frozen":    "#319795",
}

# Inline SVG icons per category (stroke color injected at render time).
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
#
# These paths map to built-in NAOqi animations shipped with Pepper.

# Conversational "background" gestures played while Pepper talks.
# Kept to Explain_* / Enthusiastic_* / YouKnowWhat_* — these are
# natural, non-directional hand movements. ShowSky_1 used to be here
# but it points straight up, which looks odd mid-sentence.
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
    """Random conversational hand gesture played while Pepper talks."""
    pepper_gesture(random.choice(TALK_GESTURES))


def pepper_wave_hello(wait: bool = False):
    """Arm wave greeting — used when a customer walks up."""
    pepper_gesture("animations/Stand/Gestures/Hey_1", wait=wait)


def pepper_wave_goodbye(wait: bool = False):
    """Actual goodbye wave (Bye_*) — the previous BowShort was a bow,
    not a wave, so it didn't match the function name."""
    pepper_gesture("animations/Stand/Gestures/Bye_1", wait=wait)


def pepper_bow():
    """Short, respectful bow. Used to thank the customer."""
    pepper_gesture("animations/Stand/Gestures/BowShort_1")


def pepper_point_to_aisle():
    """Point in the direction of the aisle where Temi is heading.
    Show_* gestures point forward/lateral; ShowSky_1 (previously used)
    pointed straight up and didn't communicate direction properly."""
    pepper_gesture("animations/Stand/Gestures/Show_1")


def pepper_raise_hands():
    """Enthusiastic both-hands-up gesture — used for positive moments
    like 'Found it!' or 'All done!'"""
    pepper_gesture("animations/Stand/Gestures/Enthusiastic_4")


def pepper_thinking():
    """Small 'hmm, let me think' gesture while the LLM is parsing."""
    pepper_gesture("animations/Stand/Gestures/Thinking_1")


def pepper_nod_yes():
    """Head nod for simple affirmations. Nice complement to a spoken
    'yes' / 'sure' so Pepper feels responsive."""
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
    """Generate a self-contained HTML product card for Pepper's tablet.
    Clean, retail-display style: one hero product, clear price, aisle,
    and stock. No decorative clutter."""
    name     = product.get("name", "Item")
    price    = product.get("price", 0)
    aisle    = product.get("aisle", "?").replace("_", " ").title()
    stock    = product.get("stock", "?")
    category = product.get("category", "pantry").lower()

    color    = _CAT_COLORS.get(category, "#2c5282")
    svg_tpl  = _CAT_SVG.get(category, _CAT_SVG["pantry"])
    svg_icon = svg_tpl.replace("{c}", color)

    # Stock pill
    try:
        stock_n = int(stock)
    except (TypeError, ValueError):
        stock_n = 0
    if stock_n > 10:
        stock_label, stock_bg, stock_fg = "In stock", "#d4edda", "#1e7e34"
    elif stock_n > 0:
        stock_label, stock_bg, stock_fg = f"Only {stock_n} left", "#fff3cd", "#856404"
    else:
        stock_label, stock_bg, stock_fg = "Out of stock", "#f8d7da", "#721c24"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
{_UI_CSS_BASE}
  body {{
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
  }}
  .card {{
    width: 100%; max-width: 520px;
    background: #ffffff;
    border-radius: 16px;
    border: 1px solid #e2e8f0;
    border-top: 4px solid {color};
    box-shadow: 0 4px 20px rgba(15, 23, 42, 0.08);
    padding: 40px 44px;
    text-align: center;
  }}
  .icon-wrap {{
    width: 96px; height: 96px;
    margin: 0 auto 20px;
    border-radius: 50%;
    background: {color}14;
    display: flex; align-items: center; justify-content: center;
  }}
  .icon-wrap svg {{ width: 52px; height: 52px; }}
  .category-tag {{
    display: inline-block;
    font-size: 12px; font-weight: 700;
    color: {color};
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 8px;
  }}
  .name {{
    font-size: 30px; font-weight: 700;
    color: #1a202c; margin-bottom: 20px;
    letter-spacing: -0.5px;
  }}
  .price {{
    font-size: 44px; font-weight: 700;
    color: #1a202c; margin: 8px 0 20px;
    letter-spacing: -1px;
  }}
  .price .currency {{
    font-size: 22px; vertical-align: top;
    color: #718096; margin-right: 4px;
    font-weight: 600;
  }}
  .meta {{
    display: flex; justify-content: center; gap: 24px;
    padding: 16px 0;
    border-top: 1px solid #edf2f7;
    border-bottom: 1px solid #edf2f7;
    margin-bottom: 20px;
  }}
  .meta-item {{ text-align: center; }}
  .meta-label {{
    font-size: 11px; font-weight: 700;
    color: #a0aec0; text-transform: uppercase;
    letter-spacing: 0.8px; margin-bottom: 4px;
  }}
  .meta-value {{
    font-size: 17px; font-weight: 600;
    color: #2d3748;
  }}
  .stock-pill {{
    display: inline-block;
    padding: 8px 20px;
    border-radius: 999px;
    background: {stock_bg}; color: {stock_fg};
    font-size: 14px; font-weight: 700;
    letter-spacing: 0.3px;
  }}
</style></head><body>
  <div class="card">
    <div class="icon-wrap">{svg_icon}</div>
    <div class="category-tag">{category.title()}</div>
    <div class="name">{name}</div>
    <div class="price"><span class="currency">EUR</span>{price:.2f}</div>
    <div class="meta">
      <div class="meta-item">
        <div class="meta-label">Aisle</div>
        <div class="meta-value">{aisle}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Availability</div>
        <div class="meta-value">{stock} units</div>
      </div>
    </div>
    <div class="stock-pill">{stock_label}</div>
  </div>
</body></html>"""


def pepper_show_welcome():
    """Clean welcome screen shown the moment a customer engages."""
    if not _display_enabled(): return
    print("📺 Pepper tablet shows welcome screen")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      body {{
        background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%);
        color: #ffffff;
        display: flex; align-items: center; justify-content: center;
      }}
      .card {{
        text-align: center; padding: 48px 64px;
      }}
      .logo-circle {{
        width: 88px; height: 88px;
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 28px;
      }}
      .logo-circle svg {{ width: 48px; height: 48px; stroke: #ffffff; }}
      .brand {{
        font-size: 14px; font-weight: 700;
        letter-spacing: 4px; text-transform: uppercase;
        color: rgba(255, 255, 255, 0.7);
        margin-bottom: 16px;
      }}
      .title {{
        font-size: 52px; font-weight: 700;
        margin-bottom: 12px; letter-spacing: -1px;
      }}
      .subtitle {{
        font-size: 22px; color: rgba(255, 255, 255, 0.85);
        font-weight: 400;
      }}
    </style></head><body>
    <div class="card">
      <div class="logo-circle">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round">
          <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
          <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
        </svg>
      </div>
      <div class="brand">ShopMate Assistant</div>
      <div class="title">Welcome</div>
      <div class="subtitle">How can I help you today?</div>
    </div>
    </body></html>"""
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_welcome failed: {e}")


def pepper_show_goodbye():
    """Calm, clean goodbye screen shown at the end of a session."""
    if not _display_enabled(): return
    print("📺 Pepper tablet shows goodbye screen")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      body {{
        background: linear-gradient(135deg, #22543d 0%, #2f855a 100%);
        color: #ffffff;
        display: flex; align-items: center; justify-content: center;
      }}
      .card {{
        text-align: center; padding: 48px 64px;
      }}
      .check {{
        width: 88px; height: 88px;
        background: rgba(255, 255, 255, 0.12);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 28px;
      }}
      .check svg {{ width: 44px; height: 44px; stroke: #ffffff; }}
      .brand {{
        font-size: 14px; font-weight: 700;
        letter-spacing: 4px; text-transform: uppercase;
        color: rgba(255, 255, 255, 0.7);
        margin-bottom: 16px;
      }}
      .title {{
        font-size: 52px; font-weight: 700;
        margin-bottom: 12px; letter-spacing: -1px;
      }}
      .subtitle {{
        font-size: 22px; color: rgba(255, 255, 255, 0.85);
        font-weight: 400;
      }}
    </style></head><body>
    <div class="card">
      <div class="check">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
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


def pepper_show_idle():
    """Idle 'Say Hello to start' screen shown between customer sessions."""
    if not _display_enabled(): return
    print("📺 Pepper tablet shows idle screen (waiting for hello)")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      @keyframes subtlePulse {{
        0%, 100% {{ transform: scale(1); opacity: 1; }}
        50%      {{ transform: scale(1.03); opacity: 0.9; }}
      }}
      @keyframes gentleFloat {{
        0%, 100% {{ transform: translateY(0); }}
        50%      {{ transform: translateY(-6px); }}
      }}
      body {{
        background: linear-gradient(160deg, #1a202c 0%, #2d3748 100%);
        color: #ffffff;
        display: flex; align-items: center; justify-content: center;
      }}
      .card {{
        text-align: center; padding: 48px 64px;
        max-width: 560px;
      }}
      .wave-icon {{
        width: 96px; height: 96px;
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 28px;
        animation: gentleFloat 3s ease-in-out infinite;
      }}
      .wave-icon svg {{ width: 48px; height: 48px; stroke: #f6ad55; }}
      .brand {{
        font-size: 14px; font-weight: 700;
        letter-spacing: 4px; text-transform: uppercase;
        color: rgba(255, 255, 255, 0.6);
        margin-bottom: 16px;
      }}
      .title {{
        font-size: 48px; font-weight: 700;
        margin-bottom: 12px; letter-spacing: -1px;
        color: #ffffff;
      }}
      .subtitle {{
        font-size: 20px; color: rgba(255, 255, 255, 0.7);
        font-weight: 400; margin-bottom: 36px;
      }}
      .cta {{
        display: inline-block;
        padding: 14px 32px;
        border-radius: 999px;
        background: rgba(246, 173, 85, 0.15);
        border: 1px solid rgba(246, 173, 85, 0.4);
        color: #f6ad55;
        font-size: 17px; font-weight: 600;
        letter-spacing: 0.3px;
        animation: subtlePulse 2.8s ease-in-out infinite;
      }}
    </style></head><body>
    <div class="card">
      <div class="wave-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
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


def pepper_show_categories():
    """Category dashboard: the main landing view after greeting."""
    if not _display_enabled(): return
    print("📺 Pepper tablet shows product category dashboard")

    from grocery_db import get_all_items
    items = get_all_items()

    # Group products by category
    cats = {}
    for it in items:
        cats.setdefault(it["category"], []).append(it)

    # Build category tiles
    tiles_html = ""
    for cat_name, products in cats.items():
        color    = _CAT_COLORS.get(cat_name, "#4a5568")
        svg_tpl  = _CAT_SVG.get(cat_name, _CAT_SVG["pantry"])
        svg_icon = svg_tpl.replace("{c}", color)
        tiles_html += f'''
        <div class="tile" style="--cat-color: {color};">
          <div class="tile-icon">{svg_icon}</div>
          <div class="tile-name">{cat_name.title()}</div>
          <div class="tile-count">{len(products)} items</div>
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    {_UI_CSS_BASE}
      body {{
        background: #f5f7fa;
        padding: 20px 24px;
      }}

      /* ---------- Top bar ---------- */
      .topbar {{
        display: flex; align-items: center; justify-content: space-between;
        gap: 20px; padding: 14px 20px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        margin-bottom: 20px;
      }}
      .logo {{ display: flex; align-items: center; gap: 12px; }}
      .logo-mark {{
        width: 40px; height: 40px;
        background: #2c5282; border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
      }}
      .logo-mark svg {{ width: 22px; height: 22px; stroke: #ffffff; }}
      .logo-text {{
        font-size: 18px; font-weight: 700;
        color: #1a202c; letter-spacing: -0.3px; line-height: 1.1;
      }}
      .logo-sub {{
        font-size: 11px; font-weight: 600;
        color: #718096; text-transform: uppercase;
        letter-spacing: 1.2px; margin-top: 2px;
      }}

      /* ---------- Search ---------- */
      .search {{
        flex: 1; max-width: 420px; position: relative;
      }}
      .search svg {{
        position: absolute; left: 14px; top: 50%;
        transform: translateY(-50%); width: 18px; height: 18px;
        stroke: #a0aec0;
      }}
      .search input {{
        width: 100%; padding: 10px 16px 10px 42px;
        border: 1px solid #e2e8f0; border-radius: 8px;
        background: #f7fafc; color: #2d3748;
        font-size: 15px; font-weight: 500;
        outline: none;
      }}
      .search input::placeholder {{ color: #a0aec0; }}

      .status {{
        display: flex; align-items: center; gap: 8px;
        font-size: 13px; font-weight: 600; color: #2f855a;
      }}
      .status-dot {{
        width: 8px; height: 8px; border-radius: 50%;
        background: #2f855a;
      }}

      /* ---------- Hint banner ---------- */
      .banner {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #2c5282;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 20px;
        display: flex; align-items: center; gap: 12px;
      }}
      .banner svg {{
        width: 20px; height: 20px; stroke: #2c5282;
        flex-shrink: 0;
      }}
      .banner-text {{
        font-size: 15px; color: #2d3748;
      }}
      .banner-text strong {{ color: #1a202c; }}

      /* ---------- Category grid ---------- */
      .section-title {{
        font-size: 13px; font-weight: 700;
        color: #4a5568; text-transform: uppercase;
        letter-spacing: 1.2px; margin-bottom: 12px;
        padding-left: 4px;
      }}
      .grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
      }}
      .tile {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px 16px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
      }}
      .tile-icon {{
        width: 60px; height: 60px;
        margin: 0 auto 12px;
        background: var(--cat-color)14;
        border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
      }}
      .tile-icon svg {{ width: 32px; height: 32px; }}
      .tile-name {{
        font-size: 17px; font-weight: 700;
        color: #1a202c; margin-bottom: 4px;
        letter-spacing: -0.2px;
      }}
      .tile-count {{
        font-size: 12px; font-weight: 600;
        color: #718096; text-transform: uppercase;
        letter-spacing: 0.6px;
      }}

      /* ---------- Footer ---------- */
      .footer {{
        text-align: center; margin-top: 20px;
        font-size: 12px; font-weight: 500; color: #a0aec0;
        letter-spacing: 0.4px;
      }}
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
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 18V5l12-2v13"/>
        <circle cx="6" cy="18" r="3"/>
        <circle cx="18" cy="16" r="3"/>
      </svg>
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


def pepper_show_category_products(category: str, products: list):
    """Show all products in a category with names, prices, stock, and aisle."""
    if not _display_enabled(): return
    print(f"📺 Pepper tablet shows {category} products ({len(products)} items)")

    color    = _CAT_COLORS.get(category.lower(), "#2c5282")
    svg_tpl  = _CAT_SVG.get(category.lower(), _CAT_SVG["pantry"])
    svg_icon = svg_tpl.replace("{c}", color)

    rows = ""
    for p in products:
        try:
            sn = int(p.get("stock", 0))
        except (TypeError, ValueError):
            sn = 0
        if sn > 10:
            stock_class, stock_txt = "in",  f"{sn} in stock"
        elif sn > 0:
            stock_class, stock_txt = "low", f"Only {sn} left"
        else:
            stock_class, stock_txt = "out", "Out of stock"

        aisle = p["aisle"].replace("_", " ").title()
        rows += f'''
        <div class="product">
          <div class="p-head">
            <div class="p-name">{p["name"]}</div>
            <div class="p-price">EUR {p["price"]:.2f}</div>
          </div>
          <div class="p-meta">
            <div class="p-aisle">
              <svg viewBox="0 0 24 24" fill="none" stroke="#718096" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/>
              </svg>
              <span>{aisle}</span>
            </div>
            <div class="p-stock {stock_class}">{stock_txt}</div>
          </div>
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      body {{ background: #f5f7fa; padding: 24px; }}

      .header {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 20px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
      }}
      .h-icon {{
        width: 56px; height: 56px;
        background: {color}14;
        border-radius: 12px;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
      }}
      .h-icon svg {{ width: 32px; height: 32px; }}
      .h-title {{
        font-size: 26px; font-weight: 700;
        color: #1a202c; letter-spacing: -0.4px;
      }}
      .h-sub {{
        font-size: 13px; font-weight: 600;
        color: #718096; text-transform: uppercase;
        letter-spacing: 1px; margin-top: 2px;
      }}

      .grid {{
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 14px;
      }}
      .product {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 3px solid {color};
        border-radius: 10px;
        padding: 16px 18px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
      }}
      .p-head {{
        display: flex; justify-content: space-between;
        align-items: baseline; gap: 12px;
        margin-bottom: 12px;
      }}
      .p-name {{
        font-size: 17px; font-weight: 700;
        color: #1a202c; letter-spacing: -0.2px;
      }}
      .p-price {{
        font-size: 18px; font-weight: 700;
        color: #1a202c; white-space: nowrap;
      }}
      .p-meta {{
        display: flex; justify-content: space-between;
        align-items: center;
      }}
      .p-aisle {{
        display: flex; align-items: center; gap: 5px;
        font-size: 12px; font-weight: 600;
        color: #718096; text-transform: uppercase;
        letter-spacing: 0.5px;
      }}
      .p-aisle svg {{ width: 13px; height: 13px; }}
      .p-stock {{
        font-size: 11px; font-weight: 700;
        padding: 4px 10px; border-radius: 999px;
        text-transform: uppercase; letter-spacing: 0.5px;
      }}
      .p-stock.in  {{ background: #d4edda; color: #1e7e34; }}
      .p-stock.low {{ background: #fff3cd; color: #856404; }}
      .p-stock.out {{ background: #f8d7da; color: #721c24; }}

      .hint {{
        margin-top: 20px; padding: 14px 18px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #2c5282;
        border-radius: 8px;
        display: flex; align-items: center; gap: 12px;
        font-size: 14px; color: #2d3748;
      }}
      .hint svg {{ width: 18px; height: 18px; stroke: #2c5282; flex-shrink: 0; }}
      .hint strong {{ color: #1a202c; }}
    </style></head><body>

    <div class="header">
      <div class="h-icon">{svg_icon}</div>
      <div>
        <div class="h-title">{category.title()}</div>
        <div class="h-sub">{len(products)} product{"s" if len(products) != 1 else ""} available</div>
      </div>
    </div>

    <div class="grid">{rows}</div>

    <div class="hint">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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


def pepper_show_cart(cart: list):
    """Show the current shopping cart in a clean receipt style."""
    if not _display_enabled(): return
    if not cart:
        return
    print(f"📺 Pepper tablet shows cart ({len(cart)} items)")

    total = sum(p["price"] for p in cart)
    items_html = ""
    for i, p in enumerate(cart, 1):
        aisle = p.get("aisle", "").replace("_", " ").title()
        items_html += f'''
        <div class="line">
          <div class="line-num">{i:02d}</div>
          <div class="line-info">
            <div class="line-name">{p["name"]}</div>
            <div class="line-aisle">{aisle}</div>
          </div>
          <div class="line-price">EUR {p["price"]:.2f}</div>
        </div>'''

    item_count = len(cart)
    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
    {_UI_CSS_BASE}
      body {{
        background: #f5f7fa;
        padding: 24px;
        display: flex; align-items: center; justify-content: center;
      }}
      .receipt {{
        width: 100%; max-width: 560px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        box-shadow: 0 4px 20px rgba(15, 23, 42, 0.06);
        overflow: hidden;
      }}
      .r-head {{
        padding: 24px 28px;
        background: #1a202c;
        color: #ffffff;
        display: flex; align-items: center; justify-content: space-between;
      }}
      .r-head-left {{ display: flex; align-items: center; gap: 12px; }}
      .r-head-icon {{
        width: 40px; height: 40px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        display: flex; align-items: center; justify-content: center;
      }}
      .r-head-icon svg {{ width: 22px; height: 22px; stroke: #ffffff; }}
      .r-title {{ font-size: 18px; font-weight: 700; letter-spacing: -0.2px; }}
      .r-sub   {{ font-size: 12px; font-weight: 500; color: rgba(255,255,255,0.7); text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }}
      .r-count {{
        padding: 6px 12px;
        background: rgba(255,255,255,0.15);
        border-radius: 999px;
        font-size: 12px; font-weight: 700;
        letter-spacing: 0.5px;
      }}

      .r-body {{ padding: 16px 28px; }}
      .line {{
        display: flex; align-items: center; gap: 14px;
        padding: 12px 0;
        border-bottom: 1px solid #edf2f7;
      }}
      .line:last-child {{ border-bottom: none; }}
      .line-num {{
        font-size: 12px; font-weight: 700;
        color: #a0aec0;
        min-width: 24px;
      }}
      .line-info {{ flex: 1; }}
      .line-name {{
        font-size: 16px; font-weight: 600;
        color: #1a202c; letter-spacing: -0.1px;
      }}
      .line-aisle {{
        font-size: 11px; font-weight: 600;
        color: #a0aec0; text-transform: uppercase;
        letter-spacing: 0.6px; margin-top: 2px;
      }}
      .line-price {{
        font-size: 16px; font-weight: 700;
        color: #2d3748; white-space: nowrap;
      }}

      .r-total {{
        padding: 20px 28px;
        background: #f7fafc;
        border-top: 2px dashed #cbd5e0;
        display: flex; justify-content: space-between; align-items: center;
      }}
      .t-label {{
        font-size: 13px; font-weight: 700;
        color: #4a5568; text-transform: uppercase;
        letter-spacing: 1.2px;
      }}
      .t-value {{
        font-size: 28px; font-weight: 700;
        color: #1a202c; letter-spacing: -0.5px;
      }}

      .r-hint {{
        padding: 14px 28px;
        background: #ebf8ff;
        border-top: 1px solid #bee3f8;
        font-size: 13px; color: #2c5282;
        text-align: center;
      }}
      .r-hint strong {{ color: #1a202c; }}
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
        <div class="t-value">EUR {total:.2f}</div>
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

            # Try Google first, then Whisper fallback
            try:
                text = r.recognize_google(audio)
            except sr.UnknownValueError:
                print("[pepper_api] Google couldn't understand audio")
            except sr.RequestError as e:
                print(f"[pepper_api] Google API error: {e}")
                # Try Whisper as offline fallback
                try:
                    text = r.recognize_whisper(audio, model="base")
                except Exception:
                    pass
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