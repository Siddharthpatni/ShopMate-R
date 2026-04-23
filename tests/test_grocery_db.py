"""Tests for grocery_db — lookup, stock mutation, alternatives."""

import grocery_db


def test_every_item_has_required_fields():
    """Every record must have the fields orchestrator.py / pepper_api.py
    depend on. Catches accidental schema drift."""
    required = {"name", "category", "aisle", "price", "stock"}
    for key, rec in grocery_db.GROCERIES.items():
        missing = required - set(rec)
        assert not missing, f"{key!r} is missing {missing}"


def test_no_negative_stock_or_prices():
    for key, rec in grocery_db.GROCERIES.items():
        assert rec["stock"] >= 0, f"{key} has negative stock"
        assert rec["price"] > 0,  f"{key} has non-positive price"


def test_lookup_exact_match():
    rec = grocery_db.lookup_item("milk")
    assert rec is not None
    assert rec["key"] == "milk"
    assert rec["category"] == "milk"


def test_lookup_fuzzy_match():
    """Typos should still resolve to the canonical key."""
    assert grocery_db.lookup_item("appels")["key"] == "apples"
    assert grocery_db.lookup_item("coffe")["key"]  == "coffee"


def test_lookup_miss_returns_none():
    assert grocery_db.lookup_item("unobtainium") is None
    assert grocery_db.lookup_item("") is None
    assert grocery_db.lookup_item(None) is None


def test_decrement_stock_bounded_at_zero():
    grocery_db.GROCERIES["croissant"]["stock"] = 2
    assert grocery_db.decrement_stock("croissant", 1) is True
    assert grocery_db.GROCERIES["croissant"]["stock"] == 1
    grocery_db.decrement_stock("croissant", 999)
    assert grocery_db.GROCERIES["croissant"]["stock"] == 0
    # Further decrements should refuse
    assert grocery_db.decrement_stock("croissant", 1) is False


def test_restock_increases_stock():
    start = grocery_db.GROCERIES["milk"]["stock"]
    grocery_db.restock("milk", 3)
    assert grocery_db.GROCERIES["milk"]["stock"] == start + 3


def test_suggest_alternative_prefers_same_category():
    """If 'milk' is out of stock, the suggestion should be in the
    same category (e.g. almond milk or soy milk)."""
    grocery_db.GROCERIES["almond milk"]["stock"] = 5   # in stock
    alt = grocery_db.suggest_alternative("milk")
    assert alt is not None
    assert alt["category"] == "milk"
    assert alt["key"] != "milk"


def test_suggest_alternative_unknown_product():
    """For a product we don't stock at all, suggest_alternative should
    either return something fuzzy-similar or None — but must not crash."""
    result = grocery_db.suggest_alternative("quinoa")
    # Any answer is acceptable — we just verify it's a dict or None
    assert result is None or isinstance(result, dict)


def test_categories_and_items_by_category():
    cats = grocery_db.get_categories()
    assert "dairy" in cats
    assert "produce" in cats

    produce = grocery_db.get_items_by_category("produce")
    assert all(p["category"] == "produce" for p in produce)
    assert len(produce) >= 1


def test_low_stock_threshold():
    grocery_db.GROCERIES["eggs"]["stock"] = 2
    low = grocery_db.get_low_stock(threshold=5)
    keys = [x["key"] for x in low]
    assert "eggs" in keys
