import os
import sys
import asyncio
import httpx
import random
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from base_agent import BaseAgent

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
NAMESPACE = os.getenv("NAMESPACE", "koral-system")
POD_NAME = os.getenv("POD_NAME", "cpu-agent")
METRICS_RUNTIME = os.getenv("METRICS_RUNTIME", "kubernetes")
ALLOW_SYNTHETIC_METRICS = os.getenv("ALLOW_SYNTHETIC_METRICS", "false").lower() == "true"

QUERY = (
    f'sum(rate(container_cpu_usage_seconds_total{{namespace="{NAMESPACE}"}}[1m])) by (pod)'
    if METRICS_RUNTIME == "kubernetes"
    else 'sum(rate(container_cpu_usage_seconds_total{container_label_com_docker_compose_service="cpu-agent",image!=""}[1m]))'
)


class CpuAgent(BaseAgent):
    def __init__(self):
        super().__init__(metric="cpu", pod=POD_NAME, unit="percent")
        # Prometheus metrics
        self.create_gauge("cpu_usage_percent", "CPU usage percent")
        self.create_gauge("cpu_anomaly_score", "CPU anomaly score (z)")

    def on_measure(self, value: float, z: float, payload: dict):
        # update Prometheus gauges
        self.set_gauge("cpu_usage_percent", value)
        self.set_gauge("cpu_anomaly_score", abs(z))

    async def fetch_value(self) -> float:
        # try real Prometheus data first
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": QUERY})
                results = r.json().get("data", {}).get("result", [])
                if results:
                    setattr(self, "_synthetic_mode", False)
                    raw = sum(float(item["value"][1]) for item in results) * 100
                    return min(round(raw, 4), 100.0)
        except Exception:
            pass

        # fallback: synthetic fluctuating CPU for demo
        if not ALLOW_SYNTHETIC_METRICS:
            raise RuntimeError("real CPU metrics unavailable and synthetic metrics are disabled")
        setattr(self, "_synthetic_mode", True)
        now = asyncio.get_event_loop().time()
        base = getattr(self, "_syn_base", None)
        if base is None:
            base = random.uniform(10.0, 40.0)
            self._syn_base = base
        amp = 20.0
        drift = math.sin(now / 15.0) * amp
        spike = 0.0
        if random.random() < 0.02:
            spike = random.uniform(30, 60)
        if getattr(self, "_force_spike", False):
            spike += random.uniform(60, 140)
            setattr(self, "_force_spike", False)
        val = max(0.0, min(base + drift + spike + random.uniform(-3, 3), 100.0))
        return round(val, 4)


if __name__ == "__main__":
    agent = CpuAgent()
    agent.start_metrics_server(8001)
    asyncio.run(agent.run())
