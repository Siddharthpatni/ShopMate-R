"""
grocery_db.py — In-memory product database for ShopMate-R.

Replaces the library's BOOKS dict with a GROCERIES dict. Each product
has an aisle (matching config.TEMI_LOCATIONS), category, price, and
live stock count. Helpers below cover lookup, stock changes, and
similarity-based alternative suggestion when an item is out of stock.
"""

from difflib import get_close_matches

# -------------------------------------------------------------------------
# Product catalogue
# -------------------------------------------------------------------------
# key = lowercase canonical name; value = product record.
GROCERIES = {
    "milk": {
        "name": "Whole Milk (1L)",
        "category": "milk",
        "aisle": "dairy_aisle",
        "price": 1.29,
        "stock": 12,
    },
    "almond milk": {
        "name": "Almond Milk (1L)",
        "category": "milk",
        "aisle": "dairy_aisle",
        "price": 2.49,
        "stock": 6,
    },
    "soy milk": {
        "name": "Soy Milk (1L)",
        "category": "milk",
        "aisle": "dairy_aisle",
        "price": 2.19,
        "stock": 5,
    },
    "eggs": {
        "name": "Eggs (10-pack)",
        "category": "dairy",
        "aisle": "dairy_aisle",
        "price": 2.89,
        "stock": 20,
    },
    "butter": {
        "name": "Butter (250g)",
        "category": "dairy",
        "aisle": "dairy_aisle",
        "price": 2.49,
        "stock": 8,
    },
    "white bread": {
        "name": "White Bread Loaf",
        "category": "bakery",
        "aisle": "bakery_aisle",
        "price": 1.49,
        "stock": 10,
    },
    "whole wheat bread": {
        "name": "Whole Wheat Bread",
        "category": "bakery",
        "aisle": "bakery_aisle",
        "price": 1.99,
        "stock": 7,
    },
    "croissant": {
        "name": "Butter Croissant",
        "category": "bakery",
        "aisle": "bakery_aisle",
        "price": 1.20,
        "stock": 15,
    },
    "apples": {
        "name": "Red Apples (1kg)",
        "category": "produce",
        "aisle": "produce_aisle",
        "price": 2.29,
        "stock": 30,
    },
    "bananas": {
        "name": "Bananas (1kg)",
        "category": "produce",
        "aisle": "produce_aisle",
        "price": 1.49,
        "stock": 25,
    },
    "tomatoes": {
        "name": "Tomatoes (500g)",
        "category": "produce",
        "aisle": "produce_aisle",
        "price": 1.89,
        "stock": 18,
    },
    "cereal": {
        "name": "Corn Flakes (500g)",
        "category": "pantry",
        "aisle": "pantry_aisle",
        "price": 3.49,
        "stock": 9,
    },
    "pasta": {
        "name": "Spaghetti (500g)",
        "category": "pantry",
        "aisle": "pantry_aisle",
        "price": 0.99,
        "stock": 22,
    },
    "rice": {
        "name": "Basmati Rice (1kg)",
        "category": "pantry",
        "aisle": "pantry_aisle",
        "price": 2.99,
        "stock": 14,
    },
    "coffee": {
        "name": "Ground Coffee (250g)",
        "category": "beverages",
        "aisle": "beverages_aisle",
        "price": 4.99,
        "stock": 11,
    },
    "tea": {
        "name": "Black Tea (25 bags)",
        "category": "beverages",
        "aisle": "beverages_aisle",
        "price": 2.49,
        "stock": 13,
    },
    "orange juice": {
        "name": "Orange Juice (1L)",
        "category": "beverages",
        "aisle": "beverages_aisle",
        "price": 2.79,
        "stock": 9,
    },
    "chips": {
        "name": "Potato Chips (150g)",
        "category": "snacks",
        "aisle": "snacks_aisle",
        "price": 1.79,
        "stock": 16,
    },
    "chocolate": {
        "name": "Milk Chocolate Bar",
        "category": "snacks",
        "aisle": "snacks_aisle",
        "price": 1.29,
        "stock": 24,
    },
    "frozen pizza": {
        "name": "Frozen Margherita Pizza",
        "category": "frozen",
        "aisle": "frozen_aisle",
        "price": 3.49,
        "stock": 7,
    },
    "ice cream": {
        "name": "Vanilla Ice Cream (500ml)",
        "category": "frozen",
        "aisle": "frozen_aisle",
        "price": 3.99,
        "stock": 6,
    },
}

# -------------------------------------------------------------------------
# Lookup / mutation helpers
# -------------------------------------------------------------------------

def lookup_item(query: str):
    """Return the product record for `query`, or None.

    Tries exact match first, then a fuzzy match against canonical keys so
    "appels" or "coffe" still find the right product.
    """
    if not query:
        return None
    q = query.strip().lower()
    if q in GROCERIES:
        return {"key": q, **GROCERIES[q]}
    matches = get_close_matches(q, GROCERIES.keys(), n=1, cutoff=0.6)
    if matches:
        k = matches[0]
        return {"key": k, **GROCERIES[k]}
    return None


def is_available(query: str) -> bool:
    rec = lookup_item(query)
    return bool(rec and rec["stock"] > 0)


def decrement_stock(query: str, n: int = 1) -> bool:
    """Decrement stock when a customer takes an item. Returns True if ok."""
    rec = lookup_item(query)
    if not rec:
        return False
    key = rec["key"]
    if GROCERIES[key]["stock"] <= 0:
        return False
    GROCERIES[key]["stock"] -= n
    if GROCERIES[key]["stock"] < 0:
        GROCERIES[key]["stock"] = 0
    return True


def restock(query: str, n: int = 1) -> bool:
    rec = lookup_item(query)
    if not rec:
        return False
    GROCERIES[rec["key"]]["stock"] += n
    return True


def suggest_alternative(query: str):
    """Suggest a semantically similar in-stock product.

    Strategy: find the closest canonical match, then look for another
    product in the same category that still has stock. This is the
    "recommend similar alternatives" behaviour described in the paper.
    """
    rec = lookup_item(query)
    if rec is None:
        # unknown product — offer any fuzzy neighbour that's in stock
        matches = get_close_matches(query.lower(), GROCERIES.keys(), n=3, cutoff=0.4)
        for m in matches:
            if GROCERIES[m]["stock"] > 0:
                return {"key": m, **GROCERIES[m]}
        return None

    target_cat = rec["category"]
    for k, v in GROCERIES.items():
        if k == rec["key"]:
            continue
        if v["category"] == target_cat and v["stock"] > 0:
            return {"key": k, **v}
    return None


def get_all_items():
    return [{"key": k, **v} for k, v in GROCERIES.items()]


def get_low_stock(threshold: int = 5):
    return [{"key": k, **v} for k, v in GROCERIES.items() if v["stock"] <= threshold]
