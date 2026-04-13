"""
orchestrator.py — ShopMate-R central controller.

Customer flow:
  1. Pepper greets the customer (with hand gestures).
  2. Customer asks for an item (via mic or keyboard).
  3. Orchestrator parses intent with the LLM.
  4. Orchestrator checks the inventory database.
  5. Pepper confirms and talks the customer through it, using gestures.
  6. Temi drives to the aisle and delivers the item.
  7. Pepper says BYE, waves, and the conversation ENDS.

If the item is out of stock, Pepper offers a similar alternative and
the flow continues with that product.
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


# A module-level flag main.py watches to decide when to break the loop.
conversation_ended = False


# =========================================================================
# Intent extraction
# =========================================================================

INTENT_SYSTEM_PROMPT = """You are the NLU module of a grocery store robot
assistant called ShopMate-R. Given a customer message, return a JSON
object with these fields:

  intent      one of: find_item, check_price, suggest_alternative,
                       greeting, help, goodbye, unknown
  item        the grocery item the customer is asking about, or null
  confidence  a float from 0.0 to 1.0

Return ONLY the JSON object, no prose.
"""


def extract_intent(message: str) -> dict:
    if _client is None:
        return _fallback_intent(message)
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
        return _fallback_intent(message)


def _fallback_intent(message: str) -> dict:
    m = message.lower().strip()
    if any(w in m for w in ["bye", "goodbye", "thank you", "thanks", "that's all"]):
        return {"intent": "goodbye", "item": None, "confidence": 0.9}
    if any(w in m for w in ["hello", "hi ", "hey", "good morning", "good afternoon"]):
        return {"intent": "greeting", "item": None, "confidence": 0.9}
    if "help" in m or "what can you" in m:
        return {"intent": "help", "item": None, "confidence": 0.9}
    if "price" in m or "how much" in m or "cost" in m:
        item = _guess_item(m)
        return {"intent": "check_price", "item": item, "confidence": 0.6}
    if any(w in m for w in ["instead", "alternative", "similar", "other"]):
        item = _guess_item(m)
        return {"intent": "suggest_alternative", "item": item, "confidence": 0.6}
    item = _guess_item(m)
    return {"intent": "find_item", "item": item, "confidence": 0.5 if item else 0.2}


def _guess_item(text: str):
    for key in grocery_db.GROCERIES.keys():
        if key in text:
            return key
    return None


# =========================================================================
# Intent handlers
# =========================================================================

def _handle_greeting():
    pepper_wave_hello()
    pepper_say("Hello and welcome to our grocery store! I'm ShopMate.")
    pepper_raise_hands()
    pepper_say("Tell me what product you need and Temi will bring it to you.")


def _handle_help():
    pepper_say("You can ask me for any grocery item, like 'where is the milk', "
               "or 'do you have almond milk'.")
    pepper_say("I can also suggest alternatives when something is out of stock.")


def _handle_find_item(item_query: str):
    if not item_query:
        pepper_say("I didn't catch which product you need. Could you say it again?")
        return

    pepper_thinking()
    rec = grocery_db.lookup_item(item_query)

    if rec is None:
        pepper_say(f"I couldn't find {item_query} in our catalogue. "
                   "Let me suggest something similar.")
        alt = _handle_suggest_alternative(item_query, _deliver=True)
        if alt:
            _say_goodbye()
        return

    if rec["stock"] <= 0:
        pepper_say(f"I'm sorry, {rec['name']} is currently out of stock.")
        alt = _handle_suggest_alternative(item_query, _deliver=True)
        if alt:
            _say_goodbye()
        return

    # Item is available — show it, confirm, dispatch Temi
    pepper_show_product(rec)
    pepper_point_to_aisle()
    pepper_say(f"Yes, we have {rec['name']}. It's in the "
               f"{rec['aisle'].replace('_',' ')}, "
               f"and it costs {rec['price']:.2f} euros.")
    pepper_say("Please wait here. Temi will fetch it and bring it to you.")

    # Temi does the delivery (blocks until arrived + item announced)
    temi_deliver_item(rec)

    # Decrement stock — the customer is taking the item
    grocery_db.decrement_stock(rec["key"], 1)

    # And Pepper says goodbye → conversation ends
    _say_goodbye()


def _handle_check_price(item_query: str):
    rec = grocery_db.lookup_item(item_query) if item_query else None
    if rec is None:
        pepper_say("I'm not sure which item you mean. Could you say it again?")
        return
    pepper_show_product(rec)
    pepper_say(f"{rec['name']} costs {rec['price']:.2f} euros, "
               f"and you'll find it in the {rec['aisle'].replace('_',' ')}.")


def _handle_suggest_alternative(item_query: str, _deliver: bool = False):
    """Suggest (and optionally deliver) a similar in-stock product.

    Returns the alternative record if one was found, else None.
    """
    alt = grocery_db.suggest_alternative(item_query or "")
    if alt is None:
        pepper_say("I couldn't find a similar product in stock right now. "
                   "A staff member can help you at the counter.")
        return None

    pepper_show_product(alt)
    pepper_raise_hands()
    pepper_say(f"How about {alt['name']} instead? It's in the "
               f"{alt['aisle'].replace('_',' ')} and costs "
               f"{alt['price']:.2f} euros.")

    if _deliver:
        pepper_say("Please wait here. Temi will fetch it and bring it to you.")
        temi_deliver_item(alt)
        grocery_db.decrement_stock(alt["key"], 1)

    return alt


def _handle_unknown(message: str):
    pepper_say("I'm not sure I understood that. You can ask me where a "
               "product is, or what it costs.")


def _handle_goodbye():
    _say_goodbye()


# =========================================================================
# Goodbye — called automatically after Temi delivers an item
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
    # Temi is already back at the entrance after delivering
    conversation_ended = True


# =========================================================================
# Public entry point
# =========================================================================

def run_turn(customer_message: str):
    """Process one customer turn end-to-end."""
    print(f"\n👤 Customer: {customer_message}")
    parsed = extract_intent(customer_message)
    print(f"🧠 Intent  : {parsed}")

    intent = parsed.get("intent", "unknown")
    item   = parsed.get("item")

    if intent == "greeting":
        _handle_greeting()
    elif intent == "help":
        _handle_help()
    elif intent == "find_item":
        _handle_find_item(item or customer_message)
    elif intent == "check_price":
        _handle_check_price(item)
    elif intent == "suggest_alternative":
        _handle_suggest_alternative(item or customer_message, _deliver=True)
        if item or customer_message:
            _say_goodbye()
    elif intent == "goodbye":
        _handle_goodbye()
    else:
        _handle_unknown(customer_message)


def reset():
    """Reset the ended flag so main.py can start a new customer session."""
    global conversation_ended
    conversation_ended = False
