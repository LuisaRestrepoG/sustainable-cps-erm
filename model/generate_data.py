"""Synthetic data generator for the ERM-HS1 lab case (stage 1 hypertension).

IMPORTANT: this is SYNTHETIC data. The generative relationships below are
modelling ASSUMPTIONS chosen to be clinically plausible for illustration; they
are not estimated from patients and must not be used for clinical purposes.

Each record is an older adult who starts a 3-month treatment plan with a stage 1
systolic blood pressure (SBP) of 130-139 mm Hg (2017 ACC/AHA categories).
Target: SBP after 3 months.

Usage:  python generate_data.py --n 1000 --seed 42 --out data/synthetic_patients.csv
"""
import argparse
import numpy as np
import pandas as pd

# ---- generative assumptions (documented in the paper, Table "Synthetic data") ----
ADHERENCE_EFFECT = -10.0   # mm Hg change at 100 % medication adherence vs 0 %
AGE_EFFECT = 0.15          # mm Hg per year above 70
WEIGHT_EFFECT = 0.20       # mm Hg per kg above 73 kg
HR_EFFECT = 0.10           # mm Hg per bpm above 74
SEX_EFFECT = 1.5           # mm Hg, male vs female
NOISE_SD = 4.0             # mm Hg, unexplained within-patient variability


def generate(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    sex = rng.integers(0, 2, n)                                   # 0 female, 1 male
    age = rng.integers(60, 91, n)                                 # years
    weight = np.clip(rng.normal(np.where(sex == 1, 78, 68), 12), 45, 130).round(1)  # kg
    heart_rate = np.clip(rng.normal(74, 9, n), 50, 110).round(0)  # bpm
    temperature = np.clip(rng.normal(36.7, 0.3, n), 35.5, 38.5).round(1)  # deg C (not causal)
    adherence = (rng.beta(5, 2, n) * 100).round(0)                # % of prescribed doses taken
    sbp0 = rng.uniform(130, 140, n).round(0).clip(130, 139)       # baseline SBP, stage 1
    sbp3 = (sbp0
            + ADHERENCE_EFFECT * adherence / 100
            + AGE_EFFECT * (age - 70)
            + WEIGHT_EFFECT * (weight - 73)
            + HR_EFFECT * (heart_rate - 74)
            + SEX_EFFECT * sex
            + rng.normal(0, NOISE_SD, n)).round(1)
    return pd.DataFrame({
        "age": age, "sex": sex, "weight_kg": weight, "heart_rate_bpm": heart_rate,
        "temperature_c": temperature, "medication_adherence_pct": adherence,
        "sbp_baseline": sbp0, "sbp_3_months": sbp3,
    })


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/synthetic_patients.csv")
    a = ap.parse_args()
    import os
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    df = generate(a.n, a.seed)
    df.to_csv(a.out, index=False)
    print(df.describe().round(1).to_string())
