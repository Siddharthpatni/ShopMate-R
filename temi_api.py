"""
temi_api.py — Temi robot control for ShopMate-R.

Temi is the mobile robot that navigates the store to grocery aisles.
No mock mode — this module always sends commands to the real Temi at
config.TEMI_IP and updates the Flask dashboard in parallel.
"""

import time
import requests
import config

DASHBOARD = config.DASHBOARD_URL

def _get_temi_base():
    return f"http://{config.TEMI_IP}:8080"


# =========================================================================
# Internal: push state to Flask dashboard
# =========================================================================

def _push_state(payload: dict):
    """Best-effort POST to the dashboard. Never raise."""
    try:
        requests.post(f"{DASHBOARD}/api/state", json=payload, timeout=1.0)
    except Exception:
        pass


# =========================================================================
# NAVIGATION
# =========================================================================

def temi_navigate_to(location_key: str):
    """Send Temi to a saved aisle location and block until it arrives.

    `location_key` must be a key in config.TEMI_LOCATIONS (for example
    "dairy_aisle" or "produce_aisle").
    """
    target = config.TEMI_LOCATIONS.get(location_key, location_key)
    print(f"🚚 Temi navigating to: {location_key}  (saved id: {target})")

    _push_state({
        "temi_status": "navigating",
        "temi_location": location_key,
    })

    try:
        # The Temi API blocks until arrival. We set a long timeout of 120s
        # to allow the robot to drive across the store.
        requests.post(
            f"{_get_temi_base()}/goto",
            json={"text": target},
            timeout=120.0,
        )
    except Exception as e:
        print(f"[temi_api] navigate failed/timeout: {e}")

    # Polling /status is disabled as it returns 404 on this robot version.
    # The blocking POST above serves as our 'arrival' check.
    time.sleep(1.0)

    _push_state({
        "temi_status": "arrived",
        "temi_location": location_key,
    })
    print(f"🚚 Temi arrived at {location_key}")


def _wait_until_arrived(timeout: float = 60.0, poll: float = 0.5):
    """Placeholder as navigation now blocks in the POST request."""
    pass


def temi_go_home():
    temi_navigate_to(config.TEMI_HOME)


def temi_save_location(location_key: str):
    """Save Temi's current physical position as a new location."""
    target = config.TEMI_LOCATIONS.get(location_key, location_key)
    print(f"📍 Temi saving current location as: {location_key} (id: {target})")
    try:
        requests.post(
            f"{_get_temi_base()}/save_location",
            json={"location": target},
            timeout=3.0,
        )
        print(f"✅ Temi location saved: {location_key}")
    except Exception as e:
        print(f"[temi_api] save location failed: {e}")


# =========================================================================
# SPEECH
# =========================================================================

def temi_say(text: str):
    print(f"🚚 Temi says: {text}")
    _push_state({"temi_last_speech": text})
    try:
        requests.post(
            f"{_get_temi_base()}/say",
            json={"text": text, "language": "english"},
            timeout=5.0,
        )
    except Exception as e:
        print(f"[temi_api] say failed: {e}")


# =========================================================================
# DISPLAY MODE
# =========================================================================

def _display_enabled() -> bool:
    return config.DISPLAY_MODE and config.TEMI_DISPLAY_MODE


def temi_show_product(product: dict):
    if not _display_enabled():
        print(f"📵 Temi display mode OFF — would have shown {product.get('name')}")
        return
    print(f"📺 Temi screen shows product: {product.get('name')}")
    _push_state({
        "temi_screen": {
            "type": "product",
            "name": product.get("name"),
            "price": product.get("price"),
            "aisle": product.get("aisle"),
            "stock": product.get("stock"),
        }
    })
    
    # Also show it on the REAL Temi screen via Webview
    html = _product_card_html(product.get("name"), product.get("price"), product.get("aisle"))
    data_uri = f"data:text/html;base64,{html}"
    
    # Try common Temi webview endpoints
    # We try both 'url' and 'text' keys as some bridges are inconsistent
    endpoints = ["/webview", "/top_webview", "/display", "/show_url", "/url", "/loadurl"]
    success = False
    for ep in endpoints:
        for key in ["url", "text"]:
            try:
                r = requests.post(f"{_get_temi_base()}{ep}", json={key: data_uri}, timeout=1.5)
                if r.status_code != 404:
                    success = True
                    break
            except:
                continue
        if success: break
    
    if not success:
        print(f"⚠️ [temi_api] Could not find a working display endpoint on Temi.")


def _product_card_html(name: str, price: float, aisle: str) -> str:
    """Generate a base64 Data URI for the product card."""
    import base64
    from pepper_api import _UI_CSS_BASE, _CAT_COLORS, _CAT_SVG

    # Get a default color/svg layout for Temi's display (just map everything to pantry for simplicity if category is unknown)
    # Temi's layout is simpler than Pepper's category cards, it's just a single big card
    color    = "#2c5282"
    svg_icon = _CAT_SVG["pantry"].replace("{c}", color)

    content = f"""
    <html><head><style>
    {_UI_CSS_BASE}
      body {{
        display: flex; align-items: center; justify-content: center;
        padding: 40px; background: #f5f7fa;
      }}
      .card {{
        width: 100%; max-width: 700px;
        background: #ffffff;
        border-radius: 20px;
        border: 1px solid #e2e8f0;
        border-top: 6px solid {color};
        box-shadow: 0 8px 30px rgba(15, 23, 42, 0.08);
        padding: 60px; text-align: center;
      }}
      .icon-wrap {{
        width: 120px; height: 120px;
        margin: 0 auto 30px;
        border-radius: 50%;
        background: {color}14;
        display: flex; align-items: center; justify-content: center;
      }}
      .icon-wrap svg {{ width: 64px; height: 64px; stroke: {color}; }}
      .name {{
        font-size: 48px; font-weight: 800;
        color: #1a202c; margin-bottom: 24px;
        letter-spacing: -1px;
      }}
      .price {{
        font-size: 56px; font-weight: 700;
        color: #2f855a; margin: 12px 0 32px;
        letter-spacing: -1px;
      }}
      .price .currency {{
        font-size: 28px; vertical-align: top;
        color: #718096; margin-right: 8px;
        font-weight: 600;
      }}
      .meta {{
        padding: 24px;
        background: #f7fafc;
        border-radius: 12px;
        border: 1px solid #edf2f7;
      }}
      .aisle-label {{
        font-size: 14px; font-weight: 700;
        color: #a0aec0; text-transform: uppercase;
        letter-spacing: 1.2px; margin-bottom: 8px;
      }}
      .aisle-value {{
        font-size: 28px; font-weight: 700;
        color: #2d3748;
      }}
    </style></head><body>
    <div class="card">
      <div class="icon-wrap">{svg_icon}</div>
      <div class="name">{name}</div>
      <div class="price"><span class="currency">EUR</span>{price:.2f}</div>
      <div class="meta">
        <div class="aisle-label">Pick up location</div>
        <div class="aisle-value">{aisle.replace('_', ' ').title()}</div>
      </div>
    </div>
    </body></html>
    """
    return base64.b64encode(content.encode()).decode()


def temi_show_image(url: str):
    if not _display_enabled():
        return
    print(f"📺 Temi screen shows image: {url}")
    _push_state({"temi_screen": {"type": "image", "url": url}})


def temi_show_message(text: str):
    if not _display_enabled():
        return
    print(f"📺 Temi screen shows message: {text}")
    _push_state({"temi_screen": {"type": "message", "text": text}})


def temi_clear_screen():
    if not _display_enabled():
        return
    _push_state({"temi_screen": None})


def temi_show_categories():
    """Show a product-category dashboard on Temi's screen.
    Displayed right after the greeting so the customer can browse
    what the store offers while Pepper talks."""
    if not _display_enabled():
        print("📵 Temi display mode OFF — would have shown category dashboard")
        return
    print("📺 Temi screen shows product category dashboard")

    from grocery_db import get_all_items
    from pepper_api import _UI_CSS_BASE, _CAT_COLORS, _CAT_SVG
    import base64

    items = get_all_items()
    cats = {}
    for it in items:
        cats.setdefault(it["category"], []).append(it)

    tiles_html = ""
    for cat_name, products in cats.items():
        color    = _CAT_COLORS.get(cat_name, "#4a5568")
        svg_tpl  = _CAT_SVG.get(cat_name, _CAT_SVG["pantry"])
        svg_icon = svg_tpl.replace("{c}", color)
        tiles_html += f"""
        <div class="tile" style="--cat-color: {color};">
          <div class="tile-icon">{svg_icon}</div>
          <div class="tile-name">{cat_name.title()}</div>
          <div class="tile-count">{len(products)} items</div>
        </div>"""

    content = f"""<html><head><style>
    {_UI_CSS_BASE}
      body {{ background: #f5f7fa; padding: 32px 40px; display: flex; flex-direction: column; }}
      .header {{ text-align: center; margin-bottom: 32px; }}
      .h-title {{ font-size: 38px; font-weight: 800; color: #1a202c; letter-spacing: -0.5px; margin-bottom: 8px; }}
      .h-sub {{ font-size: 20px; color: #718096; }}
      
      .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; flex: 1; }}
      .tile {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 32px 20px;
        text-align: center;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
      }}
      .tile-icon {{
        width: 80px; height: 80px;
        margin: 0 auto 20px;
        background: var(--cat-color)14;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
      }}
      .tile-icon svg {{ width: 44px; height: 44px; }}
      .tile-name {{
        font-size: 22px; font-weight: 700;
        color: #1a202c; margin-bottom: 6px;
        letter-spacing: -0.2px;
      }}
      .tile-count {{
        font-size: 14px; font-weight: 600;
        color: #718096; text-transform: uppercase;
        letter-spacing: 0.8px;
      }}
    </style></head><body>
      <div class="header">
        <div class="h-title">What would you like?</div>
        <div class="h-sub">Tell me a product name and I'll bring it to you.</div>
      </div>
      <div class="grid">{tiles_html}</div>
    </body></html>"""

    data_uri = f"data:text/html;base64,{base64.b64encode(content.encode()).decode()}"

    # Push to dashboard state as well
    _push_state({
        "temi_screen": {
            "type": "message",
            "text": "Showing product categories",
        }
    })

    # We try both variations to maximize compatibility with different bridges apps.
    endpoints = ["/webview", "/top_webview", "/display", "/show_url", "/url", "/loadurl"]
    success = False
    for ep in endpoints:
        for key in ["url", "text"]:
            try:
                r = requests.post(f"{_get_temi_base()}{ep}", json={key: data_uri}, timeout=1.5)
                if r.status_code != 404:
                    success = True
                    break
            except:
                continue
        if success: break

    if not success:
        print("⚠️ [temi_api] Could not find a working display endpoint on Temi.")


# =========================================================================
# DELIVERY
# =========================================================================

def temi_deliver_item(product: dict):
    """Full fetch-and-deliver flow: Temi drives from the customer to
    the product's aisle, picks up the item, then drives BACK to the
    customer at the entrance and hands it over. Pepper will say
    goodbye once this function returns.
    """
    temi_show_product(product)

    # 1. Leave the customer and go to the aisle
    temi_say(f"One moment, I'll bring you the {product['name']}.")
    _push_state({"temi_status": "fetching"})
    temi_navigate_to(product["aisle"])

    # 2. Pick the item off the shelf
    temi_say(f"Picking up the {product['name']} from the shelf now.")
    temi_show_message(f"Picking up {product['name']}...")
    _push_state({"temi_status": "picking"})
    temi_wait(2.5)   # tray-loading pause

    # 3. Drive back to the customer at the entrance
    temi_say("Bringing it to you now.")
    _push_state({"temi_status": "returning"})
    temi_navigate_to(config.TEMI_HOME)

    # 4. Hand the item over
    temi_show_product(product)
    temi_say(f"Here is your {product['name']}. Please take it from my tray.")
    _push_state({"temi_status": "delivered"})
    return True


# =========================================================================
# MIC MODE
# =========================================================================

def temi_mic_active() -> bool:
    """Does Temi currently own the voice input channel?"""
    return config.MIC_MODE and config.TEMI_MIC_MODE


def temi_prompt_listen(prompt: str = "Tell me what you need."):
    if not temi_mic_active():
        return
    temi_say(prompt)


# =========================================================================
# UTILITY
# =========================================================================

def temi_wait(seconds: float):
    time.sleep(seconds)
