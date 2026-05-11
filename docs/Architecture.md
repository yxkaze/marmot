# Marmot 从零重写架构设计（Greenfield Rebuild）

> 本文档描述的是 **在一个空白分支上从 0 开始重新实现 marmot** 的架构与开发路线。
> 现有 `main` 分支代码仅作为 **功能参考与行为基准**，不直接复用任何文件。
> 每个开发单元完成后，项目处于一个"能跑起来、能演示、能测试"的自洽状态，逐步逼近完整功能。

---

## 0. 项目定位（重申不可破坏的约束）

- **嵌入式**：以库形式嵌入用户 Python 进程，无独立服务、无额外部署
- **0 运行时依赖**：只用 Python stdlib + SQLite（`sqlite3` 也是 stdlib）
- **Python 3.10+**
- **同步友好**：对外 API 全部是普通同步函数，不暴露 `async`
- **功能对齐目标**（来自 main 分支的既有能力）：
  - 阈值规则（多等级、连续次数、聚合窗口、静默窗口）
  - 手动 `fire` / `resolve`
  - 心跳 `ping` 与 `@job` 装饰器
  - 多通道通知（Console / Webhook / Markdown Webhook / 钉钉 / 企微 / 飞书 / Email / Phone）
  - 升级策略（多级 `after_seconds`）
  - SQLite 持久化
  - 内置 Web 控制台（只读）
  - 模块级便捷 API：`marmot.configure/report/fire/ping/resolve/job/shutdown`

---

## 1. 分支策略（建议）

当前 `refactor/architecture-redesign` 是从 `main` 拉出来的，仍带有完整历史与文件。"从零开发"的语义最好用 **orphan 分支**：

```
git checkout --orphan rebuild/v2
git rm -rf .                    # 清空工作区
# 逐步按 Unit 1..N 新建文件
```

这样分支里只有你新写的文件，没有历史包袱。现有的 `refactor/architecture-redesign` 可以删掉，或者保留它只放 `ARCHITECTURE.md` 作为规划文档。

**待确认**：是否按上面方式切换到 orphan 分支？（代码实现阶段再执行，不影响本设计稿）

---

## 2. 架构全景（目标形态）

自底向上 4 层。上层依赖下层，禁止反向依赖：

```
┌──────────────────────────────────────────────────────────┐
│ L4 Facade / Public API                                   │
│   marmot/__init__.py     → 模块级便捷函数 + 单例            │
│   marmot/api.py          → MarmotApp（装配 + 门面方法）      │
├──────────────────────────────────────────────────────────┤
│ L3 Runtime（有状态、有线程）                                 │
│   runtime/registry.py    规则 / 通知器注册表                │
│   runtime/clock.py       时间抽象（测试可注入）              │
│   runtime/bucket.py      滑动窗口指标缓冲                   │
│   runtime/dispatcher.py  把 Decision 落到存储 + 通知队列     │
│   runtime/notify_queue.py 有界队列 + worker 线程池           │
│   runtime/scheduler.py   后台周期任务（升级扫描等）           │
├──────────────────────────────────────────────────────────┤
│ L2 Adapters（可替换实现）                                   │
│   storage/base.py        Storage Protocol                │
│   storage/memory.py      内存实现（用于早期单元 + 测试）      │
│   storage/sqlite.py      SQLite 实现                      │
│   notifiers/base.py      Notifier Protocol + HTTP 工具     │
│   notifiers/{console,webhook,dingtalk,wecom,feishu,...}.py │
│   web/server.py + handlers.py + read_model.py             │
├──────────────────────────────────────────────────────────┤
│ L1 Domain（纯逻辑，无 I/O，无线程）                          │
│   domain/models.py       dataclass + 枚举                 │
│   domain/keys.py         dedup key / 标签规范化             │
│   domain/time_utils.py   utcnow / parse_duration          │
│   domain/state_machine.py  AlertStateMachine.transition   │
│   domain/decisions.py    Decision / SideEffect             │
│   domain/evaluator.py    ThresholdEvaluator 等             │
│   domain/aggregator.py   聚合计算                          │
│   domain/escalation.py   升级判定                          │
└──────────────────────────────────────────────────────────┘
```

**核心思想**：领域层全部是纯函数或纯 dataclass。一次 `report()` 的路径是：
`Facade → Evaluator(纯) → StateMachine(纯) → Decision(数据) → Dispatcher(副作用) → Storage / NotifyQueue`

---

## 3. 模块职责详表

| 层 | 模块 | 职责 | 不做什么 |
| --- | --- | --- | --- |
| L1 | `domain.models` | 所有数据类与枚举：`AlertEvent / Rule / ThresholdRule / ThresholdLevel / EscalationStep / RunRecord / Notification / AggregateConfig` 及枚举 | 不做 I/O，不知道存储格式 |
| L1 | `domain.keys` | `build_dedup_key(rule_name, labels)`、`normalize_notify` | 不接触状态 |
| L1 | `domain.time_utils` | `utcnow / to_iso / from_iso / parse_duration` | 不用 `time.monotonic` |
| L1 | `domain.state_machine` | 纯函数 `transition(event, hit, miss, now, force_fire, silence_expired) -> Decision` | 不写库、不发通知 |
| L1 | `domain.decisions` | `Decision(new_state, event_patch, actions: list[SideEffect])`；`SideEffect` 为封闭并集：`NotifyFiring / NotifyResolved / NotifyEscalation / EnterSilence / EnterResolving / MarkEscalated` | 不执行 |
| L1 | `domain.evaluator` | `ThresholdEvaluator.evaluate(rule, value, labels, prior_event, now)` 返回 `Observation(hit, miss, matched_severity, dedup_key)`；同理 `HeartbeatEvaluator`、`JobEvaluator` | 不动存储、不操作 Bucket |
| L1 | `domain.aggregator` | 给定 Bucket 快照 + 聚合配置，返回有效观测值 | 不存窗口数据 |
| L1 | `domain.escalation` | `should_escalate(event, steps, now) -> EscalationDecision` | 不调度 |
| L2 | `storage.base` | `Storage` Protocol（rule / threshold_rule / alert_event / run / notification 的 CRUD） | 不绑定实现 |
| L2 | `storage.memory` | 基于 `dict` 的实现，便于早期单元/测试 | 不持久化 |
| L2 | `storage.sqlite` | SQLite 实现 + 建表语句 + 线程安全 RLock + WAL | 不包含业务语义 |
| L2 | `notifiers.base` | `Notifier` Protocol；通用 HTTP POST、severity/state 标签表 | 不含具体渠道 |
| L2 | `notifiers.*` | 每个渠道一个文件，独立格式化 | 不感知状态机 |
| L2 | `web.read_model` | 提供 UI 只读查询（聚合多条 storage 调用） | 不改状态 |
| L2 | `web.handlers` | HTTP endpoint 实现，调用 `read_model` | 不直接摸 Storage |
| L2 | `web.server` | `ThreadingHTTPServer` 封装，daemon 线程启停 | 不含路由逻辑 |
| L3 | `runtime.clock` | `Clock` 协议 + `SystemClock` 默认实现 | 仅两个方法 |
| L3 | `runtime.bucket` | 线程安全滑动窗口（`deque + Lock`） | 不知道规则类型 |
| L3 | `runtime.registry` | 规则/通知器注册表 | 不驱动状态机 |
| L3 | `runtime.notify_queue` | 有界队列 + 固定 worker；溢出策略 `drop_oldest/drop_new/block` | 不关心通知内容组装 |
| L3 | `runtime.dispatcher` | 消费 `Decision`：写 event、记录 run、入通知队列、排期升级 | 不做决策 |
| L3 | `runtime.scheduler` | 统一周期任务 `schedule(name, period, fn)`；`start/stop` | 不关心任务内容 |
| L4 | `api.MarmotApp` | 组装所有组件；门面方法 `report/fire/ping/resolve/job/register_*/shutdown/list_*` | 不含判定逻辑 |
| L4 | `__init__` | 模块级单例 + 便捷函数 + 公开符号集合 | 不含实现 |

---

## 4. 依赖关系与数据流

### 4.1 依赖图

```
__init__  ──►  api.MarmotApp
                │
                ├──►  runtime.registry
                ├──►  runtime.dispatcher ──► storage.* (Protocol)
                │                       └─► runtime.notify_queue ──► notifiers.*
                ├──►  runtime.scheduler ──► domain.escalation
                ├──►  runtime.bucket
                ├──►  runtime.clock
                └──►  domain.evaluator / state_machine / decisions / aggregator

web.server ──► web.handlers ──► web.read_model ──► storage.* (Protocol)
```

- `domain/*` 不依赖 `runtime / storage / notifiers / web`
- `runtime/*` 依赖 `domain` 与 `storage.base`（Protocol），不依赖具体 storage/notifier
- `web/*` 只经由 `read_model` 查存储，不调用 `api`

### 4.2 `report()` 数据流（阈值 + 标签模式）

```
user.report(name, value, labels)
 │
 ▼ api.MarmotApp.report
 │   rule = registry.get_threshold_rule(name)
 │   若聚合模式: bucket.add → aggregator.evaluate 得到 (trigger, value)
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
 │        NotifyXxx     → notify_queue.put(Notification)
 │        EnterSilence  → 仅更新 event 字段
 │        MarkEscalated → 仅更新 event 字段
 │
 ▼ notify_queue worker
     → notifiers[target].send(Notification)
     → storage.record_notification(status)
```

`fire / ping / resolve / @job` 走同一管线，只是 Evaluator 不同。

### 4.3 升级扫描数据流

```
scheduler (每 N 秒)
 → storage.list_escalatable_alerts()
 → for e in events:
     decision = escalation.evaluate(e, now)
     if decision.should_escalate:
         dispatcher.apply(decision)  # 写库 + 入队通知
```

---

## 5. 技术选型与理由

| 项 | 选择 | 理由 |
| --- | --- | --- |
| 持久化 | SQLite（通过 `Storage` Protocol） | 0 依赖硬约束；Protocol 让内存/其他实现可插拔 |
| 并发 | `threading` + `queue.Queue` | 与同步对外 API 一致；不引入 asyncio 传染 |
| 通知异步 | 有界队列 + 固定 worker 线程（默认 2） | 慢通道不阻塞 `report()`；溢出策略显式可配 |
| 时间 | 自建 `Clock` Protocol + `SystemClock` | 测试可注入 `FakeClock`；避免散落 `datetime.now` |
| 状态机 | 纯函数 + `Decision` dataclass | 0 依赖；天然可单测 |
| Web | `http.server.ThreadingHTTPServer` | 0 依赖；只作调试只读面板 |
| 类型 | `typing.Protocol` + `@dataclass(slots=True)` | Protocol 取代 ABC，减少继承耦合 |
| 测试 | `pytest`（仅 dev 依赖） | 业界共识，足够轻 |
| 配置 | `configure(db_path, **options)` 关键字参数 | 避免引入 pydantic/yaml |
| 日志 | stdlib `logging`，logger 名 `marmot.<module>` | 与宿主工程一致 |
| 打包 | 单包 `marmot`，`src/` 布局 | 嵌入式库的常规形态 |
| HTML 资源 | 模板放 `web/assets/index.html`，用 `importlib.resources` 读取 | 避免 Python 字符串混编 |

**显式拒绝**：`asyncio` / `pydantic` / `sqlalchemy` / `apscheduler` / `fastapi` / 第三方 HTTP 客户端 / ORM。

---

## 6. 对外暴露的接口

### 6.1 模块级（保持与现行一致的使用习惯）

```python
marmot.configure(db_path: str, **options) -> MarmotApp
marmot.get_app() -> MarmotApp
marmot.shutdown() -> None

marmot.register_rule(rule: Rule) -> None
marmot.register_threshold_rule(rule: ThresholdRule) -> None
marmot.register_notifier(name: str, notifier: Notifier) -> None

marmot.report(name: str, value: float, labels: dict | None = None) -> None
marmot.fire(name: str, *, severity: str, labels: dict | None = None, message: str = "") -> str
marmot.ping(name: str, *, status: str = "success", labels: dict | None = None) -> None
marmot.resolve(name: str, *, labels: dict | None = None) -> None

@marmot.job(name: str, *, on_failure_severity: str = "error")
def task(): ...

marmot.start_ui_server(host="127.0.0.1", port=8765) -> UIServer
```

### 6.2 `configure` 支持的选项

```python
marmot.configure(
    db_path: str,
    notify_workers: int = 2,
    notify_queue_size: int = 1024,
    notify_overflow: Literal["drop_oldest","drop_new","block"] = "drop_oldest",
    escalation_interval: float = 10.0,
    clock: Clock | None = None,
    storage: Storage | None = None,   # 可注入替代实现
) -> MarmotApp
```

### 6.3 `MarmotApp` 上的只读查询

```python
app.list_active_alerts() -> list[AlertEvent]
app.list_alert_history(limit: int = 100) -> list[AlertEvent]
app.list_recent_runs(limit: int = 100) -> list[RunRecord]
app.list_notifications(alert_id: str | None = None, limit: int = 100) -> list[Notification]
app.get_alert(alert_id: str) -> AlertEvent | None
```

### 6.4 扩展点（Protocol）

```python
class Storage(Protocol):   # 见 storage/base.py
class Notifier(Protocol):  # send(n: Notification) -> bool
class Clock(Protocol):     # now() -> datetime; monotonic() -> float
```

---

## 7. 开发单元清单（从空白分支起步，按依赖顺序）

每个单元作为一个可独立落地的 milestone：有明确的新增文件、有可运行/可测试的行为。**每个单元结束时 `pytest -v` 必须全绿**。

---

### Unit 1 — 工程骨架
- **新建文件**：
  - `pyproject.toml`（包名 marmot，Python 3.10+，dev: pytest）
  - `src/marmot/__init__.py`（仅 `__version__`）
  - `README.md`（最小说明）
  - `.gitignore`
  - `tests/__init__.py`、`tests/test_smoke.py`（`import marmot` 即通过）
- **可验证行为**：
  - `pip install -e ".[dev]"` 成功
  - `python -c "import marmot; print(marmot.__version__)"` 输出版本
  - `pytest -v` 至少 1 个用例通过

---

### Unit 2 — 领域数据类与枚举
- **新建文件**：
  - `src/marmot/domain/__init__.py`
  - `src/marmot/domain/models.py`（`AlertState / Severity / AlertStage / RunStatus / NotificationStatus / AggregateFn / Rule / ThresholdRule / ThresholdLevel / EscalationStep / AlertEvent / RunRecord / Notification / AggregateConfig`）
  - `src/marmot/domain/time_utils.py`（`utcnow / to_iso / from_iso / parse_duration`）
  - `src/marmot/domain/keys.py`（`build_dedup_key / normalize_notify`）
  - `tests/test_domain_models.py`
- **可验证行为**：
  - 数据类可构造；`to_dict` / `from_dict` 圆桌可逆
  - `parse_duration("5m") == 300`
  - `build_dedup_key("cpu", {"host":"a"})` 稳定

---

### Unit 3 — 纯状态机
- **新建文件**：
  - `src/marmot/domain/decisions.py`（`Decision`, `SideEffect` 并集）
  - `src/marmot/domain/state_machine.py`（`AlertStateMachine.transition`，纯函数）
  - `tests/test_state_machine.py`（覆盖 `PENDING→FIRING`、`FIRING→RESOLVING→RESOLVED`、`SILENCED` 进入/退出、`force_fire`、`ESCALATED→RESOLVING` 等所有分支）
- **可验证行为**：所有状态分支单测通过；该模块不 import 任何 `runtime/storage/notifiers`

---

### Unit 4 — Storage Protocol + 内存实现
- **新建文件**：
  - `src/marmot/storage/__init__.py`
  - `src/marmot/storage/base.py`（`Storage` Protocol）
  - `src/marmot/storage/memory.py`（基于 dict/list 的实现）
  - `tests/test_storage_memory.py`
- **可验证行为**：CRUD 往返（创建/查询/更新/列表）通过；线程安全基础（加锁）

---

### Unit 5 — Clock + Registry
- **新建文件**：
  - `src/marmot/runtime/__init__.py`
  - `src/marmot/runtime/clock.py`（`Clock` Protocol + `SystemClock` + 测试用 `FakeClock` 放在 tests 下）
  - `src/marmot/runtime/registry.py`（`RuleRegistry` / `NotifierRegistry`）
  - `tests/test_clock.py`、`tests/test_registry.py`
- **可验证行为**：注册/查询/删除；`FakeClock.advance(seconds)` 可控推进

---

### Unit 6 — Evaluator（最小可用：阈值标签模式）
- **新建文件**：
  - `src/marmot/domain/evaluator.py`（`ThresholdEvaluator.evaluate(...)` 返回 `Observation`）
  - `tests/test_evaluator_threshold.py`
- **可验证行为**：多等级匹配选取最高匹配 severity；`hit/miss` 计数正确

---

### Unit 7 — Dispatcher + 最小 MarmotApp + 同步通知
- **新建文件**：
  - `src/marmot/notifiers/__init__.py`
  - `src/marmot/notifiers/base.py`（`Notifier` Protocol）
  - `src/marmot/notifiers/console.py`（`ConsoleNotifier`）
  - `src/marmot/runtime/dispatcher.py`（同步版本：直接调 `Notifier.send`）
  - `src/marmot/api.py`（`MarmotApp`，目前支持 `register_threshold_rule / register_notifier / report`）
  - `src/marmot/__init__.py` 更新：导出 `configure / get_app / register_* / report / ConsoleNotifier / ThresholdRule / ThresholdLevel`
  - `tests/test_report_pipeline.py`
  - `examples/quickstart.py`（能跑通一个最小 demo）
- **可验证行为**：
  - 在内存存储 + ConsoleNotifier 上，阈值触发 3 次后 stdout 打印 firing
  - 连续 miss 后打印 resolved
  - `examples/quickstart.py` 可运行

> **里程碑 M1**：到此项目已是一个"能用的告警框架"（无持久化 / 无聚合 / 无升级 / 无 Web）。

---

### Unit 8 — SQLite Storage
- **新建文件**：
  - `src/marmot/storage/sqlite.py`（建表 + CRUD + RLock + WAL）
  - `tests/test_storage_sqlite.py`（用 `tmp_path` fixture）
  - `api.MarmotApp`：`configure(db_path=...)` 默认构造 `SQLiteStorage`
- **可验证行为**：与 `storage.memory` 同一组契约测试跑通；进程重启后 active alert 仍在

---

### Unit 9 — 聚合窗口
- **新建文件**：
  - `src/marmot/runtime/bucket.py`
  - `src/marmot/domain/aggregator.py`
  - `api.MarmotApp.report` 在 `rule.aggregate` 存在时走聚合分支
  - `tests/test_bucket.py`、`tests/test_aggregate.py`
- **可验证行为**：avg/max/min/sum/count 正确；窗口外数据被剪枝；聚合规则按 rule name 去重

---

### Unit 10 — 心跳 + Job 装饰器 + 手动 fire/resolve
- **新建文件/改动**：
  - `src/marmot/domain/evaluator.py` 新增 `HeartbeatEvaluator / JobEvaluator`
  - `api.MarmotApp`：`fire / ping / resolve / job` 方法
  - `src/marmot/__init__.py` 导出 `fire / ping / resolve / job / register_rule / Rule`
  - `tests/test_heartbeat.py`、`tests/test_job.py`、`tests/test_manual_fire_resolve.py`
- **可验证行为**：
  - 心跳超时后产生 firing；下一次 ping 自动 resolve
  - `@job` 装饰的函数抛异常 → firing；成功 → resolve；`RunRecord` 有 duration/status

---

### Unit 11 — 异步通知队列
- **新建文件/改动**：
  - `src/marmot/runtime/notify_queue.py`（有界队列 + N 个 worker + 溢出策略）
  - `dispatcher` 改为把 `NotifyXxx` SideEffect 塞入队列
  - `api.MarmotApp.shutdown` 优雅停机（等队列排空或超时）
  - `tests/test_notify_queue.py`（慢通知器不阻塞 report；溢出策略）
- **可验证行为**：
  - 一个 sleep 2s 的假通知器存在时，`report()` 本身耗时 ≈ 0
  - 队列满触发 `drop_oldest` 有 warning 日志
  - `shutdown()` 能在 2s 内停止所有 worker

---

### Unit 12 — 升级策略 + Scheduler
- **新建文件/改动**：
  - `src/marmot/domain/escalation.py`（`should_escalate(event, steps, now)`）
  - `src/marmot/runtime/scheduler.py`（`schedule(name, period, fn) + start/stop`）
  - `api.MarmotApp` 组装：启动时用 scheduler 跑升级扫描
  - `tests/test_escalation.py`（FakeClock 驱动，不用 sleep）
- **可验证行为**：FIRING 超过第 N 级 `after_seconds` → 状态变 ESCALATED，按升级 targets 派发通知

---

### Unit 13 — 外部通知渠道
- **新建文件**：
  - `src/marmot/notifiers/webhook.py`（`WebhookNotifier / MarkdownWebhookNotifier`）
  - `src/marmot/notifiers/dingtalk.py`（含 HMAC 签名）
  - `src/marmot/notifiers/wecom.py`
  - `src/marmot/notifiers/feishu.py`（含签名）
  - `src/marmot/notifiers/email.py`（通过 callback 解耦 SMTP）
  - `src/marmot/notifiers/phone.py`（severity gating）
  - `tests/test_notifiers_*.py`（用 `monkeypatch` 拦截 `urllib.request.urlopen`）
- **可验证行为**：每个渠道 payload 格式测试通过；Phone 对非 critical/error 不发送

---

### Unit 14 — 只读查询 API
- **新建文件/改动**：
  - `api.MarmotApp`：`list_active_alerts / list_alert_history / list_recent_runs / list_notifications / get_alert`
  - `tests/test_read_api.py`
- **可验证行为**：所有只读方法返回正确数据且不修改状态

---

### Unit 15 — Web 控制台
- **新建文件**：
  - `src/marmot/web/__init__.py`
  - `src/marmot/web/read_model.py`（封装 `MarmotApp` 的只读方法）
  - `src/marmot/web/handlers.py`（各 endpoint）
  - `src/marmot/web/server.py`（`ThreadingHTTPServer` + daemon 线程 + `start_ui_server`）
  - `src/marmot/web/assets/index.html`（HTML/JS 模板）
  - `src/marmot/__init__.py` 导出 `start_ui_server`
  - `tests/test_web_api.py`（用 `http.client` 打本机端口）
- **可验证行为**：启动后 `GET /` 返回 HTML；`/api/alerts`、`/api/history`、`/api/runs`、`/api/notifications`、`/api/rules` 返回正确 JSON

---

### Unit 16 — 文档与打包定稿
- **新建/更新**：
  - `README.md` / `README_CN.md`
  - `CHANGELOG.md`（v0.1.0 首版）
  - `AGENTS.md`（新结构说明）
  - `pyproject.toml`：`package-data` 打包 `web/assets/*`；设置 classifiers 与 license
- **可验证行为**：
  - `pip install .` 后 `import marmot` 可用；`marmot.start_ui_server()` 能加载 HTML 资源
  - `examples/quickstart.py` 端到端演示：阈值 + 聚合 + 心跳 + Web

> **里程碑 M2**：功能对齐 main 分支。

---

## 8. 验收标准

- `pytest -v` 全绿，且覆盖：状态机所有分支、Evaluator 所有分支、聚合、心跳/Job、升级、异步通知、Storage 契约（memory & sqlite）
- `examples/quickstart.py` 可一键运行完整 demo
- 任一源文件 ≤ 300 行
- `src/marmot/api.py` ≤ 300 行
- `shutdown()` 2s 内停止所有后台线程与 worker
- 运行时 0 第三方依赖（pyproject 的 `dependencies = []`）
- 单进程 1 万次 `report()` 主路径耗时稳定（异步队列保证）

---

## 9. 风险与应对

| 风险 | 应对 |
| --- | --- |
| 从零重写功能对齐遗漏 | 以 main 分支为行为基准，每个 Unit 附带契约测试；最终用原 `examples/quickstart.py` 的等价脚本验证 |
| 异步通知改变"调用即打印"的直觉 | `ConsoleNotifier` 提供 `sync=True` 选项；文档明示 |
| Web 静态资源打包遗漏 | 使用 `importlib.resources` 读取 `web/assets/index.html`；`pyproject.toml` 的 `package-data` 登记 |
| SQLite 多线程错用 | `check_same_thread=False` + 全局 `RLock` + WAL；契约测试覆盖并发 CRUD |
| orphan 分支切换时本地脏文件丢失 | 切换前显式确认；保留一个临时分支指向当前 commit |
