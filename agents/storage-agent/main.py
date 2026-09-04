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
POD_NAME = os.getenv("POD_NAME", "storage-agent")
METRICS_RUNTIME = os.getenv("METRICS_RUNTIME", "kubernetes")
ALLOW_SYNTHETIC_METRICS = os.getenv("ALLOW_SYNTHETIC_METRICS", "false").lower() == "true"

QUERY = (
    f'sum(rate(container_fs_writes_bytes_total{{namespace="{NAMESPACE}"}}[1m])) by (pod)'
    if METRICS_RUNTIME == "kubernetes"
    else 'sum(rate(container_fs_writes_bytes_total{container_label_com_docker_compose_service="storage-agent",image!=""}[1m]))'
)


class StorageAgent(BaseAgent):
    def __init__(self):
        super().__init__(metric="storage", pod=POD_NAME, unit="KB/s")
        # Prometheus metrics
        self.create_gauge("storage_usage_percent", "Storage I/O usage percent")
        self.create_gauge("disk_io_rate", "Disk IO rate KB/s")
        self.max_io_kb = float(os.getenv("MAX_IO_KB", str(1024 * 1024)))

    def on_measure(self, value: float, z: float, payload: dict):
        # value is KB/s
        self.set_gauge("disk_io_rate", value)
        percent = min((value / self.max_io_kb) * 100, 100.0) if self.max_io_kb > 0 else 0.0
        self.set_gauge("storage_usage_percent", percent)

    async def fetch_value(self) -> float:
        # try Prometheus first
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": QUERY})
                results = r.json().get("data", {}).get("result", [])
                if results:
                    setattr(self, "_synthetic_mode", False)
                    total_bytes = sum(float(item["value"][1]) for item in results)
                    return total_bytes / 1024
        except Exception:
            pass

        # synthetic KB/s
        if not ALLOW_SYNTHETIC_METRICS:
            raise RuntimeError("real storage metrics unavailable and synthetic metrics are disabled")
        setattr(self, "_synthetic_mode", True)
        now = asyncio.get_event_loop().time()
        base = getattr(self, "_syn_base", None)
        if base is None:
            base = random.uniform(10.0, 200.0)
            self._syn_base = base
        drift = math.sin(now / 20.0) * 50.0
        spike = 0.0
        if random.random() < 0.03:
            spike = random.uniform(500.0, 5000.0)
        if getattr(self, "_force_spike", False):
            spike += random.uniform(2000.0, 20000.0)
            setattr(self, "_force_spike", False)
        val = max(0.0, base + drift + spike + random.uniform(-5, 5))
        return round(val, 4)


if __name__ == "__main__":
    agent = StorageAgent()
    agent.start_metrics_server(8003)
    asyncio.run(agent.run())
