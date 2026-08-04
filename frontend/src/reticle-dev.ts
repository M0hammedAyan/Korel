// Reticle dev-only SDK — self-guards on import.meta.env.DEV, no-op in prod
import { registerCapabilities } from '@reticlehq/react';

if (import.meta.env.DEV) {
  registerCapabilities({
    testids: [
      'dashboard-metrics',
      'anomaly-chart',
      'incident-list',
      'remediation-btn',
      'slo-panel',
      'nav-sidebar',
    ],
    signals: [
      'anomaly:detected',
      'incident:correlated',
      'remediation:planned',
      'remediation:approved',
      'remediation:executed',
      'verification:completed',
    ],
    stores: [],
  });
}
