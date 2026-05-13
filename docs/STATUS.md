# Marmot 重写现状总结

## 项目信息

- **分支**: `rebuild/v2` (orphan 分支，从零开始)
- **MVP 目标**: Unit 1-7
- **当前进度**: Unit 6 完成，MVP 进度 6/7 (86%)

## 已完成的工作

### Unit 1: 工程骨架 ✅

**新建文件：**
- `pyproject.toml` - 包配置，Python 3.10+，零依赖
- `src/marmot/__init__.py` - 模块入口
- `README.md` - 最小说明
- `.gitignore` - Git 忽略配置
- `tests/__init__.py` - 测试包
- `tests/test_smoke.py` - 冒烟测试

**验证通过：**
- ✅ `pip install -e ".[dev]"` 成功
- ✅ `import marmot` 可用
- ✅ `pytest -v` 1 个用例通过

**提交记录：**
- `6303d1d` - feat: Unit 1 - 工程骨架

---

### Unit 2: 领域数据类与枚举 ✅

**目录结构：**
```
src/marmot/domain/
  __init__.py          # 聚合导出
  models/
    __init__.py        # 模型聚合
    enums.py           # 枚举类（6个）
    rules.py           # 规则数据类（5个）
    events.py          # 事件数据类（3个）
    time_utils.py      # 时间工具（4个函数）
    keys.py            # 键工具（2个函数）
```

**枚举类（6 个）：**

1. **AlertState** - 告警状态
   - PENDING, FIRING, SILENCED, ESCALATED, RESOLVING, RESOLVED

2. **Severity** - 严重程度
   - INFO, WARNING, ERROR, CRITICAL

3. **AlertStage** - 触发机制
   - THRESHOLD, TIMEOUT, HEARTBEAT, MANUAL

4. **RunStatus** - 任务状态
   - RUNNING, SUCCESS, FAILED, TIMEOUT

5. **NotificationStatus** - 通知状态
   - PENDING, SENT, FAILED

6. **AggregateFn** - 聚合函数
   - AVG, MAX, MIN, SUM, COUNT

**规则数据类（5 个）：**

1. **EscalationStep** - 升级步骤（可选）
   - `after_seconds: float` - 触发时间
   - `severity: Severity | str | None` - 升级到的严重程度（可选）
   - `notify: list[str]` - 通知目标

2. **ThresholdLevel** - 阈值等级
   - `value: float` - 阈值
   - `severity: Severity | str` - 严重程度
   - `notify: list[str]` - 通知目标（可选）
   - `silence_seconds: float` - 静默时间（可选）

3. **AggregateConfig** - 聚合配置
   - `fn: AggregateFn | str` - 聚合函数
   - `window: float` - 窗口大小

4. **Rule** - 通用规则（心跳/Job）
   - `name: str`
   - `expected_interval_seconds: float | None`
   - `timeout_seconds: float | None`
   - `silence_seconds: float`
   - `severity: Severity | str`
   - `notify_targets: list[str]`
   - `escalation_steps: list[EscalationStep]`

5. **ThresholdRule** - 阈值规则
   - `name: str`
   - `thresholds: list[ThresholdLevel]`
   - `consecutive_count: int` - 连续触发次数
   - `silence_seconds: float`
   - `notify_targets: list[str]`
   - `escalation_steps: list[EscalationStep]`
   - `aggregate: AggregateConfig | None`
   - `evaluate(value) -> ThresholdLevel | None` - 评估方法

**事件数据类（3 个）：**

1. **AlertEvent** - 告警事件（核心实体）
   - `id: int | None` - 数据库主键
   - `rule_name: str`
   - `dedup_key: str`
   - `state: AlertState` - 当前状态
   - `severity: Severity | None`
   - `stage: AlertStage | None`
   - `message: str`
   - `labels: dict[str, Any]`
   - `current_value: float | None`
   - `consecutive_hits: int` - 连续触发次数
   - `consecutive_misses: int` - 连续恢复次数
   - `fired_at: datetime`
   - `resolved_at: datetime | None`
   - `silenced_until: datetime | None`
   - `escalated_at: datetime | None`
   - `escalation_level: int`

2. **RunRecord** - 任务执行记录
   - `id: int | None`
   - `rule_name: str`
   - `status: RunStatus`
   - `message: str`
   - `error: str | None`
   - `labels: dict[str, Any]`
   - `started_at: datetime`
   - `finished_at: datetime | None`
   - `duration_ms: float` - 计算属性

3. **Notification** - 通知记录
   - `id: int | None`
   - `alert_event_id: int`
   - `rule_name: str`
   - `dedup_key: str`
   - `status: NotificationStatus`
   - `state: AlertState | None`
   - `message: str`
   - `severity: Severity | None`
   - `labels: dict[str, Any]`
   - `stage: AlertStage | None`
   - `notifier_name: str`
   - `sent_at: datetime`

**工具函数：**

- `time_utils.py`:
  - `utcnow() -> datetime`
  - `to_iso(dt: datetime | None) -> str | None`
  - `from_iso(v: str | None) -> datetime | None`
  - `parse_duration(v: Any) -> float | None`

- `keys.py`:
  - `build_dedup_key(rule_name: str, labels: dict | None) -> str`
  - `normalize_notify(v: str | Iterable[str] | None) -> list[str]`

**关键设计决策：**

1. ✅ **支持字符串和枚举双输入**
   - 开发者可以用字符串 `severity="warning"` 或枚举 `Severity.WARNING`
   - 通过 `__post_init__` 自动转换

2. ✅ **统一使用枚举类型**
   - 所有该用枚举的地方都用枚举
   - 字段类型：`Severity | str` 或 `Severity`

3. ✅ **AlertEvent 状态机设计**
   - PENDING: 触发确认中，防误报
   - RESOLVING: 恢复确认中，防误恢复
   - 两个"防震荡"状态

4. ✅ **EscalationStep 可选配置**
   - severity 可选，支持多种升级策略
   - 可以只改变通知目标，也可以同时改变严重程度

5. ✅ **模块化设计**
   - 拆分为 enums.py, rules.py, events.py
   - 每个文件职责清晰，便于维护

**测试覆盖：**
- ✅ 31 个测试用例全部通过
- ✅ 覆盖枚举、数据类、工具函数
- ✅ 覆盖字符串和枚举双输入

**提交记录：**
- `5ebebb4` - feat: Unit 2.1 - 创建 domain 目录结构
- `838bdf1` - feat: Unit 2.2 - 实现枚举类
- `78ca416` - feat: Unit 2.3 - 实现 Rule 相关数据类
- `d392b1c` - docs: 补充枚举类详细中文注释
- `e9bbcb3` - refactor: 拆分 models.py 为多个模块
- `2bfa5c1` - refactor: 将 models 相关文件移至 models 子目录
- `832a418` - refactor: 移除重复的 _utcnow 函数
- `4abe76a` - feat: Unit 2.7 - 编写 domain 测试
- `e154eb0` - refactor: 修正 Event 字段类型，使用枚举代替字符串
- `9786a48` - refactor: 统一使用枚举类型代替字符串
- `b68c56f` - feat: 支持字符串和枚举双输入
- `6c2bef7` - feat: EscalationStep 增加 severity 字段

---

### Unit 3: 纯状态机 ✅

**新建文件：**
- `src/marmot/domain/decisions.py` - 决策数据类
- `src/marmot/domain/state_machine.py` - 状态机核心逻辑
- `tests/test_state_machine.py` - 状态机测试

**决策数据类：**

1. **Decision** - 状态机输出
   - `new_state: str` - 新状态
   - `event_patch: dict` - 要更新的事件字段
   - `actions: list[SideEffect]` - 要执行的动作列表

2. **SideEffect** - 动作并集类型
   - `NotifyFiring` - 发送告警通知
   - `NotifyResolved` - 发送恢复通知
   - `NotifyEscalated` - 发送升级通知（未实现）
   - `EnterSilence` - 进入静默期
   - `EnterResolving` - 进入恢复确认
   - `MarkEscalated` - 标记已升级（未实现）

**状态机逻辑：**

**已实现的状态转换：**
- `PENDING → FIRING` - 连续N次触发
- `PENDING → PENDING` - 计数中或恢复正常重置
- `FIRING → SILENCED` - 进入静默
- `FIRING → RESOLVING` - 开始恢复
- `SILENCED → FIRING` - 静默结束，还在触发
- `SILENCED → RESOLVING` - 静默结束，开始恢复
- `RESOLVING → RESOLVED` - 连续N次正常
- `RESOLVING → FIRING` - 又触发了
- `RESOLVED → PENDING` - 重新触发
- `ESCALATED → RESOLVING` - 开始恢复

**关键设计决策：**
1. ✅ **配置驱动** - consecutive_count、silence_seconds 由用户配置
2. ✅ **纯函数** - 无副作用，不修改 event
3. ✅ **决策分离** - 状态机只判断，调用者执行动作
4. ✅ **静默逻辑** - SILENCED 独立状态，避免一直告警

**测试覆盖：**
- ✅ 10 个状态转换测试用例
- ✅ 覆盖主要状态转换路径

**提交记录：**
- `07b01c4` - feat: Unit 3 - 纯状态机

---

### Unit 4: Storage Protocol + 内存实现 ✅

**新建文件：**
- `src/marmot/storage/__init__.py` - 存储包入口
- `src/marmot/storage/base.py` - Storage Protocol 定义
- `src/marmot/storage/memory.py` - 内存存储实现
- `tests/test_storage_base.py` - Protocol 测试
- `tests/test_storage_memory.py` - 内存存储测试

**Storage Protocol 定义：**

定义了存储接口，包括：

**AlertEvent CRUD：**
- `get_or_create_alert_event()` - 获取或创建告警事件
- `update_alert_event()` - 更新告警事件
- `get_alert_event()` - 获取单个告警事件
- `list_active_alerts()` - 列出活跃告警
- `list_alert_history()` - 列出告警历史

**RunRecord CRUD：**
- `create_run_record()` - 创建运行记录
- `list_recent_runs()` - 列出最近运行记录

**Notification CRUD：**
- `create_notification()` - 创建通知记录
- `list_notifications()` - 列出通知记录

**MemoryStorage 实现：**

- 基于 `dict` 和 `list` 的内存存储
- 线程安全（使用 `RLock`）
- 自动 ID 分配
- 支持去重键索引

**关键设计决策：**
1. ✅ **Protocol 抽象** - Storage 是 Protocol，便于替换实现
2. ✅ **线程安全** - 所有操作使用 `with self._lock` 保护
3. ✅ **去重键索引** - `_alert_events_by_key` 字典加速查找
4. ✅ **自动 ID 分配** - `_get_next_id()` 方法管理 ID

**测试覆盖：**
- ✅ 8 个测试用例
- ✅ 覆盖 AlertEvent、RunRecord、Notification 的 CRUD
- ✅ 覆盖去重逻辑、更新逻辑、列表过滤

**文件统计：**
- `storage/base.py`: 131 行
- `storage/memory.py`: 225 行

**提交记录：**
- `4591613` - feat: Unit 4.1 - Storage Protocol 定义
- `c277b38` - feat: Unit 4.2 - 内存存储实现
- `41b214c` - refactor: 重构 Storage Protocol 和 MemoryStorage，对齐 main 分支设计
- `ea45dcb` - refactor: 拆分 Storage 为三个独立 Protocol

---

### Unit 5: Clock + Registry ✅

**新建文件：**
- `src/marmot/runtime/__init__.py` - 运行时组件包入口
- `src/marmot/runtime/clock.py` - Clock Protocol + SystemClock
- `src/marmot/runtime/registry.py` - RuleRegistry + NotifierRegistry
- `tests/test_clock.py` - Clock 测试
- `tests/test_registry.py` - Registry 测试

**Clock Protocol：**
- `now() -> datetime` - 获取当前 UTC 时间
- `monotonic() -> float` - 获取单调时间（不倒退）

**SystemClock：** 生产环境实现，直接调用 `datetime.utcnow()` 和 `time.monotonic()`

**RuleRegistry：**
- `register_threshold_rule(rule)` - 注册阈值规则
- `get_threshold_rule(name)` - 获取阈值规则
- `list_threshold_rules()` - 列出所有阈值规则
- `register_rule(rule)` - 注册通用规则（心跳/Job）
- `get_rule(name)` - 获取通用规则
- `list_rules()` - 列出所有通用规则

**NotifierRegistry：**
- `register(name, notifier)` - 注册通知器
- `get(name)` - 获取通知器
- `list()` - 列出所有通知器名称

**关键设计决策：**
1. ✅ **Clock Protocol** - 让测试可以注入假时钟，不用 sleep
2. ✅ **线程安全** - 所有注册表使用 RLock
3. ✅ **注册 = 配置监控项** - 用户先注册规则，再 report 数据

**测试覆盖：**
- ✅ 11 个测试用例（Clock 3 个 + Registry 8 个）

**文件统计：**
- `runtime/clock.py`: 33 行
- `runtime/registry.py`: 72 行

**提交记录：**
- `f041cad` - feat: Unit 5.1 - Clock Protocol 和 SystemClock
- `d27ccf8` - feat: Unit 5.2 - RuleRegistry 和 NotifierRegistry

---

### Unit 6: ThresholdEvaluator ✅

**新建文件：**
- `src/marmot/domain/evaluator.py` - Observation 数据类 + ThresholdEvaluator
- `tests/test_evaluator.py` - 评估器测试

**Observation 数据类：**
- `hit: bool` - 是否超过阈值
- `miss: bool` - 是否低于阈值
- `matched_severity: Severity | None` - 匹配的最高严重程度
- `dedup_key: str` - 去重键
- `notify_targets: list[str]` - 通知目标

**ThresholdEvaluator：**
- `evaluate(rule, value, labels, prior_event, now) -> Observation`
- 多阈值匹配时选最高严重程度
- 匹配等级有 notify 则用等级的，否则用规则的
- 有 prior_event 时复用 dedup_key

**测试覆盖：**
- ✅ 7 个测试用例
- ✅ 覆盖超阈值/低于阈值/多等级/去重键/通知目标

**文件统计：**
- `domain/evaluator.py`: 82 行

**提交记录：**
- `ed4ab18` - feat: Unit 6 - ThresholdEvaluator 实现

---

## 文件统计

```
src/marmot/domain/models/enums.py      91 行
src/marmot/domain/models/events.py    106 行
src/marmot/domain/models/rules.py     167 行
src/marmot/domain/models/time_utils.py 104 行
src/marmot/domain/models/keys.py       56 行
src/marmot/domain/models/__init__.py   51 行
src/marmot/domain/decisions.py         73 行
src/marmot/domain/state_machine.py    183 行
src/marmot/domain/evaluator.py         82 行
src/marmot/storage/base.py            131 行
src/marmot/storage/memory.py          225 行
src/marmot/runtime/clock.py            33 行
src/marmot/runtime/registry.py         72 行
tests/test_domain_models.py           295 行
tests/test_state_machine.py           277 行
tests/test_storage_base.py            24 行
tests/test_storage_memory.py          134 行
tests/test_clock.py                    24 行
tests/test_registry.py                 84 行
tests/test_evaluator.py               151 行
```

**所有文件均 ≤ 300 行，符合要求。**

---

## 待完成的工作

### Unit 7: Dispatcher + 最小 MarmotApp + 同步通知 ⏳
- `notifiers/base.py` - Notifier Protocol
- `notifiers/console.py` - ConsoleNotifier
- `runtime/dispatcher.py` - 同步分发
- `api.py` - MarmotApp
- `tests/test_report_pipeline.py`
- `examples/quickstart.py`

**完成 Unit 7 后达到 MVP 里程碑 M1。**

---

## 技术栈确认

- **Python**: 3.10+
- **依赖**: 零运行时依赖（仅 stdlib）
- **测试**: pytest (dev dependency)
- **打包**: hatchling
- **类型**: typing.Protocol + @dataclass(slots=True)

---

## 下一步计划

1. **Unit 7**: 实现 Dispatcher 和 MarmotApp（达到 MVP）

**预计完成时间**: 1 天

---

## 备注

- 所有代码都有详细中文注释
- 所有测试用例都使用中文注释
- 保持简洁，保留可扩展性
- 为后续功能预留扩展空间
- 升级逻辑（Unit 12）留到后面实现
