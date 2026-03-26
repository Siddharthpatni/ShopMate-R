
# config.py
# Central configuration for ShopMate-R project.

import os

# Path to the inventory JSON file
INVENTORY_FILE = os.path.join(os.path.dirname(__file__), "data", "inventory.json")

# OpenAI settings (Week 3)
OPENAI_MODEL = "gpt-4o"
OPENAI_MAX_TOKENS = 512
OPENAI_TEMPERATURE = 0.4

# System prompt injected into every LLM conversation
SYSTEM_PROMPT = (
    "You are ShopMate, a friendly grocery store assistant robot. "
    "You help customers find products, check stock availability, and "
    "guide them to the right aisle. "
    "Always be concise, polite, and helpful. "
    "If a product is out of stock, suggest alternatives when possible."
)
