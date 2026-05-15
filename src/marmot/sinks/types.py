"""
Sink 类型别名。

Sink 不是 Protocol、不是基类——只是类型提示。运行期是普通 callable。
"""
from typing import Callable

from ..domain.models.events import Notification

NotificationSink = Callable[[Notification], bool]
"""通知 Sink 类型别名。

返回 ``True`` 表示发送成功，``False`` 表示失败。
异常会被 Dispatcher 捕获并视为失败。

写回约定（重要）
================
``Notification`` 是 mutable dataclass，sink 可以直接修改字段：

- 推荐：``n.message = <实际发出去的内容>``，让审计记录看到真实内容
- 可选：``n.labels[...] = <额外信息>``（如 channel 的 trace_id / response）

框架不强制写回；不写回时 ``message`` 保留为状态枚举值
（"firing" / "resolved" / ...），仍能查到事件、sink、时间、成败等基础事实。
"""
