# ShopMate-R

A multi-robot grocery shopping assistant using Pepper, Temi, M5Stack sensors, and LLM orchestration.

Built for Smart IoT (SoSe 2026, Prof. Tobias Dörnbach, Ostfalia University).

## What It Does

Customer walks into a simulated grocery store → talks to Pepper → LLM checks inventory and decides what to do → Temi fetches items from shelves → sensor detects pickups and updates stock → dashboard shows everything live.

## Architecture

```text
┌────────────────────┐  NAOqi (port 9559)   ┌───────────────┐
│                    │ ──────────────────▶  │  Pepper       │
│   orchestrator.py  │ ◀──────────────────  │  (humanoid)   │
│   (Python 3.10)    │                      └───────────────┘
│                    │  HTTP REST (8080)     ┌───────────────┐
│   + GPT-4o         │ ──────────────────▶  │  Temi         │
│   function calling  │ ◀──────────────────  │  (mobile)     │
└────────┬───────────┘                      └───────────────┘
         │
         │  REST            ┌───────────────┐
         ├─────────────────▶│  M5Stack      │
         │                  │  (sensor)     │
         │                  └───────────────┘
         │
         │  File I/O        ┌───────────────┐
         └─────────────────▶│  Dashboard    │
                            │  (Flask)      │
                            └───────────────┘
```

## Files

| File | What it does |
|---|---|
| `orchestrator.py` | Main loop: LLM function calling, multi-user queue, robot dispatch |
| `pepper_api.py` | Pepper wrapper (pypepper on Linux, console mock on macOS) |
| `temi_api.py` | Temi wrapper (pytemi HTTP REST, works on any OS) |
| `inventory.py` | JSON inventory: search, stock check, auto-update |
| `sensors.py` | M5Stack distance sensor for shelf pickup detection |
| `dashboard.py` | Flask dashboard: live inventory, order queue, Temi status, action log |
| `config.py` | All IPs, API keys, thresholds, store layout |
| `PROMPT.md` | Master prompt for AI coding assistants |

## Quick Start (macOS — mock mode, no robots)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install openai requests flask
echo "OPENAI_API_KEY=your-key" > .env
python orchestrator.py
```

In a second terminal:
```bash
source .venv/bin/activate
python dashboard.py
# Open http://localhost:5000
```

Then type:
```
> Hi, I need some milk
> customer:2 Do you have chips?
> done
> stock
> quit
```

## Quick Start (Lab — real robots)

```bash
source .venv/bin/activate
pip install git+https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/pypepper.git
pip install git+https://gitlab-fi.ostfalia.de/hcr-lab/robot-control/middleware/pytemi.git
# Update IPs in config.py
# Make sure TemiMiddleware is running on Temi
python orchestrator.py
```

## Team

- Siddharth Patni
- Charmin Thesiya
