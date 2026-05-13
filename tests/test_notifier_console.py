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
    assert "error" in text
