"""Load generator: N simulated home devices, each sending one vital-sign reading
every PERIOD seconds to the entry point (gateway or monolith) for DURATION seconds.
Writes per-request latencies and a summary to OUT (JSON).
"""
import asyncio
import json
import os
import random
import time

import httpx

TARGET = os.environ.get("TARGET", "http://gateway:8000/readings")
N = int(os.environ.get("N_DEVICES", "10"))
PERIOD = float(os.environ.get("PERIOD", "1.0"))
DURATION = float(os.environ.get("DURATION", "30"))
WARMUP = float(os.environ.get("WARMUP", "3"))
SEED = int(os.environ.get("SEED", "1"))
OUT = os.environ.get("OUT", "/out/result.json")
TOKEN = os.environ.get("API_TOKEN", "lab-case-token")
CRASH_AT = float(os.environ.get("CRASH_AT", "-1"))       # seconds after start, -1 = no fault
CRASH_URL = os.environ.get("CRASH_URL", "")

records = []   # (t_rel, latency_s, ok)


async def device(i, cl, t0, rng):
    await asyncio.sleep(rng.uniform(0, PERIOD))
    n = 0
    while True:
        now = time.perf_counter()
        if now - t0 > WARMUP + DURATION:
            return
        sbp = 185.0 if rng.random() < 0.01 else float(rng.randint(125, 145))
        body = {"patient_id": i, "sbp": sbp, "heart_rate_bpm": float(rng.randint(60, 100)),
                "temperature_c": round(rng.uniform(36.2, 37.2), 1)}
        s = time.perf_counter()
        ok = False
        try:
            r = await cl.post(TARGET, json=body, headers={"Authorization": f"Bearer {TOKEN}"})
            ok = r.status_code == 200
        except httpx.HTTPError:
            ok = False
        e = time.perf_counter()
        if s - t0 >= WARMUP:
            records.append((s - t0 - WARMUP, e - s, ok))
        n += 1
        await asyncio.sleep(max(0.0, PERIOD - (time.perf_counter() - s)))


async def crash(cl, t0):
    await asyncio.sleep(WARMUP + CRASH_AT)
    try:
        await cl.post(CRASH_URL)
    except httpx.HTTPError:
        pass
    return time.perf_counter() - t0 - WARMUP


async def main():
    rng = random.Random(SEED)
    limits = httpx.Limits(max_connections=max(50, N), max_keepalive_connections=max(50, N))
    async with httpx.AsyncClient(timeout=10.0, limits=limits) as cl:
        t0 = time.perf_counter()
        tasks = [asyncio.create_task(device(i, cl, t0, random.Random(SEED * 100000 + i))) for i in range(N)]
        crash_t = None
        if CRASH_AT >= 0 and CRASH_URL:
            crash_t = await crash(cl, t0)
        await asyncio.gather(*tasks)
    lat = sorted(r[1] for r in records if r[2])
    nok = sum(1 for r in records if not r[2])
    def pct(p):
        return lat[min(len(lat) - 1, int(p * len(lat)))] if lat else None
    summary = {"n_devices": N, "period": PERIOD, "duration": DURATION, "seed": SEED,
               "requests": len(records), "ok": len(lat), "failed": nok,
               "throughput_rps": len(lat) / DURATION,
               "lat_mean_ms": 1000 * sum(lat) / len(lat) if lat else None,
               "lat_p50_ms": 1000 * pct(0.50) if lat else None,
               "lat_p95_ms": 1000 * pct(0.95) if lat else None,
               "lat_p99_ms": 1000 * pct(0.99) if lat else None,
               "crash_t": crash_t}
    if crash_t is not None:
        fails = [r[0] + r[1] for r in records if not r[2] and r[0] + r[1] >= crash_t]
        summary["failed_after_crash"] = len(fails)
        # recovery time = from the crash until the last failed request completes
        # (after that, every request succeeds again); 0 if no request failed
        summary["recovery_s"] = (max(fails) - crash_t) if fails else 0.0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"summary": summary, "records": records}, f)
    print(json.dumps(summary))


if __name__ == "__main__":
    asyncio.run(main())
