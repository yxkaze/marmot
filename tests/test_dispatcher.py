"""
测试 Dispatcher。
"""
from datetime import UTC, datetime

from marmot.runtime.dispatcher import Dispatcher
from marmot.storage.memory import MemoryStorage
from marmot.runtime.registry import SinkRegistry
from marmot.runtime.clock import SystemClock
from marmot.domain.decisions import Decision, NotifyFiring, NotifyResolved
from marmot.domain.models.events import AlertEvent, Notification
from marmot.domain.models.enums import AlertStage, AlertState, NotificationStatus, Severity


def _make_event(storage: MemoryStorage, **overrides) -> AlertEvent:
    defaults = dict(
        rule_name="test_rule",
        dedup_key="test_key",
        state=AlertState.PENDING,
        severity=Severity.WARNING,
        stage=AlertStage.THRESHOLD,
        labels={},
        fired_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return storage.create_alert_event(AlertEvent(**defaults))


def test_apply_updates_event_state():
    """应该能更新事件状态。"""
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage, SinkRegistry(), SystemClock())

    event = _make_event(storage)
    decision = Decision(
        new_state=AlertState.FIRING,
        event_patch={"consecutive_hits": 3},
        actions=[],
    )
    dispatcher.apply(event, decision)

    updated = storage.get_alert(event.id)
    assert updated.state == AlertState.FIRING
    assert updated.consecutive_hits == 3


def test_apply_notify_firing_calls_sink():
    """firing 决策应调用 sink。"""
    storage = MemoryStorage()
    sink_registry = SinkRegistry()
    sent = []

    def sink(n: Notification) -> bool:
        sent.append(n)
        return True

    sink_registry.register("console", sink)
    dispatcher = Dispatcher(storage, sink_registry, SystemClock())

    event = _make_event(storage, labels={"host": "server1"})
    decision = Decision(
        new_state=AlertState.FIRING,
        event_patch={},
        actions=[NotifyFiring(severity=Severity.WARNING, notify_targets=["console"])],
    )
    dispatcher.apply(event, decision)

    assert len(sent) == 1
    assert sent[0].rule_name == "test_rule"
    assert sent[0].sink_name == "console"


def test_apply_notify_resolved_calls_sink():
    """resolved 决策应调用 sink。"""
    storage = MemoryStorage()
    sink_registry = SinkRegistry()
    sent = []
    sink_registry.register("console", lambda n: sent.append(n) or True)
    dispatcher = Dispatcher(storage, sink_registry, SystemClock())

    event = _make_event(storage, state=AlertState.RESOLVING)
    decision = Decision(
        new_state=AlertState.RESOLVED,
        event_patch={},
        actions=[NotifyResolved(notify_targets=["console"])],
    )
    dispatcher.apply(event, decision)

    assert len(sent) == 1


def test_sink_writeback_message_is_persisted():
    """sink 写回 n.message 后，storage 持久化的应是写回值。"""
    storage = MemoryStorage()
    sink_registry = SinkRegistry()

    def sink(n: Notification) -> bool:
        n.message = "<rendered markdown content>"
        return True

    sink_registry.register("console", sink)
    dispatcher = Dispatcher(storage, sink_registry, SystemClock())

    event = _make_event(storage)
    decision = Decision(
        new_state=AlertState.FIRING,
        event_patch={},
        actions=[NotifyFiring(severity=Severity.WARNING, notify_targets=["console"])],
    )
    dispatcher.apply(event, decision)

    notifications = storage.list_notifications()
    assert len(notifications) == 1
    assert notifications[0].message == "<rendered markdown content>"
    assert notifications[0].stage is AlertStage.THRESHOLD
    assert notifications[0].status == NotificationStatus.SENT


def test_sink_returns_false_marks_failed():
    """sink 返回 False 应标记 FAILED 但仍持久化。"""
    storage = MemoryStorage()
    sink_registry = SinkRegistry()
    sink_registry.register("console", lambda n: False)
    dispatcher = Dispatcher(storage, sink_registry, SystemClock())

    event = _make_event(storage)
    decision = Decision(
        new_state=AlertState.FIRING,
        event_patch={},
        actions=[NotifyFiring(severity=Severity.WARNING, notify_targets=["console"])],
    )
    dispatcher.apply(event, decision)

    notifications = storage.list_notifications()
    assert len(notifications) == 1
    assert notifications[0].status == NotificationStatus.FAILED


def test_sink_raises_marks_failed_and_still_persists():
    """sink 抛异常时应标记 FAILED 并仍持久化。"""
    storage = MemoryStorage()
    sink_registry = SinkRegistry()

    def boom(n):
        raise RuntimeError("boom")

    sink_registry.register("console", boom)
    dispatcher = Dispatcher(storage, sink_registry, SystemClock())

    event = _make_event(storage)
    decision = Decision(
        new_state=AlertState.FIRING,
        event_patch={},
        actions=[NotifyFiring(severity=Severity.WARNING, notify_targets=["console"])],
    )
    dispatcher.apply(event, decision)

    notifications = storage.list_notifications()
    assert len(notifications) == 1
    assert notifications[0].status == NotificationStatus.FAILED


def test_record_called_after_sink():
    """持久化必须发生在 sink 调用之后（保证 sink 写回生效）。"""
    storage = MemoryStorage()
    sink_registry = SinkRegistry()
    order: list[str] = []

    original_record = storage.record_notification

    def spy_record(n):
        order.append("record")
        return original_record(n)

    storage.record_notification = spy_record  # type: ignore[method-assign]

    def sink(n: Notification) -> bool:
        order.append("sink")
        return True

    sink_registry.register("console", sink)
    dispatcher = Dispatcher(storage, sink_registry, SystemClock())

    event = _make_event(storage)
    decision = Decision(
        new_state=AlertState.FIRING,
        event_patch={},
        actions=[NotifyFiring(severity=Severity.WARNING, notify_targets=["console"])],
    )
    dispatcher.apply(event, decision)

    assert order == ["sink", "record"]
