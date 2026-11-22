"""Step 2: weighted demand-gap score per LSOA + sensitivity analysis.
Run from project root:  python3 src/02_score.py
Input : data/clean/lsoa_base.parquet
Output: data/clean/lsoa_score.parquet, data/clean/sensitivity.csv
Higher score = bigger gap between need and provision.
"""
from pathlib import Path
import numpy as np
import pandas as pd

CLEAN = Path("data/clean")
df = pd.read_parquet(CLEAN / "lsoa_base.parquet")

# --- Components (each oriented so higher = worse provision / higher need) ---
df["stops_per_1000"] = df["n_stops"] / df["population"] * 1000
comp = pd.DataFrame({
    "access":  df["dist_nearest_stop_m"],          # far from a stop
    "supply":  -df["stops_per_1000"],              # few stops per person
    # TODO after GTFS: replace "supply" with service frequency (trips/hour by time band)
    "density": df["pop_density"],                  # many people to serve
    "deprivation": df["imd_score"],                # higher = more deprived
}, index=df.index)

def norm01(s, lo=0.01, hi=0.99):
    """Winsorise at 1st/99th percentile, then min-max to 0-1."""
    a, b = s.quantile([lo, hi])
    return ((s.clip(a, b) - a) / (b - a))

N = comp.apply(norm01)

# --- Baseline weights (PLACEHOLDER: justify from literature in the report) ---
W = {"access": 0.30, "supply": 0.30, "density": 0.20, "deprivation": 0.20}

def score(weights):
    w = pd.Series(weights)[N.columns]
    return (N * (w / w.sum())).sum(axis=1)

df["gap_score"] = score(W)
df["gap_rank"] = df["gap_score"].rank(ascending=False, method="first").astype(int)
df["gap_top10"] = df["gap_rank"] <= int(0.10 * len(df))

# --- Sensitivity: 500 random weight sets (Dirichlet), compare with baseline ---
rng = np.random.default_rng(42)
base_top = set(df.index[df["gap_top10"]])
base_rank = df["gap_score"].rank()
rows = []
for i in range(500):
    w = dict(zip(N.columns, rng.dirichlet(np.ones(len(N.columns)))))
    s = score(w)
    top = set(s.nlargest(len(base_top)).index)
    rows.append({"run": i, **w,
                 "spearman_vs_base": s.rank().corr(base_rank),
                 "top10_overlap": len(top & base_top) / len(base_top)})
sens = pd.DataFrame(rows)

df.to_parquet(CLEAN / "lsoa_score.parquet", index=False)
sens.to_csv(CLEAN / "sensitivity.csv", index=False)

print("Baseline weights:", W)
print(df["gap_score"].describe().round(3))
print("\nSensitivity (500 random weight sets):")
print(sens[["spearman_vs_base", "top10_overlap"]].describe().round(3))
print("\nTop 10% by region type:")
print(df.groupby("Urban_rura")["gap_top10"].mean().round(3))
