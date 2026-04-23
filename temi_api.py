"""
temi_api.py — Temi robot control for ShopMate-R.

Temi is the mobile robot that navigates the store to grocery aisles.
No mock mode — this module always sends commands to the real Temi at
config.TEMI_IP and updates the Flask dashboard in parallel.

Connection layer (navigation, speech, HTTP POSTs, webview endpoint
discovery) is BYTE-IDENTICAL to the original implementation.  The
only things I've changed in this file are the HTML strings rendered
on Temi's screen: a glass-style product card and a glass category
dashboard.  Everything that touches the wire is unchanged.
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
    """Generate a base64 Data URI for the product card.

    Glass-style card: translucent surface, blurred saturated backdrop,
    thin white border, inset highlight, soft shadow. The structure
    (base64 Data URI) and function signature are unchanged — only the
    rendered HTML/CSS is more polished.
    """
    import base64
    safe_aisle = (aisle or "").replace("_", " ").title()
    content = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  *,*::before,*::after {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display',
                 'Roboto', 'Segoe UI', Arial, sans-serif;
    color: #ffffff;
    background:
      radial-gradient(1200px 800px at 10% 10%, rgba(175,82,222,0.45) 0%, transparent 55%),
      radial-gradient(1000px 700px at 95% 20%, rgba(10,132,255,0.50) 0%, transparent 55%),
      radial-gradient(900px 700px at 20% 100%, rgba(255,55,95,0.40) 0%, transparent 55%),
      radial-gradient(900px 700px at 100% 100%, rgba(255,159,10,0.35) 0%, transparent 55%),
      linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%);
    min-height: 100vh;
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
  }}
  .card {{
    width: 100%; max-width: 640px;
    padding: 44px 48px;
    text-align: center;
    border-radius: 32px;
    background: rgba(255,255,255,0.12);
    -webkit-backdrop-filter: blur(40px) saturate(180%);
            backdrop-filter: blur(40px) saturate(180%);
    border: 1px solid rgba(255,255,255,0.24);
    box-shadow:
      0 1px 0 rgba(255,255,255,0.3) inset,
      0 20px 50px rgba(0,0,0,0.4),
      0 40px 100px rgba(0,0,0,0.25);
    position: relative; overflow: hidden;
  }}
  .card::before {{
    content: ""; position: absolute; inset: 0 0 auto 0; height: 5px;
    background: linear-gradient(90deg, #34C759 0%, #0A84FF 100%);
  }}
  .icon {{
    width: 112px; height: 112px;
    margin: 14px auto 28px;
    border-radius: 28px;
    background: rgba(255,255,255,0.18);
    -webkit-backdrop-filter: blur(20px);
            backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.35);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 1px 0 rgba(255,255,255,0.4) inset;
  }}
  .icon svg {{ width: 60px; height: 60px; stroke: #ffffff; }}
  .name {{
    font-size: 46px; font-weight: 700;
    margin-bottom: 26px; letter-spacing: -1px;
    line-height: 1.1; color: #ffffff;
  }}
  .price {{
    font-size: 60px; font-weight: 700;
    margin-bottom: 20px;
    letter-spacing: -2px; line-height: 1;
    color: #ffffff;
  }}
  .price .cur {{
    font-size: 24px; color: rgba(255,255,255,0.6);
    vertical-align: top; margin-right: 8px; font-weight: 600;
  }}
  .aisle {{
    display: inline-flex; align-items: center; gap: 10px;
    padding: 14px 24px;
    background: rgba(255,255,255,0.14);
    -webkit-backdrop-filter: blur(16px);
            backdrop-filter: blur(16px);
    border: 1px solid rgba(255,255,255,0.28);
    border-radius: 999px;
    font-size: 20px; font-weight: 600;
    color: rgba(255,255,255,0.95);
  }}
  .aisle svg {{ width: 20px; height: 20px; stroke: #34C759; }}
</style></head><body>
  <div class="card">
    <div class="icon">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4H6z"/>
        <path d="M3 6h18"/><path d="M16 10a4 4 0 01-8 0"/>
      </svg>
    </div>
    <div class="name">{name}</div>
    <div class="price"><span class="cur">EUR</span>{float(price or 0):.2f}</div>
    <div class="aisle">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/>
      </svg>
      Find in {safe_aisle}
    </div>
  </div>
</body></html>"""
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
            cats[c] = {"count": 0, "in_stock": 0}
        cats[c]["count"] += 1
        if it["stock"] > 0:
            cats[c]["in_stock"] += 1

    # Apple SF-inspired palette + inline SVG icons (no emoji — Temi's
    # browser may not have an emoji font).
    _meta = {
        "dairy":     {"color": "#0A84FF", "on": "#CCE5FF",
                      "svg": '<ellipse cx="12" cy="12" rx="8" ry="9"/><path d="M8 8c1 2 5 2 8 0"/>'},
        "milk":      {"color": "#30B0C7", "on": "#CFF2F7",
                      "svg": '<path d="M8 2h8v4l2 3v11a2 2 0 01-2 2H8a2 2 0 01-2-2V9l2-3V2z"/><path d="M6 9h12"/>'},
        "bakery":    {"color": "#FF9F0A", "on": "#FFE5B8",
                      "svg": '<path d="M5 18h14a2 2 0 002-2c0-2-3-3-3-6 0-2-1-4-4-4h-4c-3 0-4 2-4 4 0 3-3 4-3 6a2 2 0 002 2z"/>'},
        "produce":   {"color": "#34C759", "on": "#CBEFD3",
                      "svg": '<circle cx="12" cy="14" r="7"/><path d="M12 7V3"/>'},
        "beverages": {"color": "#AF52DE", "on": "#ECD6F7",
                      "svg": '<path d="M18 8h1a4 4 0 010 8h-1"/><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/>'},
        "pantry":    {"color": "#FF6B35", "on": "#FFD3BD",
                      "svg": '<path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4H6z"/><path d="M3 6h18"/>'},
        "snacks":    {"color": "#FF375F", "on": "#FFC9D4",
                      "svg": '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M3 12h18"/>'},
        "frozen":    {"color": "#5AC8FA", "on": "#D1EFFC",
                      "svg": '<path d="M12 2v20M2 12h20"/>'},
    }

    tiles = ""
    for cat_name, info in cats.items():
        meta = _meta.get(cat_name, {"color": "#8E8E93", "on": "#E5E5EA",
                                     "svg": '<rect x="4" y="4" width="16" height="16" rx="3"/>'})
        tiles += f"""
        <div class="tile">
          <div class="t-icon" style="background: linear-gradient(135deg, {meta['color']} 0%, {meta['on']}33 100%); border-color: {meta['color']}66;">
            <svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              {meta['svg']}
            </svg>
          </div>
          <div class="t-name">{cat_name.title()}</div>
          <div class="t-count">{info['in_stock']} of {info['count']} in stock</div>
        </div>"""

    content = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
      *,*::before,*::after {{ margin:0; padding:0; box-sizing:border-box; }}
      body {{
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display',
                     'Roboto', 'Segoe UI', Arial, sans-serif;
        background:
          radial-gradient(1200px 800px at 10% 10%, rgba(175,82,222,0.45) 0%, transparent 55%),
          radial-gradient(1000px 700px at 95% 20%, rgba(10,132,255,0.50) 0%, transparent 55%),
          radial-gradient(900px 700px at 20% 100%, rgba(255,55,95,0.40) 0%, transparent 55%),
          radial-gradient(900px 700px at 100% 100%, rgba(255,159,10,0.35) 0%, transparent 55%),
          linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%);
        color: #fff;
        min-height: 100vh;
        padding: 24px 28px;
      }}
      .header {{
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 22px;
        padding: 14px 20px;
        border-radius: 20px;
        background: rgba(255,255,255,0.12);
        -webkit-backdrop-filter: blur(28px) saturate(180%);
                backdrop-filter: blur(28px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.22);
        box-shadow: 0 1px 0 rgba(255,255,255,0.3) inset, 0 8px 24px rgba(0,0,0,0.2);
      }}
      h1 {{ font-size: 28px; font-weight: 700; letter-spacing: -0.5px; color: #fff; }}
      .sub {{ font-size: 14px; color: rgba(255,255,255,0.65); margin-top: 4px;
              letter-spacing: 0.4px; }}
      .status {{
        padding: 8px 16px; border-radius: 999px;
        background: rgba(52,199,89,0.2);
        border: 1px solid rgba(52,199,89,0.4);
        color: #6EEA90;
        font-size: 13px; font-weight: 700; letter-spacing: 0.4px;
      }}
      .grid {{
        display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px;
      }}
      .tile {{
        padding: 20px 16px;
        border-radius: 22px;
        text-align: center;
        background: rgba(255,255,255,0.12);
        -webkit-backdrop-filter: blur(26px) saturate(180%);
                backdrop-filter: blur(26px) saturate(180%);
        border: 1px solid rgba(255,255,255,0.22);
        box-shadow:
          0 1px 0 rgba(255,255,255,0.3) inset,
          0 8px 24px rgba(0,0,0,0.2);
      }}
      .t-icon {{
        width: 60px; height: 60px;
        border: 1px solid; border-radius: 18px;
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 12px;
        box-shadow: 0 1px 0 rgba(255,255,255,0.3) inset;
      }}
      .t-icon svg {{ width: 32px; height: 32px; }}
      .t-name  {{ font-size: 18px; font-weight: 700; margin-bottom: 4px;
                  color: #fff; letter-spacing: -0.3px; }}
      .t-count {{ font-size: 11px; font-weight: 700; color: rgba(255,255,255,0.6);
                  text-transform: uppercase; letter-spacing: 1px; }}
    </style></head><body>
      <div class="header">
        <div>
          <h1>What would you like?</h1>
          <div class="sub">Tell me the product name</div>
        </div>
        <div class="status">● ShopMate</div>
      </div>
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
