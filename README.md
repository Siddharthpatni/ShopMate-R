# Siddharth Patni's Workspace
# ShopMate-R

ShopMate-R is a multi-robot grocery shopping assistant being developed as a university project for Smart IoT (SoSe 2026, Prof. Tobias Dörnbach, Ostfalia University).

## Project Plan & Objectives

The goal of this project is to integrate two robots, **Pepper** and **Temi**, alongside M5Stack sensors and an intelligent orchestration system to assist customers in a simulated grocery store physically located in the university robotics lab.

### Initial Roadmap

- [x] Initial project setup and repository creation.
- [x] Investigate `pypepper` API for Pepper's interaction capabilities.
- [x] Investigate `pytemi` API for Temi's navigation capabilities.
- [ ] Set up main conversation logic for natural language requests.
- [ ] Connect M5Stack sensors for shelf pickup detection.
- [ ] Develop a Flask-based live dashboard.
- [ ] Conduct live testing in the Ostfalia robotics lab.

## Team

- Siddharth Patni
- Charmin Thesiya
- Vivek Devganiya 
- Mansi dayani

## What It Does

Customer walks into a simulated grocery store → talks to Pepper → System checks inventory and decides what to do → Temi fetches items from shelves → sensor detects pickups and updates stock → dashboard shows everything live.

## Architecture

```text
┌────────────────────┐                      ┌───────────────┐
│                    │ ──────────────────▶  │  Pepper       │
│   orchestrator.py  │ ◀──────────────────  │  (humanoid)   │
│   (Python 3.10)    │                      └───────────────┘
│                    │                      ┌───────────────┐
│   + NLP            │ ──────────────────▶  │  Temi         │
│   logic handler    │ ◀──────────────────  │  (mobile)     │
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

## Temi Navigation Setup (Lab Only)

Before running the orchestrator, you must manually save the shelf locations on Temi's internal map using its touchscreen mapping feature. The location names are exactly case-sensitive and must match `config.py`:

1. Physically drive Temi to the Fruits & Vegetables area. Save location precisely as: `Area A`
2. Drive to Drinks & Dairy. Save as: `Area B`
3. Drive to Snacks & Dry Goods. Save as: `Area C`
4. Drive to the Entrance/Checkout section. Save as: `Area D`
5. Ensure Temi has a `home base` location saved at its charging station.

Once these are saved, TemiMiddleware will successfully dispatch the robot when `orchestrator.py` commands it.