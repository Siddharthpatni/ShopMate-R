# dashboard.py
# Live dashboard for ShopMate-R.
# Reads inventory from inventory.json and state from state.json.
# Refreshes every 2 seconds via JS polling.
#
# Run: python dashboard.py
# Open: http://localhost:5000

import json
from flask import Flask, jsonify, Response
from config import STATE_FILE, DASHBOARD_PORT
from inventory import Inventory

app = Flask(__name__)
inventory = Inventory()


def read_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"temi_busy": False, "temi_current_task": None, "queue": [], "log": []}


PAGE = """<!DOCTYPE html>
<html>
<head>
<title>ShopMate-R Dashboard</title>
<meta charset="utf-8">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,sans-serif; background:#111827; color:#e5e7eb; padding:24px; }
h1 { font-size:20px; margin-bottom:20px; color:#f9fafb; }
h1 span { color:#ef4444; }
h2 { font-size:13px; text-transform:uppercase; letter-spacing:1px; color:#9ca3af;
     margin-bottom:10px; padding-bottom:6px; border-bottom:1px solid #1f2937; }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:16px; }
.card { background:#1f2937; border-radius:8px; padding:16px; }
.full { grid-column:1/-1; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { text-align:left; padding:5px 8px; border-bottom:1px solid #374151; }
th { color:#6b7280; font-size:11px; text-transform:uppercase; }
.out { color:#ef4444; font-weight:600; }
.low { color:#f59e0b; }
.ok { color:#10b981; }
.badge { display:inline-block; padding:4px 10px; border-radius:4px; font-size:13px; font-weight:500; }
.badge-idle { background:#1f2937; border:1px solid #374151; color:#9ca3af; }
.badge-busy { background:#7f1d1d; border:1px solid #ef4444; color:#fca5a5; }
.queue-item { padding:8px 10px; background:#111827; border-radius:4px; margin-bottom:4px; font-size:13px; }
.log-entry { padding:3px 0; font-size:12px; color:#9ca3af; }
.ts { color:#4b5563; margin-right:6px; font-family:monospace; font-size:11px; }
#upd { font-size:11px; color:#4b5563; text-align:right; margin-top:12px; }
</style>
</head>
<body>
<h1><span>ShopMate-R</span> Dashboard</h1>
<div class="grid">
  <div class="card">
    <h2>Temi Status</h2>
    <div id="temi">Loading...</div>
  </div>
  <div class="card">
    <h2>Order Queue</h2>
    <div id="queue">Loading...</div>
  </div>
  <div class="card full">
    <h2>Inventory</h2>
    <table><thead><tr><th>Item</th><th>Area</th><th>Stock</th><th>Price</th></tr></thead>
    <tbody id="inv"><tr><td colspan="4">Loading...</td></tr></tbody></table>
  </div>
  <div class="card full">
    <h2>Action Log</h2>
    <div id="log" style="max-height:180px;overflow-y:auto;">—</div>
  </div>
</div>
<div id="upd"></div>
<script>
const A={fruits_vegetables:"A · Fruits",drinks_dairy:"B · Drinks",snacks_dry:"C · Dry Goods",checkout:"D · Checkout"};
async function r(){try{
const[inv,st]=await Promise.all([fetch("/api/inventory").then(r=>r.json()),fetch("/api/state").then(r=>r.json())]);
document.getElementById("inv").innerHTML=inv.map(i=>{
let c="ok",t=i.stock+" left";if(i.stock===0){c="out";t="OUT";}else if(i.stock<=3){c="low";t=i.stock+" (low)";}
return`<tr><td>${i.name}</td><td>${A[i.category]||i.category}</td><td class="${c}">${t}</td><td>€${i.price.toFixed(2)}</td></tr>`;
}).join("");
const td=document.getElementById("temi");
if(st.temi_busy&&st.temi_current_task){const k=st.temi_current_task;
td.innerHTML=`<span class="badge badge-busy">BUSY</span> Fetching <b>${k.item_id}</b> from ${A[k.area]||k.area} for customer ${k.customer_id}`;}
else{td.innerHTML=`<span class="badge badge-idle">IDLE</span> Waiting at entrance`;}
const qd=document.getElementById("queue");
if(st.queue&&st.queue.length>0){qd.innerHTML=st.queue.map((t,i)=>
`<div class="queue-item">#${i+1} ${t.item_id} → ${A[t.area]||t.area} (cust ${t.customer_id})</div>`).join("");}
else{qd.innerHTML=`<div class="queue-item" style="color:#6b7280">Empty</div>`;}
const ld=document.getElementById("log");
if(st.log&&st.log.length>0){ld.innerHTML=st.log.slice(-20).reverse().map(e=>
`<div class="log-entry"><span class="ts">${e.time||""}</span>${e.message}</div>`).join("");}
document.getElementById("upd").textContent="Updated "+new Date().toLocaleTimeString();
}catch(e){console.error(e);}}
setInterval(r,2000);r();
</script>
</body>
</html>"""


@app.route("/")
def index():
    return Response(PAGE, mimetype="text/html")


@app.route("/api/inventory")
def api_inventory():
    inventory.load()
    return jsonify(inventory.items)


@app.route("/api/state")
def api_state():
    return jsonify(read_state())


if __name__ == "__main__":
    print(f"Dashboard at http://localhost:{DASHBOARD_PORT}")
    app.run(port=DASHBOARD_PORT, debug=False)
