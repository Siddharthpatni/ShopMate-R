"""
orchestrator.py — ShopMate-R central controller.

Customer flow:
  1. Pepper greets the customer (with hand gestures).
  2. Customer browses categories or asks for items.
  3. Items are added to a shopping cart (up to MAX_CART items).
  4. When the customer says "done" / "that's all" / cart is full,
     Temi does one delivery run for all cart items.
  5. Pepper says BYE, waves, and the conversation ENDS.

If an item is out of stock, Pepper offers a similar alternative.
"""

import json

import config
import grocery_db
from pepper_api import (
    pepper_say,
    pepper_wave_hello,
    pepper_wave_goodbye,
    pepper_bow,
    pepper_point_to_aisle,
    pepper_raise_hands,
    pepper_thinking,
    pepper_show_product,
    pepper_show_category_products,
    pepper_show_cart,
    pepper_clear_tablet,
)
from temi_api import (
    temi_deliver_item,
    temi_say,
    temi_show_product,
    temi_show_message,
    temi_go_home,
)

# OpenAI client — optional; we fall back to a keyword parser if unavailable
_client = None
if config.OPENAI_API_KEY:
    try:
        from openai import OpenAI
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    except Exception as e:
        print(f"[orchestrator] OpenAI unavailable: {e}")


# ---- State ------------------------------------------------------------------
conversation_ended = False

# Shopping cart — holds up to MAX_CART items before Temi delivers them all.
MAX_CART = 4
_cart = []


# =========================================================================
# Intent extraction
# =========================================================================

INTENT_SYSTEM_PROMPT = """You are the NLU module of a grocery store robot
assistant called ShopMate-R. Given a customer message, return a JSON
object with these fields:

  intent      one of: find_item, check_price, suggest_alternative,
                       browse_category, greeting, help, done, goodbye, unknown
  item        the grocery item the customer is asking about, or null
  category    the product category if intent is browse_category, or null
  confidence  a float from 0.0 to 1.0

Categories: dairy, milk, bakery, produce, beverages, pantry, snacks, frozen

"done" means the customer wants to finish adding items (e.g. "that's all",
"I'm done", "nothing else", "send temi", "deliver").

Return ONLY the JSON object, no prose.
"""


def extract_intent(message: str) -> dict:
    # First, try to parse locally. If it's a high-confidence exact match 
    # (like hello, bye, done, or an exact category), we bypass the slow LLM!
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


# All known category names for matching
_CATEGORIES = set(grocery_db.get_categories())


def _fallback_intent(message: str) -> dict:
    m = message.lower().strip()

    # Done / "that's all" — triggers delivery of the cart
    if any(w in m for w in ["done", "that's all", "thats all", "nothing else",
                             "no more", "send temi", "deliver", "finish"]):
        return {"intent": "done", "item": None, "category": None, "confidence": 0.9}

    if any(w in m for w in ["bye", "goodbye", "thank you", "thanks"]):
        return {"intent": "goodbye", "item": None, "category": None, "confidence": 0.9}
    if any(w in m for w in ["hello", "hi ", "hey", "good morning", "good afternoon"]):
        return {"intent": "greeting", "item": None, "category": None, "confidence": 0.9}
    if "help" in m or "what can you" in m:
        return {"intent": "help", "item": None, "category": None, "confidence": 0.9}

    # Category browsing — check if they said a category name
    for cat in _CATEGORIES:
        if cat in m:
            return {"intent": "browse_category", "item": None,
                    "category": cat, "confidence": 0.8}

    if "price" in m or "how much" in m or "cost" in m:
        item = _guess_item(m)
        return {"intent": "check_price", "item": item, "category": None, "confidence": 0.6}
    if any(w in m for w in ["instead", "alternative", "similar", "other"]):
        item = _guess_item(m)
        return {"intent": "suggest_alternative", "item": item, "category": None, "confidence": 0.6}

    item = _guess_item(m)
    return {"intent": "find_item", "item": item, "category": None,
            "confidence": 0.5 if item else 0.2}


def _guess_item(text: str):
    for key in grocery_db.GROCERIES.keys():
        if key in text:
            return key
    return None


# =========================================================================
# Intent handlers
# =========================================================================

def _handle_greeting():
    # Start the wave animation in the background, but disable the 
    # default random talking gesture on the first sentence so it doesn't 
    # immediately override the wave motion!
    pepper_wave_hello(wait=False)
    pepper_say("Hello and welcome to our grocery store! I'm ShopMate.", gesture=False)
    
    # Wait a tiny bit then do standard conversational hands for the second part
    pepper_say("Tell me what products you need and Temi will bring them to you. "
               "You can add up to 4 items at a time!")


def _handle_help():
    pepper_say("You can ask me for any grocery item, like 'I need milk', "
               "or say a category like 'dairy' or 'snacks' to browse.")
    pepper_say("Add up to 4 items, then say 'done' and Temi will deliver them all.")


def _handle_browse_category(category: str):
    """Show all products in a category on Pepper's tablet."""
    products = grocery_db.get_items_by_category(category)
    if not products:
        pepper_say(f"I don't have a category called {category}. "
                   "Try dairy, bakery, produce, beverages, pantry, snacks, or frozen.")
        return

    from pepper_api import pepper_talk_gesture
    pepper_talk_gesture()
    pepper_show_category_products(category, products)
    in_stock = sum(1 for p in products if p["stock"] > 0)
    pepper_say(f"Here are the {category} products. We have {len(products)} items, "
               f"{in_stock} currently in stock.")
    pepper_say("Just tell me which one you'd like!")


def _handle_find_item(item_query: str):
    """Add an item to the cart instead of immediately delivering."""
    global _cart

    if not item_query:
        pepper_say("I didn't catch which product you need. Could you say it again?")
        return

    from pepper_api import pepper_talk_gesture
    rec = grocery_db.lookup_item(item_query)

    if rec is None:
        pepper_say(f"I couldn't find {item_query} in our catalogue. "
                   "Let me suggest something similar.")
        alt = _suggest_alternative_for_cart(item_query)
        return

    if rec["stock"] <= 0:
        pepper_say(f"I'm sorry, {rec['name']} is currently out of stock.")
        _suggest_alternative_for_cart(item_query)
        return

    # Add to cart
    _cart.append(rec)
    pepper_show_product(rec)
    pepper_point_to_aisle()
    pepper_say(f"Added {rec['name']} to your cart! "
               f"It costs {rec['price']:.2f} euros.")

    if len(_cart) >= MAX_CART:
        pepper_say(f"Your cart is full with {len(_cart)} items. "
                   "Let me send Temi to fetch everything!")
        _deliver_cart()
    else:
        remaining = MAX_CART - len(_cart)
        pepper_say(f"You have {len(_cart)} item{'s' if len(_cart) > 1 else ''} "
                   f"in your cart. You can add {remaining} more, "
                   "or say 'done' when you're ready.")
        pepper_show_cart(_cart)


def _suggest_alternative_for_cart(item_query: str):
    """Suggest and optionally add an alternative to the cart."""
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
    _cart.append(alt)

    if len(_cart) >= MAX_CART:
        pepper_say(f"Your cart is full with {len(_cart)} items. "
                   "Let me send Temi to fetch everything!")
        _deliver_cart()
    else:
        pepper_show_cart(_cart)


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


def _handle_done():
    """Customer is finished adding items — deliver the cart."""
    if not _cart:
        pepper_say("Your cart is empty. Tell me what you need first!")
        return
    pepper_say(f"Great! You have {len(_cart)} item{'s' if len(_cart) > 1 else ''} "
               "in your cart. Temi is on the way!")
    _deliver_cart()


def _handle_unknown(message: str):
    pepper_say("I'm not sure I understood that. You can ask me where a "
               "product is, say a category name like 'dairy', or say 'done' to finish.")


def _handle_goodbye():
    """Customer says bye — deliver cart if it has items, then say goodbye."""
    if _cart:
        pepper_say(f"Before you go, let me send Temi to fetch your "
                   f"{len(_cart)} item{'s' if len(_cart) > 1 else ''}!")
        _deliver_cart()
    else:
        _say_goodbye()


# =========================================================================
# Cart delivery — Temi fetches all items in one run
# =========================================================================

def _deliver_cart():
    """Temi does a multi-stop delivery for all items in the cart,
    then returns home. Pepper says goodbye when done."""
    global _cart

    items = list(_cart)
    pepper_show_cart(items)

    # Group items by aisle to minimize travel
    aisles = {}
    for item in items:
        aisle = item["aisle"]
        if aisle not in aisles:
            aisles[aisle] = []
        aisles[aisle].append(item)

    item_names = ", ".join(p["name"] for p in items)
    pepper_say(f"Temi is fetching: {item_names}. Please wait here!")
    temi_say(f"On my way to fetch {len(items)} items!")

    # Temi visits each aisle and picks up the items
    for aisle, aisle_items in aisles.items():
        names = ", ".join(p["name"] for p in aisle_items)
        temi_show_message(f"Heading to {aisle.replace('_',' ').title()}")
        temi_say(f"Going to the {aisle.replace('_',' ')} to pick up {names}.")

        from temi_api import temi_navigate_to, temi_wait, _push_state

        _push_state({"temi_status": "fetching"})
        temi_navigate_to(aisle)

        for p in aisle_items:
            temi_show_message(f"Picking up {p['name']}...")
            temi_say(f"Picking up {p['name']}.")
            _push_state({"temi_status": "picking"})
            temi_wait(1.5)  # tray-loading pause
            grocery_db.decrement_stock(p["key"], 1)

    # Drive back to customer
    temi_say("Bringing everything to you now!")
    temi_show_message("Returning to customer...")
    from temi_api import temi_navigate_to, _push_state
    _push_state({"temi_status": "returning"})
    temi_navigate_to(config.TEMI_HOME)

    # Hand over
    temi_say(f"Here are your {len(items)} items! Please take them from my tray.")
    temi_show_message(f"Delivered {len(items)} items!")
    _push_state({"temi_status": "delivered"})

    # Clear the cart
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
# Public entry point
# =========================================================================

def run_turn(customer_message: str):
    """Process one customer turn end-to-end."""
    print(f"\n👤 Customer: {customer_message}")
    parsed = extract_intent(customer_message)
    print(f"🧠 Intent  : {parsed}")

    intent   = parsed.get("intent", "unknown")
    item     = parsed.get("item")
    category = parsed.get("category")

    if intent == "greeting":
        _handle_greeting()
    elif intent == "help":
        _handle_help()
    elif intent == "browse_category":
        _handle_browse_category(category or item or customer_message)
    elif intent == "find_item":
        _handle_find_item(item or customer_message)
    elif intent == "check_price":
        _handle_check_price(item)
    elif intent == "suggest_alternative":
        _handle_suggest_alternative(item or customer_message)
    elif intent == "done":
        _handle_done()
    elif intent == "goodbye":
        _handle_goodbye()
    else:
        _handle_unknown(customer_message)


def reset():
    """Reset state for a new customer session."""
    global conversation_ended, _cart
    conversation_ended = False
    _cart = []
