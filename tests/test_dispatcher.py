"""
测试 Dispatcher。
"""
from datetime import UTC, datetime

from marmot.runtime.dispatcher import Dispatcher
from marmot.storage.memory import MemoryStorage
from marmot.runtime.registry import NotifierRegistry
from marmot.runtime.clock import SystemClock
from marmot.domain.decisions import Decision, NotifyFiring, NotifyResolved
from marmot.domain.models.events import AlertEvent
from marmot.domain.models.enums import AlertState, Severity


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
        fired_at=datetime.now(UTC),
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
        fired_at=datetime.now(UTC),
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
        fired_at=datetime.now(UTC),
    ))
    
    decision = Decision(
        new_state=AlertState.RESOLVED.value,
        event_patch={},
        actions=[NotifyResolved(notify_targets=["console"])],
    )
    
    dispatcher.apply(event, decision)
    
    assert len(sent) == 1
