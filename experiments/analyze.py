"""Aggregates results/runs.csv.

- Per configuration: median and interquartile range (robust to the stalled runs,
  which are kept, not excluded), plus mean and 95 % CI for reference.
- Mann-Whitney U tests (two-sided) micro vs mono (E1), cache on vs off (E2),
  1 vs 2 replicas (E3), and 1 vs 2 replicas under load (E1 vs E4).
- pgfplots data files (median, q1, q3) for the paper figures.

CPU energy is ESTIMATED (not measured) with a linear model:
  E = CPU time x P_thread,  P_thread = TDP / hardware threads  (i7-4790K: 88 W / 8 = 11 W)
This is an upper bound of the dynamic CPU energy attributable to the services.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

R = Path(__file__).resolve().parent / "results"
P_THREAD_W = 88.0 / 8

df = pd.read_csv(R / "runs.csv")
df["cache_ttl"] = df["cache_ttl"].astype(str)
df["replicas"] = df["replicas"].astype(str)
df["energy_mj_per_req"] = df["cpu_ms_per_req"] * P_THREAD_W          # ms * W = mJ
df["served_ratio"] = df["throughput_rps"] / df["n_devices"]
df["cpu_w_avg"] = df["cpu_s"] / 30.0 * P_THREAD_W                      # avg estimated CPU power (30 s runs)
df["hit_ratio"] = df["cache_hits"] / (df["cache_hits"] + df["cache_misses"])
# a run is flagged as "stalled" if, in some window of >= 5 consecutive seconds, the whole
# system completed no request at all (all devices waiting on 10 s timeouts). Stalled runs are
# KEPT in every statistic; the flag is only reported.
import json


def longest_zero_window(run_id):
    rec = json.load(open(R / "raw" / f"{run_id}.json"))["records"]
    per_s = np.zeros(31, int)
    for t, lat, ok in rec:
        if ok and int(t + lat) < 31:
            per_s[int(t + lat)] += 1
    best = cur = 0
    for v in per_s[:30]:
        cur = cur + 1 if v == 0 else 0
        best = max(best, cur)
    return best


def run_id(r):
    rid = f"{r.exp}_{r.arch}_n{r.n_devices}_r{r.rep}"
    if r.exp == "E2":
        rid += f"_CACHE_TTL{r.cache_ttl}"
    if r.exp in ("E3", "E4"):
        rid += f"_REPLICAS{r.replicas}"
    return rid


df["zero_window_s"] = [longest_zero_window(run_id(r)) for r in df.itertuples()]
df["stalled"] = df["zero_window_s"] >= 5
df.to_csv(R / "runs_enriched.csv", index=False)

METRICS = ["throughput_rps", "served_ratio", "lat_p50_ms", "lat_p95_ms", "lat_p99_ms", "cpu_ms_per_req",
           "energy_mj_per_req", "cpu_w_avg", "mem_mib", "net_bytes_per_req", "failed", "failed_after_crash",
           "recovery_s", "hit_ratio"]
keys = ["exp", "arch", "n_devices", "cache_ttl", "replicas"]
rows = []
for k, g in df.groupby(keys):
    row = dict(zip(keys, k)); row["reps"] = len(g); row["stalled_runs"] = int(g["stalled"].sum())
    for m in METRICS:
        x = g[m].astype(float).dropna()
        if len(x) == 0:
            continue
        row[m + "_med"] = x.median(); row[m + "_q1"] = x.quantile(.25); row[m + "_q3"] = x.quantile(.75)
        row[m + "_mean"] = x.mean()
        row[m + "_ci95"] = stats.t.ppf(.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan
    rows.append(row)
agg = pd.DataFrame(rows)
agg.to_csv(R / "summary.csv", index=False)


def mwu(a, b, label, metric, n):
    a, b = a.astype(float).dropna(), b.astype(float).dropna()
    if len(a) < 2 or len(b) < 2:
        return None
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {"comparison": label, "n_devices": n, "metric": metric, "A_median": a.median(), "B_median": b.median(),
            "ratio_A_B": a.median() / b.median() if b.median() else np.nan, "U": u, "p_value": p}


tests = []
e1 = df[df.exp == "E1"]
for n, g in e1.groupby("n_devices"):
    for m in ["lat_p50_ms", "lat_p95_ms", "throughput_rps", "cpu_ms_per_req", "mem_mib", "net_bytes_per_req"]:
        tests.append(mwu(g[g.arch == "micro"][m], g[g.arch == "mono"][m], "E1 micro(A) vs mono(B)", m, n))
e2 = df[df.exp == "E2"]
for m in ["lat_p50_ms", "lat_p95_ms", "cpu_ms_per_req", "net_bytes_per_req", "throughput_rps"]:
    tests.append(mwu(e2[e2.cache_ttl == "60"][m], e2[e2.cache_ttl == "0"][m], "E2 cache on(A) vs off(B)", m, 100))
e3 = df[df.exp == "E3"]
for m in ["failed_after_crash", "recovery_s", "lat_p95_ms", "mem_mib"]:
    tests.append(mwu(e3[e3.replicas == "2"][m], e3[e3.replicas == "1"][m], "E3 2 replicas(A) vs 1(B)", m, 50))
e4 = df[df.exp == "E4"]
for n in (100, 200):
    for m in ["throughput_rps", "lat_p50_ms", "lat_p95_ms"]:
        if len(e4):
            tests.append(mwu(e4[e4.n_devices == n][m], e1[(e1.arch == "micro") & (e1.n_devices == n)][m],
                             "E4 2 replicas(A) vs E1 1 replica(B)", m, n))
tests = pd.DataFrame([t for t in tests if t])
tests.to_csv(R / "tests.csv", index=False)

pg = R / "pgf"; pg.mkdir(exist_ok=True)
cols = ["n_devices"] + [f"{m}_{s}" for m in ["lat_p50_ms", "lat_p95_ms", "throughput_rps", "cpu_ms_per_req",
                                            "energy_mj_per_req", "mem_mib"] for s in ("med", "q1", "q3")]
for (exp, arch, rep), name in [(("E1", "micro", "1"), "e1_micro"), (("E1", "mono", "1"), "e1_mono"),
                               (("E4", "micro", "2"), "e4_micro2")]:
    s = agg[(agg.exp == exp) & (agg.arch == arch) & (agg.replicas == rep)].sort_values("n_devices")
    if len(s):
        s[cols].to_csv(pg / f"{name}.dat", sep=" ", index=False, float_format="%.3f")

pd.set_option("display.width", 300)
show = ["exp", "arch", "n_devices", "cache_ttl", "replicas", "reps", "stalled_runs"]
for m in ["throughput_rps", "lat_p50_ms", "lat_p95_ms", "cpu_ms_per_req", "mem_mib", "net_bytes_per_req",
          "failed_after_crash", "recovery_s", "hit_ratio", "cpu_w_avg"]:
    agg[m] = agg.apply(lambda r: f"{r.get(m+'_med', np.nan):.1f} [{r.get(m+'_q1', np.nan):.1f}-{r.get(m+'_q3', np.nan):.1f}]"
                       if pd.notna(r.get(m + "_med", np.nan)) else "-", axis=1)
    show.append(m)
print(agg[show].to_string(index=False))
print()
print(tests.round(4).to_string(index=False))
