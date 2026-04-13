"""
config.py — ShopMate-R Grocery Assistant configuration.

Global toggles and settings for the multi-robot grocery assistant.
This build targets REAL hardware only — Pepper over SSH and Temi over
its HTTP control endpoint. There is no mock mode.
"""

import os

# =========================================================================
# MIC MODE  — voice input from customer
# =========================================================================
# Master switch for microphone input. When False, the system reads typed
# text from the console instead.
MIC_MODE = False

# Per-robot mic ownership. When MIC_MODE is True these decide which robot
# "owns" the active microphone channel. Pepper is the default front-desk
# greeter; Temi's mic lets customers talk to it at the shelf.
PEPPER_MIC_MODE = True    # listen through Pepper (store entrance)
TEMI_MIC_MODE   = False   # listen through Temi (at the shelf)

# =========================================================================
# DISPLAY MODE  — visual output on robot screens
# =========================================================================
DISPLAY_MODE = True

PEPPER_DISPLAY_MODE = True   # show product cards on Pepper's tablet
TEMI_DISPLAY_MODE   = True   # show item info on Temi's screen / dashboard

# =========================================================================
# OPENAI  — natural language understanding
# Never hardcode keys. Set the environment variable OPENAI_API_KEY before
# running, e.g.   export OPENAI_API_KEY="sk-..."
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-4o-mini"

# =========================================================================
# ROBOT NETWORK
# =========================================================================
PEPPER_IP = "172.30.36.41"
PEPPER_VOLUME = 70
TEMI_IP   = "172.30.36.31"

# =========================================================================
# DASHBOARD
# =========================================================================
DASHBOARD_PORT = 5050
DASHBOARD_URL  = f"http://127.0.0.1:{DASHBOARD_PORT}"

# =========================================================================
# STORE LAYOUT  — Temi navigation targets
# =========================================================================
TEMI_LOCATIONS = {
    "entrance":        "entrance",
    "checkout":        "entrance",      # same physical position as entrance
    "produce_aisle":   "a",
    "dairy_aisle":     "b",
    "bakery_aisle":    "c",
    "beverages_aisle": "d",
    "snacks_aisle":    "a",             # shares location A with produce
    "frozen_aisle":    "b",             # shares location B with dairy
    "pantry_aisle":    "c",             # shares location C with bakery
}

TEMI_HOME = "entrance"
