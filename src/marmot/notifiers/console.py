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
