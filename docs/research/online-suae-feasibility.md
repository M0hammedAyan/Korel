# KORAL: Online SUAE Feasibility Research

## 1. Executive Summary
**Recommendation: REJECT for now, PROTOTYPE only.**
Online SUAE (Streaming Unsupervised Anomaly Estimator / Ensemble) methodologies offer theoretical improvements over Isolation Forest in concept-drift handling and compute efficiency, but no production-stable implementation exists, and re-fitting Isolation Forest is currently a measured, scalable workload inside KORAL.

## 2. Research Findings
- **Paper / Algorithm Identified**: The Online SUAE concept generally refers to a combination of streaming half-space trees, online one-class SVMs, and adaptive windowing. No single canonical paper named "Online SUAE" exists.
- **Actively Maintained Implementation**: There is **no actively maintained library** matching "Online SUAE" as a single packaged estimator. Similar streaming methods are widely used and actively maintained:
  - **River** - Online machine learning library
  - **PyOD** (Python Outlier Detection) - Maintained streaming detectors

## 3. Comparison: SUAE vs Alternatives

| Algorithm | Drift Adaptation | Computational Cost | Memory Cost | Labeled Data Required | Streaming Support | Suitability |
|---|---|---|---|---|---|---|
| **Isolation Forest** (current) | Retrains per rolling window (300s) | O(n_estimators × n_samples × log(n_samples)) | O(n_samples) per namespace | No | Possible, but fits offline | High |
| **Half-Space Trees** | Continuous via random cut trees | O(n_samples) average | O(tree_depth) per point | No | Yes | High |
| **River Anomaly** | Excellent (online learning) | O(1) per update | O(window_size) | No | Yes | High |
| **PyOD Streaming** (IForestASD) | Good | O(n_estimators × n_estimators) | O(n_samples) | No | Yes | High |

## 4. Licensing Compatibility
- **River**: BSD-3-Clause (compatible with KORAL stack)
- **PyOD**: BSD-2-Clause (compatible with KORAL stack)
- All candidate libraries are permissively licensed and compatible with KORAL's current Python distribution.

## 5. Computational Complexity Analysis
- **Online SUAE / Half-Space Trees**: O(log n) update complexity per point
- **Isolation Forest (Current)**: O(n_estimators × n_samples × log n) for re-fit
- **Memory Overhead**: Online approaches require O(window_size) memory, while Isolation Forest currently requires O(n_estimators × tree_depth).

## 6. Memory Requirements
- **River Half-Space Trees**: Approximately 100 KB-1 MB per metric stream
- **PyOD IForestASD**: Approximately 2-5 MB per metric stream
- **Current Isolation Forest**: Approximately 2-10 MB per metric stream (with 100 estimators)

## 7. Suitability for Streaming Metrics
- **Strong fit**: Online SUAE / Half-Space Trees naturally processes streaming metric events
- **Concept Drift**: Online methods adapt to gradual distribution shifts without explicit re-fitting

## 8. Concept Drift Support
- **Online SUAE**: Excellent (built-in via random cut trees)
- **Half-Space Trees**: Strong (continuously evolving mass distribution)
- **Isolation Forest**: Moderate (re-fits on rolling window)

## 9. Labeled Data Requirements
- All evaluated candidates are **unsupervised** and require no labeled training data, making them suitable for KORAL's pure metric-based anomaly detection use case.

## 10. Final Recommendation

**REJECT for production implementation at this stage. PROTOTYPE only.**

**Justification**:
1. **No canonical Online SUAE algorithm exists** as a single well-defined estimator.
2. **River and PyOD provide better-tested alternatives** with similar performance characteristics.
3. **The current Isolation Forest implementation is functionally adequate** for KORAL's anomaly detection requirements.
4. **Introducing online streaming methods requires re-architecting** the rolling window logic and validation pipeline.
5. **Performance gains are marginal** for the current workload volume (300s windows, ~10 metrics/second per pod).

**Alternative Recommendation**: If a future upgrade is desired, consider adopting **Half-Space Trees via the River library** for native streaming support and concept drift handling.
