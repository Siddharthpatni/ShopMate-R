"""
mock_dashboard.py — ShopMate-R live operations dashboard.

Runs a small Flask server that:
  • Renders a single-page dashboard at `/` (inventory, Temi status,
    Temi screen mirror, live terminal feed, low-stock alerts).
  • Accepts POSTs from the rest of the system:
        /api/state    — temi_api pushes robot state updates here
        /api/log      — main.py mirrors every stdout line here
        /api/sensor   — m5stack_sensor.py posts shelf-sensor events here
  • Exposes JSON for the page to poll:
        /api/snapshot — full current state + last N log lines
        /api/inventory — live inventory (reads grocery_db)

Run stand-alone:

    python mock_dashboard.py

or let main.py launch it for you.
"""

from __future__ import annotations
import time
from collections import deque
from threading import Lock

from flask import Flask, jsonify, request, render_template_string

import config
import grocery_db

app = Flask(__name__)

# -------------------------------------------------------------------------
# In-memory state — reset on each dashboard restart
# -------------------------------------------------------------------------
_STATE: dict = {
    "temi_status":      "idle",          # idle | navigating | fetching | picking | returning | delivered
    "temi_location":    config.TEMI_HOME,
    "temi_last_speech": "",
    "temi_screen":      None,            # {type: product|message|image, ...}
    "updated_at":       time.time(),
}
_LOG: deque = deque(maxlen=400)
_SENSOR_EVENTS: deque = deque(maxlen=100)
_LOCK = Lock()


# -------------------------------------------------------------------------
# API endpoints
# -------------------------------------------------------------------------

@app.route("/api/state", methods=["POST"])
def post_state():
    """temi_api._push_state posts here on every robot transition."""
    data = request.get_json(silent=True) or {}
    with _LOCK:
        _STATE.update(data)
        _STATE["updated_at"] = time.time()
    return jsonify({"ok": True})


@app.route("/api/log", methods=["POST"])
def post_log():
    """main.py mirrors every stdout line here via TeeWriter."""
    line = (request.get_json(silent=True) or {}).get("line", "")
    if line.strip():
        with _LOCK:
            _LOG.append({"t": time.time(), "line": line})
    return jsonify({"ok": True})


@app.route("/api/sensor", methods=["POST"])
def post_sensor():
    """M5Stack shelf sensors POST here when a customer takes / restocks
    an item. Supports either JSON body or querystring. Example JSON:

        {"item": "milk", "event": "taken", "count": 1}
    """
    body = request.get_json(silent=True) or {}
    item  = body.get("item")  or request.args.get("item", "").strip()
    event = (body.get("event") or request.args.get("event", "taken")).strip().lower()
    count = int(body.get("count") or request.args.get("count", 1))

    if not item:
        return jsonify({"ok": False, "error": "missing item"}), 400

    rec = grocery_db.lookup_item(item)
    if rec is None:
        return jsonify({"ok": False, "error": f"unknown item '{item}'"}), 404

    if event == "taken":
        grocery_db.decrement_stock(rec["key"], count)
    elif event in ("restocked", "restock", "added"):
        grocery_db.restock(rec["key"], count)
    else:
        return jsonify({"ok": False, "error": f"unknown event '{event}'"}), 400

    with _LOCK:
        _SENSOR_EVENTS.append({
            "t": time.time(),
            "item": rec["key"],
            "event": event,
            "count": count,
        })
        _LOG.append({
            "t": time.time(),
            "line": f"[sensor] {event.upper()} {count}× {rec['name']}",
        })

    return jsonify({
        "ok": True,
        "item": rec["key"],
        "new_stock": grocery_db.lookup_item(rec["key"])["stock"],
    })


@app.route("/api/snapshot")
def snapshot():
    """Everything the SPA needs in one poll."""
    with _LOCK:
        return jsonify({
            "state":  dict(_STATE),
            "log":    list(_LOG)[-100:],
            "events": list(_SENSOR_EVENTS)[-20:],
        })


@app.route("/api/inventory")
def inventory():
    items = grocery_db.get_all_items()
    low   = grocery_db.get_low_stock(threshold=5)
    return jsonify({
        "items":      items,
        "low_stock":  [x["key"] for x in low],
        "categories": grocery_db.get_categories(),
    })


# -------------------------------------------------------------------------
# Dashboard page
# -------------------------------------------------------------------------

_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>ShopMate-R Dashboard</title>
<style>
  *,*::before,*::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Roboto','Segoe UI',Arial,sans-serif;
    background: linear-gradient(160deg,#1A237E 0%,#311B92 50%,#4A148C 100%);
    color: #E7E0EC; min-height: 100vh; padding: 20px;
  }
  h1 { font-size: 24px; font-weight: 700; letter-spacing: -0.4px; }
  h2 { font-size: 13px; font-weight: 700; letter-spacing: 1.4px;
       text-transform: uppercase; color: #D0BCFF; margin-bottom: 10px; }

  .top { display: flex; align-items: center; justify-content: space-between;
         margin-bottom: 20px; background: rgba(255,255,255,0.06);
         border: 1px solid rgba(255,255,255,0.1); border-radius: 16px;
         padding: 14px 20px; backdrop-filter: blur(8px); }
  .pill { padding: 6px 14px; border-radius: 999px; font-size: 12px;
          font-weight: 700; letter-spacing: 0.6px; }
  .pill.ok  { background: #064E3B; color: #6EE7B7; }

  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

  .card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 20px; padding: 18px 20px;
    backdrop-filter: blur(10px);
  }

  .status-row { display: flex; gap: 10px; flex-wrap: wrap;
                margin-bottom: 12px; }
  .status { padding: 8px 14px; border-radius: 12px; font-size: 13px;
            font-weight: 600; background: rgba(255,255,255,0.08); }
  .status b { color: #FFD54F; font-weight: 700; }

  .inv { width: 100%; border-collapse: collapse; font-size: 13px; }
  .inv th, .inv td { text-align: left; padding: 8px 6px;
                     border-bottom: 1px solid rgba(255,255,255,0.08); }
  .inv th { color: #CFBCFF; font-weight: 700; text-transform: uppercase;
            font-size: 11px; letter-spacing: 0.8px; }
  .inv td.num { text-align: right; font-variant-numeric: tabular-nums; }
  .chip { display: inline-block; padding: 2px 10px; border-radius: 999px;
          font-size: 11px; font-weight: 700; }
  .chip.ok   { background: #064E3B; color: #6EE7B7; }
  .chip.low  { background: #713F12; color: #FCD34D; }
  .chip.out  { background: #7F1D1D; color: #FCA5A5; }

  pre.log {
    background: #0F0A1F; color: #D4D4D8; font-family: 'JetBrains Mono',
    Consolas, monospace; font-size: 12px; border-radius: 12px;
    padding: 14px; max-height: 300px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-word;
    border: 1px solid rgba(255,255,255,0.08);
  }

  .temi-screen {
    min-height: 140px; border-radius: 16px; padding: 18px;
    background: linear-gradient(135deg,#1A237E 0%,#4A148C 100%);
    border: 1px solid rgba(255,255,255,0.15);
    display: flex; align-items: center; justify-content: center;
    text-align: center; color: #FFFFFF;
  }
  .temi-screen .name { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
  .temi-screen .price { font-size: 18px; color: #FFD54F; }
  .temi-screen .msg { font-size: 18px; font-weight: 600; color: #E1BEE7; }
</style></head>
<body>
<div class="top">
  <div>
    <h1>🛒 ShopMate-R Operations Dashboard</h1>
    <div style="font-size:12px; color:#B39DDB; margin-top:4px; letter-spacing:0.6px;">
      Pepper &amp; Temi — multi-robot grocery assistant
    </div>
  </div>
  <div class="pill ok" id="heartbeat">● Live</div>
</div>

<div class="grid">

  <div class="card" style="grid-column: 1 / -1;">
    <h2>Temi status</h2>
    <div class="status-row" id="status-row"></div>
    <div class="temi-screen" id="temi-screen">
      <div class="msg">Waiting for Temi…</div>
    </div>
  </div>

  <div class="card">
    <h2>Inventory</h2>
    <table class="inv" id="inv">
      <thead><tr><th>Item</th><th>Aisle</th><th class="num">Price</th>
                 <th class="num">Stock</th><th></th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="card">
    <h2>Live log</h2>
    <pre class="log" id="log">(waiting for events…)</pre>
  </div>

</div>

<script>
function statusChip(s) {
  const map = {
    idle:       ['#334155','#94A3B8'],
    navigating: ['#1E3A8A','#93C5FD'],
    fetching:   ['#713F12','#FCD34D'],
    picking:    ['#14532D','#86EFAC'],
    returning:  ['#581C87','#E9D5FF'],
    delivered:  ['#064E3B','#6EE7B7'],
    arrived:    ['#134E4A','#99F6E4'],
  };
  const [bg,fg] = map[s] || ['#334155','#94A3B8'];
  return `<span class="chip" style="background:${bg};color:${fg}">${s}</span>`;
}

function stockChip(n){
  if (n <= 0)  return `<span class="chip out">out</span>`;
  if (n <= 5)  return `<span class="chip low">low (${n})</span>`;
  return             `<span class="chip ok">${n}</span>`;
}

async function refresh() {
  try {
    const [snap, inv] = await Promise.all([
      fetch('/api/snapshot').then(r=>r.json()),
      fetch('/api/inventory').then(r=>r.json()),
    ]);
    // ---- status ----
    const st = snap.state || {};
    document.getElementById('status-row').innerHTML =
      `<div class="status">Status ${statusChip(st.temi_status||'idle')}</div>
       <div class="status">Location <b>${(st.temi_location||'—').replace(/_/g,' ')}</b></div>
       <div class="status">Last line: ${
          (st.temi_last_speech||'—').replace(/</g,'&lt;').slice(0,60)}</div>`;
    // ---- temi screen mirror ----
    const scr = st.temi_screen;
    const mount = document.getElementById('temi-screen');
    if (!scr) mount.innerHTML = '<div class="msg">Screen idle</div>';
    else if (scr.type === 'product')
      mount.innerHTML = `<div>
         <div class="name">${scr.name||''}</div>
         <div class="price">EUR ${(scr.price||0).toFixed(2)}</div>
         <div style="font-size:13px;margin-top:6px;opacity:0.8">
           ${(scr.aisle||'').replace(/_/g,' ')}</div></div>`;
    else if (scr.type === 'message')
      mount.innerHTML = `<div class="msg">${scr.text||''}</div>`;
    else mount.innerHTML = `<div class="msg">${JSON.stringify(scr)}</div>`;

    // ---- inventory ----
    const rows = (inv.items||[]).map(it => `
      <tr>
        <td>${it.name}</td>
        <td>${(it.aisle||'').replace(/_/g,' ')}</td>
        <td class="num">${(it.price||0).toFixed(2)}</td>
        <td class="num">${it.stock}</td>
        <td>${stockChip(it.stock)}</td>
      </tr>`).join('');
    document.querySelector('#inv tbody').innerHTML = rows;

    // ---- log ----
    const lg = (snap.log||[]).map(l=>l.line).join('\n') || '(waiting…)';
    const pre = document.getElementById('log');
    pre.textContent = lg;
    pre.scrollTop = pre.scrollHeight;
  } catch (e) {
    document.getElementById('heartbeat').textContent = '⚠ offline';
    document.getElementById('heartbeat').style.background = '#7F1D1D';
    document.getElementById('heartbeat').style.color = '#FCA5A5';
  }
}
refresh();
setInterval(refresh, 1500);
</script>
</body></html>
"""


@app.route("/")
def index():
    return render_template_string(_PAGE)


def main():
    print(f"📊 Dashboard running on {config.DASHBOARD_URL}")
    # Flask's dev server is plenty for a single-machine demo.
    app.run(host="127.0.0.1", port=config.DASHBOARD_PORT, debug=False,
            use_reloader=False)


if __name__ == "__main__":
    main()
