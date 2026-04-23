# ShopMate-R

**Multi-robot grocery assistant** built around two robots and a web dashboard.

A customer walks up, greets Pepper, asks for what they need in natural
language, and watches Temi do the aisle run. Items accumulate in a
cart on Pepper's tablet; once the customer is done, Temi makes a
single optimized trip through the store.

> Pepper handles the conversation. Temi handles the walking. Pepper's
> tablet handles the visuals. A Flask dashboard handles everything
> else — live inventory, Temi status, terminal feed, and the
> `/api/sensor` endpoint the M5Stack shelf sensors post to.

---
### Initial Roadmap

- [x] Initial project setup and repository creation.
- [x] Investigate `pypepper` API for Pepper's interaction capabilities.
- [x] Investigate `pytemi` API for Temi's navigation capabilities.
- [x] Set up main conversation logic for natural language requests.
- [x] Connect M5Stack sensors for shelf pickup detection.
- [x] Develop a Flask-based live dashboard.
- [x] Conduct live testing in the Ostfalia robotics lab.

## Team

- Siddharth Patni
- Charmin Thesiya
- Vivek Devganiya 
- Mansi Dayani

## Table of contents

1. [Architecture](#architecture)
2. [Customer flow](#customer-flow)
3. [Getting started](#getting-started)
4. [File layout](#file-layout)
5. [Configuration](#configuration)
6. [Pepper's hand gestures](#peppers-hand-gestures)
7. [Tablet UI](#tablet-ui)
8. [Utility scripts](#utility-scripts)
9. [Troubleshooting](#troubleshooting)

---

## Architecture

```
                  ┌──────────────────────┐
                  │  Python orchestrator │
                  │     (main.py)        │
                  └──────────┬───────────┘
                             │
         ┌───────────────────┼────────────────────────┐
         │                   │                        │
┌────────▼────────┐  ┌───────▼────────┐  ┌────────────▼───────────┐
│ Pepper (SSH)    │  │ Temi (HTTP)    │  │ Flask dashboard        │
│ speech, tablet, │  │ navigation,    │  │ inventory, logs,       │
│ mic, gestures   │  │ speech, screen │  │ /api/sensor endpoint   │
└─────────────────┘  └────────────────┘  └────────────────────────┘
                                                     ▲
                                                     │
                                          ┌──────────┴──────────┐
                                          │ M5Stack shelf IoT   │
                                          │ (simulated via CLI) │
                                          └─────────────────────┘
```

- **Pepper** is the stationary humanoid at the entrance. It greets
  customers, drives the conversation with expressive hand gestures,
  and renders every visual on its tablet.
- **Temi** is the mobile robot. It plans a multi-stop route through
  the aisles, picks up every cart item in one trip, and delivers them
  back to the customer.
- **Dashboard** (Flask) mirrors Temi's state, inventory, and a live
  log stream. It also serves as the receiver for simulated shelf-sensor
  events.

### No mock mode

Both robot drivers target **real hardware** only. `pepper_api.py`
opens an SSH session at import time; `temi_api.py` POSTs to
`config.TEMI_IP`. Make sure both robots are on the same network as the
orchestrator host before launching.

---

## Customer flow

```
Pepper 👋  "Hello, welcome! Tell me what you need."
Customer    "I need milk"
Pepper 📺  shows Whole Milk card, points to the dairy aisle
Pepper 🛒  adds it to the cart on the tablet
Customer    "Also some chocolate and a coffee"
Pepper 🛒  (adds two more items, shows running cart)
Customer    "That's all"
Pepper 🗣  "Temi is fetching your 3 items. Please wait here!"
Temi   🚚  groups items by aisle and makes one trip
Temi   🗣  "Here are your 3 items. Please take them from my tray."
Pepper 👋  waves goodbye, clears the tablet
Pepper 🙇  bows
                                       ← conversation ENDS
                    waiting for next customer...
```

The cart holds up to **4 items** (`orchestrator.MAX_CART`). Temi runs
the delivery as soon as the cart is full or the customer says *done /
that's all / deliver*.

---

## Getting started

### Prerequisites

- Python 3.10+
- Real Pepper on the network (SSH reachable at `config.PEPPER_IP`)
- Real Temi on the network (HTTP reachable at `config.TEMI_IP:8080`)
- `OPENAI_API_KEY` — optional; a keyword parser covers most utterances

### Install

```bash
python -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Pre-flight check

Before launching anything, verify the network is ready:

```bash
python health_check.py
```

You should see a green row for each robot and for the dashboard. If
the dashboard row is yellow, that's expected — it only goes green
once `mock_dashboard.py` is running.

### Launch

```bash
export OPENAI_API_KEY="sk-..."     # optional
python main.py
```

`main.py` auto-spawns `mock_dashboard.py` on port `5050` and begins
the multi-customer loop. Open `http://127.0.0.1:5050` to watch the
dashboard update live.

### Try it

Say or type:

```
where is the milk
do you have almond milk
how much are apples
I want bread
snacks
done
```

---

## File layout

### Core runtime

| File | Purpose |
|---|---|
| `main.py` | Entry point — banner, dashboard launcher, customer loop, stdin/mic bridge |
| `orchestrator.py` | Intent extraction (LLM + fallback), cart state, Pepper/Temi dispatch |
| `pepper_api.py` | Pepper speech, hand gestures, Material Design tablet, mic gating |
| `temi_api.py` | Temi navigation, speech, Material screen, mic gating |
| `pypepper_ssh.py` | Real Pepper SSH driver (connection layer — do not edit lightly) |
| `grocery_db.py` | In-memory catalogue + fuzzy lookup + similar-item suggestion |
| `config.py` | Toggles, robot IPs, aisle map |

### Dashboard + IoT

| File | Purpose |
|---|---|
| `mock_dashboard.py` | Flask server — live inventory, Temi mirror, log stream, `/api/sensor` |
| `m5stack_sensor.py` | CLI that posts shelf-sensor events (simulates M5Stack IoT units) |

### Dev tooling

| File | Purpose |
|---|---|
| `demo.py` | Scripted customer flow — no voice/keyboard input needed |
| `health_check.py` | Pre-flight diagnostic: reach Pepper, Temi, dashboard; inventory sanity |
| `tablet_preview.py` | Render every Pepper tablet screen to `./preview/*.html` for desktop preview |
| `gesture_tester.py` | Fire one Pepper gesture at a time (interactive or by name) |
| `db_inspector.py` | CLI to list / show / low-stock / take / restock inventory items |
| `tests/` | pytest suite — runs without hardware (58 tests) |
| `Makefile` | Shortcut targets: `make run / demo / test / preview / health / ...` |

### Other

| File | Purpose |
|---|---|
| `requirements.txt` | Pip dependencies |
| `CHANGELOG.md` | Notable changes per version |
| `.gitignore` | venv, caches, temp audio files |

---

## Configuration

Edit `config.py` — every knob is there.

```python
# Mic: Pepper is the front-desk greeter by default
MIC_MODE            = True
PEPPER_MIC_MODE     = True      # listen through Pepper (store entrance)
TEMI_MIC_MODE       = False     # listen through Temi (at the shelf)

# Display: both robots show product cards
DISPLAY_MODE        = True
PEPPER_DISPLAY_MODE = True      # product cards on Pepper's tablet
TEMI_DISPLAY_MODE   = True      # product cards on Temi's screen

# Network
PEPPER_IP = "172.30.36.41"
TEMI_IP   = "172.30.36.32"
```

Set `MIC_MODE = False` to read customer input from the keyboard
instead of either robot's microphone.

---

## Pepper's hand gestures

Every `pepper_say()` plays a small conversational hand gesture from
`TALK_GESTURES` so Pepper never looks frozen. Specific moments trigger
named gestures:

| Moment | Function | NAOqi path |
|---|---|---|
| First greeting | `pepper_wave_hello()` | `animations/Stand/Gestures/Hey_1` |
| Pointing to an aisle | `pepper_point_to_aisle()` | `animations/Stand/Gestures/Show_1` |
| Suggesting an alternative | `pepper_raise_hands()` | `animations/Stand/Gestures/Enthusiastic_4` |
| Parsing a request | `pepper_thinking()` | `animations/Stand/Gestures/Thinking_1` |
| Affirmative nod | `pepper_nod_yes()` | `animations/Stand/Gestures/Yes_1` |
| Saying bye at the end | `pepper_wave_goodbye()` | `animations/Stand/Gestures/Bye_1` |
| Bowing to thank the customer | `pepper_bow()` | `animations/Stand/Gestures/BowShort_1` |
| While talking | `pepper_talk_gesture()` | random from `TALK_GESTURES` |

Try them interactively without launching the whole app:

```bash
python gesture_tester.py                  # interactive menu
python gesture_tester.py wave_hello       # one-shot
python gesture_tester.py --path animations/Stand/Gestures/Yes_3
python gesture_tester.py --say "Hi there" wave_hello
```

---

## Tablet UI

The tablet has seven screens, all rendered from a single Apple-style
glassmorphism token system in `pepper_api.py`. Each screen layers
semi-transparent cards with `backdrop-filter: blur() saturate()` over
a vibrant multi-light aurora gradient, with thin white borders, inset
highlights, and soft double-layer shadows — the same recipe macOS and
iOS use for their frosted-glass surfaces.

The categories dashboard uses a **2-column** grid of large category
tiles, and each tile shows an inline 2-column preview of its top
products so customers can see options without tapping through.

| Screen | Shown when |
|---|---|
| `welcome` | Customer first engages |
| `idle` | Between customer sessions — prompts next customer to say hello |
| `categories` | Right after greeting — top-level category dashboard |
| `category_products` | Customer says a category ("dairy") |
| `product` | Single-product detail (price, aisle, stock badge) |
| `cart` | Running cart with subtotals |
| `goodbye` | End of session |

To preview them all in your desktop browser without touching Pepper:

```bash
python tablet_preview.py
```

This writes `preview/welcome.html`, `preview/cart.html`, etc., and
opens an index page. Use it every time you iterate on the tablet CSS.

---

## Utility scripts

All utility scripts are fully independent — none of them touches the
main customer loop. Useful for debugging, demos, and development.

```bash
python health_check.py              # pre-flight: Pepper / Temi / dashboard
python tablet_preview.py            # render all tablet screens locally
python gesture_tester.py            # try Pepper gestures interactively
python demo.py                      # scripted customer flow (happy path)
python demo.py alternative          # scenario: item out of stock
python demo.py cart_full            # scenario: cart auto-delivers at 4 items
python demo.py --list               # show all scenarios
python db_inspector.py              # print inventory
python db_inspector.py low          # low-stock alerts
python db_inspector.py categories   # per-category summary
python db_inspector.py take milk 2  # simulate 2 milks taken
python m5stack_sensor.py milk       # same thing via the "IoT" path
python m5stack_sensor.py chips restocked 10
```

If `make` is available, `make help` lists all the shortcut targets
(`make run / demo / preview / test / health / dashboard / ...`).

---

## Testing

The project ships with a pytest suite in `tests/` that runs without
any hardware — `conftest.py` stubs out the SSH driver and patches
`requests` so Pepper and Temi don't need to be reachable.

```bash
pip install pytest
pytest                       # or: make test
```

Covers: grocery_db lookup and mutation, the intent parser's fast
path, full orchestrator cart lifecycle (add / auto-deliver / done /
goodbye), and every tablet screen's rendered HTML (glass markers,
2-column grid layout, no leaked f-string placeholders).

---

## Troubleshooting

**"Pepper SSH failed"** — check `PEPPER_IP` in `config.py`, make sure
Pepper is awake, and try the alternate password (`Pepper` vs `nao`)
by editing `pypepper_ssh.py` if the defaults don't work.

**"Could not find a working display endpoint on Temi"** — Temi
firmware forks expose different webview endpoints. `temi_api.py`
already tries six variants (`/webview`, `/top_webview`, `/display`,
`/show_url`, `/url`, `/loadurl`). If none work, check with your
Temi bridge app's documentation and add its endpoint to
`_WEBVIEW_ENDPOINTS` in `temi_api.py`.

**Mic keeps failing** — the app automatically falls back to keyboard
after 3 consecutive mic failures. You can force keyboard mode by
setting `MIC_MODE = False` in `config.py`.

**Dashboard shows "offline"** — `main.py` is supposed to launch
`mock_dashboard.py` automatically. If the dashboard page says offline,
run it manually in a second terminal: `python mock_dashboard.py`.

**Tablet looks broken** — Pepper's tablet runs an older Android
WebView. Preview your changes with `tablet_preview.py` first;
anything that looks right in desktop Chrome should also render on
Pepper, but very modern CSS (`container-queries`, `:has()`, etc.)
may silently fail on the robot.
# ShopMate-R Final Migration
## Deployment Ready
