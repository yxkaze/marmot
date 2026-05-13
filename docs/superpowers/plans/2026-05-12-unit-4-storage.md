# Unit 4: Storage Protocol + 内存实现 实现计划

> **给执行者：** 必须使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 逐任务执行。步骤使用复选框 (`- [ ]`) 语法追踪。

**目标：** 定义存储抽象协议，并提供内存实现用于测试和早期开发。

**架构：** L2 适配层 - Storage Protocol 定义接口，MemoryStorage 提供基于 dict/list 的实现。

**技术栈：** Python 3.10+, typing.Protocol, threading.RLock, dataclasses

---

## 文件结构

本次 Unit 会创建以下文件：

```
src/marmot/storage/
  __init__.py          # 导出 Storage 和 MemoryStorage
  base.py              # Storage Protocol 定义
  memory.py            # 内存存储实现

tests/
  test_storage_base.py    # Protocol 测试
  test_storage_memory.py  # 内存存储测试
```

---

## 任务 1: 创建 Storage Protocol

**文件：**
- 新建: `src/marmot/storage/__init__.py`
- 新建: `src/marmot/storage/base.py`
- 新建: `tests/test_storage_base.py`

- [ ] **步骤 1: 创建 storage 包**

创建 `src/marmot/storage/__init__.py`:

```python
"""
存储层。

提供 Storage Protocol 和多种实现。
"""
from .base import Storage

__all__ = ["Storage"]
```

- [ ] **步骤 2: 写失败的测试**

创建 `tests/test_storage_base.py`:

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

- [ ] **步骤 3: 运行测试确认失败**

运行: `pytest tests/test_storage_base.py -v`

预期: FAIL 并提示 "ModuleNotFoundError: No module named 'marmot.storage.base'"

- [ ] **步骤 4: 实现 Storage Protocol**

创建 `src/marmot/storage/base.py`:

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
        
        参数:
            rule_name: 规则名称
            dedup_key: 去重键
            **defaults: 如果创建，使用的默认值
            
        返回:
            (event, created): 事件对象和是否新创建
        """
        ...
    
    def update_alert_event(self, event_id: int, **updates) -> None:
        """更新告警事件。
        
        参数:
            event_id: 事件 ID
            **updates: 要更新的字段
        """
        ...
    
    def list_active_alerts(self, rule_name: str | None = None) -> list[Any]:
        """列出活跃告警。
        
        参数:
            rule_name: 可选，过滤规则名称
            
        返回:
            活跃告警列表（非 RESOLVED 状态）
        """
        ...
    
    def list_alert_history(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[Any]:
        """列出告警历史。
        
        参数:
            rule_name: 可选，过滤规则名称
            limit: 限制数量
            
        返回:
            告警历史列表（按时间倒序）
        """
        ...
    
    def get_alert_event(self, event_id: int) -> Any | None:
        """获取单个告警事件。
        
        参数:
            event_id: 事件 ID
            
        返回:
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
        
        返回:
            记录 ID
        """
        ...
    
    def list_recent_runs(
        self,
        rule_name: str | None = None,
        limit: int = 100
    ) -> list[Any]:
        """列出最近运行记录。
        
        参数:
            rule_name: 可选，过滤规则名称
            limit: 限制数量
            
        返回:
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
        
        返回:
            记录 ID
        """
        ...
    
    def list_notifications(
        self,
        alert_event_id: int | None = None,
        limit: int = 100
    ) -> list[Any]:
        """列出通知记录。
        
        参数:
            alert_event_id: 可选，过滤告警事件 ID
            limit: 限制数量
            
        返回:
            通知记录列表（按时间倒序）
        """
        ...
```

- [ ] **步骤 5: 运行测试确认通过**

运行: `pytest tests/test_storage_base.py -v`

预期: PASS (2 个测试)

- [ ] **步骤 6: 提交**

```bash
git add src/marmot/storage/ tests/test_storage_base.py
git commit -m "feat: Unit 4.1 - Storage Protocol 定义"
```

---

## 任务 2: 实现内存存储

**文件：**
- 新建: `src/marmot/storage/memory.py`
- 新建: `tests/test_storage_memory.py`
- 修改: `src/marmot/storage/__init__.py`

- [ ] **步骤 1: 写失败的测试**

创建 `tests/test_storage_memory.py`:

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

- [ ] **步骤 2: 运行测试确认失败**

运行: `pytest tests/test_storage_memory.py -v`

预期: FAIL 并提示 "ModuleNotFoundError: No module named 'marmot.storage.memory'"

- [ ] **步骤 3: 实现 MemoryStorage**

创建 `src/marmot/storage/memory.py`:

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

- [ ] **步骤 4: 更新 storage 包导出**

更新 `src/marmot/storage/__init__.py`:

```python
"""
存储层。

提供 Storage Protocol 和多种实现。
"""
from .base import Storage
from .memory import MemoryStorage

__all__ = ["Storage", "MemoryStorage"]
```

- [ ] **步骤 5: 运行测试确认通过**

运行: `pytest tests/test_storage_memory.py -v`

预期: PASS (6 个测试)

- [ ] **步骤 6: 提交**

```bash
git add src/marmot/storage/ tests/test_storage_memory.py
git commit -m "feat: Unit 4.2 - 内存存储实现"
```

---

## 验证

- [ ] **运行所有测试**

运行: `pytest tests/ -v`

预期: 所有测试通过

- [ ] **验证 Unit 4 完成**

确认:
- ✅ Storage Protocol 已定义
- ✅ MemoryStorage 已实现
- ✅ 所有测试通过
- ✅ 文件 ≤ 300 行

---

## Unit 4 完成后的状态

**新增文件：**
- `src/marmot/storage/__init__.py`
- `src/marmot/storage/base.py`
- `src/marmot/storage/memory.py`
- `tests/test_storage_base.py`
- `tests/test_storage_memory.py`

**功能：**
- 可以创建、更新、查询告警事件
- 可以创建、查询运行记录
- 可以创建、查询通知记录
- 线程安全（使用 RLock）
- 基于内存，进程重启后数据丢失

**下一步：** Unit 5 - Clock + Registry

---

**计划已保存到 `docs/superpowers/plans/2026-05-12-unit-4-storage.md`**
