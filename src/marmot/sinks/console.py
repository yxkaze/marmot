"""
默认控制台 sink（参考实现）。

仅用于 quickstart / 测试 / 排错。生产请按业务自行编写 sink。
"""
from typing import TextIO

from ..channels.console import ConsoleChannel
from ..domain.models.events import Notification
from .types import NotificationSink


def make_console_sink(
    channel: ConsoleChannel | None = None,
    *,
    output: TextIO | None = None,
) -> NotificationSink:
    """创建一个写入 ConsoleChannel 的 sink。

    生产请按业务自行编写 sink——这只是参考实现。

    :param channel: 注入的 ConsoleChannel 实例；若为 None 则按 ``output`` 创建新的
    :param output: ``channel`` 为 None 时，传给新建 ConsoleChannel 的输出流
    """
    ch = channel if channel is not None else ConsoleChannel(output=output)

    def sink(n: Notification) -> bool:
        ts = n.sent_at.strftime("%Y-%m-%d %H:%M:%S")
        state = n.state.value if n.state is not None else "UNKNOWN"
        severity = n.severity.value if n.severity is not None else "INFO"
        labels_str = " ".join(f"{k}={v}" for k, v in n.labels.items())
        line = (
            f"[{ts}] [{n.rule_name}] [{state}] [{severity}] "
            f"{labels_str} - {n.message}"
        )
        ch.write_line(line)
        # 写回：让审计记录看到实际打印的文本
        n.message = line
        return True

    return sink


# 默认 sink：绑定 sys.stdout
console_sink: NotificationSink = make_console_sink()
