# orchestrator.py
# Central brain of ShopMate-R.
# Connects to the LLM, manages customer conversations, dispatches robots.
#
# Run: python orchestrator.py
# Uses text input for testing. In the lab, Pepper's mic feeds into this.

import json
import time
from collections import deque
from openai import OpenAI

from config import OPENAI_API_KEY, STORE_AREAS, STATE_FILE
from inventory import Inventory
from pepper_api import PepperRobot
from temi_api import TemiRobot

client = OpenAI(api_key=OPENAI_API_KEY)
inventory = Inventory()
pepper = PepperRobot()
temi = TemiRobot()

# --- State ---
order_queue = deque()
temi_busy = False
temi_current_task = None
conversations = {}  # per-customer conversation history
action_log = []


def sync_dashboard():
    """Write state to shared file so dashboard.py can read it."""
    state = {
        "temi_busy": temi_busy,
        "temi_current_task": temi_current_task,
        "queue": list(order_queue),
        "log": action_log[-50:]
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass


def log_action(message):
    """Add entry to action log and sync dashboard."""
    action_log.append({"time": time.strftime("%H:%M:%S"), "message": message})
    sync_dashboard()


# --- LLM function definitions ---

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_inventory",
            "description": "Search store inventory by name or category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_item_stock",
            "description": "Check stock count for a specific item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"}
                },
                "required": ["item_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pepper_say",
            "description": "Make Pepper say something to the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pepper_gesture",
            "description": "Make Pepper do a gesture.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gesture": {
                        "type": "string",
                        "enum": ["wave", "point_left", "point_right", "nod", "bow"]
                    }
                },
                "required": ["gesture"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_temi_to_fetch",
            "description": "Send Temi to a store area to fetch an item. Queues if busy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string"},
                    "area": {"type": "string", "enum": list(STORE_AREAS.keys())},
                    "customer_id": {"type": "string"},
                },
                "required": ["item_id", "area", "customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "temi_speak",
            "description": "Make Temi say something through its speaker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_queue_status",
            "description": "Check how many orders are waiting.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
]

SYSTEM_PROMPT = """You are ShopMate-R, a friendly grocery store assistant speaking through the Pepper robot.

Temi is a mobile robot that fetches items from shelves when you tell it to.

Current inventory:

{inventory}

Rules:
- Greet customers briefly. Don't be over the top.
- Search inventory before promising anything.
- If out of stock, suggest a similar item that IS in stock.
- Vague requests ("something for breakfast") → suggest 2-3 specific items and ask.
- Multiple items → batch by area so Temi makes fewer trips.
- Temi busy → tell customer their order is queued.
- Stock ≤ 3 → mention casually ("we're running low on those").
- Talk like a person in a small shop. Short sentences. No corporate speak.
- Never mention item IDs, area codes, or technical details to the customer.
- Use gestures naturally: wave to greet, nod to confirm, point toward areas.
"""


def execute_function(name, args):
    """Run a function the LLM called. Return result string."""
    global temi_busy, temi_current_task

    if name == "search_inventory":
        results = inventory.search(args["query"])
        if results:
            return json.dumps([
                {"id": r["id"], "name": r["name"], "area": r["category"],
                 "stock": r["stock"], "price": r["price"]}
                for r in results
            ])
        return "No matching items found."

    elif name == "check_item_stock":
        in_stock, count = inventory.check_stock(args["item_id"])
        item = inventory.get_by_id(args["item_id"])
        if item:
            return f"{item['name']}: {count} in stock, area: {item['category']}"
        return "Item not found."

    elif name == "pepper_say":
        text = args.get("text", "")
        pepper.say(text)
        log_action(f"Pepper: {text[:80]}")
        return "Done."

    elif name == "pepper_gesture":
        gesture = args.get("gesture", "nod")
        pepper.gesture(gesture)
        log_action(f"Pepper gesture: {gesture}")
        return "Done."

    elif name == "send_temi_to_fetch":
        item_id = args["item_id"]
        area = args["area"]
        cust = args.get("customer_id", "?")
        task = {"item_id": item_id, "area": area, "customer_id": cust}

        if not temi_busy:
            temi_busy = True
            temi_current_task = task
            area_name = STORE_AREAS.get(area, area)
            temi.say(f"Heading to {area_name}")
            temi.goto(area_name)
            log_action(f"Temi → {area_name} for {item_id} (customer {cust})")
            sync_dashboard()
            return f"Temi heading to {area_name} for {item_id}."
        else:
            order_queue.append(task)
            log_action(f"Queued: {item_id} for customer {cust} (#{len(order_queue)})")
            sync_dashboard()
            return f"Temi busy. Queued at position {len(order_queue)}."

    elif name == "temi_speak":
        temi.say(args.get("text", ""))
        return "Done."

    elif name == "get_queue_status":
        current = temi_current_task["item_id"] if temi_current_task else "none"
        return f"Fetching: {current}. Queued: {len(order_queue)}."

    return "Unknown function."


def temi_task_done():
    """Called when Temi finishes a delivery."""
    global temi_busy, temi_current_task

    if temi_current_task:
        inventory.decrease_stock(temi_current_task["item_id"])
        log_action(f"Delivered {temi_current_task['item_id']} to customer {temi_current_task['customer_id']}")
        print(f"  [DONE] Delivered {temi_current_task['item_id']}. Stock updated.")

    if order_queue:
        next_task = order_queue.popleft()
        temi_current_task = next_task
        area_name = STORE_AREAS.get(next_task["area"], next_task["area"])
        temi.say(f"Next up, heading to {area_name}")
        temi.goto(area_name)
        log_action(f"Temi → {area_name} for {next_task['item_id']}")
        print(f"  [TEMI] Next: {next_task['item_id']} at {area_name}")
    else:
        temi_busy = False
        temi_current_task = None
        temi.goto("Area D")
        print("  [TEMI] Queue empty. Returning to entrance.")

    sync_dashboard()


def handle_customer(customer_id, message):
    """Process a customer message through the LLM."""
    if customer_id not in conversations:
        conversations[customer_id] = []

    conversations[customer_id].append({
        "role": "user",
        "content": f"[Customer {customer_id}]: {message}"
    })

    system = SYSTEM_PROMPT.format(inventory=inventory.as_text())
    messages = [{"role": "system", "content": system}] + conversations[customer_id]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )
    msg = response.choices[0].message

    # LLM might call multiple functions before giving a final answer
    while msg.tool_calls:
        conversations[customer_id].append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]
        })

        for tc in msg.tool_calls:
            result = execute_function(tc.function.name, json.loads(tc.function.arguments))
            conversations[customer_id].append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result
            })

        messages = [{"role": "system", "content": system}] + conversations[customer_id]
        response = client.chat.completions.create(
            model="gpt-4o", messages=messages, tools=TOOLS, tool_choice="auto",
        )
        msg = response.choices[0].message

    if msg.content:
        conversations[customer_id].append({"role": "assistant", "content": msg.content})
        print(f"\n  [LLM]: {msg.content}\n")

    return msg.content


def main():
    print("=" * 50)
    print("  ShopMate-R — Grocery Shopping Assistant")
    print("=" * 50)
    print()
    print("Commands:")
    print("  anything            → talk as customer 1")
    print("  customer:2 hello    → talk as customer 2")
    print("  done                → Temi finished delivery")
    print("  stock               → show inventory")
    print("  queue               → show order queue")
    print("  quit                → exit")
    print()

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd == "quit":
            break
        elif cmd == "done":
            temi_task_done()
            continue
        elif cmd == "stock":
            print(inventory.as_text())
            continue
        elif cmd == "queue":
            if temi_current_task:
                print(f"  Current: {temi_current_task['item_id']} → customer {temi_current_task['customer_id']}")
            else:
                print("  Temi is idle.")
            for i, task in enumerate(order_queue):
                print(f"  #{i+1}: {task['item_id']} → customer {task['customer_id']}")
            if not order_queue and not temi_current_task:
                print("  No pending orders.")
            continue

        # Parse customer ID
        if user_input.startswith("customer:"):
            parts = user_input.split(" ", 1)
            customer_id = parts[0].split(":")[1]
            message = parts[1] if len(parts) > 1 else ""
        else:
            customer_id = "1"
            message = user_input

        if message:
            handle_customer(customer_id, message)


if __name__ == "__main__":
    main()
