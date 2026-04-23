"""
db_inspector.py — CLI inventory tool for ShopMate-R.

Read-only by default (doesn't touch any robot). Supports:

    python db_inspector.py                       # pretty table of everything
    python db_inspector.py list dairy            # just one category
    python db_inspector.py show milk             # single item detail
    python db_inspector.py low                   # low-stock alert list
    python db_inspector.py categories            # summary by category

Write operations go through the dashboard's /api/sensor endpoint so
the live system sees them (same channel the M5Stack sensors use):

    python db_inspector.py take milk 2           # mark 2 taken
    python db_inspector.py restock chips 10      # add 10 to stock

This way you never edit grocery_db.GROCERIES directly in a running
process — instead, the change flows through the same path real
hardware events would.
"""

from __future__ import annotations
import argparse
import os
import sys
from typing import Iterable

import requests

import config
import grocery_db


DASHBOARD = os.environ.get("SHOPMATE_DASHBOARD", config.DASHBOARD_URL)


# -------------------------------------------------------------------------
# Read operations
# -------------------------------------------------------------------------

def _stock_pill(n: int) -> str:
    if n <= 0:    return "OUT"
    if n <= 5:    return f"LOW ({n})"
    return f"{n}"


def _print_items(items: Iterable[dict]) -> None:
    items = list(items)
    if not items:
        print("  (no items)")
        return
    # Column widths
    key_w  = max(len(it["key"]) for it in items)
    name_w = max(len(it["name"]) for it in items)
    cat_w  = max(len(it["category"]) for it in items)
    print()
    print(f"  {'key'.ljust(key_w)}  {'name'.ljust(name_w)}  "
          f"{'cat'.ljust(cat_w)}  price     stock")
    print(f"  {'-'*key_w}  {'-'*name_w}  {'-'*cat_w}  ----   -------")
    for it in items:
        print(f"  {it['key'].ljust(key_w)}  "
              f"{it['name'].ljust(name_w)}  "
              f"{it['category'].ljust(cat_w)}  "
              f"€{it['price']:>5.2f}   {_stock_pill(it['stock'])}")
    print()
    total_value = sum(it["price"] * it["stock"] for it in items)
    total_stock = sum(it["stock"] for it in items)
    print(f"  {len(items)} items, {total_stock} units, "
          f"inventory value €{total_value:,.2f}")


def cmd_list(args) -> int:
    if args.category:
        items = grocery_db.get_items_by_category(args.category)
        print(f"\n📦 Category: {args.category}")
    else:
        items = grocery_db.get_all_items()
        print("\n📦 Full catalogue")
    _print_items(items)
    return 0


def cmd_show(args) -> int:
    rec = grocery_db.lookup_item(args.item)
    if rec is None:
        print(f"❌ No item matches '{args.item}'")
        return 1
    print()
    for k, v in rec.items():
        print(f"  {k:<10}  {v}")
    print()
    return 0


def cmd_low(args) -> int:
    items = grocery_db.get_low_stock(threshold=args.threshold)
    print(f"\n🟠 Low-stock items (threshold ≤ {args.threshold})")
    _print_items(items)
    return 0 if items else 0


def cmd_categories(_args) -> int:
    print()
    print(f"  {'category':<12}  items  in-stock  value")
    print(f"  {'-'*12}  -----  --------  --------")
    for cat in grocery_db.get_categories():
        items    = grocery_db.get_items_by_category(cat)
        in_stock = sum(1 for it in items if it["stock"] > 0)
        value    = sum(it["price"] * it["stock"] for it in items)
        print(f"  {cat:<12}  {len(items):>5}  "
              f"{in_stock:>8}  €{value:>7.2f}")
    print()
    return 0


# -------------------------------------------------------------------------
# Write operations — go through /api/sensor so the live system sees them
# -------------------------------------------------------------------------

def _post_sensor(item: str, event: str, count: int) -> int:
    endpoint = f"{DASHBOARD.rstrip('/')}/api/sensor"
    try:
        r = requests.post(endpoint,
                          json={"item": item, "event": event, "count": count},
                          timeout=3.0)
    except requests.exceptions.RequestException as e:
        print(f"❌ Dashboard unreachable at {endpoint}")
        print(f"   {e}")
        print("   Start it with `python mock_dashboard.py`")
        return 2

    if r.status_code == 200 and r.json().get("ok"):
        body = r.json()
        verb = "TOOK" if event == "taken" else "RESTOCKED"
        print(f"✅ {verb} {count}× {body['item']}  →  "
              f"new stock: {body['new_stock']}")
        return 0

    try:
        err = r.json().get("error", r.text)
    except Exception:
        err = r.text
    print(f"❌ Dashboard returned {r.status_code}: {err}")
    return 1


def cmd_take(args) -> int:
    return _post_sensor(args.item.lower(), "taken", args.count)


def cmd_restock(args) -> int:
    return _post_sensor(args.item.lower(), "restocked", args.count)


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd")

    l = sub.add_parser("list", help="list items (optionally by category)")
    l.add_argument("category", nargs="?")
    l.set_defaults(fn=cmd_list)

    s = sub.add_parser("show", help="show one item's full record")
    s.add_argument("item")
    s.set_defaults(fn=cmd_show)

    lo = sub.add_parser("low", help="show low-stock items")
    lo.add_argument("--threshold", "-t", type=int, default=5)
    lo.set_defaults(fn=cmd_low)

    c = sub.add_parser("categories", help="per-category summary")
    c.set_defaults(fn=cmd_categories)

    t = sub.add_parser("take", help="mark N units taken (via /api/sensor)")
    t.add_argument("item")
    t.add_argument("count", type=int, nargs="?", default=1)
    t.set_defaults(fn=cmd_take)

    r = sub.add_parser("restock", help="restock N units (via /api/sensor)")
    r.add_argument("item")
    r.add_argument("count", type=int, nargs="?", default=1)
    r.set_defaults(fn=cmd_restock)

    return p


def main() -> int:
    args = build_parser().parse_args()
    if not getattr(args, "fn", None):
        # No subcommand → default to `list`
        return cmd_list(argparse.Namespace(category=None))
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
