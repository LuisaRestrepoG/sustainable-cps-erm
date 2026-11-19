"""Shared logic for the ERM-HS1 prototype (used by both deployments)."""
import os
import time
import sqlite3
import threading
import numpy as np
import joblib

FEATURES = ["age", "sex", "weight_kg", "heart_rate_bpm", "temperature_c",
            "medication_adherence_pct", "sbp_baseline"]
GOAL_SBP = 130.0     # ACC/AHA treatment goal
CRISIS_SBP = 180.0   # ACC/AHA severe elevation
API_TOKEN = os.environ.get("API_TOKEN", "lab-case-token")

_model = None


def model():
    global _model
    if _model is None:
        _model = joblib.load(os.environ.get("MODEL_PATH", "/app/bp_model.joblib"))
    return _model


def make_profile(patient_id: int) -> dict:
    """Deterministic synthetic patient profile (Knowledge: user profile)."""
    rng = np.random.default_rng(1000 + patient_id)
    sex = int(rng.integers(0, 2))
    return {
        "patient_id": patient_id,
        "age": int(rng.integers(60, 91)),
        "sex": sex,
        "weight_kg": round(float(np.clip(rng.normal(78 if sex else 68, 12), 45, 130)), 1),
        "medication_adherence_pct": float(round(rng.beta(5, 2) * 100)),
        "emergency_contact": f"caregiver-{patient_id}@example.org",
    }


def analyze_and_plan(reading: dict, profile: dict) -> dict:
    """Analyzer (goal manager) + Planner (operation manager)."""
    x = np.array([[profile["age"], profile["sex"], profile["weight_kg"], reading["heart_rate_bpm"],
                   reading["temperature_c"], profile["medication_adherence_pct"], reading["sbp"]]], dtype=float)
    pred = float(model().predict(x)[0])
    if reading["sbp"] > CRISIS_SBP:
        plan = "emergency"
    elif pred >= GOAL_SBP:
        plan = "recommend_adjustment"
    else:
        plan = "none"
    return {"predicted_sbp_3m": round(pred, 1), "plan": plan}


class Store:
    """Knowledge component: append-only event log in SQLite."""
    def __init__(self, path: str):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS events (ts REAL, patient_id INT, sbp REAL, pred REAL, plan TEXT)")

    def add(self, e: dict):
        with self.lock:
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?)",
                            (time.time(), e["patient_id"], e["sbp"], e["predicted_sbp_3m"], e["plan"]))
            self.db.commit()


class TTLCache:
    """Client-side cache used by the ERM for patient profiles (energy-efficiency tactic)."""
    def __init__(self, ttl: float):
        self.ttl, self.data, self.hits, self.misses = ttl, {}, 0, 0

    def get(self, key):
        if self.ttl <= 0:
            self.misses += 1
            return None
        v = self.data.get(key)
        if v and time.monotonic() - v[0] < self.ttl:
            self.hits += 1
            return v[1]
        self.misses += 1
        return None

    def put(self, key, value):
        if self.ttl > 0:
            self.data[key] = (time.monotonic(), value)
