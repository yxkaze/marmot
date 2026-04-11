"""
Marmot — Lightweight Alert Framework for Python

A developer-friendly alert framework focused on simplicity.
Register rules, report metrics, and let Marmot handle the rest:
state machine, deduplication, silence windows, escalation, and
multi-channel notifications.

Quick start::

    import marmot

    marmot.configure("my_app.db")
    marmot.register_notifier("console", marmot.ConsoleNotifier())

    marmot.register_threshold_rule(marmot.ThresholdRule(
        name="cpu_usage",
        thresholds=[
            marmot.ThresholdLevel(value=80, severity="warning"),
            marmot.ThresholdLevel(value=95, severity="critical"),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    ))

    marmot.report("cpu_usage", 92.5, labels={"host": "prod-1"})
"""

# Models
from .models import (
    # Enums
    AlertState,
    Severity,
    AlertStage,
    RunStatus,
    NotificationStatus,
    AggregateFn,
    # Data classes
    Rule,
    ThresholdRule,
    ThresholdLevel,
    EscalationStep,
    AlertEvent,
    RunRecord,
    Notification,
    AggregateConfig,
    # Helpers
    utcnow,
    to_iso,
    from_iso,
    parse_duration,
    build_dedup_key,
    normalize_notify,
    json_dumps,
    json_loads,
)

# Bucket
from .bucket import MetricBucket

# Storage
from .storage import SQLiteStorage

# App
from .app import (
    MarmotApp,
    AlertStateMachine,
    configure,
    get_app,
    register_threshold_rule,
    register_rule,
    register_notifier,
    report,
    fire,
    ping,
    resolve,
    job,
    shutdown,
)

# Web
from .web import start_ui_server

# Notifiers
from .notifiers import (
    Notifier,
    ConsoleNotifier,
    WebhookNotifier,
    MarkdownWebhookNotifier,
    DingTalkNotifier,
    WeComNotifier,
    FeishuNotifier,
    EmailNotifier,
    PhoneNotifier,
)

__version__ = "0.1.0"
__all__ = [
    # Enums
    "AlertState",
    "Severity",
    "AlertStage",
    "RunStatus",
    "NotificationStatus",
    "AggregateFn",
    # Data classes
    "Rule",
    "ThresholdRule",
    "ThresholdLevel",
    "EscalationStep",
    "AlertEvent",
    "RunRecord",
    "Notification",
    "AggregateConfig",
    # Bucket
    "MetricBucket",
    # Storage
    "SQLiteStorage",
    # Core
    "MarmotApp",
    "AlertStateMachine",
    # Module-level API
    "configure",
    "get_app",
    "register_rule",
    "register_threshold_rule",
    "register_notifier",
    "report",
    "fire",
    "ping",
    "resolve",
    "job",
    "shutdown",
    # Notifiers
    "Notifier",
    "ConsoleNotifier",
    "WebhookNotifier",
    "MarkdownWebhookNotifier",
    "DingTalkNotifier",
    "WeComNotifier",
    "FeishuNotifier",
    "EmailNotifier",
    "PhoneNotifier",
    # UI
    "start_ui_server",
    # Helpers
    "utcnow",
    "to_iso",
    "from_iso",
    "parse_duration",
    "build_dedup_key",
]
