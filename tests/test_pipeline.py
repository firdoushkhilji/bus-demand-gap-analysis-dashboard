"""Automated checks on the pipeline outputs.

Run from the project root:   python3 -m pytest tests -v

Most tests use dashboard/data/lsoa.parquet (committed to the repository), so they run without the raw data.
Tests marked "needs clean data" use data/clean/ and are skipped if those files are not present.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DASH = ROOT / "dashboard" / "data"
CLEAN = ROOT / "data" / "clean"

# DfT annual bus statistics, England, year ending March 2025 (same values as notebook 03)
REGIONS = {"London": (1.82e9, 8_913), "Metropolitan": (0.78e9, 7_899), "Non-metropolitan": (1.07e9, 13_745)}
FLOOR, OVERSUPPLY = 0.5, 1.2
TOL = 1e-6
BANDS = ["morning", "off_peak", "evening"]


@pytest.fixture(scope="module")
def d():
    return pd.read_parquet(DASH / "lsoa.parquet")


def needs_clean(name):
    p = CLEAN / name
    if not p.exists():
        pytest.skip(f"needs clean data: {p.name} not found (run the notebooks first)")
    return pd.read_csv(p) if p.suffix == ".csv" else pd.read_parquet(p)


# ---------- data integrity ----------
def test_one_row_per_england_lsoa(d):
    assert len(d) == 33_755
    assert d["LSOA21CD"].is_unique
    assert d["LSOA21CD"].str.startswith("E01").all()


def test_no_missing_values_in_key_columns(d):
    cols = ["population", "pop_density", "imd_score", "dist_nearest_stop_m", "freq_morning", "freq_off_peak",
            "freq_evening", "gap_score", "cluster", "region", "x0", "x_opt"]
    assert d[cols].isna().sum().sum() == 0


def test_values_in_valid_ranges(d):
    assert (d["population"] > 0).all()
    assert (d["dist_nearest_stop_m"] >= 0).all()
    assert (d[["freq_morning", "freq_off_peak", "freq_evening"]] >= 0).all().all()
    assert d["imd_decile"].between(1, 10).all()
    assert d["lat"].between(49.5, 56).all() and d["lon"].between(-6.5, 2).all()


def test_regions_match_known_lsoa_counts(d):
    # London has 4,994 LSOAs in England (2021 boundaries)
    assert (d["region"] == "London").sum() == 4_994
    assert set(d["region"]) == set(REGIONS)


def test_cleaning_log_is_consistent():
    log = needs_clean("cleaning_log.csv")
    assert (log["Rows after"] <= log["Rows before"]).all()


# ---------- demand-gap score ----------
def _norm(s):
    a, b = s.quantile([0.01, 0.99])
    return (s.clip(a, b) - a) / (b - a)


def test_score_between_0_and_1_and_rank_valid(d):
    assert d["gap_score"].between(0, 1).all()
    assert sorted(d["gap_rank"]) == list(range(1, len(d) + 1))


def test_score_reproduces_from_components(d):
    N = pd.DataFrame({"access": _norm(d["dist_nearest_stop_m"]), "supply": _norm(-np.log1p(d["freq_per_1000"])),
                      "density": _norm(d["pop_density"]), "deprivation": _norm(d["imd_score"])})
    expected = N["access"] * 0.3 + N["supply"] * 0.3 + N["density"] * 0.2 + N["deprivation"] * 0.2
    assert np.abs(expected - d["gap_score"]).max() < 1e-3          # parquet stores 5 decimals


def test_score_direction(d):
    """Further from a stop, less service and more deprivation should raise the score."""
    assert d["gap_score"].corr(d["dist_nearest_stop_m"], method="spearman") > 0.2
    assert d["gap_score"].corr(d["freq_per_1000"], method="spearman") < -0.2
    assert d["gap_score"].corr(d["imd_score"], method="spearman") > 0


def test_no_service_areas_score_higher_than_median(d):
    none = d[(d[["freq_morning", "freq_off_peak", "freq_evening"]].sum(axis=1) == 0)]
    assert len(none) > 0 and none["gap_score"].median() > d["gap_score"].median()


# ---------- clustering ----------
def test_cluster_labels_and_no_service_group(d):
    no_service = d[["freq_morning", "freq_off_peak", "freq_evening"]].sum(axis=1) == 0
    assert set(d["cluster"].unique()) == {-1, 0, 1, 2, 3}
    assert ((d["cluster"] == -1) == no_service).all()              # -1 exactly equals "no service"


def test_cluster_names_present(d):
    assert d.loc[d["cluster"] == -1, "cluster_name"].eq("No service").all()
    assert d["cluster_name"].notna().all()


# ---------- optimisation ----------
@pytest.mark.parametrize("region", list(REGIONS))
def test_fleet_constraint_daily(d, region):
    g = d[d["region"] == region]
    assert g["x_opt"].sum() <= REGIONS[region][1] + 1e-3
    assert g["x0"].sum() == pytest.approx(REGIONS[region][1], rel=1e-6)   # baseline uses the whole fleet


@pytest.mark.parametrize("region", list(REGIONS))
def test_allocation_bounds_daily(d, region):
    journeys, fleet = REGIONS[region]
    cap = journeys / 365 / fleet
    g = d[d["region"] == region]
    lo = FLOOR * g["x0"]
    hi = np.maximum(OVERSUPPLY * g["demand"] / cap, lo)
    assert (g["x_opt"] >= lo - 1e-4).all()
    assert (g["x_opt"] <= hi + 1e-4).all()


@pytest.mark.parametrize("region", list(REGIONS))
def test_optimised_never_worse_than_baseline(d, region):
    g = d[d["region"] == region]
    assert g["unmet_opt"].sum() <= g["unmet0"].sum() + 1e-3


def test_unmet_is_consistent_with_allocation(d):
    cap = d["region"].map({r: j / 365 / f for r, (j, f) in REGIONS.items()})
    recomputed = np.clip(d["demand"] - cap * d["x_opt"], 0, None)
    assert np.abs(recomputed - d["unmet_opt"]).max() < 1e-2


@pytest.mark.parametrize("band", BANDS)
@pytest.mark.parametrize("region", list(REGIONS))
def test_fleet_constraint_by_band(d, band, region):
    g = d[d["region"] == region]
    assert g[f"xopt_{band}"].sum() <= REGIONS[region][1] + 1e-3
    assert (g[f"xopt_{band}"] >= -1e-9).all()


def test_total_demand_matches_dft_journeys(d):
    """Calibration check: estimated demand per region equals DfT journeys per day."""
    for region, (journeys, _) in REGIONS.items():
        assert d.loc[d["region"] == region, "demand"].sum() == pytest.approx(journeys / 365, rel=1e-3)


# ---------- validation against PTAI ----------
def test_ptai_validation_direction():
    v = pd.read_csv(CLEAN / "validation_ptai.csv") if (CLEAN / "validation_ptai.csv").exists() else None
    if v is None:
        pytest.skip("needs clean data: validation_ptai.csv not found (run notebook 07)")
    jobs = v[v["PTAI measure"].str.contains("Jobs reachable in 45")].iloc[0]
    assert jobs["rho Rural"] < 0                                   # expected sign for rural areas
    assert v["n"].min() > 30_000                                   # most LSOAs matched PTAI


# ---------- dashboard data ----------
def test_dashboard_files_present():
    for f in ["lsoa.parquet", "allocation_sensitivity.csv", "allocation_bands.csv"]:
        assert (DASH / f).exists(), f


def test_sensitivity_table_shape():
    s = pd.read_csv(DASH / "allocation_sensitivity.csv")
    assert len(s) == 9 and s["reduction"].between(0, 1).all()
