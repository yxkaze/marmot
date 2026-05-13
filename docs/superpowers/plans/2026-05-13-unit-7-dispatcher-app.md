# Unit 7: Dispatcher + MarmotApp + ConsoleNotifier 实现计划

**目标：** 把所有组件串起来，实现完整的 report() 管线，达到 MVP 里程碑 M1。

**架构：** L2 通知器 + L3 分发器 + L4 API 门面

---

## 文件结构

```
src/marmot/notifiers/
  __init__.py          # 导出
  base.py              # Notifier Protocol
  console.py           # ConsoleNotifier

src/marmot/runtime/
  dispatcher.py        # 分发器（消费 Decision）

src/marmot/
  api.py               # MarmotApp 门面
  __init__.py          # 更新导出

tests/
  test_notifier_console.py  # ConsoleNotifier 测试
  test_dispatcher.py         # Dispatcher 测试
  test_report_pipeline.py    # 完整管线测试

examples/
  quickstart.py        # 快速开始示例
```

---

## 任务 1: Notifier Protocol + ConsoleNotifier

**文件：**
- 新建: `src/marmot/notifiers/__init__.py`
- 新建: `src/marmot/notifiers/base.py`
- 新建: `src/marmot/notifiers/console.py`
- 新建: `tests/test_notifier_console.py`

- [ ] **步骤 1: 创建 notifiers 包 + 写测试**

创建 `src/marmot/notifiers/__init__.py`:

```python
"""
通知器。
"""
from .base import Notifier
from .console import ConsoleNotifier

__all__ = ["Notifier", "ConsoleNotifier"]
```

创建 `tests/test_notifier_console.py`:

```python
"""
测试 ConsoleNotifier。
"""
from datetime import datetime
from io import StringIO

from marmot.notifiers.console import ConsoleNotifier
from marmot.domain.models.events import Notification
from marmot.domain.models.enums import Severity, AlertState


def test_send_prints_to_output():
    """应该能发送通知到控制台。"""
    output = StringIO()
    notifier = ConsoleNotifier(output=output)
    
    notification = Notification(
        id=1,
        alert_event_id=1,
        rule_name="cpu_high",
        dedup_key="cpu_high:host=server1",
        status="sent",
        state=AlertState.FIRING.value,
        severity=Severity.ERROR.value,
        labels={"host": "server1"},
        message="CPU usage is high",
        notifier_name="console",
        sent_at=datetime.utcnow(),
    )
    
    result = notifier.send(notification)
    
    assert result is True
    text = output.getvalue()
    assert "cpu_high" in text
    assert "ERROR" in text
```

- [ ] **步骤 2: 运行测试确认失败**

- [ ] **步骤 3: 实现 Notifier Protocol 和 ConsoleNotifier**

创建 `src/marmot/notifiers/base.py`:

```python
"""
通知器 Protocol 定义。
"""
from typing import Protocol, Any


class Notifier(Protocol):
    """通知器 Protocol。"""
    
    def send(self, notification: Any) -> bool:
        """发送通知。返回是否成功。"""
        ...
```

创建 `src/marmot/notifiers/console.py`:

```python
"""
控制台通知器。

将通知打印到标准输出或指定输出流。
"""
import sys
from typing import TextIO

from ..domain.models.events import Notification


class ConsoleNotifier:
    """控制台通知器。"""
    
    def __init__(self, output: TextIO | None = None):
        self.output = output or sys.stdout
    
    def send(self, notification: Notification) -> bool:
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

- [ ] **步骤 4: 运行测试确认通过**

- [ ] **步骤 5: 提交**

```bash
git add src/marmot/notifiers/ tests/test_notifier_console.py
git commit -m "feat: Unit 7.1 - Notifier Protocol 和 ConsoleNotifier"
```

---

## 任务 2: Dispatcher

**文件：**
- 新建: `src/marmot/runtime/dispatcher.py`
- 新建: `tests/test_dispatcher.py`

- [ ] **步骤 1: 写测试**

创建 `tests/test_dispatcher.py`:

```python
"""
测试 Dispatcher。
"""
from datetime import datetime

from marmot.runtime.dispatcher import Dispatcher
from marmot.storage.memory import MemoryStorage
from marmot.runtime.registry import NotifierRegistry
from marmot.runtime.clock import SystemClock
from marmot.domain.decisions import Decision, NotifyFiring, NotifyResolved, EnterSilence
from marmot.domain.models.events import AlertEvent
from marmot.domain.models.enums import AlertState, Severity, NotificationStatus


def test_apply_updates_event_state():
    """应该能更新事件状态。"""
    storage = MemoryStorage()
    notifier_registry = NotifierRegistry()
    clock = SystemClock()
    dispatcher = Dispatcher(storage, notifier_registry, clock)
    
    event = storage.create_alert_event(AlertEvent(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
        severity=Severity.WARNING.value,
        fired_at=datetime.utcnow(),
    ))
    
    decision = Decision(
        new_state=AlertState.FIRING.value,
        event_patch={"consecutive_hits": 3},
        actions=[],
    )
    
    dispatcher.apply(event, decision)
    
    updated = storage.get_alert(event.id)
    assert updated.state == AlertState.FIRING.value
    assert updated.consecutive_hits == 3


def test_apply_notify_firing():
    """应该能发送 firing 通知。"""
    storage = MemoryStorage()
    notifier_registry = NotifierRegistry()
    clock = SystemClock()
    
    sent = []
    class FakeNotifier:
        def send(self, n):
            sent.append(n)
            return True
    
    notifier_registry.register("console", FakeNotifier())
    dispatcher = Dispatcher(storage, notifier_registry, clock)
    
    event = storage.create_alert_event(AlertEvent(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING.value,
        severity=Severity.WARNING.value,
        labels={"host": "server1"},
        fired_at=datetime.utcnow(),
    ))
    
    decision = Decision(
        new_state=AlertState.FIRING.value,
        event_patch={},
        actions=[NotifyFiring(severity=Severity.WARNING.value, notify_targets=["console"])],
    )
    
    dispatcher.apply(event, decision)
    
    assert len(sent) == 1


def test_apply_notify_resolved():
    """应该能发送 resolved 通知。"""
    storage = MemoryStorage()
    notifier_registry = NotifierRegistry()
    clock = SystemClock()
    
    sent = []
    class FakeNotifier:
        def send(self, n):
            sent.append(n)
            return True
    
    notifier_registry.register("console", FakeNotifier())
    dispatcher = Dispatcher(storage, notifier_registry, clock)
    
    event = storage.create_alert_event(AlertEvent(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.RESOLVING.value,
        severity=Severity.WARNING.value,
        fired_at=datetime.utcnow(),
    ))
    
    decision = Decision(
        new_state=AlertState.RESOLVED.value,
        event_patch={},
        actions=[NotifyResolved(notify_targets=["console"])],
    )
    
    dispatcher.apply(event, decision)
    
    assert len(sent) == 1
```

- [ ] **步骤 2: 运行测试确认失败**

- [ ] **步骤 3: 实现 Dispatcher**

创建 `src/marmot/runtime/dispatcher.py`:

```python
"""
分发器。

消费 Decision，执行副作用（写存储、发通知）。
"""
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
        self.storage = storage
        self.notifier_registry = notifier_registry
        self.clock = clock
    
    def apply(self, event: AlertEvent, decision: Decision) -> None:
        """应用决策。"""
        # 更新事件字段
        if decision.event_patch:
            for key, value in decision.event_patch.items():
                setattr(event, key, value)
        
        # 更新事件状态
        event.state = decision.new_state
        self.storage.update_alert_event(event)
        
        # 执行动作
        for action in decision.actions:
            self._execute_action(event, action)
    
    def _execute_action(self, event: AlertEvent, action: Any) -> None:
        """执行动作。"""
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
            pass
        elif isinstance(action, EnterResolving):
            pass
    
    def _send_notification(
        self,
        event: AlertEvent,
        state: str,
        severity: str | None,
        notify_targets: list[str],
        message: str,
    ) -> None:
        """发送通知。"""
        now = self.clock.now()
        
        for target in notify_targets:
            notifier = self.notifier_registry.get(target)
            if not notifier:
                continue
            
            notification = Notification(
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
            )
            
            try:
                success = notifier.send(notification)
                notification.status = NotificationStatus.SENT.value if success else NotificationStatus.FAILED.value
            except Exception:
                notification.status = NotificationStatus.FAILED.value
            
            self.storage.record_notification(notification)
```

- [ ] **步骤 4: 更新 runtime/__init__.py 导出**

- [ ] **步骤 5: 运行测试确认通过**

- [ ] **步骤 6: 提交**

```bash
git add src/marmot/runtime/ tests/test_dispatcher.py
git commit -m "feat: Unit 7.2 - Dispatcher 实现"
```

---

## 任务 3: MarmotApp + 完整管线

**文件：**
- 新建: `src/marmot/api.py`
- 修改: `src/marmot/__init__.py`
- 新建: `tests/test_report_pipeline.py`

- [ ] **步骤 1: 写测试**

创建 `tests/test_report_pipeline.py`:

```python
"""
测试完整的 report() 管线。
"""
from datetime import datetime

from marmot import configure, shutdown
from marmot.domain.models.rules import ThresholdRule, ThresholdLevel
from marmot.domain.models.enums import Severity


def test_report_triggers_alert():
    """连续 report 超过阈值应该触发告警。"""
    app = configure(storage="memory")
    app.register_notifier("console", lambda: None)
    
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=0,
        notify_targets=["console"],
    )
    app.register_threshold_rule(rule)
    
    # 连续 3 次超过阈值
    app.report("cpu_high", 85.0, {"host": "server1"})
    app.report("cpu_high", 86.0, {"host": "server1"})
    app.report("cpu_high", 87.0, {"host": "server1"})
    
    alerts = app.list_active_alerts()
    assert len(alerts) == 1
    assert alerts[0].rule_name == "cpu_high"
    
    shutdown()


def test_report_resolves_alert():
    """连续 report 低于阈值应该恢复告警。"""
    app = configure(storage="memory")
    app.register_notifier("console", lambda: None)
    
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=2,
        silence_seconds=0,
        notify_targets=["console"],
    )
    app.register_threshold_rule(rule)
    
    # 触发告警
    app.report("cpu_high", 85.0, {"host": "server1"})
    app.report("cpu_high", 86.0, {"host": "server1"})
    
    alerts = app.list_active_alerts()
    assert len(alerts) == 1
    
    # 恢复告警
    app.report("cpu_high", 75.0, {"host": "server1"})
    app.report("cpu_high", 74.0, {"host": "server1"})
    
    alerts = app.list_active_alerts()
    assert len(alerts) == 0
    
    shutdown()


def test_report_unknown_rule():
    """上报未知规则应该报错。"""
    app = configure(storage="memory")
    
    import pytest
    with pytest.raises(ValueError, match="not found"):
        app.report("nonexistent", 85.0)
    
    shutdown()
```

- [ ] **步骤 2: 运行测试确认失败**

- [ ] **步骤 3: 实现 MarmotApp**

创建 `src/marmot/api.py` — 组装所有组件，提供门面方法。

核心 report() 流程：
1. 从 registry 获取规则
2. 从 storage 获取 prior_event（通过 dedup_key）
3. 用 evaluator 评估，得到 Observation
4. 如果没有 prior_event，创建新的 AlertEvent
5. 用 state_machine 转换，得到 Decision
6. 把 Observation 的 notify_targets 注入 Decision 的 actions
7. 用 dispatcher 应用 Decision

- [ ] **步骤 4: 更新 __init__.py 导出**

- [ ] **步骤 5: 运行测试确认通过**

- [ ] **步骤 6: 提交**

```bash
git add src/marmot/ tests/test_report_pipeline.py
git commit -m "feat: Unit 7.3 - MarmotApp 和 report() 管线"
```

---

## 任务 4: 快速开始示例

**文件：**
- 新建: `examples/quickstart.py`

- [ ] **步骤 1: 创建示例**

- [ ] **步骤 2: 运行示例确认通过**

- [ ] **步骤 3: 提交**

```bash
git add examples/
git commit -m "feat: Unit 7.4 - 快速开始示例"
```

---

## 验证

- [ ] `pytest tests/ -v` 全部通过
- [ ] `examples/quickstart.py` 可运行
- [️] **MVP 里程碑 M1 达成！**

---

**计划已保存到 `docs/superpowers/plans/2026-05-13-unit-7-dispatcher-app.md`**
