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
TEMI_BASE = f"http://{config.TEMI_IP}:8080"


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
        requests.post(
            f"{TEMI_BASE}/goto",
            json={"location": target},
            timeout=3.0,
        )
    except Exception as e:
        print(f"[temi_api] navigate failed: {e}")

    # Wait for Temi to report arrival. Real Temi exposes /status; we poll.
    _wait_until_arrived()

    _push_state({
        "temi_status": "arrived",
        "temi_location": location_key,
    })
    print(f"🚚 Temi arrived at {location_key}")


def _wait_until_arrived(timeout: float = 60.0, poll: float = 0.5):
    """Poll Temi's /status endpoint until it reports 'arrived' or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{TEMI_BASE}/status", timeout=1.0)
            if r.ok and r.json().get("status") == "arrived":
                return
        except Exception:
            pass
        time.sleep(poll)


def temi_go_home():
    temi_navigate_to(config.TEMI_HOME)


def temi_save_location(location_key: str):
    """Save Temi's current physical position as a new location."""
    target = config.TEMI_LOCATIONS.get(location_key, location_key)
    print(f"📍 Temi saving current location as: {location_key} (id: {target})")
    try:
        requests.post(
            f"{TEMI_BASE}/save_location",
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
            f"{TEMI_BASE}/say",
            json={"text": text},
            timeout=2.0,
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
