"""All services of the prototype. The SERVICE environment variable selects one.

Microservice deployment (framework layers):
  gateway   - controller layer: authentication + routing/load balancing to ERM replicas
  erm       - Emergency Response Microservice (MAPE-K inside: Monitor, Analyzer,
              Planner, Executor); calls profile, store and actuator
  profile   - patient profiles (knowledge: user profile)
  store     - knowledge component: event log
  actuator  - resource layer stand-in: receives alert/actuation commands
Monolithic baseline:
  monolith  - the same logic in a single process
"""
import itertools
import os
import time

import httpx
from fastapi import FastAPI, Header, HTTPException, Request

from common import API_TOKEN, Store, TTLCache, analyze_and_plan, make_profile

SERVICE = os.environ.get("SERVICE", "monolith")
app = FastAPI()
_client = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=10.0, limits=httpx.Limits(max_connections=200, max_keepalive_connections=100))
    return _client


def check_auth(authorization: str | None):
    if authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
async def health():
    return {"service": SERVICE, "status": "ok"}


@app.post("/admin/crash")
async def crash():
    """Fault injection for the reliability scenario (S4)."""
    os._exit(1)


# --------------------------------------------------------------------------- gateway
if SERVICE == "gateway":
    REPLICAS = [u.strip() for u in os.environ.get("ERM_URLS", "http://erm:8000").split(",")]
    _rr = itertools.cycle(range(len(REPLICAS)))

    @app.post("/readings")
    async def gw_readings(request: Request, authorization: str | None = Header(default=None)):
        check_auth(authorization)
        body = await request.json()
        start = next(_rr)
        last_err = None
        for k in range(len(REPLICAS)):          # failover: try the next replica on error
            url = REPLICAS[(start + k) % len(REPLICAS)]
            try:
                r = await client().post(f"{url}/readings", json=body)
                if r.status_code < 500:
                    return r.json()
                last_err = r.status_code
            except httpx.HTTPError as e:
                last_err = repr(e)
        raise HTTPException(status_code=503, detail=f"no healthy ERM replica ({last_err})")

# --------------------------------------------------------------------------- erm
elif SERVICE == "erm":
    PROFILE_URL = os.environ.get("PROFILE_URL", "http://profile:8000")
    STORE_URL = os.environ.get("STORE_URL", "http://store:8000")
    ACTUATOR_URL = os.environ.get("ACTUATOR_URL", "http://actuator:8000")
    cache = TTLCache(float(os.environ.get("CACHE_TTL", "0")))

    @app.post("/readings")
    async def erm_readings(reading: dict):
        # Monitor
        pid = reading["patient_id"]
        profile = cache.get(pid)
        if profile is None:
            profile = (await client().get(f"{PROFILE_URL}/patients/{pid}")).json()
            cache.put(pid, profile)
        # Analyze + Plan
        out = analyze_and_plan(reading, profile)
        # Knowledge
        await client().post(f"{STORE_URL}/events", json={"patient_id": pid, "sbp": reading["sbp"], **out})
        # Execute
        if out["plan"] != "none":
            await client().post(f"{ACTUATOR_URL}/commands", json={"patient_id": pid, "action": out["plan"],
                                                                  "contact": profile["emergency_contact"]})
        return {"patient_id": pid, **out}

    @app.get("/cache_stats")
    async def cache_stats():
        return {"hits": cache.hits, "misses": cache.misses}

# --------------------------------------------------------------------------- profile
elif SERVICE == "profile":
    @app.get("/patients/{pid}")
    async def get_profile(pid: int):
        return make_profile(pid)

# --------------------------------------------------------------------------- store
elif SERVICE == "store":
    store = Store(os.environ.get("DB_PATH", "/tmp/events.db"))

    @app.post("/events")
    async def add_event(e: dict):
        store.add(e)
        return {"ok": True}

# --------------------------------------------------------------------------- actuator
elif SERVICE == "actuator":
    COUNTS = {}

    @app.post("/commands")
    async def command(c: dict):
        COUNTS[c["action"]] = COUNTS.get(c["action"], 0) + 1
        return {"ok": True, "ts": time.time()}

    @app.get("/counts")
    async def counts():
        return COUNTS

# --------------------------------------------------------------------------- monolith
elif SERVICE == "monolith":
    store = Store(os.environ.get("DB_PATH", "/tmp/events.db"))
    COUNTS = {}

    @app.post("/readings")
    async def mono_readings(reading: dict, authorization: str | None = Header(default=None)):
        check_auth(authorization)
        pid = reading["patient_id"]
        profile = make_profile(pid)
        out = analyze_and_plan(reading, profile)
        store.add({"patient_id": pid, "sbp": reading["sbp"], **out})
        if out["plan"] != "none":
            COUNTS[out["plan"]] = COUNTS.get(out["plan"], 0) + 1
        return {"patient_id": pid, **out}
