# config.py
# All settings in one place. Never hardcode IPs or keys elsewhere.

import os

def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

_load_env()

# --- OpenAI ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# --- Robot IPs (update in lab) ---
PEPPER_IP = "172.30.36.41"
LOCAL_IP = "0.0.0.0"       # your machine IP on lab network
TEMI_IP = "172.30.36.31"

# --- M5Stack ---
M5STACK_URL = "http://m5stack-ip:port"
PICKUP_DISTANCE_THRESHOLD = 10  # cm increase = item removed

# --- Store areas (must match Temi's saved locations) ---
STORE_AREAS = {
    "fruits_vegetables": "Area A",
    "drinks_dairy": "Area B",
    "snacks_dry": "Area C",
    "checkout": "Area D",
}

# --- Paths ---
BASE_DIR = os.path.dirname(__file__)
INVENTORY_FILE = os.path.join(BASE_DIR, "data", "inventory.json")
STATE_FILE = os.path.join(BASE_DIR, "data", "state.json")

# --- Dashboard ---
DASHBOARD_PORT = 5000
