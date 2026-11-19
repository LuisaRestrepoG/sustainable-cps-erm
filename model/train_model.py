"""Trains and evaluates the blood pressure estimation model of ERM-HS1 (Task 1).

- Compares a mean baseline, multiple linear regression, and a random forest.
- Repeated 5-fold cross-validation (10 repetitions) on the training split +
  a held-out 20 % test split.
- Recomputes the two illustrative cases of the paper with the final model.
- Saves the final model (linear regression) for the prototype.

Usage:  python train_model.py --data data/synthetic_patients.csv --outdir results
"""
import argparse, json, os, platform
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RepeatedKFold, cross_validate, train_test_split
import joblib

FEATURES = ["age", "sex", "weight_kg", "heart_rate_bpm", "temperature_c",
            "medication_adherence_pct", "sbp_baseline"]
TARGET = "sbp_3_months"
GOAL_SBP = 130.0      # ACC/AHA treatment goal for most adults: SBP < 130 mm Hg
CRISIS_SBP = 180.0    # ACC/AHA: SBP > 180 mm Hg = severe elevation / hypertensive crisis

CASES = {
    "Case 1": dict(age=68, sex=0, weight_kg=65.0, heart_rate_bpm=70, temperature_c=36.6,
                   medication_adherence_pct=95, sbp_baseline=139),
    "Case 2": dict(age=82, sex=1, weight_kg=92.0, heart_rate_bpm=88, temperature_c=36.8,
                   medication_adherence_pct=30, sbp_baseline=138),
}


def decide(measured_sbp: float, predicted_sbp_3m: float) -> str:
    """Decision logic of the ERM-HS1 autonomic cycle (Analyzer + Planner)."""
    if measured_sbp > CRISIS_SBP:
        return "EMERGENCY: activate emergency response plan"
    if predicted_sbp_3m >= GOAL_SBP:
        return "Goal not expected to be reached: send treatment-adjustment recommendation to clinician"
    return "On track: no intervention"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/synthetic_patients.csv")
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    df = pd.read_csv(a.data)
    X, y = df[FEATURES], df[TARGET]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=a.seed)

    models = {
        "Mean baseline": DummyRegressor(strategy="mean"),
        "Linear regression": LinearRegression(),
        "Random forest": RandomForestRegressor(n_estimators=300, min_samples_leaf=5, random_state=a.seed, n_jobs=-1),
    }
    cv = RepeatedKFold(n_splits=5, n_repeats=10, random_state=a.seed)
    scoring = {"mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error", "r2": "r2"}
    rows = []
    for name, m in models.items():
        s = cross_validate(m, X_tr, y_tr, cv=cv, scoring=scoring)
        m.fit(X_tr, y_tr)
        p = m.predict(X_te)
        rows.append({
            "model": name,
            "cv_mae_mean": -s["test_mae"].mean(), "cv_mae_sd": s["test_mae"].std(),
            "cv_rmse_mean": -s["test_rmse"].mean(), "cv_rmse_sd": s["test_rmse"].std(),
            "cv_r2_mean": s["test_r2"].mean(), "cv_r2_sd": s["test_r2"].std(),
            "test_mae": mean_absolute_error(y_te, p),
            "test_rmse": mean_squared_error(y_te, p) ** 0.5,
            "test_r2": r2_score(y_te, p),
        })
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(a.outdir, "model_metrics.csv"), index=False)
    print(res.round(3).to_string(index=False))

    final = models["Linear regression"]
    coefs = dict(zip(FEATURES, final.coef_.round(4)))
    print("\nLinear regression intercept", round(final.intercept_, 3), "coefficients", coefs)

    cases_out = {}
    for cname, feats in CASES.items():
        pred = float(final.predict(pd.DataFrame([feats]))[0])
        cases_out[cname] = {"inputs": feats, "predicted_sbp_3_months": round(pred, 1),
                            "decision": decide(feats["sbp_baseline"], pred)}
        print(f"{cname}: measured {feats['sbp_baseline']} -> predicted {pred:.1f} -> {cases_out[cname]['decision']}")

    joblib.dump(final, os.path.join(a.outdir, "bp_model.joblib"))
    meta = {"features": FEATURES, "target": TARGET, "n_records": len(df), "n_train": len(X_tr),
            "n_test": len(X_te), "seed": a.seed, "sklearn": sklearn.__version__,
            "python": platform.python_version(), "intercept": round(float(final.intercept_), 4),
            "coefficients": {k: float(v) for k, v in coefs.items()}, "cases": cases_out}
    with open(os.path.join(a.outdir, "model_summary.json"), "w") as f:
        json.dump(meta, f, indent=2)


if __name__ == "__main__":
    main()
