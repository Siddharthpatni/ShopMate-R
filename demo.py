"""
demo.py — Scripted end-to-end walkthrough of ShopMate-R.

Runs the full customer flow against the real robots without needing
voice input or typing — useful for thesis defenses, recorded demos,
and debugging the orchestrator without wrestling with a microphone.

Three pre-baked scenarios:

    python demo.py                  # default happy-path scenario
    python demo.py happy            # customer buys 3 items and leaves
    python demo.py browse           # customer browses a category first
    python demo.py alternative      # requested item is out of stock
    python demo.py --list           # show all scenarios and exit

The scenarios exercise the same code path as main.py — Pepper speaks,
gestures, and shows its tablet; Temi drives and delivers; the
dashboard reflects it all in real time. The only thing mocked is the
customer's input.
"""

from __future__ import annotations
import argparse
import sys
import time

import orchestrator
from pepper_api import (
    pepper_show_idle,
    pepper_show_welcome,
    pepper_wave_hello,
)


# -------------------------------------------------------------------------
# Scenarios
# -------------------------------------------------------------------------
# Each scenario is a list of customer utterances. The first one should
# be a greeting; the last one triggers delivery ("done", "bye", etc.).

SCENARIOS: dict[str, list[str]] = {
    "happy": [
        "hello",
        "I need milk",
        "do you have some chocolate",
        "a loaf of white bread please",
        "that's all",
    ],
    "browse": [
        "hello",
        "show me the dairy section",
        "I want eggs",
        "also butter",
        "done",
    ],
    "alternative": [
        "hello",
        "I need soy milk",
        "also frozen pizza",
        "and some coffee",
        "bye",
    ],
    "cart_full": [
        "hello",
        "I need milk",
        "chocolate",
        "bananas",
        "chips",   # MAX_CART is 4 — this fills it and auto-delivers
    ],
    "price_check": [
        "hello",
        "how much are apples",
        "and what's the price of coffee",
        "I'll take the apples",
        "done",
    ],
}


def list_scenarios() -> None:
    print("\nAvailable scenarios:\n")
    for name, script in SCENARIOS.items():
        print(f"  {name}")
        for i, line in enumerate(script, 1):
            print(f"      {i}. \"{line}\"")
        print()


def run(scenario: str, pause: float) -> int:
    if scenario not in SCENARIOS:
        print(f"❌ Unknown scenario '{scenario}'")
        print(f"   Try one of: {', '.join(SCENARIOS)}")
        return 1

    script = SCENARIOS[scenario]
    print("=" * 64)
    print(f"  🎬  DEMO: running scenario '{scenario}' "
          f"({len(script)} turns, {pause}s between turns)")
    print("=" * 64)

    # Match main.py's startup: welcome + wave before the first turn
    pepper_show_welcome()
    pepper_wave_hello()
    time.sleep(pause)

    orchestrator.reset()
    for i, utterance in enumerate(script, 1):
        print(f"\n─── Turn {i}/{len(script)}  ─────────────────────────────")
        print(f"📝 Scripted customer says: \"{utterance}\"")
        orchestrator.run_turn(utterance)
        if orchestrator.conversation_ended:
            print("\n🏁 Orchestrator reports conversation ENDED.")
            break
        time.sleep(pause)

    # Idle screen so Pepper's tablet is ready for the next customer
    pepper_show_idle()
    print("\n✅ Demo complete.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("scenario", nargs="?", default="happy",
                   help=f"one of: {', '.join(SCENARIOS)}")
    p.add_argument("--pause", type=float, default=2.0,
                   help="seconds between scripted turns (default: 2.0)")
    p.add_argument("--list", action="store_true",
                   help="list scenarios and exit")
    args = p.parse_args()

    if args.list:
        list_scenarios()
        return 0

    try:
        return run(args.scenario, args.pause)
    except KeyboardInterrupt:
        print("\n[demo] Interrupted.")
        return 130
    finally:
        # Clean SSH teardown — mirrors main.py's final `pepper_close()`
        from pepper_api import pepper_close
        pepper_close()


if __name__ == "__main__":
    sys.exit(main())
