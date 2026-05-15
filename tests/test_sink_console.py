"""console_sink 测试。"""
import io
from datetime import datetime, UTC

from marmot.channels.console import ConsoleChannel
from marmot.domain.models.enums import AlertState, NotificationStatus, Severity
from marmot.domain.models.events import Notification
from marmot.sinks.console import make_console_sink


def _make_notification() -> Notification:
    return Notification(
        alert_event_id=1,
        rule_name="cpu_high",
        dedup_key="cpu_high|host=h1",
        status=NotificationStatus.PENDING,
        state=AlertState.FIRING,
        severity=Severity.WARNING,
        labels={"host": "h1"},
        message="firing",
        sink_name="console",
        sent_at=datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC),
    )


def test_console_sink_writes_line_and_returns_true():
    """sink 返回 True 且向 ConsoleChannel 写入了文本。"""
    buf = io.StringIO()
    sink = make_console_sink(channel=ConsoleChannel(output=buf))

    n = _make_notification()
    assert sink(n) is True

    output = buf.getvalue()
    assert "cpu_high" in output
    assert "firing" in output
    assert "warning" in output
    assert "host=h1" in output
    assert output.endswith("\n")


def test_console_sink_writes_back_message():
    """sink 应把实际打印的文本写回 notification.message，便于审计。"""
    buf = io.StringIO()
    sink = make_console_sink(channel=ConsoleChannel(output=buf))

    n = _make_notification()
    assert n.message == "firing"  # 进入 sink 前是状态摘要
    sink(n)

    # 写回后 message 等于打印行（去掉行末换行）
    expected_line = buf.getvalue().rstrip("\n")
    assert n.message == expected_line


def test_make_console_sink_with_output_kwarg():
    """make_console_sink 也支持直接传 output。"""
    buf = io.StringIO()
    sink = make_console_sink(output=buf)

    sink(_make_notification())
    assert buf.getvalue() != ""
