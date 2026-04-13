# ShopMate-R — Multi-Robot Grocery Assistant

A grocery-store assistant built around two robots:

* **Pepper** — stationary humanoid at the entrance. Greets customers,
  holds the conversation with expressive **hand gestures**, shows
  product cards on its tablet, and says **BYE** at the end.
* **Temi** — mobile robot that drives to the correct aisle and delivers
  the item the customer asked for.
* **Python orchestrator** — parses the customer's request with an LLM,
  checks the inventory database, and dispatches the two robots.
* **Flask dashboard** — live inventory, low-stock alerts, Temi status,
  Temi screen, terminal feed, and the `/api/sensor` endpoint for the
  M5Stack shelf sensors.

## NO MOCK MODE

This build targets real hardware only.
`pepper_api.py` connects to the real Pepper over SSH at import time.
`temi_api.py` sends real HTTP commands to Temi at `config.TEMI_IP`
and polls `/status` until Temi reports arrival before continuing.

Make sure both robots are reachable on the network before launching.

## Customer flow

```
Pepper 👋  "Hello, welcome! Tell me what you need."
Customer    "I need milk"
Pepper 🤔  (thinking gesture)
Pepper 📺  shows Whole Milk card
Pepper 👉  points to dairy aisle
Pepper 🗣  "Yes we have Whole Milk, 1.29 euros, dairy aisle.
            Please wait here. Temi will fetch it and bring it to you."
Temi   🚚  drives to dairy_aisle            (leaves customer)
Temi   🤲  picks up the item from the shelf
Temi   🚚  drives back to the entrance      (returns to customer)
Temi   🗣  "Here is your Whole Milk. Please take it from my tray."
Pepper 📺  clears tablet
Pepper 👋  waves goodbye
Pepper 🗣  "Thank you for shopping with us. Have a wonderful day. BYE!"
Pepper 🙇  bows
                                       ← conversation ENDS
                    waiting for next customer...
```

The conversation automatically ends after Temi delivers the item. You
don't need to type "bye" — Pepper does it. The main loop then resets
and waits for the next customer.

## Display mode + mic mode for BOTH robots

```python
# config.py
MIC_MODE            = True    # master switch
PEPPER_MIC_MODE     = True    # listen through Pepper at the front desk
TEMI_MIC_MODE       = False   # listen through Temi at the shelf

DISPLAY_MODE        = True    # master switch
PEPPER_DISPLAY_MODE = True    # product cards on Pepper's tablet
TEMI_DISPLAY_MODE   = True    # product cards on Temi's screen
```

Set `MIC_MODE = False` to use the keyboard instead.

## Pepper's hand gestures

Every time Pepper speaks it plays a random conversational hand gesture
so it looks alive. There are also named gestures for specific moments:

| Moment | Gesture |
|---|---|
| First greeting | `pepper_wave_hello()` |
| Pointing to an aisle | `pepper_point_to_aisle()` |
| Suggesting an alternative | `pepper_raise_hands()` |
| Parsing a request | `pepper_thinking()` |
| Saying bye at the end | `pepper_wave_goodbye()` + `pepper_bow()` |
| While talking (any `pepper_say`) | random gesture from `TALK_GESTURES` |

`TALK_GESTURES` includes `Explain_1..4`, `Enthusiastic_4`,
`YouKnowWhat_1`, `ShowSky_1`.

## File layout

| file | purpose |
|---|---|
| `config.py` | toggles, robot IPs, aisle map |
| `grocery_db.py` | product catalogue + fuzzy lookup + similarity suggestion |
| `pepper_api.py` | Pepper speech + hand gestures + tablet + mic gating |
| `temi_api.py` | Temi navigation + delivery + screen + mic gating |
| `orchestrator.py` | intent extraction + handlers + automatic goodbye |
| `main.py` | multi-customer loop + dashboard launcher + mic input |
| `mock_dashboard.py` | Flask dashboard + `/api/sensor` endpoint |
| `m5stack_sensor.py` | CLI simulator for the IoT shelf sensors |
| `pypepper_ssh.py` | real Pepper SSH driver |
| `requirements.txt` | pip deps |

## Running

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."   # optional — fallback parser works too
python main.py
```

Open the dashboard at `http://127.0.0.1:5050`.

Try asking:
* "where is the milk"
* "do you have almond milk"
* "how much are apples"
* "I want bread"

## Simulating the shelf sensor

```bash
python m5stack_sensor.py milk              # customer took milk
python m5stack_sensor.py bananas taken
python m5stack_sensor.py milk restocked
```
