"""
渠道（Channel）层。

每个 Channel 是一个纯渠道 SDK，按渠道原生能力暴露发送方法
（send_text / send_markdown / send_image / ...），不感知 Notification
与告警语义，可独立复用与单测。
"""
from .base import ChannelError, RateLimitError
from .console import ConsoleChannel
from .infoflow import InfoFlowChannel

__all__ = [
    "ChannelError",
    "RateLimitError",
    "ConsoleChannel",
    "InfoFlowChannel",
]
