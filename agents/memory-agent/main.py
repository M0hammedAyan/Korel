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
POD_NAME = os.getenv("POD_NAME", "memory-agent")
METRICS_RUNTIME = os.getenv("METRICS_RUNTIME", "kubernetes")
ALLOW_SYNTHETIC_METRICS = os.getenv("ALLOW_SYNTHETIC_METRICS", "false").lower() == "true"

QUERY = (
    f'sum(container_memory_working_set_bytes{{namespace="{NAMESPACE}"}}) by (pod)'
    if METRICS_RUNTIME == "kubernetes"
    else 'sum(container_memory_working_set_bytes{container_label_com_docker_compose_service="memory-agent",image!=""})'
)


class MemoryAgent(BaseAgent):
    def __init__(self):
        super().__init__(metric="memory", pod=POD_NAME, unit="MB")
        # Prometheus metrics
        self.create_gauge("memory_usage_mb", "Memory usage in MB")
        self.create_gauge("memory_usage_percent", "Memory usage percent")
        self.create_gauge("memory_anomaly_score", "Memory anomaly score (z)")
        self.total_mb = float(os.getenv("TOTAL_MEMORY_MB", "16000"))

    def on_measure(self, value: float, z: float, payload: dict):
        self.set_gauge("memory_usage_mb", value)
        percent = (value / self.total_mb) * 100 if self.total_mb > 0 else 0.0
        self.set_gauge("memory_usage_percent", percent)
        self.set_gauge("memory_anomaly_score", abs(z))

    async def fetch_value(self) -> float:
        # try real Prometheus data first
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": QUERY})
                results = r.json().get("data", {}).get("result", [])
                if results:
                    setattr(self, "_synthetic_mode", False)
                    total_bytes = sum(float(item["value"][1]) for item in results)
                    return total_bytes / (1024 ** 2)
        except Exception:
            pass

        # fallback synthetic memory usage (MB)
        if not ALLOW_SYNTHETIC_METRICS:
            raise RuntimeError("real memory metrics unavailable and synthetic metrics are disabled")
        setattr(self, "_synthetic_mode", True)
        now = asyncio.get_event_loop().time()
        base = getattr(self, "_syn_base", None)
        if base is None:
            base = random.uniform(2000.0, 8000.0)
            self._syn_base = base
        amp = 1000.0
        drift = math.sin(now / 30.0) * amp
        spike = 0.0
        if random.random() < 0.03:
            spike = random.uniform(500.0, 3000.0)
        if getattr(self, "_force_spike", False):
            spike += random.uniform(2000.0, 8000.0)
            setattr(self, "_force_spike", False)
        val = max(0.0, min(base + drift + spike + random.uniform(-100, 100), self.total_mb))
        return round(val, 4)


if __name__ == "__main__":
    agent = MemoryAgent()
    agent.start_metrics_server(8002)
    asyncio.run(agent.run())
