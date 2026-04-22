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
    pepper_gesture("animations/Stand/Gestures/Hey_1", wait=wait)


def pepper_wave_goodbye(wait: bool = False):
    pepper_gesture("animations/Stand/Gestures/BowShort_1", wait=wait)


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


def pepper_show_idle():
    """Show an idle 'Say Hello to start' screen on Pepper's tablet.
    Displayed between customer sessions so the next person knows
    to greet Pepper to begin."""
    if not _display_enabled(): return
    print("📺 Pepper tablet shows idle screen (waiting for hello)")
    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
      @keyframes pulse { 0%,100% { transform: scale(1); opacity: 0.9; } 50% { transform: scale(1.05); opacity: 1; } }
      @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
      * { margin:0; padding:0; box-sizing:border-box; }
      body {
        font-family: Arial, sans-serif;
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        display: flex; align-items: center; justify-content: center;
        min-height: 100vh; color: #fff; margin:0;
      }
      .card {
        background: rgba(255,255,255,0.08);
        backdrop-filter: blur(16px);
        border-radius: 32px; padding: 60px 80px;
        text-align: center;
        box-shadow: 0 8px 40px rgba(0,0,0,0.4);
        border: 1px solid rgba(255,255,255,0.12);
      }
      .wave {
        animation: float 3s ease-in-out infinite;
        margin-bottom: 16px;
      }
      .wave svg { width: 80px; height: 80px; }
      .title { font-size: 48px; font-weight: bold; margin-bottom: 12px;
        background: linear-gradient(90deg, #f7971e, #ffd200);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
      .subtitle { font-size: 26px; opacity: 0.7; margin-bottom: 24px; }
      .hint {
        display: inline-block; padding: 12px 36px; border-radius: 999px;
        background: rgba(255,255,255,0.12); font-size: 22px;
        animation: pulse 2.5s ease-in-out infinite;
        border: 1px solid rgba(255,255,255,0.2);
      }
    </style></head><body>
    <div class="card">
      <div class="wave">
        <svg viewBox="0 0 24 24" fill="none" stroke="#ffd200" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M7 11V7a5 5 0 0110 0v4"/>
          <path d="M4 15.5C4 12.5 6 11 8 11h8c2 0 4 1.5 4 4.5 0 4-3 7.5-8 7.5s-8-3.5-8-7.5z"/>
          <path d="M16 11V5a2 2 0 00-4 0"/>
          <path d="M12 11V4a2 2 0 00-4 0v7"/>
        </svg>
      </div>
      <div class="title">Say Hello!</div>
      <div class="subtitle">I'm ShopMate - your grocery assistant</div>
      <div class="hint">Wave or say "Hello" to start</div>
    </div>
    </body></html>"""
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_idle failed: {e}")


def pepper_show_categories():
    """Show a full product-category dashboard on Pepper's tablet.
    Uses SVG icons (no emoji — Pepper's old Android browser can't
    render them). Includes a search bar and product listings."""
    if not _display_enabled(): return
    print("📺 Pepper tablet shows product category dashboard")

    from grocery_db import get_all_items
    items = get_all_items()

    # Group products by category
    cats = {}
    for it in items:
        c = it["category"]
        if c not in cats:
            cats[c] = []
        cats[c].append(it)

    # SVG icons per category (inline, no external deps)
    _svg = {
        "dairy": '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><ellipse cx="12" cy="12" rx="8" ry="9"/><path d="M8 8c1 2 5 2 8 0"/><path d="M9 14c.5 1 4.5 1 6 0"/></svg>',
        "milk": '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M8 2h8v4l2 3v11a2 2 0 01-2 2H8a2 2 0 01-2-2V9l2-3V2z"/><path d="M6 9h12"/></svg>',
        "bakery": '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M5 18h14a2 2 0 002-2c0-2-3-3-3-6 0-2-1-4-4-4h-4c-3 0-4 2-4 4 0 3-3 4-3 6a2 2 0 002 2z"/><path d="M9 18v2a1 1 0 001 1h4a1 1 0 001-1v-2"/></svg>',
        "produce": '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="14" r="7"/><path d="M12 7V3"/><path d="M15 5c-1 1-3 1.5-5 .5"/></svg>',
        "beverages": '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M18 8h1a4 4 0 010 8h-1"/><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/><path d="M6 1v3"/><path d="M10 1v3"/><path d="M14 1v3"/></svg>',
        "pantry": '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4H6z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 01-8 0"/></svg>',
        "snacks": '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 12h18"/><path d="M9 4v16"/><path d="M15 4v16"/></svg>',
        "frozen": '<svg viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round"><path d="M12 2v20M2 12h20"/><path d="M20 16l-4-4 4-4"/><path d="M4 8l4 4-4 4"/><path d="M16 4l-4 4-4-4"/><path d="M8 20l4-4 4 4"/></svg>',
    }

    _colors = {
        "dairy": "#4fc3f7", "milk": "#81d4fa", "bakery": "#ffcc80",
        "produce": "#66bb6a", "beverages": "#ce93d8", "pantry": "#ffab91",
        "snacks": "#ef9a9a", "frozen": "#80deea",
    }

    # Build category sections
    sections_html = ""
    for cat_name, products in cats.items():
        color = _colors.get(cat_name, "#90a4ae")
        svg_template = _svg.get(cat_name, _svg["pantry"])
        svg_icon = svg_template.replace("{c}", color)

        sections_html += f'''
        <div class="category" style="--cat-color: {color};">
          <div class="cat-icon">{svg_icon}</div>
          <div class="cat-name">{cat_name.title()}</div>
          <div class="cat-count">{len(products)} Items</div>
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      body {{
        font-family: 'Segoe UI', Arial, sans-serif;
        background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%);
        min-height: 100vh; padding: 20px; color: #1f2937;
      }}

      /* ---- HEADER ---- */
      .top-bar {{
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 20px; background: rgba(255,255,255,0.8);
        padding: 12px 24px; border-radius: 20px; box-shadow: 0 8px 32px rgba(31,38,135,0.07);
        backdrop-filter: blur(10px);
      }}
      .logo {{ display: flex; align-items: center; gap: 12px; }}
      .logo svg {{ width: 40px; height: 40px; stroke: #6b21a8; }}
      .logo-text {{ font-size: 24px; font-weight: 800; color: #4c1d95; letter-spacing: -0.5px; }}
      .logo-sub {{ font-size: 13px; color: #6b7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}

      /* ---- SEARCH BAR ---- */
      .search-wrap {{
        flex: 1; max-width: 400px; margin: 0 20px; position: relative;
      }}
      .search-wrap svg {{
        position: absolute; left: 14px; top: 50%;
        transform: translateY(-50%); width: 20px; height: 20px; stroke: #9ca3af;
      }}
      .search-wrap input {{
        width: 100%; padding: 12px 16px 12px 42px;
        border-radius: 999px; border: 2px solid transparent;
        background: #fff; color: #111827; font-size: 16px; font-weight: 500;
        outline: none; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
      }}
      .search-wrap input:focus {{ border-color: #8b5cf6; box-shadow: 0 0 0 4px rgba(139,92,246,0.1); }}
      .search-wrap input::placeholder {{ color: #9ca3af; }}

      /* ---- HINT BANNER ---- */
      .hint {{
        text-align: center; padding: 14px;
        background: linear-gradient(135deg, #f6d365 0%, #fda085 100%);
        border-radius: 16px; margin-bottom: 24px;
        font-size: 18px; font-weight: 700; color: #fff;
        box-shadow: 0 10px 20px rgba(253,160,133,0.2);
        letter-spacing: 0.5px;
      }}

      /* ---- CATEGORY GRID ---- */
      .grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 24px;
        max-width: 1100px;
        margin: 0 auto;
      }}
      .category {{
        background: rgba(255,255,255,0.95);
        border-radius: 28px; padding: 36px 20px;
        text-align: center;
        border-bottom: 8px solid var(--cat-color);
        box-shadow: 0 12px 30px rgba(0,0,0,0.06);
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: 16px;
      }}
      .cat-icon {{
        width: 80px; height: 80px;
        background: #fff; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
        border: 2px solid #f3f4f6;
      }}
      .cat-icon svg {{ width: 44px; height: 44px; stroke: var(--cat-color); }}
      .cat-name {{
        font-size: 24px; font-weight: 800;
        color: #1f2937; letter-spacing: -0.5px;
      }}
      .cat-count {{
        font-size: 15px; color: #6b7280; font-weight: 700;
        background: #f3f4f6; padding: 6px 16px; border-radius: 999px;
      }}

      /* ---- FOOTER ---- */
      .footer {{
        text-align: center; margin-top: 24px; font-size: 14px; font-weight: 600;
        color: rgba(255,255,255,0.8);
      }}
    </style></head><body>
    
    <div class="top-bar">
      <div class="logo">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round">
          <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
          <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
        </svg>
        <div>
          <div class="logo-text">ShopMate</div>
          <div class="logo-sub">Grocery Assistant</div>
        </div>
      </div>
      <div class="search-wrap">
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
        <input type="text" placeholder="I'm listening..." readonly>
      </div>
    </div>

    <div class="hint">Tell me what you need — e.g. "I need milk"</div>

    <div class="grid">
      {sections_html}
    </div>

    <div class="footer">Say "Help" or "Goodbye" anytime</div>

    </body></html>'''
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_categories failed: {e}")


def pepper_show_category_products(category: str, products: list):
    """Show all products in a category on Pepper's tablet with
    names, prices, stock, and aisle info."""
    if not _display_enabled(): return
    print(f"📺 Pepper tablet shows {category} products ({len(products)} items)")

    _colors = {
        "dairy": "#4fc3f7", "milk": "#81d4fa", "bakery": "#ffcc80",
        "produce": "#66bb6a", "beverages": "#ce93d8", "pantry": "#ffab91",
        "snacks": "#ef9a9a", "frozen": "#80deea",
    }
    color = _colors.get(category.lower(), "#667eea")

    rows = ""
    for p in products:
        stock_class = "in" if p["stock"] > 0 else "out"
        stock_txt = f'{p["stock"]} in stock' if p["stock"] > 0 else "Out of stock"
        rows += f'''
        <div class="product-card">
          <div class="pc-name">{p["name"]}</div>
          <div class="pc-aisle">{p["aisle"].replace("_"," ").title()}</div>
          <div class="pc-price">EUR {p["price"]:.2f}</div>
          <div class="pc-stock {stock_class}">{stock_txt}</div>
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      body {{
        font-family: 'Segoe UI', Arial, sans-serif;
        background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%);
        color: #1f2937; min-height: 100vh; padding: 30px;
      }}
      .header {{
        text-align: center; margin-bottom: 30px;
        padding: 20px; background: rgba(255,255,255,0.95);
        border-radius: 20px; box-shadow: 0 8px 30px rgba(0,0,0,0.06);
        border: 2px solid #fff; border-bottom: 6px solid {color};
        max-width: 1000px; margin: 0 auto 30px auto;
      }}
      .header h1 {{ font-size: 36px; font-weight: 800; color: {color}; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 1px; }}
      .header p {{ font-size: 18px; color: #6b7280; font-weight: 600; }}
      
      .grid {{
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;
        max-width: 1000px; margin: 0 auto;
      }}
      .product-card {{
        background: #fff; border-radius: 24px; padding: 30px 20px;
        border: 2px solid #e5e7eb; border-top: 8px solid {color};
        box-shadow: 0 4px 15px rgba(0,0,0,0.04);
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        text-align: center;
      }}
      .pc-name {{ font-size: 22px; font-weight: 800; color: #111827; margin-bottom: 6px; letter-spacing: -0.5px; }}
      .pc-aisle {{ font-size: 14px; color: #9ca3af; font-weight: 700; text-transform: uppercase; margin-bottom: 16px; letter-spacing: 0.5px; }}
      .pc-price {{ font-size: 26px; font-weight: 800; color: #059669; margin-bottom: 12px; }}
      .pc-stock {{ font-size: 13px; font-weight: 800; padding: 6px 14px; border-radius: 99px; text-transform: uppercase; letter-spacing: 0.5px; }}
      .pc-stock.in {{ background: #d1fae5; color: #059669; }}
      .pc-stock.out {{ background: #fee2e2; color: #dc2626; }}

      .hint {{
        text-align: center; margin: 30px auto 0; padding: 16px;
        background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); 
        border-radius: 100px; font-size: 18px; font-weight: 700; color: #fff;
        max-width: 600px; box-shadow: 0 10px 20px rgba(253,160,133,0.3); border: 2px solid #fff;
      }}
    </style></head><body>
    <div class="header">
      <h1>{category.title()}</h1>
      <p>{len(products)} product{"s" if len(products) != 1 else ""} available</p>
    </div>
    <div class="grid">{rows}</div>
    <div class="hint">Say the product name to add it to your cart - e.g. "I want milk"</div>
    </body></html>'''
    try:
        _pepper.show_html(html)
    except Exception as e:
        print(f"[pepper_api] show_category_products failed: {e}")


def pepper_show_cart(cart: list):
    """Show the current shopping cart on Pepper's tablet."""
    if not _display_enabled(): return
    if not cart:
        return
    print(f"📺 Pepper tablet shows cart ({len(cart)} items)")

    total = sum(p["price"] for p in cart)
    items_html = ""
    for i, p in enumerate(cart, 1):
        items_html += f'''
        <div class="cart-item">
          <span class="num">{i}.</span>
          <span class="ci-name">{p["name"]}</span>
          <span class="ci-price">EUR {p["price"]:.2f}</span>
        </div>'''

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
      * {{ margin:0; padding:0; box-sizing:border-box; }}
      body {{
        font-family: 'Segoe UI', Arial, sans-serif;
        background: linear-gradient(135deg, #e0c3fc 0%, #8ec5fc 100%);
        color: #1f2937; min-height: 100vh; padding: 30px;
        display: flex; align-items: center; justify-content: center;
      }}
      .card {{
        background: #ffffff; border-radius: 24px; padding: 40px 48px;
        min-width: 480px; border-top: 8px solid #8b5cf6;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
      }}
      .card h1 {{
        font-size: 32px; color: #7c3aed; margin-bottom: 8px;
        display: flex; align-items: center; gap: 12px; font-weight: 800; letter-spacing: -0.5px;
      }}
      .card h1 svg {{ width: 36px; height: 36px; stroke: #7c3aed; }}
      .subtitle {{ font-size: 16px; color: #6b7280; font-weight: 600; margin-bottom: 24px; text-transform: uppercase; }}
      .cart-item {{
        display: flex; align-items: center; gap: 12px;
        padding: 14px 16px; margin-bottom: 10px;
        background: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb;
      }}
      .num {{ color: #7c3aed; font-weight: 800; font-size: 18px; min-width: 28px; }}
      .ci-name {{ flex: 1; font-size: 20px; font-weight: 700; color: #111827; }}
      .ci-price {{ font-weight: 800; color: #059669; font-size: 18px; }}
      .total {{
        display: flex; justify-content: space-between;
        margin-top: 24px; padding-top: 20px;
        border-top: 2px dashed #d1d5db;
        font-size: 24px; font-weight: 800;
      }}
      .total .label {{ color: #374151; }}
      .total .val {{ color: #059669; }}
      .hint {{
        text-align: center; margin-top: 24px; padding: 14px;
        background: #ede9fe; color: #5b21b6; border-radius: 12px;
        font-size: 16px; font-weight: 600;
      }}
    </style></head><body>
    <div class="card">
      <h1>
        <svg viewBox="0 0 24 24" fill="none" stroke-width="2.5">
          <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
          <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
        </svg>
        Your Cart
      </h1>
      <div class="subtitle">{len(cart)} item{"s" if len(cart) != 1 else ""}</div>
      {items_html}
      <div class="total">
        <span class="label">Total</span>
        <span class="val">EUR {total:.2f}</span>
      </div>
      <div class="hint">Say "done" or "that's all" when ready, or add more items</div>
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
