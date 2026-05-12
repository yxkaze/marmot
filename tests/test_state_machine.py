"""
状态机测试。
"""

import pytest
from datetime import datetime, UTC, timedelta

from marmot.domain import (
    AlertState,
    Severity,
    AlertStage,
    AlertEvent,
    AlertStateMachine,
    Decision,
    NotifyFiring,
    NotifyResolved,
    EnterSilence,
    EnterResolving,
)


class TestStateMachine:
    """状态机测试。"""
    
    def test_pending_to_firing(self):
        """测试 PENDING → FIRING（连续N次触发）"""
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.PENDING,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
            consecutive_hits=0,
        )
        
        # 第1次触发
        decision = AlertStateMachine.transition(
            event=event,
            hit=True,
            consecutive_count=3,
            now=datetime.now(UTC),
        )
        assert decision.new_state == AlertState.PENDING.value
        assert decision.event_patch["consecutive_hits"] == 1
        
        # 第2次触发
        event.consecutive_hits = 1
        decision = AlertStateMachine.transition(
            event=event,
            hit=True,
            consecutive_count=3,
            now=datetime.now(UTC),
        )
        assert decision.new_state == AlertState.PENDING.value
        assert decision.event_patch["consecutive_hits"] == 2
        
        # 第3次触发 → FIRING
        event.consecutive_hits = 2
        decision = AlertStateMachine.transition(
            event=event,
            hit=True,
            consecutive_count=3,
            now=datetime.now(UTC),
        )
        assert decision.new_state == AlertState.FIRING.value
        assert decision.event_patch["consecutive_hits"] == 3
        assert len(decision.actions) == 1
        assert isinstance(decision.actions[0], NotifyFiring)
    
    def test_pending_normal_reset(self):
        """测试 PENDING 状态恢复正常，重置计数"""
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.PENDING,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
            consecutive_hits=2,
        )
        
        # 恢复正常
        decision = AlertStateMachine.transition(
            event=event,
            hit=False,
            consecutive_count=3,
            now=datetime.now(UTC),
        )
        assert decision.new_state == AlertState.PENDING.value
        assert decision.event_patch["consecutive_hits"] == 0
        assert decision.event_patch["consecutive_misses"] == 1
    
    def test_firing_to_silenced(self):
        """测试 FIRING → SILENCED（进入静默）"""
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.FIRING,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
        )
        
        now = datetime.now(UTC)
        decision = AlertStateMachine.transition(
            event=event,
            hit=True,
            consecutive_count=3,
            now=now,
            silence_seconds=300,
        )
        
        assert decision.new_state == AlertState.SILENCED.value
        assert "silenced_until" in decision.event_patch
        assert len(decision.actions) == 1
        assert isinstance(decision.actions[0], EnterSilence)
    
    def test_firing_to_resolving(self):
        """测试 FIRING → RESOLVING（开始恢复）"""
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.FIRING,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
        )
        
        decision = AlertStateMachine.transition(
            event=event,
            hit=False,
            consecutive_count=3,
            now=datetime.now(UTC),
        )
        
        assert decision.new_state == AlertState.RESOLVING.value
        assert decision.event_patch["consecutive_misses"] == 1
        assert len(decision.actions) == 1
        assert isinstance(decision.actions[0], EnterResolving)
    
    def test_resolving_to_resolved(self):
        """测试 RESOLVING → RESOLVED（连续N次正常）"""
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.RESOLVING,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
            consecutive_misses=2,
        )
        
        now = datetime.now(UTC)
        decision = AlertStateMachine.transition(
            event=event,
            hit=False,
            consecutive_count=3,
            now=now,
        )
        
        assert decision.new_state == AlertState.RESOLVED.value
        assert decision.event_patch["consecutive_misses"] == 3
        assert "resolved_at" in decision.event_patch
        assert len(decision.actions) == 1
        assert isinstance(decision.actions[0], NotifyResolved)
    
    def test_resolving_back_to_firing(self):
        """测试 RESOLVING 又触发了，回到 FIRING"""
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.RESOLVING,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
            consecutive_misses=1,
        )
        
        decision = AlertStateMachine.transition(
            event=event,
            hit=True,
            consecutive_count=3,
            now=datetime.now(UTC),
        )
        
        assert decision.new_state == AlertState.FIRING.value
        assert decision.event_patch["consecutive_hits"] == 1
        assert decision.event_patch["consecutive_misses"] == 0
        assert len(decision.actions) == 1
        assert isinstance(decision.actions[0], NotifyFiring)
    
    def test_silenced_still_in_silence(self):
        """测试 SILENCED 还在静默中"""
        now = datetime.now(UTC)
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.SILENCED,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
            silenced_until=(now + timedelta(seconds=100)).timestamp(),
        )
        
        decision = AlertStateMachine.transition(
            event=event,
            hit=True,
            consecutive_count=3,
            now=now,
            silence_seconds=300,
        )
        
        assert decision.new_state == AlertState.SILENCED.value
        assert len(decision.actions) == 0
    
    def test_silenced_expired_still_firing(self):
        """测试 SILENCED 静默结束，还在触发"""
        now = datetime.now(UTC)
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.SILENCED,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
            silenced_until=(now - timedelta(seconds=1)).timestamp(),
        )
        
        decision = AlertStateMachine.transition(
            event=event,
            hit=True,
            consecutive_count=3,
            now=now,
            silence_seconds=300,
        )
        
        # 再次进入静默
        assert decision.new_state == AlertState.SILENCED.value
        assert len(decision.actions) == 2
        assert isinstance(decision.actions[0], NotifyFiring)
        assert isinstance(decision.actions[1], EnterSilence)
    
    def test_silenced_expired_start_resolving(self):
        """测试 SILENCED 静默结束，开始恢复"""
        now = datetime.now(UTC)
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.SILENCED,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
            silenced_until=(now - timedelta(seconds=1)).timestamp(),
        )
        
        decision = AlertStateMachine.transition(
            event=event,
            hit=False,
            consecutive_count=3,
            now=now,
            silence_seconds=300,
        )
        
        assert decision.new_state == AlertState.RESOLVING.value
        assert decision.event_patch["silenced_until"] is None
        assert len(decision.actions) == 1
        assert isinstance(decision.actions[0], EnterResolving)
    
    def test_resolved_retrigger(self):
        """测试 RESOLVED 又触发了"""
        event = AlertEvent(
            rule_name="cpu_usage",
            state=AlertState.RESOLVED,
            severity=Severity.ERROR,
            stage=AlertStage.THRESHOLD,
        )
        
        decision = AlertStateMachine.transition(
            event=event,
            hit=True,
            consecutive_count=3,
            now=datetime.now(UTC),
        )
        
        assert decision.new_state == AlertState.PENDING.value
        assert decision.event_patch["consecutive_hits"] == 1
        assert decision.event_patch["resolved_at"] is None
