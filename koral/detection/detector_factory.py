"""
Detector Factory — Routes metrics to the correct detector instance.

Each unique (namespace, pod, metric) triple gets its own detector instance.
Streaming detectors (RRCF) maintain state per-series.
Batch detectors (STL+IF) are stateless per call but reuse the same config.
"""
import logging
from typing import Dict, Tuple

from koral.config import settings
from koral.detection.base import DetectorBase
from koral.detection.rrcf_detector import RRCFStreamDetector
from koral.detection.stl_if_detector import STLIFDetector
from koral.ingestion.metric_router import classify_metric, get_detector_for_type

logger = logging.getLogger(__name__)

# Cache key: (namespace, pod_name, metric_name)
DetectorKey = Tuple[str, str, str]


class DetectorFactory:
    """
    Creates and caches detector instances per metric series.

    RRCF detectors are stateful (maintain forest per series) → cached.
    STL+IF detectors are stateless per batch call → one per metric type is enough.
    """

    def __init__(self):
        self._detectors: Dict[DetectorKey, DetectorBase] = {}

    def get_detector(self, namespace: str, pod_name: str, metric_name: str) -> DetectorBase:
        """
        Get or create a detector for the given metric series.

        Returns an RRCF detector for spiky metrics, STL+IF for seasonal/drift.
        """
        key: DetectorKey = (namespace, pod_name, metric_name)

        if key not in self._detectors:
            metric_type = classify_metric(metric_name)
            detector_kind = get_detector_for_type(metric_type)

            if detector_kind == "rrcf":
                detector = RRCFStreamDetector(
                    metric_name=metric_name,
                    pod_name=pod_name,
                    namespace=namespace,
                    num_trees=settings.rrcf_num_trees,
                    tree_size=settings.rrcf_tree_size,
                    shingle_size=settings.rrcf_shingle_size,
                    threshold=settings.rrcf_anomaly_threshold,
                )
            else:
                detector = STLIFDetector(
                    metric_name=metric_name,
                    pod_name=pod_name,
                    namespace=namespace,
                    contamination=settings.if_contamination,
                )

            self._detectors[key] = detector
            logger.debug(f"[factory] Created {detector_kind} detector for {key}")

        return self._detectors[key]

    def get_detector_count(self) -> int:
        """Return number of active detector instances."""
        return len(self._detectors)

    def clear(self) -> None:
        """Clear all cached detectors. Use when resetting state."""
        self._detectors.clear()

    def remove_detector(self, namespace: str, pod_name: str, metric_name: str) -> bool:
        """Remove a specific detector (e.g., when a pod is terminated)."""
        key = (namespace, pod_name, metric_name)
        if key in self._detectors:
            del self._detectors[key]
            return True
        return False


# Global factory instance
factory = DetectorFactory()
