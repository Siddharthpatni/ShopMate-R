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
    content = f"""
    <html><head><style>
      body {{ background: #1a1a1a; color: white; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
      .card {{ background: #2d2d2d; padding: 40px; border-radius: 30px; border: 4px solid #4ade80; text-align: center; width: 80%; }}
      .icon {{ margin-bottom: 20px; }}
      .name {{ font-size: 48px; font-weight: bold; margin-bottom: 15px; color: #4ade80; }}
      .price {{ font-size: 42px; color: #ffffff; margin-bottom: 10px; }}
      .aisle {{ font-size: 32px; color: #9ca3af; }}
    </style></head><body>
    <div class="card">
      <div class="icon">
        <svg width="100" height="100" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M6 2L3 6V20C3 20.5304 3.21071 21.0391 3.58579 21.4142C3.96086 21.7893 4.46957 22 5 22H19C19.5304 22 20.0391 21.7893 20.4142 21.4142C20.7893 21.0391 21 20.5304 21 20V6L18 2H6Z" stroke="#4ade80" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M3 6H21" stroke="#4ade80" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M16 10C16 11.0609 15.5786 12.0783 14.8284 12.8284C14.0783 13.5786 13.0609 14 12 14C10.9391 14 9.92172 13.5786 9.17157 12.8284C8.42143 12.0783 8 11.0609 8 10" stroke="#4ade80" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <div class="name">{name}</div>
      <div class="price">EUR {price:.2f}</div>
      <div class="aisle">Find in: {aisle.replace('_', ' ').title()}</div>
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
    import base64

    items = get_all_items()
    cats = {}
    for it in items:
        c = it["category"]
        if c not in cats:
            cats[c] = {"count": 0}
        cats[c]["count"] += 1

    _meta = {
        "dairy":     {"icon": "&#x1F9C0;", "color": "#4fc3f7"},
        "milk":      {"icon": "&#x1F95B;", "color": "#81d4fa"},
        "bakery":    {"icon": "&#x1F950;", "color": "#ffcc80"},
        "produce":   {"icon": "&#x1F34E;", "color": "#a5d6a7"},
        "beverages": {"icon": "&#x2615;",  "color": "#ce93d8"},
        "pantry":    {"icon": "&#x1F35D;", "color": "#ffab91"},
        "snacks":    {"icon": "&#x1F36B;", "color": "#ef9a9a"},
        "frozen":    {"icon": "&#x1F9CA;", "color": "#80deea"},
    }

    tiles = ""
    for cat_name, info in cats.items():
        meta = _meta.get(cat_name, {"icon": "&#x1F4E6;", "color": "#90a4ae"})
        tiles += f"""
        <div style="background:#2d2d2d; border-radius:20px; padding:20px 14px;
             text-align:center; border-left:5px solid {meta['color']};
             box-shadow:0 4px 16px rgba(0,0,0,0.3);">
          <div style="font-size:42px; margin-bottom:6px;">{meta['icon']}</div>
          <div style="font-size:18px; font-weight:700; color:{meta['color']};">
            {cat_name.title()}</div>
          <div style="font-size:13px; color:#9ca3af;">{info['count']} items</div>
        </div>"""

    content = f"""<html><head><style>
      body {{ background:#1a1a1a; color:white; font-family:sans-serif;
             margin:0; padding:24px; }}
      h1 {{ text-align:center; font-size:28px; color:#4ade80;
           margin-bottom:6px; }}
      p  {{ text-align:center; font-size:16px; color:#9ca3af;
           margin-bottom:20px; }}
      .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }}
    </style></head><body>
      <h1>What would you like?</h1>
      <p>Tell me the product name</p>
      <div class="grid">{tiles}</div>
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
