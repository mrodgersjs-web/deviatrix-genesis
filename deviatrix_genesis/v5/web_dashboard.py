"""Interactive web dashboard — FastAPI + WebSocket for live telemetry.

Serves a real-time dashboard showing:
  * Live expedition results (z-score, band, verdict)
  * Convergence sparkline
  * Quality metrics
  * Run history trends

Usage::

    python -m deviatrix_genesis.v5.web_dashboard --port 8080

Or programmatically::

    from deviatrix_genesis.v5.web_dashboard import create_app
    app = create_app()
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from .run_history import RunHistory
from .telemetry import EventBus, get_bus

__all__ = ["create_app"]

_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>Deviatrix v5 Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'SF Mono', 'Fira Code', monospace; background: #0a0a0a; color: #e0e0e0; padding: 20px; }
  h1 { color: #00ff88; margin-bottom: 20px; font-size: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
  .card { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 16px; }
  .card h2 { color: #00aaff; font-size: 14px; margin-bottom: 12px; text-transform: uppercase; }
  .metric { font-size: 32px; font-weight: bold; color: #00ff88; }
  .metric-label { font-size: 12px; color: #888; margin-top: 4px; }
  .sparkline { font-size: 18px; letter-spacing: 2px; color: #00ff88; }
  table { width: 100%; border-collapse: collapse; }
  th, td { padding: 6px 8px; text-align: left; border-bottom: 1px solid #333; font-size: 13px; }
  th { color: #00aaff; }
  .z-positive { color: #00ff88; }
  .z-negative { color: #ff4444; }
  .status { padding: 2px 6px; border-radius: 3px; font-size: 11px; }
  .status-pass { background: #003300; color: #00ff88; }
  .status-fail { background: #330000; color: #ff4444; }
  #log { max-height: 300px; overflow-y: auto; font-size: 12px; }
  .log-entry { padding: 2px 0; border-bottom: 1px solid #222; }
</style>
</head>
<body>
<h1>DEVIATRIX GENESIS v5</h1>
<div class="grid">
  <div class="card">
    <h2>Expeditions</h2>
    <div class="metric" id="total-exp">0</div>
    <div class="metric-label">total completed</div>
  </div>
  <div class="card">
    <h2>Pass Rate</h2>
    <div class="metric" id="pass-rate">0%</div>
    <div class="metric-label">below 30σ wall</div>
  </div>
  <div class="card">
    <h2>Best Z</h2>
    <div class="metric" id="best-z">0.00</div>
    <div class="metric-label">highest certified z</div>
  </div>
  <div class="card">
    <h2>Z Trend</h2>
    <div class="sparkline" id="z-trend"></div>
    <div class="metric-label">median z per round</div>
  </div>
</div>
<div class="card" style="margin-top: 16px;">
  <h2>Recent Expeditions</h2>
  <table>
    <thead><tr><th>Diamond</th><th>Kind</th><th>Z-Score</th><th>Band</th><th>Pass A</th><th>Pass B</th><th>Pass C</th></tr></thead>
    <tbody id="expeditions"></tbody>
  </table>
</div>
<div class="card" style="margin-top: 16px;">
  <h2>Run History</h2>
  <table>
    <thead><tr><th>Run ID</th><th>Brief</th><th>Survivors</th><th>Best Z</th><th>Time</th></tr></thead>
    <tbody id="history"></tbody>
  </table>
</div>
<div class="card" style="margin-top: 16px;">
  <h2>Live Log</h2>
  <div id="log"></div>
</div>
<script>
const ws = new WebSocket(`ws://${location.host}/ws`);
const sparkChars = '▁▂▃▄▅▆▇█';
const expeditions = [];
const zValues = [];

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);

  if (msg.type === 'expedition_complete') {
    expeditions.unshift(msg.data);
    if (expeditions.length > 20) expeditions.pop();
    zValues.push(msg.data.z || 0);
    renderExpeditions();
    updateMetrics();
  } else if (msg.type === 'round_end') {
    renderSparkline();
  }

  const log = document.getElementById('log');
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.textContent = `[${msg.type}] ${JSON.stringify(msg.data || {}).slice(0, 100)}`;
  log.prepend(entry);
  if (log.children.length > 50) log.lastChild.remove();
};

function renderExpeditions() {
  const tbody = document.getElementById('expeditions');
  tbody.innerHTML = expeditions.map(ep => {
    const zClass = (ep.z || 0) >= 0 ? 'z-positive' : 'z-negative';
    return `<tr>
      <td>${ep.diamond || ''}</td>
      <td>${ep.kind || ''}</td>
      <td class="${zClass}">${(ep.z || 0).toFixed(2)}</td>
      <td>${ep.band || ''}</td>
      <td>${ep.pass_a || ''}</td>
      <td>${ep.pass_b || ''}</td>
      <td>${ep.pass_c || ''}</td>
    </tr>`;
  }).join('');
}

function updateMetrics() {
  document.getElementById('total-exp').textContent = expeditions.length;
  const passed = expeditions.filter(ep => Math.abs(ep.z || 0) < 30).length;
  const rate = expeditions.length ? (passed / expeditions.length * 100).toFixed(0) : 0;
  document.getElementById('pass-rate').textContent = rate + '%';
  const best = Math.max(...expeditions.map(ep => Math.abs(ep.z || 0)), 0);
  document.getElementById('best-z').textContent = best.toFixed(2);
}

function renderSparkline() {
  if (!zValues.length) return;
  const lo = Math.min(...zValues), hi = Math.max(...zValues);
  const span = hi - lo || 1;
  document.getElementById('z-trend').textContent = zValues.map(v =>
    sparkChars[Math.min(Math.floor((v - lo) / span * 7), 7)]
  ).join('');
}

// Load run history
fetch('/api/history').then(r => r.json()).then(runs => {
  const tbody = document.getElementById('history');
  tbody.innerHTML = runs.map(r => `<tr>
    <td>${r.run_id}</td>
    <td>${(r.brief || '').slice(0, 40)}</td>
    <td>${r.n_survivors}</td>
    <td>${r.best_z.toFixed(2)}</td>
    <td>${r.wall_clock_s.toFixed(1)}s</td>
  </tr>`).join('');
});
</script>
</body>
</html>"""


def create_app() -> Any:
    """Create the FastAPI dashboard app."""
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import HTMLResponse
    except ImportError:
        raise ImportError("pip install fastapi uvicorn for web dashboard")

    app = FastAPI(title="Deviatrix v5 Dashboard")
    bus = get_bus()
    connected_clients: set[WebSocket] = set()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _HTML_TEMPLATE

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        connected_clients.add(ws)
        try:
            while True:
                await ws.receive_text()  # keep alive
        except WebSocketDisconnect:
            connected_clients.discard(ws)

    @app.get("/api/history")
    async def api_history():
        history = RunHistory()
        runs = history.recent_runs(limit=20)
        return [
            {
                "run_id": r.run_id, "brief": r.brief,
                "n_survivors": r.n_survivors, "best_z": r.best_z,
                "wall_clock_s": r.wall_clock_s, "n_rounds": r.n_rounds,
            }
            for r in runs
        ]

    @app.get("/api/trends")
    async def api_trends():
        history = RunHistory()
        return history.trend_analysis()

    # Subscribe to bus events and broadcast to WebSocket clients
    async def broadcast(event_type: str, data: dict[str, Any]) -> None:
        msg = json.dumps({"type": event_type, "data": data})
        dead = set()
        for ws in connected_clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        connected_clients.difference_update(dead)

    def _on_bus_event(evt):
        loop = None
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return
        if loop and not loop.is_closed():
            loop.create_task(broadcast(evt.event_type, evt.payload))

    bus.subscribe(_on_bus_event)

    return app


def main() -> None:
    """Launch the web dashboard."""
    import argparse
    p = argparse.ArgumentParser(description="Deviatrix v5 web dashboard")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--host", default="127.0.0.1")
    args = p.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Install uvicorn: pip install uvicorn")
        return

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
