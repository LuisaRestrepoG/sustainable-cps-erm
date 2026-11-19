"""Runs the three experiments of the paper on the Docker prototype.

E1 Scalability/performance : architecture (micro, mono) x N devices x repetitions
E2 Client-side caching      : micro, N=100, CACHE_TTL in {0, 60 s} x repetitions
E3 Reliability (fault)      : micro with 1 or 2 ERM replicas, crash erm1 at t=10 s
E4 Horizontal scaling       : micro with 2 ERM replicas, N in {100, 200}

Every run starts from fresh containers. Per container we read (cgroup v2):
CPU time (cpu.stat usage_usec), memory (memory.current) and network bytes
(eth0 rx+tx) before and after the load phase.

Usage: python run_experiments.py [--reps 5] [--duration 30] [--only E1,E2,E3]
"""
import argparse, csv, json, os, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "prototype"
RAW = ROOT / "experiments" / "results" / "raw"
CSV = ROOT / "experiments" / "results" / "runs.csv"

SERVICES = {"micro": ["gateway", "erm1", "erm2", "profile", "store", "actuator"], "mono": ["monolith"]}


def sh(cmd, env=None, check=True):
    e = os.environ.copy(); e.update(env or {})
    r = subprocess.run(cmd, cwd=PROTO, env=e, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{cmd}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def compose(arch):
    return ["docker", "compose", "-f", f"docker-compose.{arch}.yml"]


def running(arch):
    out = sh(compose(arch) + ["ps", "--services", "--status", "running"], check=False)
    return [s for s in out.split() if s in SERVICES[arch]]


def probe(arch, svc):
    out = sh(compose(arch) + ["exec", "-T", svc, "sh", "-c",
             "grep usage_usec /sys/fs/cgroup/cpu.stat | cut -d' ' -f2; cat /sys/fs/cgroup/memory.current; "
             "cat /sys/class/net/eth0/statistics/rx_bytes; cat /sys/class/net/eth0/statistics/tx_bytes"], check=False)
    v = [int(x) for x in out.split()] if out.strip() else [0, 0, 0, 0]
    return {"cpu_us": v[0], "mem": v[1], "net": v[2] + v[3]}


def wait_healthy(arch, svc_entry, tries=40):
    for _ in range(tries):
        r = subprocess.run(compose(arch) + ["exec", "-T", svc_entry, "python", "-c",
                           "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"],
                           cwd=PROTO, capture_output=True)
        if r.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("service not healthy")


def run(exp, arch, n, rep, duration, extra_env=None, profiles=()):
    run_id = f"{exp}_{arch}_n{n}_r{rep}" + "".join(f"_{k}{v}" for k, v in sorted((extra_env or {}).items())
                                                    if k in ("CACHE_TTL", "REPLICAS"))
    env = {"OUT_DIR": str(RAW), "N_DEVICES": str(n), "DURATION": str(duration), "SEED": str(rep),
           "RUN_ID": run_id, **(extra_env or {})}
    prof = sum([["--profile", p] for p in profiles], [])
    sh(compose(arch) + ["--profile", "load", "--profile", "replica", "down", "-v"], env, check=False)
    sh(compose(arch) + prof + ["up", "-d"], env)
    wait_healthy(arch, "gateway" if arch == "micro" else "monolith")
    for s in running(arch):
        wait_healthy(arch, s)
    time.sleep(2)
    svcs = running(arch)
    before = {s: probe(arch, s) for s in svcs}
    t = time.time()
    sh(compose(arch) + prof + ["--profile", "load", "run", "--rm", "loadgen"], env)
    wall = time.time() - t
    after = {s: probe(arch, s) for s in running(arch)}
    cache = None
    if arch == "micro" and "erm1" in after:
        out = sh(compose(arch) + ["exec", "-T", "erm1", "python", "-c",
                 "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/cache_stats').read().decode())"], check=False)
        cache = json.loads(out) if out.strip().startswith("{") else None
    sh(compose(arch) + ["--profile", "load", "--profile", "replica", "down", "-v"], env, check=False)

    summ = json.load(open(RAW / f"{run_id}.json"))["summary"]
    cpu_s = sum(max(0, after[s]["cpu_us"] - before[s]["cpu_us"]) for s in after if s in before) / 1e6
    net = sum(max(0, after[s]["net"] - before[s]["net"]) for s in after if s in before)
    mem = sum(after[s]["mem"] for s in after) / 2**20
    row = {"exp": exp, "arch": arch, "n_devices": n, "rep": rep, "cache_ttl": (extra_env or {}).get("CACHE_TTL", "0"),
           "replicas": (extra_env or {}).get("REPLICAS", "1"), **{k: summ.get(k) for k in
           ["requests", "ok", "failed", "throughput_rps", "lat_mean_ms", "lat_p50_ms", "lat_p95_ms", "lat_p99_ms",
            "failed_after_crash", "recovery_s"]},
           "cpu_s": round(cpu_s, 3), "cpu_ms_per_req": round(1000 * cpu_s / max(1, summ["ok"]), 4),
           "mem_mib": round(mem, 1), "net_kib": round(net / 1024, 1),
           "net_bytes_per_req": round(net / max(1, summ["ok"]), 1),
           "per_service": json.dumps({s: {"cpu_s": round((after[s]["cpu_us"] - before[s]["cpu_us"]) / 1e6, 3),
                                         "mem_mib": round(after[s]["mem"] / 2**20, 1)} for s in after if s in before}),
           "cache_hits": cache and cache.get("hits"), "cache_misses": cache and cache.get("misses"),
           "wall_s": round(wall, 1)}
    new = not CSV.exists()
    with open(CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row)); new and w.writeheader(); w.writerow(row)
    print(f"{run_id}: ok={summ['ok']} fail={summ['failed']} p50={summ['lat_p50_ms'] and round(summ['lat_p50_ms'],1)}ms "
          f"p95={summ['lat_p95_ms'] and round(summ['lat_p95_ms'],1)}ms cpu={cpu_s:.2f}s mem={mem:.0f}MiB", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--only", default="E1,E2,E3")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    exps = a.only.split(",")
    for rep in range(1, a.reps + 1):          # interleave repetitions to spread drift
        if "E1" in exps:
            for n in (10, 50, 100, 200, 400):
                for arch in ("micro", "mono"):
                    run("E1", arch, n, rep, a.duration)
        if "E2" in exps:
            for ttl in ("0", "60"):
                run("E2", "micro", 100, rep, a.duration, {"CACHE_TTL": ttl})
        if "E3" in exps:
            for reps_ in ("1", "2"):
                urls = "http://erm1:8000" + (",http://erm2:8000" if reps_ == "2" else "")
                run("E3", "micro", 50, rep, a.duration,
                    {"REPLICAS": reps_, "ERM_URLS": urls, "CRASH_AT": "10", "CRASH_URL": "http://erm1:8000/admin/crash"},
                    profiles=("replica",) if reps_ == "2" else ())
        if "E4" in exps:                      # horizontal scaling: 2 ERM replicas
            for n in (100, 200):
                run("E4", "micro", n, rep, a.duration,
                    {"REPLICAS": "2", "ERM_URLS": "http://erm1:8000,http://erm2:8000"}, profiles=("replica",))


if __name__ == "__main__":
    main()
