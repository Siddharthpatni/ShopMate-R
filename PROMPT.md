# ShopMate-R — Master Prompt for AI Assistants

Copy everything below this line and paste it at the start of any AI conversation (Claude, GPT, Gemini, Cursor, Antigravity, etc.) when working on this project.

---

```
You are helping me build ShopMate-R, a multi-robot grocery shopping assistant. This is a university project for Smart IoT (Prof. Tobias Dörnbach, Ostfalia University of Applied Sciences, SoSe 2026).

Read this entire prompt carefully before responding to any request.

## PROJECT OVERVIEW

Two robots help customers shop in a simulated grocery store set up in our university robotics lab:

- **Pepper** (humanoid, stationary) stands at the entrance and talks to customers. Takes requests, suggests products, handles follow-up conversation, uses gestures.
- **Temi** (mobile, navigates) drives through the store, goes to shelves, brings items back to customers.
- **LLM (GPT-4o)** orchestrates everything via OpenAI function calling. Receives customer speech, searches inventory, decides what Pepper says, dispatches Temi.
- **M5Stack Core2** with distance sensor on a shelf. Detects item pickups, updates inventory automatically.
- **Flask dashboard** on a laptop shows live inventory, order queue, Temi location, action log.

Multi-user: if Temi is busy, new requests get queued. LLM batches same-area requests.

## ROBOT APIs (CRITICAL — read this carefully)

### Pepper — pypepper library
- Connects via NAOqi protocol (port 9559), direct to Pepper's onboard runtime
- **Linux only, Python 3.10 only** (the qi SDK wheel is compiled for CPython 3.10 on 64-bit Linux)
- No middleware needed on the robot side
- pypepper also starts a small HTTP server on your machine to serve images/text to Pepper's tablet
- Repository: https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/pypepper.git
- System requirements: 64-bit Linux (Ubuntu 22.04/24.04), Python 3.10 exactly, libicu70

Connection:
```python
from pypepper import Pepper
robot_pepper = Pepper(
    robot_ip="172.30.36.41",    # Pepper's IP (press chest button to hear it)
    local_ip="0.0.0.0"          # your machine's IP on the lab network
)
```

Key methods (blocking calls):
```python
robot_pepper.say("Hello, welcome to the store!")
robot_pepper.animate("animations/Stand/Gestures/Hey_1")  # wave
robot_pepper.show_text("Welcome!")  # shows on Pepper's tablet
# Speech recognition — check pypepper docs for exact method
```

### Temi — pytemi library + TemiMiddleware
- Communicates via HTTP REST through TemiMiddleware Android app
- TemiMiddleware must be built in Android Studio and installed on Temi via ADB
- TemiMiddleware exposes REST API on port 8080 on the robot
- pytemi works on **any OS, Python 3.10+**
- Repository: https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/pytemi.git
- TemiMiddleware repo: https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/temi-middleware.git

Connection:
```python
from pytemi import TemiRobot
robot_temi = TemiRobot("172.30.36.31")  # Temi's IP
```

Key methods (blocking — return after action completes):
```python
robot_temi.say("Heading to the drinks section!")
robot_temi.goto("Area B")  # navigate to saved location
```

### Network requirement
Both robots and your machine must be on the **same network** in the lab.

### Architecture diagram (from professor's code)
```
┌────────────────────┐  NAOqi (port 9559)   ┌─────────────────────┐
│                    │ ──────────────────▶  │   Pepper Robot      │
│   orchestrator.py  │ ◀──────────────────  │   (NAOqi on-board)  │
│   (Python 3.10)    │                      └─────────────────────┘
│                    │  HTTP REST (8080)     ┌─────────────────────┐
│                    │ ──────────────────▶  │  TemiMiddleware     │
│                    │ ◀──────────────────  │  (Android, on Temi) │
└────────────────────┘                      └─────────────────────┘
         │
         │ HTTP server (port 8080, this machine)
         ▼
   Serves images/text to Pepper's tablet
```

## STORE LAYOUT

Lab is set up with 4 areas:
- **Area A**: Fruits & Vegetables (apples, bananas, tomatoes, lettuce, onions)
- **Area B**: Drinks & Dairy (milk, oat milk, almond milk [OUT], OJ, water, cheese, yogurt)
- **Area C**: Snacks & Dry Goods (bread, pasta, rice, chips, chocolate, cereal, pasta sauce)
- **Area D**: Entrance/Checkout (Pepper stands here, customers start here)

Temi has all 4 locations saved in its navigation map.

## PROJECT STRUCTURE

```
ShopMate-R/
├── .gitignore
├── .env                  # OPENAI_API_KEY (never commit)
├── README.md
├── PROMPT.md             # This file
├── requirements.txt
├── config.py             # All IPs, keys, thresholds, store areas
├── orchestrator.py       # Main: LLM function calling, customer queue, robot dispatch
├── inventory.py          # JSON inventory: search, stock check, update
├── pepper_api.py         # pypepper wrapper (real on Linux, mock prints on macOS)
├── temi_api.py           # pytemi wrapper (HTTP REST, works anywhere)
├── sensors.py            # M5Stack distance sensor REST client
├── dashboard.py          # Flask: live inventory, queue, Temi status, action log
└── data/
    ├── inventory.json    # 19 products with stock, prices, locations
    └── state.json        # Shared state for dashboard sync
```

## LLM FUNCTION CALLING TOOLS

The orchestrator defines these 7 functions that GPT-4o can call:

1. `search_inventory(query)` — search products by name/category, returns matches with stock and location
2. `check_item_stock(item_id)` — check specific item availability and count
3. `pepper_say(text)` — make Pepper speak to the customer
4. `pepper_gesture(gesture)` — wave, point_left, point_right, nod, bow
5. `send_temi_to_fetch(item_id, area, customer_id)` — dispatch Temi, queues if busy
6. `temi_speak(text)` — make Temi say something while moving
7. `get_queue_status()` — check pending orders count

## SYSTEM PROMPT FOR THE LLM

The LLM is told to:
- Act like a friendly small-shop assistant speaking through Pepper
- Search inventory before promising anything
- Suggest alternatives when items are out of stock
- Handle vague requests ("I'm making pasta") by suggesting specific items
- Batch multi-item requests by area for efficient Temi trips
- Tell customers when Temi is busy and their order is queued
- Mention low stock (≤3) casually
- Keep responses short — customer is standing in front of Pepper
- Never mention item IDs or technical details to the customer
- Use gestures naturally (wave to greet, nod to confirm, point toward areas)

## DEVELOPMENT SETUP

### macOS (daily development — mock mode)
- Python 3.10 via pyenv
- `pip install openai requests flask`
- pypepper does NOT work on macOS — pepper_api.py falls back to console prints
- pytemi works if on same network as Temi (HTTP REST)
- orchestrator.py has a text-based demo mode for testing without robots

### Lab (robot testing — Linux)
- Python 3.10 required (for pypepper)
- Install pypepper: `pip install git+https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/pypepper.git`
- Install pytemi: `pip install git+https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/pytemi.git`
- Book robots at https://remotelab-i.ostfalia.de/ (VPN required)
- TemiMiddleware must be running on Temi before connecting
- Press Pepper's chest button to hear its IP
- Update IPs in config.py

## GRADING CRITERIA

- **4.0 level**: Pepper + Temi do something useful, communication works
- **1.0 level**: Pepper + Temi + extra device (M5Stack) doing something fancy with seamless interaction, good code quality and reusability
- Video demo (2-4 min) due April 20, 12:00
- Weekly Python commits required (real .py code changes, March 16 — April 20)
- Conference paper in ACM format, weekly 1000-char LaTeX diffs (March 9 — deadline)
- Handwritten paper summary exam in June

## CODING CONVENTIONS

- All settings in config.py, never hardcode IPs or keys
- Robot wrappers (pepper_api.py, temi_api.py) must have mock fallbacks for development without hardware
- All inter-device communication via REST
- Use deque for the order queue
- Dashboard syncs via shared state.json file
- Keep it simple — 5-week university project, not production software
- Commit messages should describe what changed and why

## CURRENT STATUS

[UPDATE THIS SECTION AS YOU PROGRESS]
- [x] Orchestrator with LLM function calling (7 tools)
- [x] Inventory system (19 products, search, stock management)
- [x] Pepper API wrapper with macOS mock fallback
- [x] Temi API wrapper (HTTP REST)
- [x] M5Stack sensor client (distance-based pickup detection)
- [x] Flask dashboard (inventory, queue, Temi status, action log)
- [x] Multi-user queue management
- [ ] Real Pepper testing in lab
- [ ] Real Temi testing in lab
- [ ] M5Stack hardware integration
- [ ] Pepper speech recognition for live input
- [ ] User study (pilot 2-3, full 5+)
- [ ] Video recording (due April 20)
- [ ] Conference paper completion

## IMPORTANT REMINDERS

- pypepper = Linux + Python 3.10 ONLY. Do not try to make it work on macOS.
- TemiMiddleware must be running on Temi's screen before pytemi can connect.
- The professor checks Ostfalia GitLab (gitlab-fi.ostfalia.de) for weekly commits, not GitHub.
- Every week between March 16 and April 20, each person needs at least one meaningful Python commit.
- The conference paper must be written in your own voice — there's a handwritten exam that catches AI-generated text.
- All external function calling must be done via REST (course requirement).
- The LLM must be used for orchestration via function calling (course requirement).

When I ask for help, keep code consistent with the existing patterns. Use config.py for settings, mock mode fallbacks in robot wrappers, REST for everything. Match the existing code style.
```
