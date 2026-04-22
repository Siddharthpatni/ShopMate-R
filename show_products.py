import config
import pepper_api
from grocery_db import get_items_by_category

if __name__ == "__main__":
    print("Showing Milk Products in Grid Layout...")
    products = get_items_by_category("milk")
    pepper_api.pepper_show_category_products("milk", products)
    
    print("Dashboard rendered on tablet. Keeping connection open for 15 seconds...")
    try:
        import time
        for i in range(15):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        pepper_api.pepper_close()
        print("Done.")
