# Unit 6: Evaluator 实现计划

**目标：** 实现阈值评估器，判断数值是否触发告警，返回观测结果。

**架构：** L1 领域层 - 纯函数，无 I/O，不修改状态。

---

## 文件结构

```
src/marmot/domain/
  evaluator.py        # Observation + ThresholdEvaluator

tests/
  test_evaluator.py   # 评估器测试
```

---

## 任务 1: 实现 ThresholdEvaluator

**文件：**
- 新建: `src/marmot/domain/evaluator.py`
- 新建: `tests/test_evaluator.py`
- 修改: `src/marmot/domain/__init__.py`

- [ ] **步骤 1: 写失败的测试**

创建 `tests/test_evaluator.py`:

```python
"""
测试阈值评估器。
"""
import pytest
from datetime import datetime

from marmot.domain.evaluator import ThresholdEvaluator, Observation
from marmot.domain.models.rules import ThresholdRule, ThresholdLevel
from marmot.domain.models.enums import Severity
from marmot.domain.models.events import AlertEvent
from marmot.domain.models.enums import AlertState


def test_hit_when_value_exceeds_threshold():
    """超过阈值应该 hit。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 85.0, {"host": "server1"}, None, datetime.utcnow())
    
    assert obs.hit is True
    assert obs.miss is False
    assert obs.matched_severity == Severity.WARNING


def test_miss_when_value_below_threshold():
    """低于阈值应该 miss。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 75.0, {"host": "server1"}, None, datetime.utcnow())
    
    assert obs.hit is False
    assert obs.miss is True
    assert obs.matched_severity is None


def test_highest_severity_wins():
    """多个阈值匹配时，应该选最高严重程度。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING),
            ThresholdLevel(value=90.0, severity=Severity.ERROR),
            ThresholdLevel(value=95.0, severity=Severity.CRITICAL),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    
    obs1 = evaluator.evaluate(rule, 85.0, {}, None, datetime.utcnow())
    assert obs1.matched_severity == Severity.WARNING
    
    obs2 = evaluator.evaluate(rule, 92.0, {}, None, datetime.utcnow())
    assert obs2.matched_severity == Severity.ERROR
    
    obs3 = evaluator.evaluate(rule, 98.0, {}, None, datetime.utcnow())
    assert obs3.matched_severity == Severity.CRITICAL


def test_dedup_key_from_labels():
    """应该根据规则名和标签生成 dedup_key。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 85.0, {"host": "server1"}, None, datetime.utcnow())
    
    assert obs.dedup_key == "cpu_high:host=server1"


def test_dedup_key_reused_from_prior_event():
    """有 prior_event 时应该复用其 dedup_key。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    prior = AlertEvent(
        id=1,
        rule_name="cpu_high",
        dedup_key="cpu_high:host=server1",
        state=AlertState.PENDING.value,
        labels={"host": "server1"},
        fired_at=datetime.utcnow(),
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 85.0, {"host": "server1"}, prior, datetime.utcnow())
    
    assert obs.dedup_key == "cpu_high:host=server1"


def test_notify_targets_from_matched_level():
    """应该返回匹配到的阈值等级的通知目标。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[
            ThresholdLevel(value=80.0, severity=Severity.WARNING, notify=["console"]),
            ThresholdLevel(value=90.0, severity=Severity.ERROR, notify=["console", "webhook"]),
        ],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console"],
    )
    
    evaluator = ThresholdEvaluator()
    
    obs1 = evaluator.evaluate(rule, 85.0, {}, None, datetime.utcnow())
    assert obs1.notify_targets == ["console"]
    
    obs2 = evaluator.evaluate(rule, 92.0, {}, None, datetime.utcnow())
    assert obs2.notify_targets == ["console", "webhook"]


def test_notify_targets_fallback_to_rule():
    """匹配的等级没有指定 notify 时，应该用规则的 notify_targets。"""
    rule = ThresholdRule(
        name="cpu_high",
        thresholds=[ThresholdLevel(value=80.0, severity=Severity.WARNING)],
        consecutive_count=3,
        silence_seconds=300,
        notify_targets=["console", "email"],
    )
    
    evaluator = ThresholdEvaluator()
    obs = evaluator.evaluate(rule, 85.0, {}, None, datetime.utcnow())
    
    assert obs.notify_targets == ["console", "email"]
```

- [ ] **步骤 2: 运行测试确认失败**

运行: `pytest tests/test_evaluator.py -v`

预期: FAIL（ModuleNotFoundError）

- [ ] **步骤 3: 实现 Observation 和 ThresholdEvaluator**

创建 `src/marmot/domain/evaluator.py`:

```python
"""
评估器。

根据规则评估数值，返回观测结果。
纯函数，无 I/O，不修改状态。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .models.enums import Severity
from .models.events import AlertEvent
from .models.rules import ThresholdRule
from .keys import build_dedup_key


@dataclass
class Observation:
    """观测结果。
    
    一次 report() 的评估输出。
    """
    hit: bool
    miss: bool
    matched_severity: Severity | None
    dedup_key: str
    notify_targets: list[str] = field(default_factory=list)


class ThresholdEvaluator:
    """阈值评估器。"""
    
    def evaluate(
        self,
        rule: ThresholdRule,
        value: float,
        labels: dict[str, Any],
        prior_event: AlertEvent | None,
        now: datetime,
    ) -> Observation:
        """评估阈值。
        
        参数:
            rule: 阈值规则
            value: 当前值
            labels: 标签
            prior_event: 先前的告警事件
            now: 当前时间
        """
        matched_level = rule.evaluate(value)
        
        hit = matched_level is not None
        miss = not hit
        
        matched_severity = None
        notify_targets = rule.notify_targets
        
        if matched_level:
            severity = matched_level.severity
            if isinstance(severity, str):
                matched_severity = Severity(severity)
            else:
                matched_severity = severity
            
            if matched_level.notify:
                notify_targets = matched_level.notify
        
        if prior_event:
            dedup_key = prior_event.dedup_key
        else:
            dedup_key = build_dedup_key(rule.name, labels)
        
        return Observation(
            hit=hit,
            miss=miss,
            matched_severity=matched_severity,
            dedup_key=dedup_key,
            notify_targets=notify_targets,
        )
```

- [ ] **步骤 4: 更新 domain/__init__.py 导出**

- [ ] **步骤 5: 运行测试确认通过**

运行: `pytest tests/test_evaluator.py -v`

预期: PASS (7 个测试)

- [ ] **步骤 6: 提交**

```bash
git add src/marmot/domain/evaluator.py tests/test_evaluator.py src/marmot/domain/__init__.py
git commit -m "feat: Unit 6 - ThresholdEvaluator 实现"
```

---

## 验证

- [ ] `pytest tests/ -v` 全部通过

---

**计划已保存到 `docs/superpowers/plans/2026-05-13-unit-6-evaluator.md`**
