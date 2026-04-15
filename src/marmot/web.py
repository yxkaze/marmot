"""
Marmot Alert Framework — Web UI & API Server

A built-in web console for monitoring alerts, run history,
and notification logs.  Zero external dependencies — uses only
the Python standard library ``http.server``.

API Endpoints::

    GET  /                       → HTML dashboard
    GET  /api/alerts             → Active alerts
    GET  /api/alerts/:id         → Single alert detail
    GET  /api/history            → Resolved alert history
    GET  /api/runs               → Recent run records
    GET  /api/notifications      → Notification log
    GET  /api/rules              → Registered rules
    GET  /api/threshold-rules    → Registered threshold rules
"""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .app import MarmotApp


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Marmot Console</title>
  <style>
    :root {
      --bg: #f5efe7;
      --panel: rgba(255,255,255,0.88);
      --ink: #1f2933;
      --muted: #61707d;
      --accent: #a05a2c;
      --danger: #b42318;
      --ok: #067647;
      --warn: #b45309;
      --info: #1d4ed8;
      --line: rgba(160, 90, 44, 0.18);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(160,90,44,0.12), transparent 30%),
        linear-gradient(180deg, #fbf7f2, #efe2d3 60%, #e7d4c0);
      min-height: 100vh;
    }
    .wrap { max-width: 1200px; margin: 0 auto; padding: 28px 20px 48px; }
    header { display: flex; align-items: center; gap: 16px; margin-bottom: 8px; }
    h1 { font-size: 36px; font-weight: 800; letter-spacing: -0.02em; color: var(--ink); }
    h1 span { color: var(--accent); }
    .subtitle { color: var(--muted); font-size: 15px; margin-bottom: 24px; }
    .grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); margin-bottom: 24px; }
    .card {
      background: var(--panel);
      backdrop-filter: blur(8px);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px 18px;
      box-shadow: 0 4px 20px rgba(58,36,20,0.06);
      transition: transform 0.15s, box-shadow 0.15s;
    }
    .card:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(58,36,20,0.1); }
    .card .label { font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
    .card .value { font-size: 30px; font-weight: 800; margin-top: 4px; }
    .card .value.danger { color: var(--danger); }
    .card .value.ok { color: var(--ok); }
    .card .value.warn { color: var(--warn); }
    .panel {
      background: var(--panel);
      backdrop-filter: blur(8px);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px;
      margin-bottom: 20px;
      box-shadow: 0 4px 20px rgba(58,36,20,0.06);
      overflow: auto;
    }
    .panel h2 { font-size: 16px; font-weight: 700; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
    .panel h2 .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
    .panel h2 .dot.red { background: var(--danger); }
    .panel h2 .dot.green { background: var(--ok); }
    .panel h2 .dot.blue { background: var(--info); }
    .panel h2 .dot.orange { background: var(--warn); }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 10px 10px; border-bottom: 1px solid rgba(31,41,51,0.06); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
    tr:hover td { background: rgba(160,90,44,0.03); }
    .pill { border-radius: 999px; padding: 3px 10px; font-size: 11px; font-weight: 600; display: inline-block; letter-spacing: 0.02em; }
    .firing, .timeout, .missed, .fail, .failed { background: rgba(180,35,24,0.1); color: var(--danger); }
    .resolved, .ok, .success { background: rgba(6,118,71,0.1); color: var(--ok); }
    .silenced, .escalated, .running { background: rgba(160,90,44,0.12); color: var(--accent); }
    .pending, .resolving { background: rgba(29,78,216,0.08); color: var(--info); }
    .msg { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .empty { color: var(--muted); font-size: 14px; padding: 16px 0; text-align: center; }
    .refresh { float: right; font-size: 12px; color: var(--muted); cursor: pointer; }
    .refresh:hover { color: var(--accent); }
    @media (max-width: 720px) {
      h1 { font-size: 28px; }
      table { font-size: 12px; }
      .msg { max-width: 160px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1><span>Marmot</span></h1>
    </header>
    <p class="subtitle">Lightweight alert framework for Python — developer-friendly, zero-config monitoring.</p>
    <section class="grid" id="summary"></section>
    <section class="panel"><h2><span class="dot red"></span>Active Alerts <span class="refresh" onclick="load()">\u21bb refresh</span></h2><div id="active"></div></section>
    <section class="panel"><h2><span class="dot green"></span>Alert History</h2><div id="history"></div></section>
    <section class="panel"><h2><span class="dot blue"></span>Recent Runs</h2><div id="runs"></div></section>
    <section class="panel"><h2><span class="dot orange"></span>Notification Log</h2><div id="notifications"></div></section>
    <section class="panel"><h2>Rules</h2><div id="rules"></div></section>
  </div>
  <script>
    const pill = (v) => '<span class="pill ' + v + '">' + v + '</span>';
    const esc = (s) => s ? String(s).replace(/</g,'&lt;') : '-';
    const renderTable = (items, cols, empty) => {
      if (!items || !items.length) return '<p class="empty">' + empty + '</p>';
      const head = cols.map(c => '<th>' + c.label + '</th>').join('');
      const rows = items.map(item =>
        '<tr>' + cols.map(c => '<td>' + (typeof c.render === 'function' ? c.render(item) : esc(item[c.key])) + '</td>').join('') + '</tr>'
      ).join('');
      return '<table><thead><tr>' + head + '</tr></thead><tbody>' + rows + '</tbody></table>';
    };
    const dur = (ms) => ms != null ? (ms >= 1000 ? (ms/1000).toFixed(1) + 's' : Math.round(ms) + 'ms') : '-';
    async function load() {
      try {
        const [active, history, runs, notifs, rules] = await Promise.all([
          fetch('/api/alerts').then(r => r.json()),
          fetch('/api/history').then(r => r.json()),
          fetch('/api/runs').then(r => r.json()),
          fetch('/api/notifications').then(r => r.json()),
          fetch('/api/rules').then(r => r.json()),
        ]);
        const activeFiring = active.filter(a => a.state === 'firing' || a.state === 'escalated').length;
        const activeSilenced = active.filter(a => a.state === 'silenced').length;
        document.getElementById('summary').innerHTML = [
          ['Active', active.length, activeFiring > 0 ? 'danger' : 'ok'],
          ['Firing / Escalated', activeFiring, activeFiring > 0 ? 'danger' : 'ok'],
          ['Silenced', activeSilenced, 'warn'],
          ['Total Runs', runs.length, ''],
          ['Notifications', notifs.length, ''],
          ['Rules', rules.length, ''],
        ].map(([label, value, cls]) =>
          '<article class="card"><div class="label">' + label + '</div><div class="value ' + cls + '">' + value + '</div></article>'
        ).join('');
        document.getElementById('active').innerHTML = renderTable(active, [
          { label: 'Rule', key: 'rule_name' },
          { label: 'Severity', render: i => pill(i.severity) },
          { label: 'State', render: i => pill(i.state) },
          { label: 'Stage', key: 'stage' },
          { label: 'Message', render: i => '<span class="msg">' + esc(i.message) + '</span>' },
          { label: 'Hits', key: 'consecutive_hits' },
          { label: 'Updated', key: 'updated_at' },
        ], 'No active alerts.');
        document.getElementById('history').innerHTML = renderTable(history, [
          { label: 'Rule', key: 'rule_name' },
          { label: 'Severity', render: i => pill(i.severity) },
          { label: 'State', render: i => pill(i.state) },
          { label: 'Message', render: i => '<span class="msg">' + esc(i.message) + '</span>' },
          { label: 'Fired', key: 'fired_at' },
          { label: 'Resolved', render: i => i.resolved_at || '-' },
        ], 'No resolved alerts yet.');
        document.getElementById('runs').innerHTML = renderTable(runs, [
          { label: 'Rule', key: 'rule_name' },
          { label: 'Status', render: i => pill(i.status) },
          { label: 'Message', render: i => '<span class="msg">' + esc(i.message) + '</span>' },
          { label: 'Duration', render: i => dur(i.duration_ms) },
          { label: 'Started', key: 'started_at' },
        ], 'No runs yet.');
        document.getElementById('notifications').innerHTML = renderTable(notifs, [
          { label: 'Rule', key: 'rule_name' },
          { label: 'Notifier', key: 'notifier_name' },
          { label: 'Stage', render: i => pill(i.stage) },
          { label: 'Severity', render: i => pill(i.severity) },
          { label: 'State', render: i => pill(i.state) },
          { label: 'Time', key: 'sent_at' },
        ], 'No notifications yet.');
        document.getElementById('rules').innerHTML = renderTable(rules, [
          { label: 'Name', key: 'name' },
          { label: 'Type', key: 'type' },
          { label: 'Notify', render: i => (i.notify_targets || []).join(', ') || '-' },
        ], 'No rules registered.');
      } catch(e) { console.error(e); }
    }
    load();
    setInterval(load, 5000);
  </script>
</body>
</html>
"""


@dataclass(slots=True)
class UIServer:
    app: "MarmotApp"
    server: ThreadingHTTPServer
    thread: threading.Thread

    @property
    def url(self) -> str:
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


def start_ui_server(
    app: "MarmotApp", host: str = "0.0.0.0", port: int = 8765
) -> UIServer:
    """Start the built-in web console.

    Parameters
    ----------
    app : MarmotApp
    host : str
    port : int

    Returns
    -------
    UIServer
        Call ``.stop()`` to shut down.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)

            if parsed.path == "/":
                self._send_html(HTML)
                return

            # --- JSON APIs ---
            if parsed.path == "/api/alerts":
                payload = [item.to_dict() for item in app.storage.list_active_alerts()]
                self._send_json(payload)
                return

            if parsed.path.startswith("/api/alerts/"):
                try:
                    alert_id = int(parsed.path.rsplit("/", 1)[-1])
                except ValueError:
                    self.send_error(HTTPStatus.BAD_REQUEST, "invalid alert id")
                    return
                alert = app.storage.get_alert(alert_id)
                if alert is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "alert not found")
                    return
                payload = alert.to_dict()
                payload["notifications"] = app.storage.list_notifications(
                    alert_event_id=alert_id
                )
                self._send_json(payload)
                return

            if parsed.path == "/api/history":
                self._send_json(
                    [item.to_dict() for item in app.storage.list_alert_history()]
                )
                return

            if parsed.path == "/api/runs":
                self._send_json([item.to_dict() for item in app.storage.list_runs()])
                return

            if parsed.path == "/api/notifications":
                self._send_json(app.storage.list_notifications())
                return

            if parsed.path == "/api/rules":
                # Combine both rule types
                items = []
                for r in app.storage.list_rules():
                    items.append(
                        {
                            "name": r.name,
                            "type": "heartbeat",
                            "notify_targets": r.notify_targets,
                        }
                    )
                for r in app.storage.list_threshold_rules():
                    items.append(
                        {
                            "name": r.name,
                            "type": "threshold",
                            "notify_targets": r.notify_targets,
                        }
                    )
                self._send_json(items)
                return

            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: object) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(
        target=server.serve_forever, daemon=True, name="marmot-ui"
    )
    thread.start()
    return UIServer(app=app, server=server, thread=thread)
