# Marmot MVP Units 4-7 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Units 4-7 to reach MVP milestone M1 (a usable alert framework with in-memory storage, threshold rules, and console notifications).

**Architecture:** Layer-by-layer implementation from Storage (L2) → Runtime (L3) → Evaluator (L1) → Dispatcher + API (L4). Each unit builds on the previous, maintaining "runnable + testable" state after each commit.

**Tech Stack:** Python 3.10+, zero runtime dependencies, pytest for testing, dataclasses with slots, typing.Protocol

---

## Unit 4: Storage Protocol + Memory Implementation

**Purpose:** Define storage abstraction and provide in-memory implementation for testing and early development.

### Task 1: Create Storage Protocol

**Files:**
- Create: `src/marmot/storage/__init__.py`
- Create: `src/marmot/storage/base.py`
- Create: `tests/test_storage_base.py`

- [ ] **Step 1: Create storage package**

```python
# src/marmot/storage/__init__.py
"""
存储层。

提供 Storage Protocol 和多种实现。
"""
from .base import Storage

__all__ = ["Storage"]
```

- [ ] **Step 2: Write the failing test for Storage Protocol**

Create `tests/test_storage_base.py`:

```python
"""
测试 Storage Protocol 定义。
"""
import pytest
from marmot.storage.base import Storage


def test_storage_is_protocol():
    """Storage 应该是一个 Protocol。"""
    from typing import Protocol
    assert issubclass(Storage, Protocol)


def test_storage_has_required_methods():
    """Storage 应该有必需的方法签名。"""
    # 这是一个编译时检查，运行时只需确认 Protocol 存在
    assert hasattr(Storage, 'get_or_create_alert_event')
    assert hasattr(Storage, 'update_alert_event')
    assert hasattr(Storage, 'list_active_alerts')
    assert hasattr(Storage, 'list_alert_history')
    assert hasattr(Storage, 'create_run_record')
    assert hasattr(Storage, 'list_recent_runs')
    assert hasattr(Storage, 'create_notification')
    assert hasattr(Storage, 'list_notifications')
```

- [ ] **Step 3: Implement Storage Protocol**

Create `src/marmot/storage/base.py`:

```python
"""
存储层 Protocol 定义。
"""
from typing import Protocol, Any
from datetime import datetime


class Storage(Protocol):
    """存储抽象 Protocol。
    
    定义了告警事件、运行记录、通知记录的 CRUD 操作。
    """
    
    # AlertEvent CRUD
    def get_or_create_alert_event(
        self,
        rule_name: str,
        dedup_key: str,
        **defaults
    ) -> tuple[Any, bool]:
        """获取或创建告警事件。
        
        Args:
            rule_name: 规则名称
            dedup_key: 去重键
            **defaults: 如果创建，使用的默认值
            
        Returns:
            (event, created): 事件对象和是否新创建
        """
        ...
    
    def update_alert_event(self, event_id: int, **updates) -> None:
        """更新告警事件。
        
        Args:
            event_id: 事件 ID
            **updates: 要更新的字段
        """
        ...
    
    def list_active_alerts(self, rule_name: str | None = None) -> list[Any]:
        """列出活跃告警。
        
        Args:
            rule_name: 可选，过滤规则名称
            
        Returns:
            活跃告警列表（非 RESOLVED 状态）
        """
        ...
    
    def list_alert_history(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[Any]:
        """列出告警历史。
        
        Args:
            rule_name: 可选，过滤规则名称
            limit: 限制数量
            
        Returns:
            告警历史列表（按时间倒序）
        """
        ...
    
    def get_alert_event(self, event_id: int) -> Any | None:
        """获取单个告警事件。
        
        Args:
            event_id: 事件 ID
            
        Returns:
            事件对象或 None
        """
        ...
    
    # RunRecord CRUD
    def create_run_record(
        self,
        rule_name: str,
        status: str,
        message: str = "",
        error: str | None = None,
        labels: dict | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> int:
        """创建运行记录。
        
        Returns:
            记录 ID
        """
        ...
    
    def list_recent_runs(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[Any]:
        """列出最近运行记录。
        
        Args:
            rule_name: 可选，过滤规则名称
            limit: 限制数量
            
        Returns:
            运行记录列表（按时间倒序）
        """
        ...
    
    # Notification CRUD
    def create_notification(
        self,
        alert_event_id: int,
        rule_name: str,
        dedup_key: str,
        status: str,
        state: str | None = None,
        message: str = "",
        severity: str | None = None,
        labels: dict | None = None,
        stage: str | None = None,
        notifier_name: str = "",
        sent_at: datetime | None = None,
    ) -> int:
        """创建通知记录。
        
        Returns:
            记录 ID
        """
        ...
    
    def list_notifications(
        self,
        alert_event_id: int | None = None,
        limit: int = 100
    ) -> list[Any]:
        """列出通知记录。
        
        Args:
            alert_event_id: 可选，过滤告警事件 ID
            limit: 限制数量
            
        Returns:
            通知记录列表（按时间倒序）
        """
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_base.py -v`

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/marmot/storage/ tests/test_storage_base.py
git commit -m "feat: Unit 4.1 - Storage Protocol 定义"
```

---

### Task 2: Implement In-Memory Storage

**Files:**
- Create: `src/marmot/storage/memory.py`
- Create: `tests/test_storage_memory.py`

- [ ] **Step 1: Write the failing test for memory storage**

Create `tests/test_storage_memory.py`:

```python
"""
测试内存存储实现。
"""
import pytest
from datetime import datetime
from marmot.storage.memory import MemoryStorage
from marmot.domain.models.events import AlertEvent
from marmot.domain.models.enums import AlertState, Severity


def test_create_alert_event():
    """应该能创建告警事件。"""
    storage = MemoryStorage()
    event, created = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
        severity=Severity.WARNING.value,
    )
    
    assert created is True
    assert event.rule_name == "test_rule"
    assert event.dedup_key == "test_key"
    assert event.state == AlertState.PENDING.value


def test_get_existing_alert_event():
    """应该能获取已存在的事件。"""
    storage = MemoryStorage()
    event1, created1 = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
    )
    
    event2, created2 = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.FIRING.value,  # 这个值会被忽略
    )
    
    assert created1 is True
    assert created2 is False
    assert event1.id == event2.id


def test_update_alert_event():
    """应该能更新告警事件。"""
    storage = MemoryStorage()
    event, _ = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
    )
    
    storage.update_alert_event(event.id, state=AlertState.FIRING.value)
    
    updated = storage.get_alert_event(event.id)
    assert updated.state == AlertState.FIRING.value


def test_list_active_alerts():
    """应该能列出活跃告警。"""
    storage = MemoryStorage()
    
    # 创建活跃告警
    storage.get_or_create_alert_event(
        rule_name="rule1",
        dedup_key="key1",
        state=AlertState.FIRING.value,
    )
    storage.get_or_create_alert_event(
        rule_name="rule2",
        dedup_key="key2",
        state=AlertState.PENDING.value,
    )
    
    # 创建已恢复告警
    event3, _ = storage.get_or_create_alert_event(
        rule_name="rule3",
        dedup_key="key3",
        state=AlertState.RESOLVED.value,
    )
    
    active = storage.list_active_alerts()
    assert len(active) == 2
    
    active_rule1 = storage.list_active_alerts(rule_name="rule1")
    assert len(active_rule1) == 1


def test_create_run_record():
    """应该能创建运行记录。"""
    storage = MemoryStorage()
    now = datetime.utcnow()
    
    record_id = storage.create_run_record(
        rule_name="test_job",
        status="success",
        message="Job completed",
        started_at=now,
        finished_at=now,
    )
    
    assert record_id == 1
    
    records = storage.list_recent_runs()
    assert len(records) == 1
    assert records[0].rule_name == "test_job"


def test_create_notification():
    """应该能创建通知记录。"""
    storage = MemoryStorage()
    event, _ = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.FIRING.value,
    )
    
    now = datetime.utcnow()
    notification_id = storage.create_notification(
        alert_event_id=event.id,
        rule_name="test_rule",
        dedup_key="test_key",
        status="sent",
        state=AlertState.FIRING.value,
        notifier_name="console",
        sent_at=now,
    )
    
    assert notification_id == 1
    
    notifications = storage.list_notifications(alert_event_id=event.id)
    assert len(notifications) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_memory.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'marmot.storage.memory'"

- [ ] **Step 3: Implement MemoryStorage**

Create `src/marmot/storage/memory.py`:

```python
"""
内存存储实现。

用于测试和早期开发，不持久化。
"""
from datetime import datetime
from threading import RLock
from typing import Any
from dataclasses import asdict

from ..domain.models.events import AlertEvent, RunRecord, Notification


class MemoryStorage:
    """内存存储实现（线程安全）。"""
    
    def __init__(self):
        self._lock = RLock()
        self._alert_events: dict[int, AlertEvent] = {}
        self._alert_events_by_key: dict[str, int] = {}  # dedup_key -> id
        self._run_records: list[RunRecord] = []
        self._notifications: list[Notification] = []
        self._next_id = 1
    
    def _get_next_id(self) -> int:
        """获取下一个 ID。"""
        with self._lock:
            id = self._next_id
            self._next_id += 1
            return id
    
    def get_or_create_alert_event(
        self,
        rule_name: str,
        dedup_key: str,
        **defaults
    ) -> tuple[AlertEvent, bool]:
        """获取或创建告警事件。"""
        with self._lock:
            # 查找已存在的事件
            if dedup_key in self._alert_events_by_key:
                event_id = self._alert_events_by_key[dedup_key]
                return self._alert_events[event_id], False
            
            # 创建新事件
            event_id = self._get_next_id()
            now = datetime.utcnow()
            
            event = AlertEvent(
                id=event_id,
                rule_name=rule_name,
                dedup_key=dedup_key,
                state=defaults.get('state', 'pending'),
                severity=defaults.get('severity'),
                stage=defaults.get('stage'),
                message=defaults.get('message', ''),
                labels=defaults.get('labels', {}),
                current_value=defaults.get('current_value'),
                consecutive_hits=defaults.get('consecutive_hits', 0),
                consecutive_misses=defaults.get('consecutive_misses', 0),
                fired_at=defaults.get('fired_at', now),
                resolved_at=defaults.get('resolved_at'),
                silenced_until=defaults.get('silenced_until'),
                escalated_at=defaults.get('escalated_at'),
                escalation_level=defaults.get('escalation_level', 0),
            )
            
            self._alert_events[event_id] = event
            self._alert_events_by_key[dedup_key] = event_id
            
            return event, True
    
    def update_alert_event(self, event_id: int, **updates) -> None:
        """更新告警事件。"""
        with self._lock:
            if event_id not in self._alert_events:
                raise ValueError(f"Alert event {event_id} not found")
            
            event = self._alert_events[event_id]
            
            # 创建更新后的事件
            updated_data = asdict(event)
            updated_data.update(updates)
            
            self._alert_events[event_id] = AlertEvent(**updated_data)
    
    def get_alert_event(self, event_id: int) -> AlertEvent | None:
        """获取单个告警事件。"""
        with self._lock:
            return self._alert_events.get(event_id)
    
    def list_active_alerts(self, rule_name: str | None = None) -> list[AlertEvent]:
        """列出活跃告警。"""
        with self._lock:
            events = list(self._alert_events.values())
            
            # 过滤活跃状态
            from ..domain.models.enums import AlertState
            active_states = {
                AlertState.PENDING.value,
                AlertState.FIRING.value,
                AlertState.SILENCED.value,
                AlertState.ESCALATED.value,
                AlertState.RESOLVING.value,
            }
            events = [e for e in events if e.state in active_states]
            
            # 过滤规则名称
            if rule_name:
                events = [e for e in events if e.rule_name == rule_name]
            
            # 按时间倒序
            events.sort(key=lambda e: e.fired_at, reverse=True)
            return events
    
    def list_alert_history(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[AlertEvent]:
        """列出告警历史。"""
        with self._lock:
            events = list(self._alert_events.values())
            
            # 过滤规则名称
            if rule_name:
                events = [e for e in events if e.rule_name == rule_name]
            
            # 按时间倒序
            events.sort(key=lambda e: e.fired_at, reverse=True)
            
            return events[:limit]
    
    def create_run_record(
        self,
        rule_name: str,
        status: str,
        message: str = "",
        error: str | None = None,
        labels: dict | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> int:
        """创建运行记录。"""
        with self._lock:
            record_id = self._get_next_id()
            
            record = RunRecord(
                id=record_id,
                rule_name=rule_name,
                status=status,
                message=message,
                error=error,
                labels=labels or {},
                started_at=started_at or datetime.utcnow(),
                finished_at=finished_at,
            )
            
            self._run_records.append(record)
            return record_id
    
    def list_recent_runs(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[RunRecord]:
        """列出最近运行记录。"""
        with self._lock:
            records = self._run_records.copy()
            
            # 过滤规则名称
            if rule_name:
                records = [r for r in records if r.rule_name == rule_name]
            
            # 按时间倒序
            records.sort(key=lambda r: r.started_at, reverse=True)
            
            return records[:limit]
    
    def create_notification(
        self,
        alert_event_id: int,
        rule_name: str,
        dedup_key: str,
        status: str,
        state: str | None = None,
        message: str = "",
        severity: str | None = None,
        labels: dict | None = None,
        stage: str | None = None,
        notifier_name: str = "",
        sent_at: datetime | None = None,
    ) -> int:
        """创建通知记录。"""
        with self._lock:
            notification_id = self._get_next_id()
            
            notification = Notification(
                id=notification_id,
                alert_event_id=alert_event_id,
                rule_name=rule_name,
                dedup_key=dedup_key,
                status=status,
                state=state,
                message=message,
                severity=severity,
                labels=labels or {},
                stage=stage,
                notifier_name=notifier_name,
                sent_at=sent_at or datetime.utcnow(),
            )
            
            self._notifications.append(notification)
            return notification_id
    
    def list_notifications(
        self,
        alert_event_id: int | None = None,
        limit: int = 100
    ) -> list[Notification]:
        """列出通知记录。"""
        with self._lock:
            notifications = self._notifications.copy()
            
            # 过滤告警事件 ID
            if alert_event_id:
                notifications = [n for n in notifications if n.alert_event_id == alert_event_id]
            
            # 按时间倒序
            notifications.sort(key=lambda n: n.sent_at, reverse=True)
            
            return notifications[:limit]
```

- [ ] **Step 4: Update storage package to export MemoryStorage**

Update `src/marmot/storage/__init__.py`:

```python
"""
存储层。

提供 Storage Protocol 和多种实现。
"""
from .base import Storage
from .memory import MemoryStorage

__all__ = ["Storage", "MemoryStorage"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_storage_memory.py -v`

Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add src/marmot/storage/ tests/test_storage_memory.py
git commit -m "feat: Unit 4.2 - 内存存储实现"
```

---

## Unit 5: Clock + Registry

**Purpose:** Provide time abstraction for testing and rule/notifier registration.

### Task 3: Implement Clock

**Files:**
- Create: `src/marmot/runtime/__init__.py`
- Create: `src/marmot/runtime/clock.py`
- Create: `tests/test_clock.py`

- [ ] **Step 1: Create runtime package**

Create `src/marmot/runtime/__init__.py`:

```python
"""
运行时组件。

提供 Clock、Registry、Dispatcher 等有状态组件。
"""
from .clock import Clock, SystemClock

__all__ = ["Clock", "SystemClock"]
```

- [ ] **Step 2: Write the failing test for Clock**

Create `tests/test_clock.py`:

```python
"""
测试 Clock 抽象。
"""
import pytest
from datetime import datetime
from marmot.runtime.clock import Clock, SystemClock


def test_clock_is_protocol():
    """Clock 应该是一个 Protocol。"""
    from typing import Protocol
    assert issubclass(Clock, Protocol)


def test_system_clock_now():
    """SystemClock.now() 应该返回当前时间。"""
    clock = SystemClock()
    now = clock.now()
    
    assert isinstance(now, datetime)
    # 应该接近当前时间
    assert (datetime.utcnow() - now).total_seconds() < 1.0


def test_system_clock_monotonic():
    """SystemClock.monotonic() 应该返回单调递增的时间。"""
    clock = SystemClock()
    t1 = clock.monotonic()
    t2 = clock.monotonic()
    
    assert isinstance(t1, float)
    assert t2 >= t1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_clock.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'marmot.runtime.clock'"

- [ ] **Step 4: Implement Clock Protocol and SystemClock**

Create `src/marmot/runtime/clock.py`:

```python
"""
时间抽象。

提供 Clock Protocol 和系统实现，支持测试注入。
"""
import time
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """时间抽象 Protocol。
    
    提供两个时间方法：当前时间和单调时间。
    """
    
    def now(self) -> datetime:
        """获取当前 UTC 时间。"""
        ...
    
    def monotonic(self) -> float:
        """获取单调时间（秒）。
        
        单调时间保证不会倒退，适合用于计时和超时判断。
        """
        ...


class SystemClock:
    """系统时钟实现。"""
    
    def now(self) -> datetime:
        """获取当前 UTC 时间。"""
        return datetime.utcnow()
    
    def monotonic(self) -> float:
        """获取单调时间（秒）。"""
        return time.monotonic()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_clock.py -v`

Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add src/marmot/runtime/ tests/test_clock.py
git commit -m "feat: Unit 5.1 - Clock Protocol 和 SystemClock"
```

---

### Task 4: Implement Registry

**Files:**
- Create: `src/marmot/runtime/registry.py`
- Create: `tests/test_registry.py`

- [ ] **Step 1: Write the failing test for Registry**

Create `tests/test_registry.py`:

```python
"""
测试 Registry。
"""
import pytest
from marmot.runtime.registry import RuleRegistry, NotifierRegistry
from marmot.domain.models.rules import ThresholdRule, ThresholdLevel
from marmot.domain.models.enums import Severity


def test_rule_registry_register_and_get():
    """应该能注册和获取规则。"""
    registry = RuleRegistry()
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    registry.register_threshold_rule(rule)
    
    retrieved = registry.get_threshold_rule("cpu_high")
    assert retrieved.name == "cpu_high"


def test_rule_registry_get_nonexistent():
    """获取不存在的规则应该返回 None。"""
    registry = RuleRegistry()
    assert registry.get_threshold_rule("nonexistent") is None


def test_rule_registry_list():
    """应该能列出所有规则。"""
    registry = RuleRegistry()
    rule1 = ThresholdRule(
        name="rule1",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    rule2 = ThresholdRule(
        name="rule2",
        thresholds=[ThresholdLevel(value=90.0, severity=Severity.ERROR)],
        consecutive_count=2,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    registry.register_threshold_rule(rule1)
    registry.register_threshold_rule(rule2)
    
    rules = registry.list_threshold_rules()
    assert len(rules) == 2


def test_notifier_registry_register_and_get():
    """应该能注册和获取通知器。"""
    registry = NotifierRegistry()
    
    class MockNotifier:
        def send(self, notification):
            return True
    
    notifier = MockNotifier()
    registry.register("console", notifier)
    
    retrieved = registry.get("console")
    assert retrieved is notifier


def test_notifier_registry_get_nonexistent():
    """获取不存在的通知器应该返回 None。"""
    registry = NotifierRegistry()
    assert registry.get("nonexistent") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registry.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'marmot.runtime.registry'"

- [ ] **Step 3: Implement Registry**

Create `src/marmot/runtime/registry.py`:

```python
"""
注册表。

提供规则和通知器的注册、查询功能。
"""
from typing import Any
from threading import RLock

from ..domain.models.rules import ThresholdRule, Rule


class RuleRegistry:
    """规则注册表（线程安全）。"""
    
    def __init__(self):
        self._lock = RLock()
        self._threshold_rules: dict[str, ThresholdRule] = {}
        self._rules: dict[str, Rule] = {}
    
    def register_threshold_rule(self, rule: ThresholdRule) -> None:
        """注册阈值规则。"""
        with self._lock:
            self._threshold_rules[rule.name] = rule
    
    def get_threshold_rule(self, name: str) -> ThresholdRule | None:
        """获取阈值规则。"""
        with self._lock:
            return self._threshold_rules.get(name)
    
    def list_threshold_rules(self) -> list[ThresholdRule]:
        """列出所有阈值规则。"""
        with self._lock:
            return list(self._threshold_rules.values())
    
    def register_rule(self, rule: Rule) -> None:
        """注册通用规则（心跳/Job）。"""
        with self._lock:
            self._rules[rule.name] = rule
    
    def get_rule(self, name: str) -> Rule | None:
        """获取通用规则。"""
        with self._lock:
            return self._rules.get(name)
    
    def list_rules(self) -> list[Rule]:
        """列出所有通用规则。"""
        with self._lock:
            return list(self._rules.values())


class NotifierRegistry:
    """通知器注册表（线程安全）。"""
    
    def __init__(self):
        self._lock = RLock()
        self._notifiers: dict[str, Any] = {}
    
    def register(self, name: str, notifier: Any) -> None:
        """注册通知器。"""
        with self._lock:
            self._notifiers[name] = notifier
    
    def get(self, name: str) -> Any | None:
        """获取通知器。"""
        with self._lock:
            return self._notifiers.get(name)
    
    def list(self) -> list[str]:
        """列出所有通知器名称。"""
        with self._lock:
            return list(self._notifiers.keys())
```

- [ ] **Step 4: Update runtime package to export Registry**

Update `src/marmot/runtime/__init__.py`:

```python
"""
运行时组件。

提供 Clock、Registry、Dispatcher 等有状态组件。
"""
from .clock import Clock, SystemClock
from .registry import RuleRegistry, NotifierRegistry

__all__ = ["Clock", "SystemClock", "RuleRegistry", "NotifierRegistry"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_registry.py -v`

Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add src/marmot/runtime/ tests/test_registry.py
git commit -m "feat: Unit 5.2 - RuleRegistry 和 NotifierRegistry"
```

---

## Unit 6: Evaluator

**Purpose:** Implement threshold evaluator to determine if a value triggers an alert.

### Task 5: Implement ThresholdEvaluator

**Files:**
- Create: `src/marmot/domain/evaluator.py`
- Create: `tests/test_evaluator_threshold.py`

- [ ] **Step 1: Write the failing test for ThresholdEvaluator**

Create `tests/test_evaluator_threshold.py`:

```python
"""
测试阈值评估器。
"""
import pytest
from datetime import datetime
from marmot.domain.evaluator import ThresholdEvaluator, Observation
from marmot.domain.models.rules import ThresholdRule, ThresholdLevel
from marmot.domain.models.enums import Severity
from marmot.domain.models.events import AlertEvent
from marmot.domain.models.enums import AlertState


def test_threshold_evaluator_hit():
    """超过阈值应该触发。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
            ThresholdLevel(value=90.0, severity=Severity.ERROR),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    observation = evaluator.evaluate(
        rule=rule,
        value=85.0,
        labels={"host": "server1"},
        prior_event=None,
        now=datetime.utcnow(),
    )
    
    assert observation.hit is True
    assert observation.miss is False
    assert observation.matched_severity == Severity.WARNING
    assert observation.dedup_key == "cpu_high:host=server1"


def test_threshold_evaluator_miss():
    """低于阈值不应该触发。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    observation = evaluator.evaluate(
        rule=rule,
        value=75.0,
        labels={"host": "server1"},
        prior_event=None,
        now=datetime.utcnow(),
    )
    
    assert observation.hit is False
    assert observation.miss is True
    assert observation.matched_severity is None


def test_threshold_evaluator_highest_severity():
    """应该选择最高严重程度。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
            ThresholdLevel(value=90.0, severity=Severity.ERROR),
            ThresholdLevel(value=95.0, severity=Severity.CRITICAL),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    
    # 85% 匹配 WARNING
    obs1 = evaluator.evaluate(rule, 85.0, {}, None, datetime.utcnow())
    assert obs1.matched_severity == Severity.WARNING
    
    # 92% 匹配 ERROR
    obs2 = evaluator.evaluate(rule, 92.0, {}, None, datetime.utcnow())
    assert obs2.matched_severity == Severity.ERROR
    
    # 98% 匹配 CRITICAL
    obs3 = evaluator.evaluate(rule, 98.0, {}, None, datetime.utcnow())
    assert obs3.matched_severity == Severity.CRITICAL


def test_threshold_evaluator_with_prior_event():
    """有 prior_event 时应该复用 dedup_key。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    prior_event = AlertEvent(
        id=1,
        rule_name="cpu_high",
        dedup_key="cpu_high:host=server1",
        state=AlertState.PENDING.value,
        labels={"host": "server1"},
        fired_at=datetime.utcnow(),
    )
    
    evaluator = ThresholdEvaluator()
    observation = evaluator.evaluate(
        rule=rule,
        value=85.0,
        labels={"host": "server1"},  # 相同 labels
        prior_event=prior_event,
        now=datetime.utcnow(),
    )
    
    assert observation.dedup_key == "cpu_high:host=server1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_evaluator_threshold.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'marmot.domain.evaluator'"

- [ ] **Step 3: Implement ThresholdEvaluator**

Create `src/marmot/domain/evaluator.py`:

```python
"""
评估器。

提供阈值评估、心跳评估等功能。
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .models.enums import Severity
from .models.events import AlertEvent
from .models.rules import ThresholdRule
from .keys import build_dedup_key


@dataclass
class Observation:
    """观测结果。
    
    表示一次 report() 的评估结果。
    """
    hit: bool  # 是否触发（超过阈值）
    miss: bool  # 是否恢复（低于阈值）
    matched_severity: Severity | None  # 匹配的严重程度
    dedup_key: str  # 去重键


class ThresholdEvaluator:
    """阈值评估器。
    
    根据阈值规则评估数值是否触发告警。
    """
    
    def evaluate(
        self,
        rule: ThresholdRule,
        value: float,
        labels: dict[str, Any],
        prior_event: AlertEvent | None,
        now: datetime,
    ) -> Observation:
        """评估阈值。
        
        Args:
            rule: 阈值规则
            value: 当前值
            labels: 标签
            prior_event: 先前的告警事件（如果存在）
            now: 当前时间
            
        Returns:
            Observation: 观测结果
        """
        # 使用规则评估阈值
        matched_level = rule.evaluate(value)
        
        # 判断是否触发
        hit = matched_level is not None
        miss = not hit
        
        # 匹配的严重程度
        matched_severity = None
        if matched_level:
            # 转换为枚举
            severity = matched_level.severity
            if isinstance(severity, str):
                matched_severity = Severity(severity)
            else:
                matched_severity = severity
        
        # 去重键
        # 如果有 prior_event，复用其 dedup_key
        if prior_event:
            dedup_key = prior_event.dedup_key
        else:
            dedup_key = build_dedup_key(rule.name, labels)
        
        return Observation(
            hit=hit,
            miss=miss,
            matched_severity=matched_severity,
            dedup_key=dedup_key,
        )
```

- [ ] **Step 4: Update domain package to export evaluator**

Update `src/marmot/domain/__init__.py`:

```python
"""
领域层。

包含数据模型、状态机、评估器等纯逻辑组件。
"""
from .models.enums import (
    AlertState,
    Severity,
    AlertStage,
    RunStatus,
    NotificationStatus,
    AggregateFn,
)
from .models.rules import (
    Rule,
    ThresholdRule,
    ThresholdLevel,
    EscalationStep,
    AggregateConfig,
)
from .models.events import AlertEvent, RunRecord, Notification
from .models.time_utils import utcnow, to_iso, from_iso, parse_duration
from .models.keys import build_dedup_key, normalize_notify
from .decisions import Decision, NotifyFiring, NotifyResolved
from .state_machine import AlertStateMachine
from .evaluator import ThresholdEvaluator, Observation

__all__ = [
    # Enums
    "AlertState",
    "Severity",
    "AlertStage",
    "RunStatus",
    "NotificationStatus",
    "AggregateFn",
    # Rules
    "Rule",
    "ThresholdRule",
    "ThresholdLevel",
    "EscalationStep",
    "AggregateConfig",
    # Events
    "AlertEvent",
    "RunRecord",
    "Notification",
    # Utils
    "utcnow",
    "to_iso",
    "from_iso",
    "parse_duration",
    "build_dedup_key",
    "normalize_notify",
    # State Machine
    "Decision",
    "NotifyFiring",
    "NotifyResolved",
    "AlertStateMachine",
    # Evaluator
    "ThresholdEvaluator",
    "Observation",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_evaluator_threshold.py -v`

Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add src/marmot/domain/ tests/test_evaluator_threshold.py
git commit -m "feat: Unit 6 - ThresholdEvaluator 实现"
```

---

## Unit 7: Dispatcher + MarmotApp + Console Notifier

**Purpose:** Wire everything together to provide a working alert framework.

### Task 6: Implement Notifier Protocol and ConsoleNotifier

**Files:**
- Create: `src/marmot/notifiers/__init__.py`
- Create: `src/marmot/notifiers/base.py`
- Create: `src/marmot/notifiers/console.py`
- Create: `tests/test_notifier_console.py`

- [ ] **Step 1: Create notifiers package**

Create `src/marmot/notifiers/__init__.py`:

```python
"""
通知器。

提供 Notifier Protocol 和多种实现。
"""
from .base import Notifier
from .console import ConsoleNotifier

__all__ = ["Notifier", "ConsoleNotifier"]
```

- [ ] **Step 2: Write the failing test for Notifier Protocol**

Create `tests/test_notifier_console.py`:

```python
"""
测试 ConsoleNotifier。
"""
import pytest
from datetime import datetime
from io import StringIO
from marmot.notifiers.console import ConsoleNotifier
from marmot.domain.models.events import Notification
from marmot.domain.models.enums import Severity, AlertState


def test_console_notifier_send():
    """应该能发送通知到控制台。"""
    output = StringIO()
    notifier = ConsoleNotifier(output=output)
    
    notification = Notification(
        id=1,
        alert_event_id=1,
        rule_name="cpu_high",
        dedup_key="cpu_high:host=server1",
        status="pending",
        state=AlertState.FIRING.value,
        severity=Severity.ERROR.value,
        labels={"host": "server1"},
        message="CPU usage is high",
        notifier_name="console",
        sent_at=datetime.utcnow(),
    )
    
    result = notifier.send(notification)
    
    assert result is True
    output_str = output.getvalue()
    assert "cpu_high" in output_str
    assert "ERROR" in output_str
    assert "host=server1" in output_str
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_notifier_console.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'marmot.notifiers'"

- [ ] **Step 4: Implement Notifier Protocol**

Create `src/marmot/notifiers/base.py`:

```python
"""
通知器 Protocol 定义。
"""
from typing import Protocol


class Notifier(Protocol):
    """通知器 Protocol。
    
    定义通知器的统一接口。
    """
    
    def send(self, notification: Any) -> bool:
        """发送通知。
        
        Args:
            notification: 通知对象
            
        Returns:
            bool: 是否发送成功
        """
        ...
```

- [ ] **Step 5: Implement ConsoleNotifier**

Create `src/marmot/notifiers/console.py`:

```python
"""
控制台通知器。

将通知打印到标准输出或指定输出流。
"""
import sys
from typing import Any, TextIO
from datetime import datetime

from ..domain.models.events import Notification


class ConsoleNotifier:
    """控制台通知器。
    
    将通知格式化后打印到标准输出。
    """
    
    def __init__(self, output: TextIO | None = None):
        """初始化。
        
        Args:
            output: 输出流，默认为 sys.stdout
        """
        self.output = output or sys.stdout
    
    def send(self, notification: Notification) -> bool:
        """发送通知。
        
        Args:
            notification: 通知对象
            
        Returns:
            bool: 总是返回 True
        """
        # 格式化输出
        timestamp = notification.sent_at.strftime("%Y-%m-%d %H:%M:%S")
        state = notification.state or "UNKNOWN"
        severity = notification.severity or "INFO"
        labels_str = " ".join(f"{k}={v}" for k, v in notification.labels.items())
        
        message = (
            f"[{timestamp}] "
            f"[{notification.rule_name}] "
            f"[{state}] "
            f"[{severity}] "
            f"{labels_str} "
            f"- {notification.message}\n"
        )
        
        self.output.write(message)
        self.output.flush()
        
        return True
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_notifier_console.py -v`

Expected: PASS (1 test)

- [ ] **Step 7: Commit**

```bash
git add src/marmot/notifiers/ tests/test_notifier_console.py
git commit -m "feat: Unit 7.1 - Notifier Protocol 和 ConsoleNotifier"
```

---

### Task 7: Implement Dispatcher

**Files:**
- Create: `src/marmot/runtime/dispatcher.py`
- Create: `tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing test for Dispatcher**

Create `tests/test_dispatcher.py`:

```python
"""
测试 Dispatcher。
"""
import pytest
from datetime import datetime
from marmot.runtime.dispatcher import Dispatcher
from marmot.storage.memory import MemoryStorage
from marmot.runtime.registry import NotifierRegistry
from marmot.runtime.clock import SystemClock
from marmot.domain.decisions import Decision, NotifyFiring, NotifyResolved
from marmot.domain.models.events import AlertEvent
from marmot.domain.models.enums import AlertState, Severity


def test_dispatcher_apply_notify_firing():
    """应该能应用 NotifyFiring 决策。"""
    storage = MemoryStorage()
    notifier_registry = NotifierRegistry()
    clock = SystemClock()
    
    # 注册一个 mock notifier
    notifications = []
    class MockNotifier:
        def send(self, notification):
            notifications.append(notification)
            return True
    
    notifier_registry.register("console", MockNotifier())
    
    dispatcher = Dispatcher(storage, notifier_registry, clock)
    
    # 创建一个事件
    event, _ = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
        severity=Severity.WARNING.value,
        fired_at=datetime.utcnow(),
    )
    
    # 应用决策
    decision = Decision(
        new_state=AlertState.FIRING.value,
        event_patch={"consecutive_hits": 3},
        actions=[
            NotifyFiring(
                severity=Severity.WARNING.value,
                notify_targets=["console"],
            )
        ]
    )
    
    dispatcher.apply(event, decision)
    
    # 验证事件被更新
    updated = storage.get_alert_event(event.id)
    assert updated.state == AlertState.FIRING.value
    assert updated.consecutive_hits == 3
    
    # 验证通知被发送
    assert len(notifications) == 1


def test_dispatcher_apply_notify_resolved():
    """应该能应用 NotifyResolved 决策。"""
    storage = MemoryStorage()
    notifier_registry = NotifierRegistry()
    clock = SystemClock()
    
    notifications = []
    class MockNotifier:
        def send(self, notification):
            notifications.append(notification)
            return True
    
    notifier_registry.register("console", MockNotifier())
    
    dispatcher = Dispatcher(storage, notifier_registry, clock)
    
    event, _ = storage.get_or_create_alert_event(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.RESOLVING.value,
        severity=Severity.WARNING.value,
        fired_at=datetime.utcnow(),
    )
    
    decision = Decision(
        new_state=AlertState.RESOLVED.value,
        event_patch={"consecutive_misses": 3},
        actions=[
            NotifyResolved(notify_targets=["console"])
        ]
    )
    
    dispatcher.apply(event, decision)
    
    updated = storage.get_alert_event(event.id)
    assert updated.state == AlertState.RESOLVED.value
    
    assert len(notifications) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatcher.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'marmot.runtime.dispatcher'"

- [ ] **Step 3: Implement Dispatcher**

Create `src/marmot/runtime/dispatcher.py`:

```python
"""
分发器。

应用决策，执行副作用（写存储、发通知）。
"""
from datetime import datetime
from typing import Any

from ..domain.decisions import (
    Decision,
    NotifyFiring,
    NotifyResolved,
    EnterSilence,
    EnterResolving,
)
from ..domain.models.events import AlertEvent, Notification
from ..domain.models.enums import NotificationStatus
from .registry import NotifierRegistry
from .clock import Clock


class Dispatcher:
    """分发器。
    
    应用决策：更新事件状态、发送通知。
    """
    
    def __init__(
        self,
        storage: Any,
        notifier_registry: NotifierRegistry,
        clock: Clock,
    ):
        """初始化。
        
        Args:
            storage: 存储实现
            notifier_registry: 通知器注册表
            clock: 时钟
        """
        self.storage = storage
        self.notifier_registry = notifier_registry
        self.clock = clock
    
    def apply(self, event: AlertEvent, decision: Decision) -> None:
        """应用决策。
        
        Args:
            event: 当前事件
            decision: 决策
        """
        # 更新事件状态
        if decision.event_patch:
            self.storage.update_alert_event(event.id, **decision.event_patch)
        
        # 更新事件状态（单独字段）
        self.storage.update_alert_event(event.id, state=decision.new_state)
        
        # 执行动作
        for action in decision.actions:
            self._execute_action(event, action)
    
    def _execute_action(self, event: AlertEvent, action: Any) -> None:
        """执行动作。
        
        Args:
            event: 当前事件
            action: 动作对象
        """
        if isinstance(action, NotifyFiring):
            self._send_notification(
                event=event,
                state="firing",
                severity=action.severity,
                notify_targets=action.notify_targets,
                message=f"Alert firing: {event.rule_name}",
            )
        
        elif isinstance(action, NotifyResolved):
            self._send_notification(
                event=event,
                state="resolved",
                severity=None,
                notify_targets=action.notify_targets,
                message=f"Alert resolved: {event.rule_name}",
            )
        
        elif isinstance(action, EnterSilence):
            # 静默动作已经在 event_patch 中处理
            pass
        
        elif isinstance(action, EnterResolving):
            # 恢复确认动作不需要额外处理
            pass
    
    def _send_notification(
        self,
        event: AlertEvent,
        state: str,
        severity: str | None,
        notify_targets: list[str],
        message: str,
    ) -> None:
        """发送通知。
        
        Args:
            event: 告警事件
            state: 状态
            severity: 严重程度
            notify_targets: 通知目标列表
            message: 消息
        """
        now = self.clock.now()
        
        for target in notify_targets:
            # 获取通知器
            notifier = self.notifier_registry.get(target)
            if not notifier:
                # TODO: 记录日志
                continue
            
            # 创建通知记录
            notification_id = self.storage.create_notification(
                alert_event_id=event.id,
                rule_name=event.rule_name,
                dedup_key=event.dedup_key,
                status=NotificationStatus.PENDING.value,
                state=state,
                severity=severity,
                labels=event.labels,
                message=message,
                notifier_name=target,
                sent_at=now,
            )
            
            # 发送通知
            try:
                success = notifier.send(Notification(
                    id=notification_id,
                    alert_event_id=event.id,
                    rule_name=event.rule_name,
                    dedup_key=event.dedup_key,
                    status=NotificationStatus.SENT.value,
                    state=state,
                    severity=severity,
                    labels=event.labels,
                    message=message,
                    notifier_name=target,
                    sent_at=now,
                ))
                
                # 更新通知状态
                status = NotificationStatus.SENT.value if success else NotificationStatus.FAILED.value
                # TODO: 添加 update_notification 方法
                # self.storage.update_notification(notification_id, status=status)
                
            except Exception as e:
                # TODO: 记录日志
                pass
```

- [ ] **Step 4: Update runtime package to export Dispatcher**

Update `src/marmot/runtime/__init__.py`:

```python
"""
运行时组件。

提供 Clock、Registry、Dispatcher 等有状态组件。
"""
from .clock import Clock, SystemClock
from .registry import RuleRegistry, NotifierRegistry
from .dispatcher import Dispatcher

__all__ = [
    "Clock",
    "SystemClock",
    "RuleRegistry",
    "NotifierRegistry",
    "Dispatcher",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dispatcher.py -v`

Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/marmot/runtime/ tests/test_dispatcher.py
git commit -m "feat: Unit 7.2 - Dispatcher 实现"
```

---

### Task 8: Implement MarmotApp

**Files:**
- Create: `src/marmot/api.py`
- Update: `src/marmot/__init__.py`
- Create: `tests/test_report_pipeline.py`

- [ ] **Step 1: Write the failing test for MarmotApp.report()**

Create `tests/test_report_pipeline.py`:

```python
"""
测试完整的 report() 管线。
"""
import pytest
from io import StringIO
from marmot import configure, register_threshold_rule, report, shutdown
from marmot.domain.models.rules import ThresholdRule, ThresholdLevel
from marmot.domain.models.enums import Severity


def test_report_triggers_alert():
    """连续 report 超过阈值应该触发告警。"""
    output = StringIO()
    
    # 配置
    app = configure(storage="memory")
    app.register_notifier("console", lambda: None)  # 简化测试
    
    # 注册规则
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    register_threshold_rule(rule)
    
    # 模拟连续 report
    report("cpu_high", 85.0, {"host": "server1"})
    report("cpu_high", 86.0, {"host": "server1"})
    report("cpu_high", 87.0, {"host": "server1"})  # 应该触发
    
    # 验证活跃告警
    alerts = app.list_active_alerts()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "cpu_high"
    
    shutdown()


def test_report_resolves_alert():
    """连续 report 低于阈值应该恢复告警。"""
    # 配置
    app = configure(storage="memory")
    app.register_notifier("console", lambda: None)
    
    # 注册规则
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
        ],
        consecutive_count=2,  # 降低阈值便于测试
        silence_seconds=0,  # 关闭静默
        notify_targets=["console"],
    )
    register_threshold_rule(rule)
    
    # 触发告警
    report("cpu_high", 85.0, {"host": "server1"})
    report("cpu_high", 86.0, {"host": "server1"})
    
    # 验证告警触发
    alerts = app.list_active_alerts()
    assert len(alerts) == 1
    
    # 恢复告警
    report("cpu_high", 75.0, {"host": "server1"})
    report("cpu_high", 74.0, {"host": "server1"})
    
    # 验证告警恢复
    alerts = app.list_active_alerts()
    assert len(alerts) == 0
    
    shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report_pipeline.py -v`

Expected: FAIL with "ModuleNotFoundError: Cannot import name 'configure' from 'marmot'"

- [ ] **Step 3: Implement MarmotApp**

Create `src/marmot/api.py`:

```python
"""
API 层。

提供 MarmotApp 和模块级便捷函数。
"""
from typing import Any
from datetime import datetime

from .domain.models.enums import Severity, AlertState
from .domain.models.rules import ThresholdRule, Rule, ThresholdLevel
from .domain.models.events import AlertEvent
from .domain.evaluator import ThresholdEvaluator
from .domain.state_machine import AlertStateMachine
from .domain.keys import build_dedup_key
from .storage.memory import MemoryStorage
from .runtime.clock import Clock, SystemClock
from .runtime.registry import RuleRegistry, NotifierRegistry
from .runtime.dispatcher import Dispatcher
from .notifiers.base import Notifier


# 全局单例
_app: "MarmotApp | None" = None


class MarmotApp:
    """Marmot 应用。
    
    提供配置、规则注册、告警上报等功能。
    """
    
    def __init__(
        self,
        storage: Any = None,
        clock: Clock | None = None,
    ):
        """初始化。
        
        Args:
            storage: 存储实现，默认为 MemoryStorage
            clock: 时钟实现，默认为 SystemClock
        """
        self.storage = storage or MemoryStorage()
        self.clock = clock or SystemClock()
        self.rule_registry = RuleRegistry()
        self.notifier_registry = NotifierRegistry()
        self.evaluator = ThresholdEvaluator()
        self.dispatcher = Dispatcher(
            self.storage,
            self.notifier_registry,
            self.clock,
        )
    
    def register_threshold_rule(self, rule: ThresholdRule) -> None:
        """注册阈值规则。
        
        Args:
            rule: 阈值规则
        """
        self.rule_registry.register_threshold_rule(rule)
    
    def register_rule(self, rule: Rule) -> None:
        """注册通用规则。
        
        Args:
            rule: 通用规则
        """
        self.rule_registry.register_rule(rule)
    
    def register_notifier(self, name: str, notifier: Notifier) -> None:
        """注册通知器。
        
        Args:
            name: 通知器名称
            notifier: 通知器对象
        """
        self.notifier_registry.register(name, notifier)
    
    def report(
        self,
        name: str,
        value: float,
        labels: dict[str, Any] | None = None,
    ) -> None:
        """上报指标值。
        
        Args:
            name: 规则名称
            value: 指标值
            labels: 标签
        """
        labels = labels or {}
        
        # 获取规则
        rule = self.rule_registry.get_threshold_rule(name)
        if not rule:
            raise ValueError(f"Rule '{name}' not found")
        
        # 获取先前的告警事件
        dedup_key = build_dedup_key(name, labels)
        # 注意：这里我们暂时用简单的方法获取，后续可以优化
        events = self.storage.list_active_alerts(rule_name=name)
        prior_event = None
        for event in events:
            if event.dedup_key == dedup_key:
                prior_event = event
                break
        
        # 评估
        observation = self.evaluator.evaluate(
            rule=rule,
            value=value,
            labels=labels,
            prior_event=prior_event,
            now=self.clock.now(),
        )
        
        # 获取或创建告警事件
        if prior_event:
            event = prior_event
            created = False
        else:
            event, created = self.storage.get_or_create_alert_event(
                rule_name=name,
                dedup_key=dedup_key,
                state=AlertState.PENDING.value,
                severity=observation.matched_severity.value if observation.matched_severity else None,
                labels=labels,
                current_value=value,
                fired_at=self.clock.now(),
            )
        
        # 状态机转换
        decision = AlertStateMachine.transition(
            event=event,
            hit=observation.hit,
            consecutive_count=rule.consecutive_count,
            now=self.clock.now(),
            silence_seconds=rule.silence_seconds,
        )
        
        # 更新 notify_targets
        # TODO: 优化决策中的 notify_targets 获取
        from .domain.decisions import NotifyFiring, NotifyResolved
        for action in decision.actions:
            if isinstance(action, (NotifyFiring, NotifyResolved)):
                action.notify_targets = rule.notify_targets
        
        # 应用决策
        self.dispatcher.apply(event, decision)
    
    def fire(
        self,
        name: str,
        *,
        severity: str | Severity = "error",
        labels: dict[str, Any] | None = None,
        message: str = "",
    ) -> str:
        """手动触发告警。
        
        Args:
            name: 规则名称
            severity: 严重程度
            labels: 标签
            message: 消息
            
        Returns:
            str: 告警 ID
        """
        # TODO: 实现
        raise NotImplementedError("fire() will be implemented in future units")
    
    def resolve(
        self,
        name: str,
        *,
        labels: dict[str, Any] | None = None,
    ) -> None:
        """手动恢复告警。
        
        Args:
            name: 规则名称
            labels: 标签
        """
        # TODO: 实现
        raise NotImplementedError("resolve() will be implemented in future units")
    
    def shutdown(self) -> None:
        """关闭应用。"""
        # TODO: 实现优雅停机
        pass
    
    # 只读查询方法
    def list_active_alerts(self) -> list[AlertEvent]:
        """列出活跃告警。"""
        return self.storage.list_active_alerts()
    
    def list_alert_history(self, limit: int = 100) -> list[AlertEvent]:
        """列出告警历史。"""
        return self.storage.list_alert_history(limit=limit)
    
    def get_alert(self, alert_id: int) -> AlertEvent | None:
        """获取单个告警。"""
        return self.storage.get_alert_event(alert_id)


def configure(
    storage: Any = "memory",
    clock: Clock | None = None,
) -> MarmotApp:
    """配置并初始化 MarmotApp。
    
    Args:
        storage: 存储类型或实现，"memory" 表示内存存储
        clock: 时钟实现
        
    Returns:
        MarmotApp: 应用实例
    """
    global _app
    
    # 创建存储
    if storage == "memory":
        storage_impl = MemoryStorage()
    else:
        storage_impl = storage
    
    # 创建应用
    _app = MarmotApp(storage=storage_impl, clock=clock)
    
    return _app


def get_app() -> MarmotApp:
    """获取全局应用实例。
    
    Returns:
        MarmotApp: 应用实例
        
    Raises:
        RuntimeError: 如果应用未初始化
    """
    if _app is None:
        raise RuntimeError("Marmot not configured. Call configure() first.")
    return _app


def register_threshold_rule(rule: ThresholdRule) -> None:
    """注册阈值规则（模块级便捷函数）。"""
    get_app().register_threshold_rule(rule)


def register_notifier(name: str, notifier: Notifier) -> None:
    """注册通知器（模块级便捷函数）。"""
    get_app().register_notifier(name, notifier)


def report(name: str, value: float, labels: dict[str, Any] | None = None) -> None:
    """上报指标值（模块级便捷函数）。"""
    get_app().report(name, value, labels)


def shutdown() -> None:
    """关闭应用（模块级便捷函数）。"""
    get_app().shutdown()
```

- [ ] **Step 4: Update main package to export API**

Update `src/marmot/__init__.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_report_pipeline.py -v`

Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add src/marmot/ tests/test_report_pipeline.py
git commit -m "feat: Unit 7.3 - MarmotApp 和 report() 管线"
```

---

### Task 9: Create Quickstart Example

**Files:**
- Create: `examples/quickstart.py`

- [ ] **Step 1: Create quickstart example**

Create `examples/quickstart.py`:

```python
"""
快速开始示例。

演示如何使用 Marmot 创建阈值规则并触发告警。
"""
from marmot import (
    configure,
    register_threshold_rule,
    register_notifier,
    report,
    shutdown,
    ThresholdRule,
    ThresholdLevel,
    ConsoleNotifier,
    Severity,
)


def main():
    """主函数。"""
    print("=== Marmot 快速开始 ===\n")
    
    # 1. 配置 Marmot
    print("1. 配置 Marmot (内存存储)")
    app = configure(storage="memory")
    
    # 2. 注册通知器
    print("2. 注册控制台通知器")
    register_notifier("console", ConsoleNotifier())
    
    # 3. 注册阈值规则
    print("3. 注册 CPU 使用率告警规则")
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
            ThresholdLevel(value=90.0, severity=Severity.ERROR),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    register_threshold_rule(rule)
    
    # 4. 模拟上报数据
    print("\n4. 模拟上报数据...")
    print("   - 第一次上报: CPU 70% (正常)")
    report("cpu_high", 70.0, {"host": "server1"})
    
    print("   - 第二次上报: CPU 85% (超过 WARNING 阈值)")
    report("cpu_high", 85.0, {"host": "server1"})
    
    print("   - 第三次上报: CPU 87% (继续超过阈值)")
    report("cpu_high", 87.0, {"host": "server1"})
    
    print("   - 第四次上报: CPU 92% (超过 ERROR 阈值)")
    report("cpu_high", 92.0, {"host": "server1"})
    
    # 5. 检查活跃告警
    print("\n5. 检查活跃告警:")
    alerts = app.list_active_alerts()
    print(f"   活跃告警数量: {len(alerts)}")
    for alert in alerts:
        print(f"   - {alert.rule_name}: {alert.state}")
    
    # 6. 模拟恢复
    print("\n6. 模拟恢复...")
    print("   - 上报: CPU 75% (恢复正常)")
    report("cpu_high", 75.0, {"host": "server1"})
    
    print("   - 上报: CPU 70% (继续正常)")
    report("cpu_high", 70.0, {"host": "server1"})
    
    # 7. 再次检查活跃告警
    print("\n7. 再次检查活跃告警:")
    alerts = app.list_active_alerts()
    print(f"   活跃告警数量: {len(alerts)}")
    
    # 8. 关闭
    print("\n8. 关闭 Marmot")
    shutdown()
    
    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run quickstart example**

Run: `python examples/quickstart.py`

Expected: Output showing alert triggering and resolving

- [ ] **Step 3: Commit**

```bash
git add examples/
git commit -m "feat: Unit 7.4 - 快速开始示例"
```

---

## Verification

- [ ] **Run all tests**

Run: `pytest tests/ -v`

Expected: All tests pass

- [ ] **Verify MVP milestone M1**

Verify:
- ✅ Unit 1-7 complete
- ✅ `report()` can trigger and resolve alerts
- ✅ Console notifications work
- ✅ In-memory storage works
- ✅ All tests pass
- ✅ `examples/quickstart.py` runs successfully

---

## Summary

After completing all tasks:

**Completed Units:**
- ✅ Unit 4: Storage Protocol + Memory Implementation
- ✅ Unit 5: Clock + Registry
- ✅ Unit 6: ThresholdEvaluator
- ✅ Unit 7: Dispatcher + MarmotApp + ConsoleNotifier

**MVP Milestone M1 Achieved:**
- Functional alert framework with threshold rules
- In-memory storage for testing
- Console notifications
- Basic report pipeline
- Zero runtime dependencies

**Next Steps (Post-MVP):**
- Unit 8: SQLite Storage
- Unit 9: Aggregate Window
- Unit 10: Heartbeat + Job Decorator
- Unit 11: Async Notification Queue
- Unit 12: Escalation Strategy
- Unit 13: External Notification Channels
- Unit 14: Read-only Query API
- Unit 15: Web Console
- Unit 16: Documentation & Packaging

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-12-marmot-mvp-units-4-7.md`.**
