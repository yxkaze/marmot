"""
渠道层公共类型。

Channel 不强制使用 Protocol：每个渠道按自己原生能力命名方法，
签名不强行统一。这里只定义共享的异常类型。
"""


class ChannelError(Exception):
    """渠道调用失败的统一异常基类。

    HTTP 错误、网络异常、参数无效等都包装成此异常或其子类抛出。
    """


class RateLimitError(ChannelError):
    """被渠道侧限流（如机器人发消息超出每分钟配额）。"""
