"""
tablet_preview.py — Preview every Pepper tablet screen in a desktop
browser without touching the real robot.

The real Pepper tablet runs an ancient Android WebView, so iterating
on the HTML there is slow. This script renders each screen the same
way pepper_api.py builds it, then writes them to ./preview/*.html and
opens them in your system browser.

We do NOT import pepper_api — that module opens an SSH connection at
import time and would fail when Pepper isn't reachable. Instead we
import just the pure HTML-building helpers that don't touch hardware,
by patching the SSH client into a no-op before import.

Usage:
    python tablet_preview.py              # render all, open in browser
    python tablet_preview.py --no-open    # render only, don't launch browser
    python tablet_preview.py welcome cart # render only named screens
"""

from __future__ import annotations
import argparse
import os
import sys
import webbrowser
from pathlib import Path


# -------------------------------------------------------------------------
# Stub out the SSH driver BEFORE pepper_api imports it, so this script
# never tries to reach the real robot.
# -------------------------------------------------------------------------
class _FakePepper:
    def __init__(self, *a, **kw): pass
    def say(self, *a, **kw): pass
    def set_system_volume(self, *a, **kw): pass
    def play_animation(self, *a, **kw): pass
    def show_image(self, *a, **kw): pass
    def show_html(self, *a, **kw): pass
    def clear_tablet(self, *a, **kw): pass
    def record_audio(self, *a, **kw): pass
    def close(self, *a, **kw): pass


import types  # noqa: E402
_stub = types.ModuleType("pypepper_ssh")
_stub.PepperRobotSSH = _FakePepper
sys.modules["pypepper_ssh"] = _stub

# Now it's safe to import the real module and use its HTML helpers.
import pepper_api           # noqa: E402
import grocery_db           # noqa: E402


OUT_DIR = Path(__file__).resolve().parent / "preview"


# -------------------------------------------------------------------------
# Each screen is (name, callable-returning-html) — we reuse pepper_api's
# exact HTML generators so the preview matches production 1:1.
# -------------------------------------------------------------------------

def _welcome_html() -> str:
    # pepper_show_welcome sends to SSH; we replicate its body by calling
    # show_html on a capturing stub.
    return _capture(pepper_api.pepper_show_welcome)


def _goodbye_html() -> str:
    return _capture(pepper_api.pepper_show_goodbye)


def _idle_html() -> str:
    return _capture(pepper_api.pepper_show_idle)


def _categories_html() -> str:
    return _capture(pepper_api.pepper_show_categories)


def _category_products_html() -> str:
    items = grocery_db.get_items_by_category("dairy")
    return _capture(lambda: pepper_api.pepper_show_category_products("dairy", items))


def _cart_html() -> str:
    cart = [
        grocery_db.lookup_item("milk"),
        grocery_db.lookup_item("croissant"),
        grocery_db.lookup_item("bananas"),
        grocery_db.lookup_item("chocolate"),
    ]
    return _capture(lambda: pepper_api.pepper_show_cart(cart))


def _product_html() -> str:
    prod = grocery_db.lookup_item("milk")
    # _product_card_html is pure — no SSH call
    return pepper_api._product_card_html(prod)


def _capture(fn) -> str:
    """Run a pepper_show_* function and capture the HTML it would have
    sent to the tablet."""
    captured: list[str] = []
    original = pepper_api._pepper.show_html
    pepper_api._pepper.show_html = lambda html: captured.append(html)
    try:
        fn()
    finally:
        pepper_api._pepper.show_html = original
    return captured[0] if captured else "<html><body>(no HTML captured)</body></html>"


SCREENS = {
    "welcome":            _welcome_html,
    "goodbye":            _goodbye_html,
    "idle":               _idle_html,
    "categories":         _categories_html,
    "category_products":  _category_products_html,
    "cart":               _cart_html,
    "product":            _product_html,
}


# -------------------------------------------------------------------------
# Index page that links to every screen
# -------------------------------------------------------------------------

_INDEX = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>ShopMate-R tablet preview</title>
<style>
 body { font: 15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
        background: #FEF7FF; color: #1c1b1f; margin: 0; padding: 40px;
        max-width: 800px; margin: auto; }
 h1   { font-size: 28px; margin-bottom: 8px; color: #4A148C; }
 p    { color: #6750A4; margin-bottom: 28px; }
 a.s  { display: block; padding: 16px 20px; margin-bottom: 10px;
        background: #fff; border-radius: 14px; text-decoration: none;
        color: #1c1b1f; font-weight: 600;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
 a.s:hover { background: #EADDFF; }
 code { font: 13px 'JetBrains Mono', Consolas, monospace;
        color: #6750A4; background: #F3EDF7; padding: 2px 6px;
        border-radius: 6px; }
</style></head><body>
<h1>🛒 ShopMate-R Tablet Preview</h1>
<p>Every screen <code>pepper_api.py</code> can show, rendered locally.</p>
{links}
</body></html>
"""


def render_all(names: list[str]) -> list[Path]:
    OUT_DIR.mkdir(exist_ok=True)
    written: list[Path] = []
    for name in names:
        fn = SCREENS.get(name)
        if not fn:
            print(f"⚠️  Unknown screen '{name}' — skipping")
            continue
        html = fn()
        path = OUT_DIR / f"{name}.html"
        path.write_text(html, encoding="utf-8")
        print(f"✅ {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")
        written.append(path)

    # Index page
    links = "\n".join(
        f'<a class="s" href="{p.name}">📺 &nbsp; {p.stem.replace("_", " ").title()}</a>'
        for p in written
    )
    index = OUT_DIR / "index.html"
    index.write_text(_INDEX.replace("{links}", links), encoding="utf-8")
    print(f"✅ {index.name} (open this first)")
    return written


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("screens", nargs="*",
                   help="Screens to render (default: all). "
                        f"Available: {', '.join(SCREENS)}")
    p.add_argument("--no-open", action="store_true",
                   help="Don't auto-launch the browser")
    args = p.parse_args()

    targets = args.screens or list(SCREENS.keys())
    written = render_all(targets)
    if not written:
        return 1

    index_url = (OUT_DIR / "index.html").resolve().as_uri()
    print(f"\n🌐 Preview index: {index_url}")
    if not args.no_open:
        webbrowser.open(index_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
