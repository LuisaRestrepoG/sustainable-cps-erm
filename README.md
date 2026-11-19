# sustainable-cps-erm

Artifacts of the paper **"Towards Sustainable Cyber-Physical Systems: An Adaptation-Centric
Architectural Framework and a Lab Case for Healthcare Environments"**
(L. Restrepo, E. Suescún, J. Aguilar).

> **All patient data in this repository is synthetic.** The models and decision rules are a
> technical feasibility study of a software architecture. They are not clinically validated
> and must not be used for medical decisions.

## Contents

| Folder | What it contains |
|---|---|
| `model/` | Synthetic-data generator, training/evaluation of the blood pressure estimation model (ERM-HS1, Task 1), notebook that reproduces Cases 1 and 2 |
| `prototype/` | Docker prototype of the Emergency Response Microservice (ERM-HS1): microservice deployment (gateway, ERM with an internal MAPE-K loop, profile, store, actuator) and a monolithic baseline |
| `experiments/` | Scripts that run the three experiments of the paper (E1 scalability, E2 caching, E3 reliability) and the statistical analysis; raw and aggregated results |
| `ontology/` | SinSO ontology and the lab-case instantiation (OWL) |
| `focus_group/` | Questionnaire and anonymized responses of the expert evaluation |

## 1. Blood pressure model (5 minutes)

```bash
cd model
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python generate_data.py --n 1000 --seed 42 --out data/synthetic_patients.csv
python train_model.py --data data/synthetic_patients.csv --outdir results
```

Or open `ERM-HS1_model.ipynb` in Jupyter. The script prints the cross-validated metrics of a
mean baseline, a linear regression, and a random forest, and the decision for Cases 1 and 2.

## 2. Docker prototype

Requirements: Docker 24+ with Compose v2.

```bash
cd prototype
cp ../model/results/bp_model.joblib app/
docker build -t erm-hs1:1.0 .
docker compose -f docker-compose.micro.yml up -d          # microservice deployment
N_DEVICES=50 DURATION=30 docker compose -f docker-compose.micro.yml --profile load run --rm loadgen
docker compose -f docker-compose.micro.yml --profile load down
```

The same works with `docker-compose.mono.yml` (monolithic baseline).

Request path (microservices): load generator (simulated home devices) → `gateway`
(authentication, round-robin over ERM replicas with failover) → `erm` (Monitor → Analyzer
[model inference] → Planner [ACC/AHA rules] → Executor) → `profile` (cacheable), `store`
(knowledge, SQLite), `actuator` (alerts / recommendations).

## 3. Experiments

```bash
cd experiments
pip install -r requirements.txt
python run_experiments.py --reps 5 --duration 30     # ~1 h; fresh containers for every run
python analyze.py                                    # summary.csv, tests.csv, pgf/*.dat
```

CPU time, memory and network bytes are read from cgroup v2 / `/sys/class/net` inside each
container. CPU energy is **estimated** from CPU time with a linear TDP-based model (see
`analyze.py`); it is not a power measurement.

### Results reported in the paper

Host: Intel Core i7-4790K (4C/8T), Windows 10, Docker Desktop 29.2.1 (WSL2). Five 30 s runs per
configuration; medians; two-sided Mann-Whitney U tests. Every run is kept in
`experiments/results/runs.csv` and `experiments/results/raw/` (no run was excluded).

| Experiment | Main result |
|---|---|
| E1 micro vs mono, 10-50 devices | micro: 2.4-2.8x latency (16-21 vs 7-8 ms p50), 3-4x CPU/request, 3x memory, 7x network bytes (p = 0.008) |
| E1, 100-400 devices | micro with 1 ERM replica saturates between 50 and 100 devices (p50 0.97 s at 100); mono serves 175 req/s at 200 |
| E2 cache (100 devices) | hit ratio 0.97; CPU/request -35 %, bytes/request -22 % (p = 0.008); p50 235 -> 14 ms |
| E3 crash (50 devices) | 1 replica: 12 failed requests, 4.2 s recovery; 2 replicas: 0 failed in 4/5 runs (1 run: slow replica not detected, 62 timeouts) |
| E4 2 replicas | throughput x2.2 at 200 devices (63 -> 137 req/s), p50 2.5 s -> 0.2 s (p = 0.008) |

Known anomaly: run `E1_micro_n50_r1` served almost no requests (test-environment stall); it is kept
and flagged in `runs_enriched.csv`.

## How to cite

If you use these artifacts, please cite the paper (the full reference will be added after
publication):

> L. Restrepo, E. Suescún, J. Aguilar. *Towards Sustainable Cyber-Physical Systems: An
> Adaptation-Centric Architectural Framework and a Lab Case for Healthcare Environments.*
> Manuscript submitted to the Journal of Intelligent Manufacturing.

## License

Code: MIT (`LICENSE`). Data, results and the lab-case ontology instantiation: CC BY 4.0
(`LICENSE-DATA.md`).
