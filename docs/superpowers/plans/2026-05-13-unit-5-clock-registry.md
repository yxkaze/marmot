# Unit 5: Clock + Registry 实现计划

**目标：** 提供时间抽象（测试可注入）和规则/通知器注册表。

**架构：** L3 运行时层 - Clock 让测试可控推进时间，Registry 管理规则和通知器的注册与查询。

---

## 文件结构

```
src/marmot/runtime/
  __init__.py          # 导出
  clock.py             # Clock Protocol + SystemClock
  registry.py          # RuleRegistry + NotifierRegistry

tests/
  test_clock.py        # Clock 测试
  test_registry.py     # Registry 测试
```

---

## 任务 1: 实现 Clock

**文件：**
- 新建: `src/marmot/runtime/__init__.py`
- 新建: `src/marmot/runtime/clock.py`
- 新建: `tests/test_clock.py`

- [ ] **步骤 1: 创建 runtime 包**

创建 `src/marmot/runtime/__init__.py`:

```python
"""
运行时组件。
"""
from .clock import Clock, SystemClock
from .registry import RuleRegistry, NotifierRegistry

__all__ = [
    "Clock",
    "SystemClock",
    "RuleRegistry",
    "NotifierRegistry",
]
```

- [ ] **步骤 2: 写失败的测试**

创建 `tests/test_clock.py`:

```python
"""
测试 Clock 抽象。
"""
import pytest
from marmot.runtime.clock import Clock, SystemClock


def test_clock_is_protocol():
    """Clock 应该是一个 Protocol。"""
    from typing import Protocol
    assert issubclass(Clock, Protocol)


def test_system_clock_now():
    """SystemClock.now() 应该返回当前 UTC 时间。"""
    clock = SystemClock()
    now = clock.now()
    
    from datetime import datetime
    assert isinstance(now, datetime)
    assert abs((datetime.utcnow() - now).total_seconds()) < 1.0


def test_system_clock_monotonic():
    """SystemClock.monotonic() 应该返回单调递增的时间。"""
    clock = SystemClock()
    t1 = clock.monotonic()
    t2 = clock.monotonic()
    
    assert isinstance(t1, float)
    assert t2 >= t1
```

- [ ] **步骤 3: 运行测试确认失败**

运行: `pytest tests/test_clock.py -v`

预期: FAIL（ModuleNotFoundError）

- [ ] **步骤 4: 实现 Clock Protocol 和 SystemClock**

创建 `src/marmot/runtime/clock.py`:

```python
"""
时间抽象。

Clock Protocol 让测试可以注入假时钟，
SystemClock 是生产环境的默认实现。
"""
import time
from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """时间抽象 Protocol。"""
    
    def now(self) -> datetime:
        """获取当前 UTC 时间。"""
        ...
    
    def monotonic(self) -> float:
        """获取单调时间（秒），保证不倒退。"""
        ...


class SystemClock:
    """系统时钟实现。"""
    
    def now(self) -> datetime:
        """获取当前 UTC 时间。"""
        return datetime.utcnow()
    
    def monotonic(self) -> float:
        """获取单调时间（秒）。"""
        return time.monotonic()
```

- [ ] **步骤 5: 运行测试确认通过**

运行: `pytest tests/test_clock.py -v`

预期: PASS (3 个测试)

- [ ] **步骤 6: 提交**

```bash
git add src/marmot/runtime/ tests/test_clock.py
git commit -m "feat: Unit 5.1 - Clock Protocol 和 SystemClock"
```

---

## 任务 2: 实现 Registry

**文件：**
- 新建: `src/marmot/runtime/registry.py`
- 新建: `tests/test_registry.py`

- [ ] **步骤 1: 写失败的测试**

创建 `tests/test_registry.py`:

```python
"""
测试注册表。
"""
import pytest
from marmot.runtime.registry import RuleRegistry, NotifierRegistry
from marmot.domain.models.rules import ThresholdRule, Rule, ThresholdLevel
from marmot.domain.models.enums import Severity


# ── RuleRegistry ────────────────────────────────────────


def test_register_and_get_threshold_rule():
    """应该能注册和获取阈值规则。"""
    registry = RuleRegistry()
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    registry.register_threshold_rule(rule)
    
    retrieved = registry.get_threshold_rule("cpu_high")
    assert retrieved is not None
    assert retrieved.name == "cpu_high"


def test_get_threshold_rule_not_found():
    """获取不存在的规则应该返回 None。"""
    registry = RuleRegistry()
    assert registry.get_threshold_rule("nonexistent") is None


def test_list_threshold_rules():
    """应该能列出所有阈值规则。"""
    registry = RuleRegistry()
    rule1 = ThresholdRule(
        name="rule1",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    rule2 = ThresholdRule(
        name="rule2",
        thresholds=[ThresholdLevel(value=90.0, severity=Severity.ERROR)],
        consecutive_count=2,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    registry.register_threshold_rule(rule1)
    registry.register_threshold_rule(rule2)
    
    rules = registry.list_threshold_rules()
    assert len(rules) == 2


def test_register_and_get_rule():
    """应该能注册和获取通用规则。"""
    registry = RuleRegistry()
    rule = Rule(
        name="heartbeat_check",
        expected_interval_seconds=60,
        timeout_seconds=120,
        silence_seconds=300,
        severity=Severity.ERROR,
        notify_targets=["console"],
    )
    
    registry.register_rule(rule)
    
    retrieved = registry.get_rule("heartbeat_check")
    assert retrieved is not None
    assert retrieved.name == "heartbeat_check"


def test_get_rule_not_found():
    """获取不存在的通用规则应该返回 None。"""
    registry = RuleRegistry()
    assert registry.get_rule("nonexistent") is None


# ── NotifierRegistry ────────────────────────────────────


def test_register_and_get_notifier():
    """应该能注册和获取通知器。"""
    registry = NotifierRegistry()
    
    class FakeNotifier:
        def send(self, n):
            return True
    
    notifier = FakeNotifier()
    registry.register("console", notifier)
    
    retrieved = registry.get("console")
    assert retrieved is notifier


def test_get_notifier_not_found():
    """获取不存在的通知器应该返回 None。"""
    registry = NotifierRegistry()
    assert registry.get("nonexistent") is None


def test_list_notifier_names():
    """应该能列出所有通知器名称。"""
    registry = NotifierRegistry()
    
    class FakeNotifier:
        def send(self, n):
            return True
    
    registry.register("console", FakeNotifier())
    registry.register("webhook", FakeNotifier())
    
    names = registry.list()
    assert "console" in names
    assert "webhook" in names
```

- [ ] **步骤 2: 运行测试确认失败**

运行: `pytest tests/test_registry.py -v`

预期: FAIL（ModuleNotFoundError）

- [ ] **步骤 3: 实现 Registry**

创建 `src/marmot/runtime/registry.py`:

```python
"""
注册表。

管理规则和通知器的注册与查询。
"""
from typing import Any
from threading import RLock

from ..domain.models.rules import ThresholdRule, Rule


class RuleRegistry:
    """规则注册表（线程安全）。"""
    
    def __init__(self):
        self._lock = RLock()
        self._threshold_rules: dict[str, ThresholdRule] = {}
        self._rules: dict[str, Rule] = {}
    
    def register_threshold_rule(self, rule: ThresholdRule) -> None:
        """注册阈值规则。"""
        with self._lock:
            self._threshold_rules[rule.name] = rule
    
    def get_threshold_rule(self, name: str) -> ThresholdRule | None:
        """获取阈值规则。"""
        with self._lock:
            return self._threshold_rules.get(name)
    
    def list_threshold_rules(self) -> list[ThresholdRule]:
        """列出所有阈值规则。"""
        with self._lock:
            return list(self._threshold_rules.values())
    
    def register_rule(self, rule: Rule) -> None:
        """注册通用规则（心跳/Job）。"""
        with self._lock:
            self._rules[rule.name] = rule
    
    def get_rule(self, name: str) -> Rule | None:
        """获取通用规则。"""
        with self._lock:
            return self._rules.get(name)
    
    def list_rules(self) -> list[Rule]:
        """列出所有通用规则。"""
        with self._lock:
            return list(self._rules.values())


class NotifierRegistry:
    """通知器注册表（线程安全）。"""
    
    def __init__(self):
        self._lock = RLock()
        self._notifiers: dict[str, Any] = {}
    
    def register(self, name: str, notifier: Any) -> None:
        """注册通知器。"""
        with self._lock:
            self._notifiers[name] = notifier
    
    def get(self, name: str) -> Any | None:
        """获取通知器。"""
        with self._lock:
            return self._notifiers.get(name)
    
    def list(self) -> list[str]:
        """列出所有通知器名称。"""
        with self._lock:
            return list(self._notifiers.keys())
```

- [ ] **步骤 4: 运行测试确认通过**

运行: `pytest tests/test_registry.py -v`

预期: PASS (8 个测试)

- [ ] **步骤 5: 提交**

```bash
git add src/marmot/runtime/registry.py tests/test_registry.py
git commit -m "feat: Unit 5.2 - RuleRegistry 和 NotifierRegistry"
```

---

## 验证

- [ ] **运行所有测试**

运行: `pytest tests/ -v`

预期: 所有测试通过

- [ ] **验证 Unit 5 完成**

确认:
- ✅ Clock Protocol 定义，SystemClock 可用
- ✅ RuleRegistry 支持阈值规则和通用规则
- ✅ NotifierRegistry 支持注册/查询/列表
- ✅ 所有注册表线程安全

---

**计划已保存到 `docs/superpowers/plans/2026-05-13-unit-5-clock-registry.md`**
