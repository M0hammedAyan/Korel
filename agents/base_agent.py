import os
import asyncio
import httpx
import threading
from collections import deque
from statistics import mean, stdev
from datetime import datetime, timezone

# Prometheus + HTTP server
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI
from starlette.responses import PlainTextResponse, JSONResponse
import uvicorn

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
API_KEY = os.getenv("API_KEY", "")
Z_THRESHOLD = float(os.getenv("Z_THRESHOLD", "2.5"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
NAMESPACE = os.getenv("NAMESPACE", "koral-system")
HISTORY_SIZE = 30


def compute_z_score(history: deque, value: float) -> float:
    if len(history) < 2:
        return 0.0
    m, s = mean(history), stdev(history)
    return (value - m) / s if s > 0 else 0.0


class BaseAgent:
    def __init__(self, metric: str, pod: str, unit: str = "value"):
        self.metric = metric
        self.pod = pod
        self.unit = unit
        self.history: deque = deque(maxlen=HISTORY_SIZE)
        self.registry = CollectorRegistry()
        self.gauges = {}
        self._http_thread = None
        # demo/ops realism: explicitly indicate when agent is using synthetic fallback
        self.create_gauge("koral_agent_synthetic_mode", "1 if agent is using synthetic fallback, else 0")

    async def fetch_value(self) -> float:
        raise NotImplementedError

    def on_measure(self, value: float, z: float, payload: dict):
        # hook for subclasses to update Prometheus gauges
        # default: update common gauges if present
        try:
            self.set_gauge(f"{self.metric}_value", value)
        except Exception:
            pass
        try:
            self.set_gauge(f"{self.metric}_z_score", abs(z))
        except Exception:
            pass

    def create_gauge(self, name: str, description: str):
        g = Gauge(name, description, registry=self.registry)
        self.gauges[name] = g
        return g

    def set_gauge(self, name: str, value: float):
        g = self.gauges.get(name)
        if g is not None:
            try:
                g.set(value)
            except Exception:
                pass

    def start_metrics_server(self, port: int):
        app = FastAPI()

        @app.get("/metrics")
        def metrics():
            data = generate_latest(self.registry)
            return PlainTextResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

        @app.get("/health")
        def health():
            return JSONResponse({"status": "ok"})

        @app.post("/debug/spike")
        def trigger_spike():
            # instruct synthetic generator to produce a spike on next measurement
            try:
                setattr(self, "_force_spike", True)
                return JSONResponse({"status": "spike_scheduled"})
            except Exception:
                return JSONResponse({"status": "error"}, status_code=500)

        def run():
            uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

        t = threading.Thread(target=run, daemon=True)
        t.start()
        self._http_thread = t

    async def run(self):
        while True:
            try:
                value = await self.fetch_value()
                z = compute_z_score(self.history, value)
                self.history.append(value)
                payload = {
                    "timestamp": int(datetime.now(timezone.utc).timestamp()),
                    "pod": self.pod,
                    "namespace": NAMESPACE,
                    "metric": self.metric,
                    "value": round(value, 4),
                    "unit": self.unit,
                    "z_score": round(z, 4),
                    "is_anomaly": abs(z) > Z_THRESHOLD,
                    "window_size": HISTORY_SIZE * POLL_INTERVAL,
                    "source": f"{self.metric}-agent",
                }
                # update Prometheus gauges via hook
                try:
                    self.on_measure(value, z, payload)
                except Exception:
                    pass

                # expose synthetic mode gauge if subclasses set it
                try:
                    self.set_gauge("koral_agent_synthetic_mode", 1.0 if getattr(self, "_synthetic_mode", False) else 0.0)
                except Exception:
                    pass

                # log update to stdout for visibility
                print(f"[{self.metric}] value={payload['value']} z={payload['z_score']} anomaly={payload['is_anomaly']}")

                async with httpx.AsyncClient(timeout=5) as client:
                    try:
                        headers = {"X-API-Key": API_KEY} if API_KEY else {}
                        await client.post(f"{BACKEND_URL}/anomalies", json=payload, headers=headers)
                    except Exception as e:
                        print(f"[{self.metric}] backend post error: {e}")
            except Exception as e:
                print(f"[{self.metric}] error: {e}")
            await asyncio.sleep(POLL_INTERVAL)
