"""Tests that every Pepper tablet screen produces well-formed HTML
with the expected Apple-glass design markers."""

import re
import pytest


def _capture_show_html(fn_that_calls_show_html):
    """Run a `pepper_show_*` function and return the HTML it would
    have pushed to the tablet."""
    import pepper_api
    captured = []
    original = pepper_api._pepper.show_html
    pepper_api._pepper.show_html = lambda html: captured.append(html)
    try:
        fn_that_calls_show_html()
    finally:
        pepper_api._pepper.show_html = original
    return captured[0] if captured else None


# ------------------------------------------------------------------
# Per-screen fixtures
# ------------------------------------------------------------------

@pytest.fixture
def welcome_html():
    import pepper_api
    return _capture_show_html(pepper_api.pepper_show_welcome)


@pytest.fixture
def goodbye_html():
    import pepper_api
    return _capture_show_html(pepper_api.pepper_show_goodbye)


@pytest.fixture
def idle_html():
    import pepper_api
    return _capture_show_html(pepper_api.pepper_show_idle)


@pytest.fixture
def categories_html():
    import pepper_api
    return _capture_show_html(pepper_api.pepper_show_categories)


@pytest.fixture
def category_products_html():
    import pepper_api, grocery_db
    items = grocery_db.get_items_by_category("dairy")
    return _capture_show_html(
        lambda: pepper_api.pepper_show_category_products("dairy", items))


@pytest.fixture
def cart_html():
    import pepper_api, grocery_db
    cart = [grocery_db.lookup_item("milk"),
            grocery_db.lookup_item("chocolate")]
    return _capture_show_html(lambda: pepper_api.pepper_show_cart(cart))


@pytest.fixture
def product_html():
    import pepper_api, grocery_db
    # _product_card_html is pure — doesn't go through show_html
    return pepper_api._product_card_html(grocery_db.lookup_item("milk"))


# ------------------------------------------------------------------
# Every screen: produces HTML at all
# ------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", [
    "welcome_html", "goodbye_html", "idle_html",
    "categories_html", "category_products_html",
    "cart_html", "product_html",
])
def test_every_screen_produces_html(request, fixture_name):
    html = request.getfixturevalue(fixture_name)
    assert html is not None and len(html) > 500
    assert html.lstrip().lower().startswith("<!doctype html")
    # Balanced-ish: every <html> has a </html>, same for body
    assert html.count("<html") == html.count("</html>")
    assert html.count("<body") == html.count("</body>")


# ------------------------------------------------------------------
# Glass design: every card has both backdrop-filter and the WebKit
# prefix so older tablets still get the frosted effect.
# ------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", [
    "welcome_html", "goodbye_html", "idle_html",
    "categories_html", "category_products_html",
    "cart_html", "product_html",
])
def test_glass_backdrop_filter_present(request, fixture_name):
    html = request.getfixturevalue(fixture_name)
    assert "backdrop-filter" in html, \
        "Missing backdrop-filter — glass design broken"
    assert "-webkit-backdrop-filter" in html, \
        "Missing -webkit-backdrop-filter — older WebViews won't blur"


# ------------------------------------------------------------------
# 2-column layouts where the user specifically asked for them
# ------------------------------------------------------------------

def test_categories_uses_2col_outer_grid(categories_html):
    """User requirement: categories dashboard shows 2 tiles per row."""
    # The outer category grid
    assert "repeat(2, 1fr)" in categories_html
    # Plus the mini 2-col product preview inside each tile
    assert categories_html.count("repeat(2, 1fr)") >= 2, \
        "Expected both outer grid AND mini-grid to be 2-column"


def test_category_products_uses_2col_grid(category_products_html):
    """User requirement: products within a category show 2 per row."""
    assert "repeat(2, 1fr)" in category_products_html


# ------------------------------------------------------------------
# No leaked f-string placeholders (common footgun with nested {})
# ------------------------------------------------------------------

@pytest.mark.parametrize("fixture_name", [
    "welcome_html", "goodbye_html", "idle_html",
    "categories_html", "category_products_html",
    "cart_html", "product_html",
])
def test_no_unresolved_fstring_placeholders(request, fixture_name):
    html = request.getfixturevalue(fixture_name)
    # Matches single-braced tokens that look like leftover f-string slots
    # (`{foo}` where `foo` is a plain identifier). CSS uses only `{{` and
    # `}}` inside our f-strings, so any single-brace identifier is a bug.
    suspects = re.findall(r"\{[a-zA-Z_][a-zA-Z_0-9]*\}", html)
    # Filter out SVG-less false positives: there aren't any legitimate
    # `{word}` single-brace tokens we expect in the output.
    assert not suspects, f"Unresolved placeholders: {suspects[:5]}"


# ------------------------------------------------------------------
# Product card renders known values
# ------------------------------------------------------------------

def test_product_card_shows_name_and_price(product_html):
    import grocery_db
    milk = grocery_db.lookup_item("milk")
    assert milk["name"] in product_html
    assert f"{milk['price']:.2f}" in product_html


def test_cart_shows_total(cart_html):
    """Cart total should equal sum of the two items we fed in."""
    import grocery_db
    expected = (grocery_db.lookup_item("milk")["price"] +
                grocery_db.lookup_item("chocolate")["price"])
    assert f"{expected:.2f}" in cart_html
