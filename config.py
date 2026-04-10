# config.py
# All settings in one place. Never hardcode IPs or keys elsewhere.
#
# To run in the lab, add robot IPs to .env:
#   TEMI_IP=172.30.36.31
#   PEPPER_IP=172.30.36.41
#   LOCAL_IP=172.30.x.x
#
# Without those .env entries, robots run in mock mode (safe for local testing).

import os

def _load_env():
    """Load .env file into os.environ. Strips surrounding quotes."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    value = value.strip().strip('"').strip("'")
                    os.environ[key.strip()] = value

_load_env()

# OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

# Robot IPs 
PEPPER_IP = os.environ.get("PEPPER_IP", "127.0.0.1")
LOCAL_IP = os.environ.get("LOCAL_IP", "0.0.0.0")
TEMI_IP = os.environ.get("TEMI_IP", "127.0.0.1")

# Connection timeout (seconds) 
ROBOT_TIMEOUT = int(os.environ.get("ROBOT_TIMEOUT", "3"))

# M5Stack
M5STACK_URL = os.environ.get("M5STACK_URL", "http://127.0.0.1:8080")
PICKUP_DISTANCE_THRESHOLD = 10  # cm increase = item removed

# Store areas (must match Temi's saved locations)
STORE_AREAS = {
    "fruits_vegetables": "Area A",
    "drinks_dairy": "Area B",
    "snacks_dry": "Area C",
    "checkout": "Area D",
}

# Paths 
BASE_DIR = os.path.dirname(__file__)
INVENTORY_FILE = os.path.join(BASE_DIR, "data", "inventory.json")
STATE_FILE = os.path.join(BASE_DIR, "data", "state.json")

# Dashboard 
DASHBOARD_PORT = 5000
