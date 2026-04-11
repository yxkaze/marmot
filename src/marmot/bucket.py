"""
Marmot Alert Framework — Metric Bucket (Sliding Window Aggregation)

Collects individual metric data points into per-rule sliding windows
and computes aggregate values (avg / max / min / sum / count) on demand.

Design notes:
    - Purely in-memory; no persistence.  Process restart loses the buffer,
      which is acceptable because the window is typically short (e.g. 5 min)
      and the bucket refills as new reports arrive.
    - Thread-safe via reentrant lock.
    - Each ``report()`` call appends one data point.  ``compute()`` prunes
      stale entries and returns the aggregated value + sample count.
    - Zero external dependencies — uses only the standard library.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

from .models import AggregateFn


class MetricBucket:
    """Sliding window metric buffer for aggregation.

    Each rule gets its own deque of ``(timestamp, value)`` pairs.
    On every ``compute()`` call, entries older than the window are
    pruned before the aggregate function is applied.

    Parameters
    ----------
    None — the bucket is a stateful container; just create and use.

    Example::

        bucket = MetricBucket()
        bucket.add("es_disk", 82.0)
        bucket.add("es_disk", 88.0)
        bucket.add("es_disk", 85.5)
        value, count = bucket.compute("es_disk", "avg", window=300)
        # value ≈ 85.17, count = 3
    """

    def __init__(self) -> None:
        self._data: dict[str, deque[tuple[float, float]]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, rule_name: str, value: float) -> None:
        """Append a data point to the bucket for *rule_name*.

        Parameters
        ----------
        rule_name : str
            The threshold rule name (used as the bucket key).
        value : float
            The reported metric value.
        """
        ts = time.monotonic()
        with self._lock:
            if rule_name not in self._data:
                self._data[rule_name] = deque()
            self._data[rule_name].append((ts, value))

    def compute(
        self, rule_name: str, fn: str, window: float,
    ) -> tuple[float | None, int]:
        """Compute the aggregate value over the sliding window.

        Parameters
        ----------
        rule_name : str
            The threshold rule name.
        fn : str
            Aggregation function — one of ``"avg"``, ``"max"``, ``"min"``,
            ``"sum"``, ``"count"``.
        window : float
            Window size in seconds.  Data points older than this are pruned.

        Returns
        -------
        tuple[float | None, int]
            ``(aggregated_value, sample_count)``.
            ``aggregated_value`` is ``None`` when no data points remain
            in the window, or when *fn* is unrecognised.
        """
        cutoff = time.monotonic() - window
        with self._lock:
            dq = self._data.get(rule_name)
            if dq is None:
                return None, 0

            # Prune stale entries from the left side of the deque.
            while dq and dq[0][0] < cutoff:
                dq.popleft()

            if not dq:
                return None, 0

            values = [v for _, v in dq]
            count = len(values)

            if fn == AggregateFn.AVG.value:
                return sum(values) / count, count
            if fn == AggregateFn.MAX.value:
                return max(values), count
            if fn == AggregateFn.MIN.value:
                return min(values), count
            if fn == AggregateFn.SUM.value:
                return sum(values), count
            if fn == AggregateFn.COUNT.value:
                return float(count), count

            return None, 0

    def clear(self, rule_name: str | None = None) -> None:
        """Clear the bucket.

        Parameters
        ----------
        rule_name : str | None
            If given, clear only that rule's buffer.
            If ``None``, clear all buffers.
        """
        with self._lock:
            if rule_name is not None:
                self._data.pop(rule_name, None)
            else:
                self._data.clear()

    def sample_count(self, rule_name: str) -> int:
        """Return the current number of data points for *rule_name*
        (without pruning).  Useful for diagnostics."""
        with self._lock:
            dq = self._data.get(rule_name)
            return len(dq) if dq else 0
