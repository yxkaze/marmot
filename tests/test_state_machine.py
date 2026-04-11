"""Tests for Marmot AlertStateMachine."""
from __future__ import annotations

import pytest

from marmot.models import AlertEvent, AlertState, utcnow
from marmot.app import AlertStateMachine


class TestAlertStateMachine:
    def _make_event(self, state="pending", hits=0, misses=0):
        return AlertEvent(
            rule_name="test",
            dedup_key="test",
            state=state,
            consecutive_hits=hits,
            consecutive_misses=misses,
            fired_at=utcnow(),
        )

    # --- PENDING transitions ---

    def test_pending_hit_goes_to_firing(self):
        e = self._make_event("pending")
        new_state, actions = AlertStateMachine.transition(e, hit=True)
        assert new_state == AlertState.FIRING.value
        assert "notify_firing" in actions

    def test_pending_miss_stays_pending(self):
        e = self._make_event("pending")
        new_state, actions = AlertStateMachine.transition(e, miss=True)
        assert new_state == "pending"
        assert actions == []

    # --- FIRING transitions ---

    def test_firing_hit_stays_firing(self):
        e = self._make_event("firing", hits=3)
        new_state, actions = AlertStateMachine.transition(e, hit=True)
        assert new_state == "firing"

    def test_firing_miss_goes_to_resolving(self):
        e = self._make_event("firing", hits=3)
        new_state, actions = AlertStateMachine.transition(e, miss=True)
        assert new_state == AlertState.RESOLVING.value
        assert "enter_resolving" in actions

    def test_firing_silence_goes_to_silenced(self):
        from datetime import timedelta, timezone
        e = self._make_event("firing", hits=3)
        e.silenced_until = utcnow() + timedelta(seconds=300)
        new_state, actions = AlertStateMachine.transition(e, hit=True)
        assert new_state == AlertState.SILENCED.value

    # --- SILENCED transitions ---

    def test_silenced_miss_goes_to_resolving(self):
        from datetime import timedelta
        e = self._make_event("silenced")
        e.silenced_until = utcnow() + timedelta(seconds=300)
        new_state, actions = AlertStateMachine.transition(e, miss=True)
        assert new_state == AlertState.RESOLVING.value

    def test_silenced_expired_goes_to_firing(self):
        e = self._make_event("silenced")
        e.silenced_until = utcnow()  # Already expired
        new_state, actions = AlertStateMachine.transition(e, hit=True)
        assert new_state == AlertState.FIRING.value
        assert "notify_firing" in actions

    # --- RESOLVING transitions ---

    def test_resolving_hit_back_to_firing(self):
        e = self._make_event("resolving", misses=1)
        new_state, _ = AlertStateMachine.transition(e, hit=True)
        assert new_state == AlertState.FIRING.value

    def test_resolving_miss_goes_to_resolved(self):
        e = self._make_event("resolving", misses=1)
        new_state, actions = AlertStateMachine.transition(e, miss=True)
        assert new_state == AlertState.RESOLVED.value
        assert "notify_resolved" in actions

    # --- RESOLVED terminal ---

    def test_resolved_stays_resolved(self):
        e = self._make_event("resolved")
        new_state, actions = AlertStateMachine.transition(e, hit=True)
        assert new_state == "resolved"
        assert actions == []

    # --- force_fire ---

    def test_force_fire_from_any_state(self):
        e = self._make_event("pending")
        new_state, actions = AlertStateMachine.transition(e, force_fire=True)
        assert new_state == AlertState.FIRING.value
        assert "notify_firing" in actions

    def test_force_fire_from_resolved(self):
        e = self._make_event("resolved")
        new_state, actions = AlertStateMachine.transition(e, force_fire=True)
        assert new_state == AlertState.FIRING.value
        assert "notify_firing" in actions
