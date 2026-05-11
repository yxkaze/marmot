"""
Domain models - dataclasses and enums.

This module contains all data structures used throughout marmot.
No I/O, no threads, pure data definitions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class AlertState(str, Enum):
    """Alert lifecycle states."""
    PENDING = "pending"
    FIRING = "firing"
    SILENCED = "silenced"
    ESCALATED = "escalated"
    RESOLVING = "resolving"
    RESOLVED = "resolved"


class Severity(str, Enum):
    """Standard severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStage(str, Enum):
    """Which mechanism triggered the alert."""
    THRESHOLD = "threshold"
    TIMEOUT = "timeout"
    HEARTBEAT = "heartbeat"
    MANUAL = "manual"


class RunStatus(str, Enum):
    """Execution status of a monitored job."""
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class NotificationStatus(str, Enum):
    """Delivery status of a notification."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class AggregateFn(str, Enum):
    """Supported aggregation functions for metric bucket."""
    AVG = "avg"
    MAX = "max"
    MIN = "min"
    SUM = "sum"
    COUNT = "count"
