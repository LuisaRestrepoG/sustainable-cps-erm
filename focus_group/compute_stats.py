"""Recomputes the focus-group table of the paper from the anonymized responses.

Scale: 1 = strongly disagree ... 5 = strongly agree. The negatively worded item
(reverse_coded = yes in items.csv) is reverse-coded (6 - x) before aggregation.
Statistics per criterion are computed over all responses of all experts to the items of
that criterion (pooled). Quartiles use linear interpolation (numpy default, equivalent
to Excel QUARTILE.INC). SD is the sample standard deviation; CV = SD / mean.

Usage: python compute_stats.py  [responses_anonymized.csv items.csv]
"""
import csv, sys, statistics as st
from pathlib import Path
import numpy as np

here = Path(__file__).resolve().parent
resp_path = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "responses_anonymized.csv"
items_path = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "items.csv"

items = list(csv.DictReader(open(items_path, encoding="utf-8")))
resp = list(csv.DictReader(open(resp_path, encoding="utf-8")))
order = []
for it in items:
    if it["criterion"] not in order:
        order.append(it["criterion"])

print(f"experts: {len(resp)}; years of experience: {sorted(int(r['years_experience']) for r in resp)}")
print(f"{'Criterion':38s} {'k':>2s} {'n':>3s} {'Mean':>5s} {'Med':>4s} {'Mode':>4s} {'SD':>4s} {'CV':>4s} {'Q1':>4s} {'Q3':>4s} {'IQR':>4s}")
out = []
for c in order:
    its = [i for i in items if i["criterion"] == c]
    v = []
    for r in resp:
        for i in its:
            x = int(r[i["item"]])
            v.append(6 - x if i["reverse_coded"] == "yes" else x)
    q1, q3 = np.percentile(v, [25, 75])
    sd = np.std(v, ddof=1)
    row = dict(criterion=c, k=len(its), n=len(v), mean=np.mean(v), median=float(np.median(v)),
               mode="/".join(str(m) for m in sorted(st.multimode(v))), sd=sd, cv=sd / np.mean(v), q1=q1, q3=q3, iqr=q3 - q1)
    out.append(row)
    print(f"{c:38s} {row['k']:2d} {row['n']:3d} {row['mean']:5.2f} {row['median']:4.1f} {row['mode']:>4s} "
          f"{sd:4.2f} {row['cv']:4.2f} {q1:4.2f} {q3:4.2f} {row['iqr']:4.2f}")
with open(here / "summary.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader()
    for row in out:
        w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()})
