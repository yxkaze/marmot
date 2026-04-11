# Marmot (土拨鼠) — Lightweight Alert Framework for Python

[![PyPI version](https://img.shields.io/pypi/v/marmot.svg)](https://pypi.org/project/marmot/)
[![Python versions](https://img.shields.io/pypi/pyversions/marmot.svg)](https://pypi.org/project/marmot/)
[![License](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![CI](https://github.com/yxkaze/marmot/actions/workflows/ci.yml/badge.svg)](https://github.com/yxkaze/marmot/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/yxkaze/marmot/branch/main/graph/badge.svg)](https://codecov.io/gh/yxkaze/marmot)

A developer-friendly, zero-dependency alert framework focused on **simplicity** and **practicality**. Register rules, report metrics, and let Marmot handle the rest: state machine, deduplication, silence windows, escalation, and multi-channel notifications.

## Why Marmot?

| Feature | Description |
|---------|-------------|
| **Zero Dependencies** | Pure Python standard library + SQLite, no external deps |
| **State Machine** | Full alert lifecycle: PENDING → FIRING → RESOLVED |
| **Multi-channel** | DingTalk, Feishu, WeCom, Email, Webhook, Phone |
| **Deduplication** | Automatic dedup by rule_name + labels |
| **Silence Windows** | Suppress repeated alerts, avoid alert storms |
| **Escalation** | Auto-escalate to higher priority after timeout |
| **Job Monitoring** | Decorator for cron/async task tracking |
| **Heartbeat** | Liveness monitoring with auto-recovery |
| **Built-in Web UI** | Real-time dashboard at localhost:8765 |

## Installation

```bash
pip install marmot
```

## Quick Start

### 1. Initialize

```python
import marmot

# Initialize with SQLite persistence
marmot.configure("alerts.db")
```

### 2. Register Notification Channels

```python
# Console (for development)
marmot.register_notifier("console", marmot.ConsoleNotifier())

# DingTalk
marmot.register_notifier("ding", marmot.DingTalkNotifier(
    webhook_url="https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
    secret="YOUR_SECRET",  # Optional HMAC signing
))

# Feishu
marmot.register_notifier("feishu", marmot.FeishuNotifier(
    webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN",
    secret="YOUR_SECRET",
))

# Enterprise WeChat
marmot.register_notifier("wecom", marmot.WeComNotifier(
    webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY",
))

# Email (zero-dependency, callback mode)
marmot.register_notifier("email", marmot.EmailNotifier(
    send_fn=your_send_email_function,
    to=["oncall@example.com"],
))
```

### 3. Threshold Alerting

```python
# Register a threshold rule
marmot.register_threshold_rule(marmot.ThresholdRule(
    name="cpu_usage",
    thresholds=[
        marmot.ThresholdLevel(value=80, severity="warning"),
        marmot.ThresholdLevel(value=95, severity="critical"),
    ],
    consecutive_count=3,      # 3 consecutive hits to confirm
    silence_seconds=300,      # 5 min silence after firing
    notify_targets=["ding"],
))

# Report metrics (just this one line in your code)
marmot.report("cpu_usage", 92.5, labels={"host": "prod-1"})
```

### 4. Job Monitoring

```python
@marmot.job("data_pipeline", expected_interval="5m", timeout="10m", notify="ding")
def run_pipeline():
    process_data()
    # If this fails, auto-alert; if succeeds, auto-resolve
```

### 5. Heartbeat Monitoring

```python
# Register heartbeat rule
marmot.register_rule(marmot.Rule.from_inputs(
    name="worker_heartbeat",
    expected_interval="30s",
    timeout="2m",
    notify="ding",
))

# Call periodically from your worker
marmot.ping("worker_heartbeat", labels={"worker_id": "w-01"})
```

### 6. Manual Alerts

```python
# Fire an alert directly
marmot.fire(
    "payment_failure",
    "Payment gateway timeout — 5 consecutive failures",
    severity="critical",
    labels={"service": "payments"},
    notify_targets=["ding", "email"],
)

# Manually resolve
marmot.resolve("payment_failure", message="Gateway recovered")
```

## Alert State Machine

```
 report()         report()        silence expired      escalation timer
首次触发 ──► PENDING ──► FIRING ──────────────► FIRING ──────────────► ESCALATED
            (计数中)        │
                           │ report(normal) 连续N次
                           ▼
                        RESOLVING ──► RESOLVED
                         (确认中)       (已恢复)
```

## Metric Aggregation

Monitor aggregated metrics across multiple instances:

```python
marmot.register_threshold_rule(marmot.ThresholdRule(
    name="es_disk",
    thresholds=[marmot.ThresholdLevel(value=85, severity="warning")],
    aggregate=marmot.AggregateConfig(fn="avg", window=300),  # 5min avg
    notify_targets=["ding"],
))

# Each instance reports independently, framework aggregates
for cluster in clusters:
    marmot.report("es_disk", disk_usage, labels={"cluster": cluster.name})
```

Supported aggregation functions: `avg`, `max`, `min`, `sum`, `count`.

## Web Dashboard

```python
# Start built-in web server
ui = marmot.start_ui_server(host="0.0.0.0", port=8765)
# Visit http://localhost:8765

# Stop when done
ui.stop()
```

API endpoints: `/api/alerts`, `/api/history`, `/api/runs`, `/api/notifications`, `/api/rules`.

## Documentation

- [API Reference](docs/api-reference.md)
- [Examples](docs/examples.md)
- [PyPI Publishing Guide](docs/PYPI_PUBLISHING.md)

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest -v

# Run tests with coverage
pytest --cov=src/marmot --cov-report=html

# Code formatting
black src/ tests/
isort src/ tests/

# Type checking
mypy src/marmot
```

## License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
