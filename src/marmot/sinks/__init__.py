"""
Sink 层。

Sink 是 ``Callable[[Notification], bool]``——框架不再定义 Notifier
Protocol / 基类。用户写函数、lambda 或带 __call__ 的类都行。

Sink 在调 channel 后，应将"实际发出去的内容"写回 ``notification.message``，
让 Dispatcher 持久化的审计记录看到真实内容。详见 ``types`` 模块的 docstring。
"""
from .types import NotificationSink
from .console import console_sink, make_console_sink

__all__ = [
    "NotificationSink",
    "console_sink",
    "make_console_sink",
]
