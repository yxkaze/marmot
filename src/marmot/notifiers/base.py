"""
通知器 Protocol 定义。
"""
from typing import Protocol, Any


class Notifier(Protocol):
    """通知器 Protocol。"""
    
    def send(self, notification: Any) -> bool:
        """发送通知。返回是否成功。"""
        ...
