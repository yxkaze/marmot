# Marmot 架构设计

> 实际开发进度以 [`STATUS.md`](./STATUS.md) 为准。本文档描述目标架构与剩余路线图。
> 当前状态：MVP（Unit 1-7）+ Channel/Sink 重构（Unit 8）已完成。

---

## 0. 项目定位（不可破坏的约束）

- **嵌入式**：以库形式嵌入用户 Python 进程，无独立服务、无额外部署
- **0 运行时依赖**：只用 Python stdlib（含 `sqlite3` / `urllib`）
- **Python 3.10+**
- **同步友好**：对外 API 全部是普通同步函数，不暴露 `async`
- **框架不渲染通知内容**：用户在 Sink 内决定"发什么"，框架只决定"什么时候发"
- **目标能力**：
  - 阈值规则（多等级、连续次数、聚合窗口、静默窗口）
  - 手动 `fire` / `resolve`
  - 心跳 `ping` 与 `@job` 装饰器
  - Channel/Sink 通知（Console / InfoFlow 已实现，飞书 / 钉钉 / Webhook 待实现）
  - 升级策略（多级 `after_seconds`）
  - SQLite 持久化

---

## 1. 架构全景

自底向上 4 层。上层依赖下层，禁止反向依赖：

```
┌──────────────────────────────────────────────────────────┐
│ L4 Facade / Public API                                   │
│   marmot/__init__.py     → 顶层导出                        │
│   marmot/api.py          → MarmotApp（装配 + 门面方法）      │
├──────────────────────────────────────────────────────────┤
│ L3 Runtime（有状态、有线程）                                 │
│   runtime/registry.py    规则 / Sink 注册表                 │
│   runtime/clock.py       时间抽象（测试可注入）              │
│   runtime/dispatcher.py  把 Decision 落到存储 + 调用 Sink     │
│   runtime/bucket.py      滑动窗口指标缓冲（待实现）           │
│   runtime/scheduler.py   后台周期任务（待实现）              │
├──────────────────────────────────────────────────────────┤
│ L2 Adapters（可替换实现）                                   │
│   storage/base.py        Storage Protocol                │
│   storage/memory.py      内存实现                          │
│   storage/sqlite.py      SQLite 实现（待实现）              │
│   channels/base.py       ChannelError / RateLimitError    │
│   channels/console.py    ConsoleChannel                  │
│   channels/infoflow.py   InfoFlowChannel（如流机器人）       │
│   channels/{feishu,dingtalk,webhook}.py  待实现            │
│   sinks/types.py         NotificationSink = Callable      │
│   sinks/console.py       默认 console_sink                │
├──────────────────────────────────────────────────────────┤
│ L1 Domain（纯逻辑，无 I/O，无线程）                          │
│   domain/models/*        dataclass + 枚举                 │
│   domain/state_machine.py  AlertStateMachine.transition   │
│   domain/decisions.py    Decision / SideEffect             │
│   domain/evaluator.py    ThresholdEvaluator              │
│   domain/aggregator.py   聚合计算（待实现）                  │
│   domain/escalation.py   升级判定（待实现）                  │
└──────────────────────────────────────────────────────────┘
```

**核心思想**：领域层全部是纯函数或纯 dataclass。一次 `report()` 的路径是：
`Facade → Evaluator(纯) → StateMachine(纯) → Decision(数据) → Dispatcher(副作用) → Storage / Sink`

---

## 2. Channel vs Sink（关键区分）

Unit 8 的核心架构决策：把"渲染通知内容"和"调用平台 API"分开。

| 层 | 是什么 | 谁的职责 | 是否感知 Notification |
|---|---|---|---|
| **Channel** | 平台原生 SDK（如 `InfoFlowChannel.send_text(...)`） | 框架提供 | ❌ 不感知 |
| **Sink** | `Callable[[Notification], bool]` | 用户编写（或用框架默认） | ✅ 感知 |

**为什么这么设计**：原 `Notifier.send(notification)` 抽象屏蔽了 IM 平台的原生能力（卡片、@、图片、Markdown）。框架不应替用户决定"发什么"，所以：

- **Channel 无状态**：纯机械 SDK，不知道 AlertState / Severity
- **Sink 由用户写**：决定从 Notification 里取什么字段、用 Channel 的哪个方法、渲染成什么格式
- **Sink 可以写回**：在 sink 内修改 `notification.message` / `notification.labels`，dispatcher 在 sink 返回后才持久化，实际发送内容会进入审计

**Dispatcher 顺序保证**：

```python
sink = self.sink_registry.get(target)
try:
    success = bool(sink(notification))   # 先调 sink，允许写回
    notification.status = SENT if success else FAILED
except Exception:
    notification.status = FAILED
self.storage.record_notification(notification)  # 后持久化，写回生效
```

---

## 3. 模块职责

| 层 | 模块 | 职责 |
| --- | --- | --- |
| L1 | `domain.models.*` | 枚举、Rule、ThresholdRule、ThresholdLevel、EscalationStep、AlertEvent、RunRecord、Notification |
| L1 | `domain.keys` / `time_utils` | dedup key、标签规范化、时间工具 |
| L1 | `domain.state_machine` | 纯函数 `transition(...) -> Decision` |
| L1 | `domain.decisions` | `Decision` + `SideEffect` 并集（NotifyFiring / NotifyResolved / EnterSilence / ...） |
| L1 | `domain.evaluator` | `ThresholdEvaluator.evaluate(...) -> Observation` |
| L1 | `domain.aggregator` | 聚合计算（Unit 待规划） |
| L1 | `domain.escalation` | 升级判定（Unit 11） |
| L2 | `storage.base` | `Storage` Protocol |
| L2 | `storage.memory` | 内存实现 |
| L2 | `storage.sqlite` | SQLite 实现（Unit 9） |
| L2 | `channels.*` | 平台原生 SDK，纯机械调用，失败抛 `ChannelError` |
| L2 | `sinks.*` | `Callable[[Notification], bool]`；默认提供 `console_sink` |
| L3 | `runtime.clock` | `Clock` Protocol + `SystemClock` |
| L3 | `runtime.registry` | `RuleRegistry` / `SinkRegistry` |
| L3 | `runtime.dispatcher` | 应用 Decision：写 event、调 sink、记录 notification |
| L3 | `runtime.bucket` | 线程安全滑动窗口（待实现） |
| L3 | `runtime.scheduler` | 后台周期任务：心跳超时扫描、升级扫描、静默到期（Unit 10） |
| L4 | `api.MarmotApp` | 组装 + 门面方法 `report / fire / ping / resolve / job / register_*` |
| L4 | `__init__` | 顶层导出 |

---

## 4. 依赖关系与数据流

### 4.1 依赖图

```
__init__  ──►  api.MarmotApp
                │
                ├──►  runtime.registry
                ├──►  runtime.dispatcher ──► storage.* (Protocol)
                │                       └─► sink_registry ──► sinks(用户) ──► channels.*
                ├──►  runtime.scheduler ──► domain.escalation
                ├──►  runtime.clock
                └──►  domain.evaluator / state_machine / decisions
```

- `domain/*` 不依赖 `runtime / storage / channels / sinks`
- `runtime/*` 依赖 `domain` + `storage.base`（Protocol），不依赖具体实现
- `channels/*` 不感知 `domain` 类型，只是 SDK
- `sinks/*` 是连接 `domain.Notification` 与 `channels.*` 的胶水层

### 4.2 `report()` 数据流

```
user.report(name, value, labels)
 │
 ▼ api.MarmotApp.report
 │   rule = registry.get_threshold_rule(name)
 │
 ▼ evaluator.ThresholdEvaluator.evaluate(rule, value, labels, prior_event, now)
 │   → Observation{hit, miss, matched_severity, dedup_key}
 │
 ▼ state_machine.transition(prior_event, observation, now)
 │   → Decision{new_state, event_patch, actions=[NotifyFiring|EnterSilence|...]}
 │
 ▼ dispatcher.apply(decision)
 │   ├─ storage.create_or_update_alert_event(...)
 │   └─ for a in decision.actions:
 │        NotifyXxx     → 构造 Notification → sink_registry[target](notification)
 │                                        → 持久化 notification（含 sink 写回）
 │        EnterSilence  → 仅更新 event 字段
```

### 4.3 升级扫描数据流（Unit 11）

```
scheduler (每 N 秒)
 → storage.list_active_alerts()
 → for e in events:
     decision = escalation.evaluate(e, now)
     if decision.should_escalate:
         dispatcher.apply(decision)
```

---

## 5. 技术选型与理由

| 项 | 选择 | 理由 |
| --- | --- | --- |
| 持久化 | SQLite（通过 `Storage` Protocol） | 0 依赖；Protocol 让内存/其他实现可插拔 |
| 并发 | `threading` + `RLock` | 与同步对外 API 一致；不引入 asyncio 传染 |
| 通知扩展 | Channel（SDK）+ Sink（Callable） | 框架不渲染；用户决定"发什么"；Channel 可独立测试 |
| HTTP | stdlib `urllib.request` | 0 依赖；够用 |
| 时间 | 自建 `Clock` Protocol + `SystemClock` | 测试可注入 `FakeClock`；避免散落 `datetime.now` |
| 状态机 | 纯函数 + `Decision` dataclass | 0 依赖；天然可单测 |
| 类型 | `typing.Protocol` + `@dataclass(slots=True)` | Protocol 取代 ABC，减少继承耦合 |
| 测试 | `pytest`（仅 dev 依赖） | 业界共识 |
| 配置 | `configure(...)` 关键字参数 | 避免引入 pydantic/yaml |
| 日志 | stdlib `logging`，logger 名 `marmot.<module>` | 与宿主工程一致 |
| 打包 | 单包 `marmot`，`src/` 布局 | 嵌入式库的常规形态 |

**显式拒绝**：`asyncio` / `pydantic` / `sqlalchemy` / `apscheduler` / `fastapi` / `httpx` / `requests` / ORM。

---

## 6. 对外暴露的接口

### 6.1 模块级

```python
import marmot

app = marmot.MarmotApp(...)
app.register_threshold_rule(rule)
app.register_rule(rule)                    # 心跳/Job
app.register_sink(name, sink)              # sink 是 Callable[[Notification], bool]
app.report(name, value, labels)
app.fire(name, *, severity, labels=None, message="")    # 待实现
app.ping(name, *, status="success", labels=None)        # 待实现
app.resolve(name, *, labels=None)                       # 待实现

@app.job(name, *, on_failure_severity="error")          # 待实现
def task(): ...
```

### 6.2 只读查询

```python
app.list_active_alerts() -> list[AlertEvent]
app.list_alert_history(limit=100) -> list[AlertEvent]
```

### 6.3 扩展点（Protocol / 类型别名）

```python
class Storage(Protocol):              # storage/base.py
class Clock(Protocol):                # runtime/clock.py
NotificationSink = Callable[[Notification], bool]   # sinks/types.py
```

Channel 不是 Protocol，每个 Channel 类各自定义自己的方法签名（暴露平台原生能力）。

### 6.4 Sink 编写示例

```python
from marmot.channels.infoflow import InfoFlowChannel

channel = InfoFlowChannel(webhook_url="...", secret="...")

def my_alert_sink(n: Notification) -> bool:
    text = f"[{n.severity.name}] {n.rule_name}: {n.message}"
    n.message = text   # 写回，会进入审计
    try:
        channel.send_text(text, at_user_ids=["zhangsan"])
        return True
    except ChannelError:
        return False

app.register_sink("oncall", my_alert_sink)
```

---

## 7. 路线图

实际进度参见 [`STATUS.md`](./STATUS.md)。下面只列剩余 Unit。

### 已完成（Unit 1-9）

工程骨架、领域模型、状态机、Storage Protocol + 内存实现、Clock + Registry、ThresholdEvaluator、Dispatcher + MarmotApp、Channel/Sink 架构（含 InfoFlowChannel）、SQLiteStorage 持久化。

### Unit 10 — 后台调度器
- `src/marmot/runtime/scheduler.py`：`schedule(name, period, fn) + start/stop`
- 解决"被动模式"问题：心跳超时、静默到期、升级触发都需要时间驱动
- `MarmotApp.start() / stop()` 生命周期，2s 内优雅关闭
- 测试用 `FakeClock` 推进时间，不真 sleep

### Unit 11 — 升级策略
- `src/marmot/domain/escalation.py`：纯函数 `should_escalate(event, steps, now)`
- Scheduler 周期性扫描活跃告警，触发 `NotifyEscalated` / `MarkEscalated`
- 支持多级 `after_seconds`，可改 severity / notify targets

### Unit 12 — 飞书 / 钉钉 / Webhook Channel
- `src/marmot/channels/feishu.py`（含签名）
- `src/marmot/channels/dingtalk.py`（含 HMAC 签名）
- `src/marmot/channels/webhook.py`（通用 HTTP POST JSON）
- 全部用 stdlib `urllib`；测试用 `monkeypatch` 拦截 `urlopen`

### Unit 13 — REST API + WebSocket（可选，优先级低）
- 仅在用户需要"非 Python 服务接入" / "实时大屏"时再做
- 可能不内置，改为放在 `examples/` 演示 FastAPI 包装方式（保持 0 依赖原则）

### 未排期 / 待评估
- 聚合窗口（`runtime.bucket` + `domain.aggregator`）
- 心跳 + Job 装饰器 + 手动 `fire/resolve`
- 异步通知队列（目前同步 sink，慢 sink 会阻塞 `report()`）
- EmailSink

---

## 8. 验收标准

- `pytest -v` 全绿
- 任一源文件 ≤ 300 行
- `src/marmot/api.py` ≤ 300 行
- 运行时 0 第三方依赖（`pyproject.toml` 的 `dependencies = []`）
- Channel 测试全部用 `monkeypatch` 拦截 `urllib.request.urlopen`，零真实网络

---

## 9. 关键设计原则（回顾）

1. **领域层纯净**：`domain/*` 无 I/O、无线程、无外部依赖
2. **Protocol 优先**：用 `typing.Protocol` 而非 ABC，减少继承耦合
3. **框架不渲染通知**：Channel 暴露能力，Sink 由用户决定格式
4. **Sink 写回 + 后置持久化**：审计 + 用户控制权两者兼得
5. **0 依赖坚持**：HTTP 用 `urllib`，DB 用 `sqlite3`，调度用 `threading`
6. **Clock 抽象**：所有时间相关测试都注入 `FakeClock`，禁用真 sleep
