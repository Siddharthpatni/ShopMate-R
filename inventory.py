# inventory.py
# JSON-based inventory. Load, search, check stock, update counts.

import json
from config import INVENTORY_FILE, STATE_FILE


class Inventory:
    def __init__(self):
        self.items = []
        self.load()

    def load(self):
        try:
            with open(INVENTORY_FILE, "r") as f:
                self.items = json.load(f).get("items", [])
            print(f"Loaded {len(self.items)} items.")
        except FileNotFoundError:
            print(f"Warning: {INVENTORY_FILE} not found.")
            self.items = []

    def save(self):
        with open(INVENTORY_FILE, "w") as f:
            json.dump({"items": self.items}, f, indent=2)
        
        self._update_shared_state()

     def _update_shared_state(self):
        """Updates the state.json file"""
        try:
            state = {}
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, "r") as f:
                    state = json.load(f)

            state["inventory"] = self.items
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
            
            print("Successfully created/updated state.json!")
        except Exception as e:
            print(f"Logic Error: {e}")

    def search(self, query):
        """Search by name, category, or id. Case-insensitive."""
        q = query.lower()
        return [
            item for item in self.items
            if q in item["name"].lower()
            or q in item.get("category", "").lower()
            or q in item.get("id", "").lower()
        ]

    def get_by_id(self, item_id):
        for item in self.items:
            if item["id"] == item_id:
                return item
        return None

    def check_stock(self, item_id):
        """Returns (in_stock: bool, count: int)."""
        item = self.get_by_id(item_id)
        if not item:
            return False, 0
        return item["stock"] > 0, item["stock"]

    def decrease_stock(self, item_id, amount=1):
        """Decrease stock count after an item is delivered. Returns True if successful."""
        item = self.get_by_id(item_id)
        if item and item["stock"] >= amount:
            item["stock"] -= amount
            self.save()
            return True
        return False

    def get_low_stock_items(self, threshold=3):
        """
        Returns all items with stock at or below the threshold.
        Used to warn Pepper when something is running low so it can
        mention it to customers or suggest alternatives.
        """
        return [
            item for item in self.items
            if 0 < item["stock"] <= threshold
        ]

    def is_out_of_stock(self, item_id):
        """Returns True if the item is completely out of stock."""
        item = self.get_by_id(item_id)
        if not item:
            return True
        return item["stock"] == 0

    def as_text(self):
        """Full inventory as readable text for the AI assistant."""
        lines = []
        for item in self.items:
            status = f"{item['stock']} left" if item["stock"] > 0 else "OUT OF STOCK"
            lines.append(
                f"- {item['name']} (id: {item['id']}, area: {item['category']}, "
                f"€{item['price']:.2f}, {status})"
            )
        return "\n".join(lines)
