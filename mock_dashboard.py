"""
mock_dashboard.py — ShopMate-R web dashboard.

Flask app that shows staff:
  • live inventory + low-stock alerts
  • Temi's current status and location (aisle)
  • Temi's screen (product card currently displayed)
  • a live terminal feed of orchestrator actions
  • pending customer requests

Auto-launched by main.py, or run directly:
    python mock_dashboard.py
Then open http://<your-ip>:5050
"""

import threading
import collections

from flask import Flask, jsonify, request, render_template_string

from config import DASHBOARD_PORT
import grocery_db

app = Flask(__name__)

# ------------------------------------------------------------------------
# Shared state
# ------------------------------------------------------------------------
_state = {
    "temi_location":   "entrance",
    "temi_status":     "idle",
    "temi_last_speech":"",
    "temi_screen":     None,   # {type: product|image|message, ...}
    "pending_requests": [],    # list of {customer_msg, item, status}
}
_lock = threading.Lock()

_terminal_log = collections.deque(maxlen=120)
_log_lock = threading.Lock()


# ------------------------------------------------------------------------
# HTML template
# ------------------------------------------------------------------------
HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ShopMate-R — Grocery Dashboard</title>
  <meta http-equiv="refresh" content="2">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
      font-family:'Inter',sans-serif;
      background: linear-gradient(135deg,#11998e 0%,#38ef7d 100%);
      min-height:100vh; color:#1a1a1a; padding:24px;
    }
    .wrap { max-width:1300px; margin:0 auto; }
    h1 {
      color:white; font-size:28px; font-weight:700; margin-bottom:4px;
      text-shadow:0 2px 4px rgba(0,0,0,.2);
    }
    .sub { color:rgba(255,255,255,.9); margin-bottom:20px; }
    .grid {
      display:grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap:16px;
    }
    .card {
      background:white; border-radius:14px; padding:18px;
      box-shadow:0 8px 24px rgba(0,0,0,.12);
    }
    .card h2 {
      font-size:14px; text-transform:uppercase; letter-spacing:1px;
      color:#555; margin-bottom:12px; font-weight:600;
    }
    .big { font-size:22px; font-weight:700; color:#11998e; }
    .muted { color:#777; font-size:13px; }
    .pill {
      display:inline-block; padding:4px 10px; border-radius:999px;
      background:#e8f5e9; color:#2e7d32; font-size:12px; font-weight:600;
    }
    .pill.warn { background:#fff3e0; color:#ef6c00; }
    .pill.err  { background:#ffebee; color:#c62828; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { text-align:left; padding:6px 4px; border-bottom:1px solid #eee; }
    th { font-weight:600; color:#555; text-transform:uppercase; font-size:11px; }
    .screen {
      background:#0f1419; color:#e5e5e5; border-radius:10px;
      padding:16px; min-height:160px; font-family:'JetBrains Mono',monospace;
      font-size:13px;
    }
    .screen .prod { font-size:18px; font-weight:700; color:#38ef7d; }
    .term {
      background:#0f1419; color:#8aff8a; border-radius:10px;
      padding:14px; height:260px; overflow-y:auto;
      font-family:'JetBrains Mono',monospace; font-size:12px;
      white-space:pre-wrap;
    }
    .full { grid-column:1 / -1; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>🛒 ShopMate-R — Grocery Assistant Dashboard</h1>
    <div class="sub">Pepper (front desk) &nbsp;+&nbsp; Temi (mobile shelf runner)</div>

    <div class="grid">

      <div class="card">
        <h2>Temi Status</h2>
        <div class="big">{{ state.temi_status }}</div>
        <div class="muted">at {{ state.temi_location }}</div>
        <div style="margin-top:10px;" class="muted">
          Last said: {{ state.temi_last_speech or '—' }}
        </div>
      </div>

      <div class="card">
        <h2>Temi Screen</h2>
        <div class="screen">
          {% if state.temi_screen %}
            {% if state.temi_screen.type == 'product' %}
              <div class="prod">{{ state.temi_screen.name }}</div>
              <div>€ {{ '%.2f'|format(state.temi_screen.price or 0) }}</div>
              <div>Aisle: {{ state.temi_screen.aisle }}</div>
              <div>Stock: {{ state.temi_screen.stock }}</div>
            {% elif state.temi_screen.type == 'message' %}
              {{ state.temi_screen.text }}
            {% elif state.temi_screen.type == 'image' %}
              [IMAGE] {{ state.temi_screen.url }}
            {% endif %}
          {% else %}
            — idle —
          {% endif %}
        </div>
      </div>

      <div class="card">
        <h2>Low Stock Alerts</h2>
        {% if low_stock %}
          <table>
            <tr><th>Item</th><th>Aisle</th><th>Stock</th></tr>
            {% for p in low_stock %}
              <tr>
                <td>{{ p.name }}</td>
                <td>{{ p.aisle }}</td>
                <td>
                  {% if p.stock == 0 %}
                    <span class="pill err">OUT</span>
                  {% else %}
                    <span class="pill warn">{{ p.stock }}</span>
                  {% endif %}
                </td>
              </tr>
            {% endfor %}
          </table>
        {% else %}
          <div class="muted">All items well stocked ✓</div>
        {% endif %}
      </div>

      <div class="card full">
        <h2>Inventory ({{ inventory|length }} products)</h2>
        <table>
          <tr><th>Product</th><th>Category</th><th>Aisle</th><th>Price</th><th>Stock</th></tr>
          {% for p in inventory %}
            <tr>
              <td>{{ p.name }}</td>
              <td>{{ p.category }}</td>
              <td>{{ p.aisle }}</td>
              <td>€ {{ '%.2f'|format(p.price) }}</td>
              <td>
                {% if p.stock == 0 %}
                  <span class="pill err">0</span>
                {% elif p.stock <= 5 %}
                  <span class="pill warn">{{ p.stock }}</span>
                {% else %}
                  <span class="pill">{{ p.stock }}</span>
                {% endif %}
              </td>
            </tr>
          {% endfor %}
        </table>
      </div>

      <div class="card full">
        <h2>Live Terminal</h2>
        <div class="term">{{ log }}</div>
      </div>

    </div>
  </div>
</body>
</html>
"""


# ------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------
@app.route("/")
def index():
    with _lock:
        state = dict(_state)
    with _log_lock:
        log = "\n".join(_terminal_log)
    return render_template_string(
        HTML,
        state=state,
        inventory=grocery_db.get_all_items(),
        low_stock=grocery_db.get_low_stock(threshold=5),
        log=log,
    )


@app.route("/api/state", methods=["GET", "POST"])
def api_state():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        with _lock:
            _state.update(data)
        return jsonify(ok=True)
    with _lock:
        return jsonify(_state)


@app.route("/api/log", methods=["GET", "POST"])
def api_log():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        line = data.get("line", "")
        if line:
            with _log_lock:
                _terminal_log.append(line)
        return jsonify(ok=True)
    with _log_lock:
        return jsonify(list(_terminal_log))


@app.route("/api/sensor", methods=["POST"])
def api_sensor():
    """
    Endpoint for the M5Stack IoT distance sensors described in the paper.
    When a sensor detects an item removed from a shelf, it POSTs:
        {"item": "milk", "event": "taken"}
    and we decrement the inventory.
    """
    data = request.get_json(force=True, silent=True) or {}
    item  = data.get("item")
    event = data.get("event", "taken")
    if item and event == "taken":
        ok = grocery_db.decrement_stock(item, 1)
        return jsonify(ok=ok)
    if item and event == "restocked":
        ok = grocery_db.restock(item, data.get("n", 1))
        return jsonify(ok=ok)
    return jsonify(ok=False, error="bad payload"), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, debug=False)
