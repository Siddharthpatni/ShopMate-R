"""Tests for orchestrator — intent extraction and cart lifecycle.

All Pepper/Temi side effects are neutralised by conftest.py: the SSH
driver is stubbed, and requests.post is patched to a 200/ok response.
"""

import pytest


# ------------------------------------------------------------------
# Fallback intent parser (the fast local path — does not hit the LLM)
# ------------------------------------------------------------------

@pytest.mark.parametrize("msg, expected_intent", [
    ("hello",                    "greeting"),
    ("hi there",                 "greeting"),
    ("good morning",             "greeting"),
    ("bye",                      "goodbye"),
    ("thanks",                   "goodbye"),
    ("I'm done",                 "done"),
    ("that's all",               "done"),
    ("send temi",                "done"),
    ("help",                     "help"),
    ("dairy",                    "browse_category"),
    ("show me the snacks",       "browse_category"),
    ("how much is milk",         "check_price"),
    ("what's the price of eggs", "check_price"),
    ("something similar",        "suggest_alternative"),
    ("I need milk",              "find_item"),
])
def test_fallback_intent(msg, expected_intent):
    import orchestrator
    parsed = orchestrator._fallback_intent(msg)
    assert parsed["intent"] == expected_intent


def test_fallback_item_extraction():
    import orchestrator
    assert orchestrator._guess_item("I need milk please") == "milk"
    assert orchestrator._guess_item("can I have bananas") == "bananas"
    assert orchestrator._guess_item("something random") is None


# ------------------------------------------------------------------
# run_turn — full integration through the fallback path
# ------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _fresh_orchestrator():
    """Reset orchestrator state before every test."""
    import orchestrator
    orchestrator.reset()
    yield
    orchestrator.reset()


def test_greeting_does_not_end_conversation():
    import orchestrator
    orchestrator.run_turn("hello")
    assert orchestrator.conversation_ended is False


def test_find_item_adds_to_cart():
    import orchestrator
    orchestrator.run_turn("hello")
    orchestrator.run_turn("I need milk")
    # Cart is private — reach into the module-level name directly
    assert len(orchestrator._cart) == 1
    assert orchestrator._cart[0]["key"] == "milk"
    assert orchestrator.conversation_ended is False


def test_done_triggers_delivery_and_ends_conversation():
    import orchestrator
    orchestrator.run_turn("hello")
    orchestrator.run_turn("I need milk")
    orchestrator.run_turn("done")
    # After "done" the cart should be cleared and the conversation ended
    assert orchestrator._cart == []
    assert orchestrator.conversation_ended is True


def test_cart_full_auto_delivers():
    """MAX_CART is 4 — adding a 4th item should auto-trigger delivery
    even without the customer saying 'done'."""
    import orchestrator
    orchestrator.run_turn("hello")
    for item in ["milk", "chocolate", "bananas", "chips"]:
        if orchestrator.conversation_ended:
            break
        orchestrator.run_turn(f"I want {item}")
    assert orchestrator.conversation_ended is True


def test_goodbye_without_cart_just_ends():
    import orchestrator
    orchestrator.run_turn("hello")
    orchestrator.run_turn("bye")
    assert orchestrator.conversation_ended is True


def test_reset_clears_everything():
    import orchestrator
    orchestrator.run_turn("hello")
    orchestrator.run_turn("I need milk")
    orchestrator.run_turn("done")
    orchestrator.reset()
    assert orchestrator.conversation_ended is False
    assert orchestrator._cart == []


def test_remove_item():
    import orchestrator
    orchestrator.run_turn("hello")
    orchestrator.run_turn("I need milk")
    orchestrator.run_turn("I need chocolate")
    assert len(orchestrator._cart) == 2
    
    # Try to remove milk
    orchestrator.run_turn("remove the milk")
    assert len(orchestrator._cart) == 1
    assert orchestrator._cart[0]["key"] == "chocolate"
    
    # Try to remove something not there
    orchestrator.run_turn("remove bananas")
    assert len(orchestrator._cart) == 1
