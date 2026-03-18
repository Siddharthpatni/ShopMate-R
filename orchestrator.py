import json
import time

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

class Orchestrator:
    def __init__(self):
        """
        Initialize the core components of the orchestrator.
        """
        self.inventory = {} # Placeholder for inventory data
        self.order_queue = [] # Queue for Temi tasks
        self.temi_busy = False # Status flag for the mobile robot
        
        print("[INIT] Orchestrator started. Components initializing...")
        self._setup_robots()
        
    def _setup_robots(self):
        """
        Placeholder logic to connect to the physical robots (Pepper and Temi).
        """
        # pepper = PepperRobot()
        # temi = TemiRobot()
        print("[SETUP] Waiting for robot API implemention...")
        pass

    def load_inventory(self, filepath):
        """
        Loads the store inventory from a JSON file.
        """
        print(f"[STORE] Loading inventory from {filepath}...")
        # Implementation to be added in later weeks
        pass

    def handle_customer_request(self, customer_input):
        """
        The main interaction loop processing customer speech/text via the LLM.
        """
        print(f"[PEPPER - LISTENING] Customer says: '{customer_input}'")
        
        # 1. Send input to LLM (To be implemented)
        # 2. Parse LLM intent (search, stock check, fetch)
        # 3. Trigger appropriate action
        
        return "[PEPPER - SPEAKING] Let me check our stock for that."

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
        pass

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
