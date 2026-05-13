"""
Marmot — Lightweight Alert Framework for Python
"""
from .api import (
    configure,
    get_app,
    register_threshold_rule,
    register_notifier,
    report,
    shutdown,
    MarmotApp,
)
from .domain import (
    ThresholdRule,
    ThresholdLevel,
    Rule,
    AlertState,
    Severity,
)
from .notifiers import ConsoleNotifier

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "configure",
    "get_app",
    "register_threshold_rule",
    "register_notifier",
    "report",
    "shutdown",
    "MarmotApp",
    "ThresholdRule",
    "ThresholdLevel",
    "Rule",
    "AlertState",
    "Severity",
    "ConsoleNotifier",
]
