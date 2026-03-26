import json
import time
import os

# ==============================================================================
# ShopMate-R Orchestrator Logic - Week X
# 
# This file contains the foundational logic for the ShopMate-R grocery assistant.
# The functionality will be iteratively expanded over the next 5-6 weeks.
# ==============================================================================

# TODO (Week 1): basic initialization of Temi and Pepper API wrappers
# TODO (Week 2): Inventory loading and basic searching logic
# TODO (Week 3): LLM Integration (OpenAI API connection for conversation)
# TODO (Week 4): Implement Temi navigation queue and task management
# TODO (Week 5): Integrate M5Stack sensors for shelf pickup detection
# TODO (Week 6): Live testing, edge case handling, and dashboard syncing

from inventory import Inventory

try:
    from openai import OpenAI
    _openai_available = True
except ImportError:
    _openai_available = False
    print("[WARNING] openai package not installed. LLM features will be disabled.")
    print("          Run:  pip install openai")

from config import (
    OPENAI_MODEL,
    OPENAI_MAX_TOKENS,
    OPENAI_TEMPERATURE,
    SYSTEM_PROMPT,
)


class Orchestrator:
    def __init__(self):
        """
        Initialize the core components of the orchestrator.
        """
        self.inventory = Inventory()
        self.order_queue = []
        self.temi_busy = False

        self._conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self._llm_client = None
        if _openai_available:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self._llm_client = OpenAI(api_key=api_key)
                print("[LLM] OpenAI client initialised successfully.")
            else:
                print("[WARNING] OPENAI_API_KEY environment variable not set. LLM will return a stub response.")

        print("[INIT] Orchestrator started. Components initializing...")
        self._setup_robots()

    def _setup_robots(self):
        """
        Placeholder logic to connect to the physical robots (Pepper and Temi).
        """
        # pepper = PepperRobot()
        # temi = TemiRobot()
        print("[SETUP] Waiting for robot API implemention...")

    def load_inventory(self, filepath=None):
        """
        Loads the store inventory from a JSON file.
        """
        print(f"[STORE] Loading inventory from {filepath}...")
        if filepath:
            import config as _cfg
            _cfg.INVENTORY_FILE = filepath
        self.inventory.load()

    def search_inventory(self, query):
        """
        Search inventory by name, category, or id. Returns matching items.
        """
        results = self.inventory.search(query)
        if results:
            print(f"[SEARCH] '{query}' -> {len(results)} match(es) found:")
            for item in results:
                status = f"{item['stock']} in stock" if item["stock"] > 0 else "OUT OF STOCK"
                print(f"         - {item['name']} (aisle {item['aisle']}, {item['price']:.2f}) - {status}")
        else:
            print(f"[SEARCH] No items found for '{query}'.")
        return results

    def check_item_stock(self, item_id):
        """
        Returns (in_stock: bool, count: int) for a given item id.
        """
        in_stock, count = self.inventory.check_stock(item_id)
        label = f"{count} in stock" if in_stock else "OUT OF STOCK"
        print(f"[STOCK] '{item_id}' -> {label}")
        return in_stock, count

    def _build_context_message(self):
        """
        Summarise current inventory as text to inject into the LLM prompt.
        """
        return (
            "=== Current store inventory ===\n"
            + self.inventory.as_text()
            + "\n==============================="
        )

    def _ask_llm(self, user_message):
        """
        Send user_message to the OpenAI API and return the assistant reply.
        """
        if not _openai_available or self._llm_client is None:
            # Graceful stub when the SDK / key is absent
            return (
                "[LLM STUB] OpenAI client unavailable. "
                f"You asked: '{user_message}'"
            )

        # Refresh inventory context inside the system message
        self._conversation_history[0] = {
            "role": "system",
            "content": SYSTEM_PROMPT + "\n\n" + self._build_context_message(),
        }

        # Append the new user turn
        self._conversation_history.append(
            {"role": "user", "content": user_message}
        )

        try:
            response = self._llm_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=self._conversation_history,
                max_tokens=OPENAI_MAX_TOKENS,
                temperature=OPENAI_TEMPERATURE,
            )
            reply = response.choices[0].message.content.strip()
        except Exception as exc:
            reply = f"[LLM ERROR] {exc}"

        # Store assistant reply in history for multi-turn context
        self._conversation_history.append(
            {"role": "assistant", "content": reply}
        )
        return reply

    def handle_customer_request(self, customer_input):
        """
        The main interaction loop processing customer speech/text via the LLM.
        """
        print(f"[PEPPER - LISTENING] Customer says: '{customer_input}'")

        # 1. Search inventory for quick local match
        self.search_inventory(customer_input)

        # 2. Send input to LLM for natural language response
        llm_reply = self._ask_llm(customer_input)

        # 3. Trigger appropriate action
        print(f"[PEPPER - SPEAKING] {llm_reply}")
        return llm_reply

    def reset_conversation(self):
        """
        Clear conversation history (start a new customer session).
        """
        self._conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        print("[LLM] Conversation history cleared. New session started.")

    def queue_temi_task(self, item_id, area):
        """
        Adds a fetching task to Temi's queue and manages its busy state.
        """
        task = {"item": item_id, "destination": area}
        self.order_queue.append(task)
        print(f"[QUEUE] Task added: Fetch {item_id} from {area}. Queue length: {len(self.order_queue)}")
        self.process_queue()

    def process_queue(self):
        """
        Checks if Temi is free and sends it to the next location if it is.
        """
        if not self.temi_busy and len(self.order_queue) > 0:
            next_task = self.order_queue.pop(0)
            self.temi_busy = True
            print(f"[TEMI - NAVIGATING] Moving to {next_task['destination']} to fetch {next_task['item']}.")
            # Trigger temi.goto(area) here
        elif self.temi_busy:
            print("[TEMI - STATUS] Currently busy. Task remains in queue.")

    def handle_sensor_pickup(self, sensor_id):
        """
        Logic to handle unexpected stock changes based on distance sensors.
        """
        # M5Stack REST integration to be added
        print(f"[SENSOR] Activity detected at sensor {sensor_id}.")


def main():
    """
    Main execution loop.
    """
    app = Orchestrator()
    app.load_inventory("data/inventory.json")

    # Mock Interaction Loop
    print("\n--- Starting Mock Interaction ---")
    app.handle_customer_request("Do you have any almond milk?")
    app.queue_temi_task("almond_milk", "drinks_dairy")

    # Simulate time passing
    time.sleep(1)

    app.handle_sensor_pickup("sensor_dairy_01")

if __name__ == "__main__":
    main()
