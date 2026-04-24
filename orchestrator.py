"""
orchestrator.py — ShopMate-R central controller.

Customer flow:
  1. Pepper greets the customer (with hand gestures).
  2. Customer browses categories or names items.
  3. Items accumulate in a shopping cart (up to MAX_CART).
  4. When the customer says "done" / "that's all" / cart is full,
     Temi does ONE delivery run for every item in the cart.
  5. Pepper says BYE, waves, and the conversation ENDS.

If an item is out of stock, Pepper suggests a similar alternative.
"""

from __future__ import annotations

import json

import config
import grocery_db
from pepper_api import (
    pepper_bow,
    pepper_clear_tablet,
    pepper_point_to_aisle,
    pepper_raise_hands,
    pepper_say,
    pepper_show_cart,
    pepper_show_category_products,
    pepper_show_product,
    pepper_talk_gesture,
    pepper_thinking,
    pepper_wave_goodbye,
    pepper_wave_hello,
)
from temi_api import (
    _push_state,           # dashboard state helper (intentionally re-exported)
    temi_navigate_to,
    temi_say,
    temi_show_message,
    temi_wait,
)


# --- Optional OpenAI client (falls back to a keyword parser) ----------------
_client = None
if config.OPENAI_API_KEY:
    try:
        from openai import OpenAI
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    except Exception as e:
        print(f"[orchestrator] OpenAI unavailable: {e}")


# =========================================================================
# Session state
# =========================================================================

conversation_ended: bool = False

# Shopping cart — holds up to MAX_CART items before Temi runs the route.
MAX_CART: int = 4
_cart: list[dict] = []


# =========================================================================
# Intent extraction
# =========================================================================

INTENT_SYSTEM_PROMPT = """You are the NLU module of a grocery store robot
assistant called ShopMate-R. Given a customer message, return a JSON
object with these fields:

  intent      one of: find_item, check_price, suggest_alternative, remove_item,
                       browse_category, greeting, help, done, goodbye, unknown
  item        the grocery item the customer is asking about, or null
  category    the product category if intent is browse_category, or null
  confidence  a float from 0.0 to 1.0

Categories: dairy, milk, bakery, produce, beverages, pantry, snacks, frozen

"done" means the customer wants to finish adding items (e.g. "that's all",
"I'm done", "nothing else", "send temi", "deliver").

Return ONLY the JSON object, no prose.
"""


_CATEGORIES: set[str] = set(grocery_db.get_categories())

_DONE_WORDS = ("done", "that's all", "thats all", "nothing else",
               "no more", "send temi", "deliver", "finish")
_BYE_WORDS  = ("bye", "goodbye", "thank you", "thanks")
_HI_WORDS   = ("hello", "hi ", "hey", "good morning", "good afternoon")
_ALT_WORDS  = ("instead", "alternative", "similar", "other")
_PRICE_WORDS = ("price", "how much", "cost")
_CANCEL_WORDS = ("cancel", "abort", "never mind", "nevermind", "stop")
_REMOVE_WORDS = ("remove", "delete", "don't want", "dont want", "take out", "drop")


def extract_intent(message: str) -> dict:
    """Fast path: resolve the intent locally. Only call the LLM if the
    local parser isn't already confident (>= 0.8)."""
    fallback = _fallback_intent(message)
    if fallback["confidence"] >= 0.8:
        return fallback
    if _client is None:
        return fallback

    try:
        resp = _client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user",   "content": message},
            ],
            temperature=0.0,
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"[orchestrator] LLM intent parse failed: {e}")
        return fallback


def _fallback_intent(message: str) -> dict:
    m = message.lower().strip()

    if any(w in m for w in _DONE_WORDS):
        return {"intent": "done", "item": None, "category": None, "confidence": 0.9}
    if any(w in m for w in _BYE_WORDS):
        return {"intent": "goodbye", "item": None, "category": None, "confidence": 0.9}
    if any(w in m for w in _CANCEL_WORDS):
        return {"intent": "cancel", "item": None, "category": None, "confidence": 0.9}
    if any(w in m for w in _HI_WORDS):
        return {"intent": "greeting", "item": None, "category": None, "confidence": 0.9}
    if "help" in m or "what can you" in m:
        return {"intent": "help", "item": None, "category": None, "confidence": 0.9}

    if any(w in m for w in _REMOVE_WORDS):
        return {"intent": "remove_item", "item": _guess_item(m),
                "category": None, "confidence": 0.8}

    # Price/alternative keywords are specific signals — check them FIRST,
    # before category matching, so "how much is milk" resolves to
    # check_price (not browse_category, since "milk" is also a category).
    if any(w in m for w in _PRICE_WORDS):
        return {"intent": "check_price", "item": _guess_item(m),
                "category": None, "confidence": 0.7}
    if any(w in m for w in _ALT_WORDS):
        return {"intent": "suggest_alternative", "item": _guess_item(m),
                "category": None, "confidence": 0.7}

    # If the customer mentions a specific known product, prefer find_item
    # over browse_category — again because some product keys ("milk") are
    # also category names and we don't want to swallow "I need milk".
    item = _guess_item(m)
    if item:
        return {"intent": "find_item", "item": item, "category": None,
                "confidence": 0.7}

    # No specific item mentioned — fall through to category browsing
    # for utterances like "dairy", "show me the snacks", etc.
    for cat in _CATEGORIES:
        if cat in m:
            return {"intent": "browse_category", "item": None,
                    "category": cat, "confidence": 0.8}

    return {"intent": "find_item", "item": None, "category": None,
            "confidence": 0.2}


def _guess_item(text: str):
    m = text.lower()
    # 1. Check if the DB key or the exact display name is in the text
    for key, val in grocery_db.GROCERIES.items():
        if key in m or val["name"].lower() in m:
            return key
            
    # 2. Check if the user text is a substring of the key or name (e.g., "pizza" -> "frozen pizza")
    if len(m) >= 3:  # avoid matching 'a' or 'on'
        for key, val in grocery_db.GROCERIES.items():
            if m in key or m in val["name"].lower():
                return key
                
    return None


# =========================================================================
# Cart helpers
# =========================================================================

def _cart_summary() -> str:
    n = len(_cart)
    return f"{n} item{'s' if n != 1 else ''}"


def _add_to_cart(rec: dict) -> None:
    """Append to cart and auto-deliver if it's now full."""
    _cart.append(rec)
    if len(_cart) >= MAX_CART:
        pepper_say(f"Your cart is full with {_cart_summary()}. "
                   "Let me send Temi to fetch everything!")
        _deliver_cart()
    else:
        remaining = MAX_CART - len(_cart)
        pepper_say(f"You have {_cart_summary()} in your cart. "
                   f"You can add {remaining} more, "
                   "or say 'done' when you're ready.")
        pepper_show_cart(_cart)


# =========================================================================
# Intent handlers
# =========================================================================

def _handle_greeting():
    # Start the wave in the background, but disable the default random
    # talking gesture on the first sentence so it doesn't override the wave.
    pepper_wave_hello(wait=False)
    pepper_say("Hello and welcome to our grocery store! I'm ShopMate.",
               gesture=False)
    pepper_say("Tell me what products you need and Temi will bring them to you. "
               "You can add up to 4 items at a time!")


def _handle_help():
    pepper_say("You can ask me for any grocery item, like 'I need milk', "
               "or say a category like 'dairy' or 'snacks' to browse.")
    pepper_say("Add up to 4 items, then say 'done' and Temi will deliver them all.")


def _handle_browse_category(category: str):
    products = grocery_db.get_items_by_category(category)
    if not products:
        pepper_say(f"I don't have a category called {category}. "
                   "Try dairy, bakery, produce, beverages, pantry, snacks, or frozen.")
        return

    pepper_talk_gesture()
    pepper_show_category_products(category, products)
    in_stock = sum(1 for p in products if p["stock"] > 0)
    pepper_say(f"Here are the {category} products. We have {len(products)} items, "
               f"{in_stock} currently in stock.")
    pepper_say("Just tell me which one you'd like!")


def _handle_find_item(item_query: str):
    """Add an item to the cart instead of immediately delivering."""
    if not item_query:
        pepper_say("I didn't catch which product you need. Could you say it again?")
        return

    rec = grocery_db.lookup_item(item_query)

    if rec is None:
        pepper_say(f"I couldn't find {item_query} in our catalogue. "
                   "Let me suggest something similar.")
        _suggest_alternative_for_cart(item_query)
        return

    if rec["stock"] <= 0:
        pepper_say(f"I'm sorry, {rec['name']} is currently out of stock.")
        _suggest_alternative_for_cart(item_query)
        return

    pepper_show_product(rec)
    pepper_point_to_aisle()
    pepper_say(f"Added {rec['name']} to your cart! "
               f"It costs {rec['price']:.2f} euros.")
    _add_to_cart(rec)


def _suggest_alternative_for_cart(item_query: str):
    """Suggest an in-stock alternative and add it to the cart."""
    alt = grocery_db.suggest_alternative(item_query or "")
    if alt is None:
        pepper_say("I couldn't find a similar product in stock right now. "
                   "A staff member can help you at the counter.")
        return

    pepper_show_product(alt)
    pepper_raise_hands()
    pepper_say(f"How about {alt['name']} instead? It's in the "
               f"{alt['aisle'].replace('_',' ')} and costs "
               f"{alt['price']:.2f} euros. I'll add it to your cart.")
    _add_to_cart(alt)


def _handle_check_price(item_query: str):
    rec = grocery_db.lookup_item(item_query) if item_query else None
    if rec is None:
        pepper_say("I'm not sure which item you mean. Could you say it again?")
        return
    pepper_show_product(rec)
    pepper_say(f"{rec['name']} costs {rec['price']:.2f} euros, "
               f"and you'll find it in the {rec['aisle'].replace('_',' ')}.")


def _handle_suggest_alternative(item_query: str):
    _suggest_alternative_for_cart(item_query or "")


def _handle_remove_item(item_query: str):
    global _cart
    if not item_query:
        pepper_say("Which item would you like me to remove?")
        return

    # Try to find the item in the cart
    found_idx = -1
    for i, item in enumerate(_cart):
        if item_query in item["key"] or item_query in item["name"].lower():
            found_idx = i
            break

    if found_idx != -1:
        removed = _cart.pop(found_idx)
        pepper_say(f"I've removed {removed['name']} from your cart.")
        if _cart:
            pepper_show_cart(_cart)
            pepper_say(f"You now have {_cart_summary()} in your cart.")
        else:
            pepper_clear_tablet()
            pepper_say("Your cart is now empty.")
    else:
        pepper_say(f"I couldn't find {item_query} in your cart.")


def _handle_done():
    if not _cart:
        pepper_say("Your cart is empty. Tell me what you need first!")
        return
    pepper_say(f"Great! You have {_cart_summary()} in your cart. "
               "Temi is on the way!")
    _deliver_cart()


def _handle_unknown(_message: str):
    pepper_say("I'm not sure I understood that. You can ask me where a "
               "product is, say a category name like 'dairy', or say 'done' to finish.")


def _handle_goodbye():
    if _cart:
        pepper_say(f"Before you go, let me send Temi to fetch your "
                   f"{_cart_summary()}!")
        _deliver_cart()
    else:
        _say_goodbye()


def _handle_cancel():
    global _cart
    _cart = []
    pepper_say("Order canceled. I have cleared your cart.")
    _say_goodbye()


# =========================================================================
# Cart delivery — one Temi trip for every item in the cart
# =========================================================================

def _group_cart_by_aisle(items: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(item["aisle"], []).append(item)
    return grouped


def _visit_aisle(aisle: str, aisle_items: list[dict]) -> None:
    names = ", ".join(p["name"] for p in aisle_items)
    pretty_aisle = aisle.replace("_", " ").title()
    temi_show_message(f"Heading to {pretty_aisle}")
    temi_say(f"Going to the {aisle.replace('_',' ')} to pick up {names}.")

    _push_state({"temi_status": "fetching"})
    temi_navigate_to(aisle)

    for p in aisle_items:
        temi_show_message(f"Picking up {p['name']}...")
        temi_say(f"Picking up {p['name']}.")
        _push_state({"temi_status": "picking"})
        temi_wait(1.5)   # tray-loading pause
        grocery_db.decrement_stock(p["key"], 1)


def _deliver_cart():
    """Temi does a multi-stop delivery for every item in the cart,
    then returns home. Pepper says goodbye when done."""
    global _cart

    items = list(_cart)
    pepper_show_cart(items)

    aisles = _group_cart_by_aisle(items)
    item_names = ", ".join(p["name"] for p in items)
    pepper_say(f"Temi is fetching: {item_names}. Please wait here!")
    temi_say(f"On my way to fetch {len(items)} items!")

    for aisle, aisle_items in aisles.items():
        _visit_aisle(aisle, aisle_items)

    # Drive to checkout for handover
    temi_say("Bringing everything to the checkout now! Please meet me there.")
    temi_show_message("Heading to Checkout...")
    _push_state({"temi_status": "returning"})
    temi_navigate_to("checkout")

    # Hand over
    temi_say(f"Here are your {len(items)} items! Please take them from my tray and complete your checkout.")
    temi_show_message(f"Delivered {len(items)} items!")
    _push_state({"temi_status": "delivered"})
    temi_wait(4.0)

    # Return to entrance
    temi_show_message("Returning to Entrance...")
    _push_state({"temi_status": "returning"})
    temi_navigate_to(config.TEMI_HOME)

    _cart = []
    _say_goodbye()


# =========================================================================
# Goodbye
# =========================================================================

def _say_goodbye():
    """Pepper waves, says BYE, clears the tablet, and marks the
    conversation as ended so main.py will break out of its loop."""
    global conversation_ended
    pepper_clear_tablet()
    pepper_wave_goodbye()
    pepper_say("Thank you for shopping with us. Have a wonderful day. BYE!")
    pepper_bow()
    temi_show_message("Goodbye!")
    conversation_ended = True


# =========================================================================
# Public entry points
# =========================================================================

_HANDLERS = {
    "greeting":            lambda p: _handle_greeting(),
    "help":                lambda p: _handle_help(),
    "browse_category":     lambda p: _handle_browse_category(
                               p.get("category") or p.get("item") or p["_raw"]),
    "find_item":           lambda p: _handle_find_item(p.get("item") or p["_raw"]),
    "check_price":         lambda p: _handle_check_price(p.get("item")),
    "suggest_alternative": lambda p: _handle_suggest_alternative(
                               p.get("item") or p["_raw"]),
    "remove_item":         lambda p: _handle_remove_item(p.get("item") or p["_raw"]),
    "done":                lambda p: _handle_done(),
    "cancel":              lambda p: _handle_cancel(),
    "goodbye":             lambda p: _handle_goodbye(),
}


def run_turn(customer_message: str):
    """Process one customer turn end-to-end."""
    print(f"\n👤 Customer: {customer_message}")
    parsed = extract_intent(customer_message)
    parsed["_raw"] = customer_message
    print(f"🧠 Intent  : { {k: v for k, v in parsed.items() if k != '_raw'} }")

    intent = parsed.get("intent", "unknown")
    handler = _HANDLERS.get(intent)
    if handler:
        handler(parsed)
    else:
        _handle_unknown(customer_message)


def reset():
    """Reset state for a new customer session."""
    global conversation_ended, _cart
    conversation_ended = False
    _cart = []
