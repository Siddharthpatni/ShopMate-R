# ShopMate-R

ShopMate-R is a multi-robot grocery shopping assistant being developed as a university project for Smart IoT (SoSe 2026, Prof. Tobias Dörnbach, Ostfalia University).

## Project Plan & Objectives

The goal of this project is to integrate two robots, **Pepper** and **Temi**, alongside M5Stack sensors and an LLM orchestration layer to assist customers in a simulated grocery store physically located in the university robotics lab.

### Initial Roadmap

- [x] Initial project setup and repository creation.
- [ ] Investigate `pypepper` API for Pepper's interaction capabilities.
- [ ] Investigate `pytemi` API for Temi's navigation capabilities.
- [ ] Set up basic LLM AI orchestration for NLP request handling.
- [ ] Connect M5Stack sensors for shelf pickup detection.
- [ ] Develop a Flask-based live dashboard.
- [ ] Conduct live testing in the Ostfalia robotics lab.

## Team

- Siddharth Patni
- Charmin Thesiya

## What It Does

Customer walks into a simulated grocery store → talks to Pepper → LLM checks inventory and decides what to do → Temi fetches items from shelves → sensor detects pickups and updates stock → dashboard shows everything live.

## Architecture

```text
┌────────────────────┐                      ┌───────────────┐
│                    │ ──────────────────▶  │  Pepper       │
│   orchestrator.py  │ ◀──────────────────  │  (humanoid)   │
│   (Python 3.10)    │                      └───────────────┘
│                    │                      ┌───────────────┐
│   + GPT-4o         │ ──────────────────▶  │  Temi         │
│   function calling │ ◀──────────────────  │  (mobile)     │
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
