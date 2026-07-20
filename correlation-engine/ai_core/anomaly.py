"""Isolation Forest anomaly detection for Project KORAL events.

Replaces the previous rolling Z-score detector. The public interface
(detect / detect_many, same KoralEvent output shape including z_score)
is preserved so no callers need to change.

Why Isolation Forest over Z-score:
- Z-score assumes a Gaussian distribution and a single metric in isolation.
- IF is distribution-free, handles multi-modal and skewed metrics naturally,
  and is robust to gradual drift since it re-fits on the rolling window.
- The z_score field is kept by mapping IF's anomaly score to a pseudo-z
  so downstream confidence math (min(abs(z_score)/5, 1.0)) stays valid.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict, Iterable, List, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest

from .schema import KoralEvent
from .validator import validate_event

HistoryKey = Tuple[str, str, str]
HistoryPoint = Tuple[int, float]


class IsolationForestDetector:
    """Per-pod, per-metric Isolation Forest with a rolling time window.

    Parameters
    ----------
    z_threshold:
        Kept for API compatibility with the old Z-score detector.
        Maps to IF contamination: contamination = 1 / (z_threshold * 3.33).
        At the default z_threshold=3.0 this gives contamination≈0.1 (10 % outliers).
    window_size:
        Rolling window width in seconds. Points older than this are dropped.
    min_history_points:
        Minimum points required before IF makes a prediction.
        Raised from 5 (Z-score min) to 10 because IF needs more samples
        to build meaningful trees.
    n_estimators:
        Number of trees in the forest. 100 is sklearn's default and works
        well for windows up to ~1000 points.
    """

    def __init__(
        self,
        *,
        z_threshold: float = 3.0,
        window_size: int = 300,
        min_history_points: int = 10,
        n_estimators: int = 100,
    ) -> None:
        if z_threshold <= 0:
            raise ValueError("z_threshold must be positive")
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if min_history_points < 2:
            raise ValueError("min_history_points must be at least 2")

        # Map z_threshold to IF contamination (fraction of expected anomalies).
        # z=3.0 → contamination=0.10, z=2.0 → 0.15, z=4.0 → 0.075.
        self.contamination = float(max(0.01, min(0.5, 1.0 / (z_threshold * 3.33))))
        self.z_threshold = z_threshold
        self.window_size = window_size
        self.min_history_points = min_history_points
        self.n_estimators = n_estimators

        self._history: Dict[HistoryKey, Deque[HistoryPoint]] = defaultdict(deque)

    # ------------------------------------------------------------------ #
    # Public interface — identical to RollingZScoreDetector               #
    # ------------------------------------------------------------------ #

    def detect(self, raw_event: dict) -> KoralEvent:
        """Validate, score, and annotate one event."""
        event = validate_event(raw_event, final=False)
        key = (event["namespace"], event["pod"], event["metric"])
        history = self._history[key]

        self._expire_old_points(history, event["timestamp"])
        history_values = [v for _, v in history]

        pseudo_z, is_anomaly = self._score(event["value"], history_values)

        annotated: KoralEvent = {
            **event,
            "z_score": round(pseudo_z, 6),   # preserved field name for compat
            "is_anomaly": bool(is_anomaly),   # cast numpy bool_ → Python bool
            "window_size": self.window_size,
        }
        validate_event(annotated, final=True)

        history.append((event["timestamp"], event["value"]))
        return annotated

    def detect_many(self, raw_events: Iterable[dict]) -> List[KoralEvent]:
        """Score events in timestamp order to keep the rolling window stable."""
        ordered = sorted(raw_events, key=lambda e: e["timestamp"])
        return [self.detect(e) for e in ordered]

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _expire_old_points(self, history: Deque[HistoryPoint], timestamp: int) -> None:
        cutoff = timestamp - self.window_size
        while history and history[0][0] < cutoff:
            history.popleft()

    def _score(self, value: float, history_values: List[float]) -> Tuple[float, bool]:
        """Return (pseudo_z, is_anomaly) for the incoming value.

        Pseudo-z maps IF's decision_function score to a z-like scale:
            pseudo_z = -decision_score * 6
        IF decision scores sit roughly in [-0.5, 0.5]:
          - Normal points → score ≈ +0.1..+0.3  → pseudo_z ≈ -0.6..-1.8  (low)
          - Anomalies     → score ≈ -0.1..-0.5  → pseudo_z ≈ +0.6..+3.0  (high)
        This keeps the downstream confidence formula (abs(z)/5 clamped to 1)
        producing sensible values without any changes to main.py.
        """
        if len(history_values) < self.min_history_points:
            # Not enough history yet — treat as normal, emit neutral pseudo-z.
            return 0.0, False

        # Build training matrix: reshape to (n_samples, 1) for sklearn.
        X_train = np.array(history_values, dtype=float).reshape(-1, 1)
        X_new   = np.array([[value]], dtype=float)

        # Re-fit on the current window every call.  The window is bounded by
        # window_size so this is fast (typically < 300 points, ~2 ms).
        model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=42,  # deterministic scoring for the same window
        )
        model.fit(X_train)

        # decision_function: higher = more normal, negative = outlier.
        decision_score = float(model.decision_function(X_new)[0])
        is_anomaly     = model.predict(X_new)[0] == -1  # -1 = outlier in sklearn

        pseudo_z = -decision_score * 6.0
        return pseudo_z, is_anomaly
