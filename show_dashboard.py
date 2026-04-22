import config
from pypepper_ssh import PepperRobotSSH
import pepper_api

if __name__ == "__main__":
    print("Connecting to Pepper...")
    pepper = PepperRobotSSH(config.PEPPER_IP, config.PEPPER_USER, config.PEPPER_PASS)
    pepper_api.init_pepper(pepper)
    
    print("Showing Categories Dashboard...")
    pepper_api.pepper_show_categories()
    print("Dashboard rendered on tablet. Keeping connection open for 15 seconds...")
    try:
        import time
        for i in range(15):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        pepper.close()
        print("Done.")
