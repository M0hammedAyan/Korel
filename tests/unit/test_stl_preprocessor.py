"""Unit tests for STL Decomposer and STL+IF Detector (Phase 1.3-1.5)."""
import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timezone, timedelta

from koral.detection.stl_preprocessor import STLDecomposer, STLComponents
from koral.detection.stl_if_detector import STLIFDetector
from koral.detection.base import AnomalyResult


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def decomposer():
    """Small period for fast tests."""
    return STLDecomposer(period=24, seasonal=7)


@pytest.fixture
def detector():
    return STLIFDetector(
        metric_name="cpu_usage",
        pod_name="api-server-1",
        namespace="default",
        contamination=0.05,
        period=24,
        seasonal=7,
    )


def make_seasonal_series(n_points: int, period: int = 24, noise_std: float = 1.0) -> pd.Series:
    """Generate a synthetic seasonal time series (sine wave + noise)."""
    timestamps = pd.date_range(start="2025-01-01", periods=n_points, freq="10min", tz="UTC")
    t = np.arange(n_points)
    seasonal = 50.0 + 20.0 * np.sin(2 * np.pi * t / period)
    noise = np.random.normal(0, noise_std, n_points)
    return pd.Series(seasonal + noise, index=timestamps)


def make_flat_series(n_points: int, value: float = 50.0, noise_std: float = 1.0) -> pd.Series:
    """Generate a flat series with noise."""
    timestamps = pd.date_range(start="2025-01-01", periods=n_points, freq="10min", tz="UTC")
    values = value + np.random.normal(0, noise_std, n_points)
    return pd.Series(values, index=timestamps)


# ── STLDecomposer Tests ──────────────────────────────────────────────

class TestSTLSufficientData:
    def test_insufficient_data_returns_false(self, decomposer):
        """Less than 2 periods should return False."""
        short = make_seasonal_series(20, period=24)  # 20 < 24*2
        assert decomposer.has_sufficient_data(short) is False

    def test_sufficient_data_returns_true(self, decomposer):
        """At least 2 periods should return True."""
        long = make_seasonal_series(50, period=24)  # 50 >= 24*2
        assert decomposer.has_sufficient_data(long) is True

    def test_empty_series_returns_false(self, decomposer):
        """Empty series should return False."""
        empty = pd.Series([], dtype=float)
        assert decomposer.has_sufficient_data(empty) is False


class TestSTLDecompose:
    def test_decompose_returns_components(self, decomposer):
        """Valid decomposition returns STLComponents."""
        series = make_seasonal_series(100, period=24)
        result = decomposer.decompose(series)
        assert result is not None
        assert isinstance(result, STLComponents)
        assert len(result.trend) == len(series)
        assert len(result.seasonal) == len(series)
        assert len(result.residual) == len(series)

    def test_decompose_insufficient_data_returns_none(self, decomposer):
        """Insufficient data returns None."""
        short = make_seasonal_series(10, period=24)
        result = decomposer.decompose(short)
        assert result is None

    def test_residual_has_lower_variance_than_original(self, decomposer):
        """Residual should have lower variance than original (seasonal removed)."""
        series = make_seasonal_series(200, period=24, noise_std=2.0)
        result = decomposer.decompose(series)
        assert result is not None
        assert result.residual.std() < series.std()

    def test_handles_nan_values(self, decomposer):
        """NaN values should be filled and decomposition should succeed."""
        series = make_seasonal_series(100, period=24)
        series.iloc[10] = np.nan
        series.iloc[50] = np.nan
        result = decomposer.decompose(series)
        assert result is not None
        assert result.has_valid_residual

    def test_components_sum_to_original(self, decomposer):
        """trend + seasonal + residual should approximately equal original."""
        series = make_seasonal_series(100, period=24, noise_std=0.5)
        result = decomposer.decompose(series)
        assert result is not None
        reconstructed = result.trend + result.seasonal + result.residual
        # Allow small floating point differences
        diff = (reconstructed - result.original).abs().max()
        assert diff < 1e-6


class TestSTLGetResidual:
    def test_returns_residual_with_sufficient_data(self, decomposer):
        """Should return residual when enough data."""
        series = make_seasonal_series(100, period=24)
        residual = decomposer.get_residual(series)
        assert len(residual) == len(series)
        # Residual should have lower std than original
        assert residual.std() < series.std()

    def test_returns_original_with_insufficient_data(self, decomposer):
        """Should return original series when not enough data."""
        short = make_seasonal_series(10, period=24)
        result = decomposer.get_residual(short)
        assert result.equals(short)


class TestSTLTrendDrift:
    def test_detects_upward_drift(self, decomposer):
        """A monotonically increasing trend should be detected."""
        timestamps = pd.date_range(start="2025-01-01", periods=200, freq="10min", tz="UTC")
        t = np.arange(200)
        # Strong upward trend + seasonal
        values = 50.0 + 0.5 * t + 10.0 * np.sin(2 * np.pi * t / 24)
        series = pd.Series(values, index=timestamps)
        assert decomposer.detect_trend_drift(series, slope_threshold=0.01) == True

    def test_stable_series_no_drift(self, decomposer):
        """A stable seasonal series should not show drift."""
        series = make_seasonal_series(200, period=24, noise_std=1.0)
        assert decomposer.detect_trend_drift(series, slope_threshold=0.1) == False


# ── STLIFDetector Tests ──────────────────────────────────────────────

class TestSTLIFDetector:
    def test_detect_many_returns_results(self, detector):
        """detect_many should return list of AnomalyResults."""
        series = make_seasonal_series(100, period=24)
        results = detector.detect_many(series)
        assert len(results) > 0
        assert all(isinstance(r, AnomalyResult) for r in results)
        assert all(r.detector_type == "stl_if" for r in results)

    def test_normal_seasonal_few_anomalies(self, detector):
        """A clean seasonal signal should produce very few anomalies."""
        series = make_seasonal_series(200, period=24, noise_std=1.0)
        results = detector.detect_many(series)
        anomaly_count = sum(1 for r in results if r.is_anomaly)
        # With contamination=0.05, expect ~5% flagged
        # But with STL removing the seasonal, a clean signal should have very few
        expected_max = int(len(results) * 0.10)  # Allow up to 10%
        assert anomaly_count <= expected_max, f"Too many anomalies: {anomaly_count}/{len(results)}"

    def test_injected_spike_detected(self, detector):
        """A large spike injected into seasonal signal should be detected."""
        series = make_seasonal_series(200, period=24, noise_std=1.0)
        # Inject a massive spike at index 150
        spike_ts = series.index[150]
        series.iloc[150] = 200.0  # Way above normal range (30-70)

        results = detector.detect_many(series)
        # Find the result at the spike timestamp
        spike_results = [r for r in results if r.value > 150.0]
        assert len(spike_results) > 0, "Spike value not found in results"
        assert spike_results[0].is_anomaly == True

    def test_stl_applied_with_sufficient_data(self, detector):
        """When sufficient data, STL should be applied."""
        series = make_seasonal_series(100, period=24)
        results = detector.detect_many(series)
        # At least one result should show stl_applied=True
        assert any(r.metadata.get("stl_applied") for r in results)

    def test_fallback_without_sufficient_data(self, detector):
        """With insufficient data, should fall back to raw IF."""
        short = make_flat_series(20)
        results = detector.detect_many(short)
        assert len(results) == 20
        # Should show stl_applied=False
        assert all(r.metadata.get("stl_applied") is False for r in results)

    def test_detect_single_returns_neutral(self, detector):
        """detect() (single point) should return neutral — batch only."""
        result = detector.detect(50.0, datetime.now(timezone.utc))
        assert result.anomaly_score == 0.0
        assert result.is_anomaly is False

    def test_empty_series_returns_empty(self, detector):
        """Empty series should return empty list."""
        empty = pd.Series([], dtype=float)
        results = detector.detect_many(empty)
        assert results == []
