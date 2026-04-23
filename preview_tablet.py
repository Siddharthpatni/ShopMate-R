"""
preview_tablet.py — Render pepper_api tablet screens to local HTML files
so you can check alignment in a browser before pushing to the robot.

Usage:  python3 preview_tablet.py
Creates preview/ folder with one HTML file per screen.
"""

import os
import sys

# Patch config so we don't need the robot
import config
config.DISPLAY_MODE = True
config.PEPPER_DISPLAY_MODE = True

# Monkey-patch PepperRobotSSH so import doesn't try to connect
import types
class _FakePepper:
    def __getattr__(self, name):
        return lambda *a, **kw: None

sys.modules['pypepper_ssh'] = types.ModuleType('pypepper_ssh')
sys.modules['pypepper_ssh'].PepperRobotSSH = lambda **kw: _FakePepper()

# Now import pepper_api (it will use the fake pepper)
import pepper_api

# Override show_html to capture HTML to files
_captured = {}

def _capture(name):
    orig = getattr(pepper_api, name)
    def wrapper(*args, **kwargs):
        # Temporarily replace _pepper.show_html
        old_show = pepper_api._pepper.show_html
        def save_html(html):
            _captured[name] = html
        pepper_api._pepper.show_html = save_html
        try:
            orig(*args, **kwargs)
        finally:
            pepper_api._pepper.show_html = old_show
    return wrapper

os.makedirs("preview", exist_ok=True)

# 1. Welcome
fn = _capture("pepper_show_welcome")
fn()
if "pepper_show_welcome" in _captured:
    with open("preview/01_welcome.html", "w") as f:
        f.write(_captured["pepper_show_welcome"])

# 2. Idle
fn = _capture("pepper_show_idle")
fn()
if "pepper_show_idle" in _captured:
    with open("preview/02_idle.html", "w") as f:
        f.write(_captured["pepper_show_idle"])

# 3. Categories
fn = _capture("pepper_show_categories")
fn()
if "pepper_show_categories" in _captured:
    with open("preview/03_categories.html", "w") as f:
        f.write(_captured["pepper_show_categories"])

# 4. Category products (dairy)
from grocery_db import get_items_by_category
dairy = get_items_by_category("dairy")
fn = _capture("pepper_show_category_products")
fn("dairy", dairy)
if "pepper_show_category_products" in _captured:
    with open("preview/04_dairy_products.html", "w") as f:
        f.write(_captured["pepper_show_category_products"])

# 5. Product card
from grocery_db import lookup_item
milk = lookup_item("milk")
if milk:
    fn = _capture("pepper_show_product")
    old_show = pepper_api._pepper.show_html
    def save_prod(html):
        _captured["pepper_show_product"] = html
    pepper_api._pepper.show_html = save_prod
    pepper_api.pepper_show_product(milk)
    pepper_api._pepper.show_html = old_show
    if "pepper_show_product" in _captured:
        with open("preview/05_product_card.html", "w") as f:
            f.write(_captured["pepper_show_product"])

# 6. Cart
cart = [lookup_item("milk"), lookup_item("bread"), lookup_item("apple")]
cart = [c for c in cart if c]
fn = _capture("pepper_show_cart")
fn(cart)
if "pepper_show_cart" in _captured:
    with open("preview/06_cart.html", "w") as f:
        f.write(_captured["pepper_show_cart"])

# 7. Goodbye
fn = _capture("pepper_show_goodbye")
fn()
if "pepper_show_goodbye" in _captured:
    with open("preview/07_goodbye.html", "w") as f:
        f.write(_captured["pepper_show_goodbye"])

print(f"✅ Generated {len(_captured)} preview files in preview/")
for name in sorted(_captured.keys()):
    print(f"   → preview/ ... {name}")
print("\nOpen them in a browser to check alignment.")
print("Pepper's tablet is 1280×800 — resize your browser window to match.")
