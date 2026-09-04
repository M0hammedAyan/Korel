import os
import sys
import asyncio
import httpx
import random
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_agent import BaseAgent

FLUENTD_HOST = os.getenv("FLUENTD_HOST", "fluentd")
FLUENTD_PORT = os.getenv("FLUENTD_PORT", "9880")
NAMESPACE = os.getenv("NAMESPACE", "koral-system")
POD_NAME = os.getenv("POD_NAME", "log-agent")
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
ALLOW_SYNTHETIC_METRICS = os.getenv("ALLOW_SYNTHETIC_METRICS", "false").lower() == "true"

QUERY = 'sum(increase(fluentd_output_status_emit_records_total{tag=~"koral.*"}[1m]))'


class LogAgent(BaseAgent):
    def __init__(self):
        super().__init__(metric="log_error", pod=POD_NAME, unit="count")
        # Prometheus metrics
        self.create_gauge("log_error_rate", "Log error rate per second")
        self.create_gauge("log_anomaly_count", "Log anomaly flag (0/1)")

    def on_measure(self, value: float, z: float, payload: dict):
        # value is count over POLL_INTERVAL; convert to rate/sec
        interval = int(os.getenv("POLL_INTERVAL", "10"))
        rate = value / interval if interval > 0 else 0.0
        self.set_gauge("log_error_rate", rate)
        self.set_gauge("log_anomaly_count", 1.0 if payload.get("is_anomaly") else 0.0)

    async def fetch_value(self) -> float:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": QUERY})
                results = r.json().get("data", {}).get("result", [])
                if results:
                    setattr(self, "_synthetic_mode", False)
                    return float(results[0]["value"][1])
        except Exception:
            pass

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"http://{FLUENTD_HOST}:{FLUENTD_PORT}/api/plugins.json")
                plugins = r.json().get("plugins", [])
                setattr(self, "_synthetic_mode", False)
                return float(sum(
                    p.get("emit_records", 0)
                    for p in plugins
                    if "error" in p.get("tag", "").lower()
                ))
        except Exception:
            pass

        # final fallback: synthetic log errors
        if not ALLOW_SYNTHETIC_METRICS:
            raise RuntimeError("real log metrics unavailable and synthetic metrics are disabled")
        setattr(self, "_synthetic_mode", True)
        now = asyncio.get_event_loop().time()
        base = getattr(self, "_syn_base", None)
        if base is None:
            base = random.uniform(0.0, 5.0)
            self._syn_base = base
        drift = math.sin(now / 60.0) * 2.0
        spike = 0.0
        if random.random() < 0.05:
            spike = random.uniform(5.0, 50.0)
        if getattr(self, "_force_spike", False):
            spike += random.uniform(10.0, 200.0)
            setattr(self, "_force_spike", False)
        val = max(0.0, base + drift + spike + random.uniform(-1.0, 1.0))
        return round(val, 4)


if __name__ == "__main__":
    agent = LogAgent()
    agent.start_metrics_server(8004)
    asyncio.run(agent.run())
