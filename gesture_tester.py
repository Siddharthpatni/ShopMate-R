"""
gesture_tester.py — Fire a single Pepper gesture from the command line.

Connects to the real Pepper via pepper_api (same SSH path as the full
app) but skips all the orchestrator/dashboard scaffolding. Useful when
you want to confirm a gesture path exists on the robot, or pick a new
animation path interactively.

Usage:

    python gesture_tester.py                 # interactive menu
    python gesture_tester.py wave_hello
    python gesture_tester.py thinking
    python gesture_tester.py --path animations/Stand/Gestures/Yes_3
    python gesture_tester.py --say "Hello there" wave_hello
    python gesture_tester.py --list

Gesture names correspond to the `pepper_*` helpers in pepper_api.py.
"""

from __future__ import annotations
import argparse
import sys
import time

import pepper_api

# -------------------------------------------------------------------------
# Map short CLI names to the callable in pepper_api
# -------------------------------------------------------------------------
GESTURES = {
    "wave_hello":    pepper_api.pepper_wave_hello,
    "wave_goodbye":  pepper_api.pepper_wave_goodbye,
    "bow":           pepper_api.pepper_bow,
    "point":         pepper_api.pepper_point_to_aisle,
    "raise_hands":   pepper_api.pepper_raise_hands,
    "thinking":      pepper_api.pepper_thinking,
    "nod":           pepper_api.pepper_nod_yes,
    "talk_random":   pepper_api.pepper_talk_gesture,
}


def _run_named(name: str) -> int:
    fn = GESTURES.get(name)
    if fn is None:
        print(f"❌ Unknown gesture '{name}'")
        print(f"   Try one of: {', '.join(sorted(GESTURES))}")
        return 1
    print(f"▶  Running gesture: {name}")
    fn()
    time.sleep(1.5)  # let the animation play out before closing the SSH
    return 0


def _run_path(path: str) -> int:
    print(f"▶  Running raw animation path: {path}")
    pepper_api.pepper_gesture(path)
    time.sleep(1.5)
    return 0


def _list_gestures() -> None:
    print("Named gestures (CLI name → pepper_api helper):\n")
    for name, fn in sorted(GESTURES.items()):
        print(f"  {name:<14} → pepper_api.{fn.__name__}")
    print("\nConversational talk-time pool (random one plays on every `say`):")
    for path in pepper_api.TALK_GESTURES:
        print(f"  {path}")


def _interactive() -> int:
    names = sorted(GESTURES)
    print("\nInteractive gesture tester. Empty input quits.\n")
    while True:
        for i, n in enumerate(names, 1):
            print(f"  {i:>2}. {n}")
        print("   q. quit")
        choice = input("\nChoose a gesture [number or name]: ").strip().lower()
        if not choice or choice == "q":
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            _run_named(names[int(choice) - 1])
        else:
            _run_named(choice)
        print()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("gesture", nargs="?",
                   help=f"Named gesture ({', '.join(sorted(GESTURES))})")
    p.add_argument("--path", help="Play a raw NAOqi animation path instead")
    p.add_argument("--say", help="Say this text alongside the gesture")
    p.add_argument("--list", action="store_true",
                   help="List available gestures and exit")
    args = p.parse_args()

    if args.list:
        _list_gestures()
        return 0

    try:
        if args.say:
            # `gesture=False` to avoid double-gesturing; we play our own below.
            pepper_api.pepper_say(args.say, gesture=False)

        if args.path:
            rc = _run_path(args.path)
        elif args.gesture:
            rc = _run_named(args.gesture)
        else:
            rc = _interactive()
    finally:
        pepper_api.pepper_close()

    return rc


if __name__ == "__main__":
    sys.exit(main())
