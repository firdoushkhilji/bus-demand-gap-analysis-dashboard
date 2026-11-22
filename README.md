# Bus Route Demand and Vehicle Allocation Dashboard (England)

MSc Data Science, 7005SCN Individual Research Project, Coventry University. Ethics: CU Ethics P197087.

Open data only, no machine-learning prediction. For each of England's 33,755 LSOAs the project builds a weighted demand-gap score, clusters areas by time-of-day service pattern (K-means), allocates buses with linear programming (PuLP/HiGHS) per region and time band, and shows the result in a Streamlit dashboard.

## Quick start (dashboard only)
The processed data the dashboard needs is already in `dashboard/data/`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run dashboard/app.py
```

## Reproduce from raw data
Put the raw files in `data/raw/` (see the data register), then run the notebooks in this order:

1. `01_cleaning.ipynb`
2. `04_gtfs_frequency.ipynb`
3. `02_scoring.ipynb`
4. `05_clustering.ipynb`
5. `03_optimisation.ipynb`
6. `06_export_dashboard_data.ipynb` (must run after 03)
7. `07_validation.ipynb`

## Tests
```bash
python3 -m pytest tests -v
```
34 tests: data integrity, score reproducibility, clustering labels, fleet and bound constraints of the allocation, calibration to DfT totals, PTAI validation direction, dashboard files. Tests needing `data/clean/` are skipped if it is absent.

## Data register
| Dataset | Source | Licence | Used for |
|---|---|---|---|
| NaPTAN | DfT | OGL v3.0 | Stop locations |
| BODS GTFS (England), topped up with TNDS | DfT | OGL v3.0 | Service frequency (Tue 2026-10-06; bands 07-10, 10-16, 16-19) |
| LSOA 2021 boundaries (BSC) | ONS | OGL v3.0 | Geography |
| Population estimates, LSOA | ONS | OGL v3.0 | Population, density |
| English Indices of Deprivation 2025 | MHCLG | OGL v3.0 | Deprivation |
| Public Transport Accessibility Indicators 2022 (v2022.1) | UBDC, doi 10.5281/zenodo.8037156 | OGL v3.0 (safeguarded) | External validation |
| Annual bus statistics, year ending March 2025 | DfT | OGL v3.0 | Demand and fleet calibration |

Add the download date for each file before submission. Raw data is not committed (see `.gitignore`).

## Method summary
- Score = 0.30 access + 0.30 supply + 0.20 density + 0.20 deprivation (winsorised 1st/99th percentile, min-max scaled). Sensitivity: 500 random weight sets plus named alternatives.
- Clustering: K-means (k = 4) on time-band shares plus a log service level; LSOAs with no service are a separate group.
- Allocation: minimise gap-weighted unmet demand; fleet cap per region, floor 50% of baseline, ceiling 120% of demand/capacity.

## Limitations
Demand is assumed proportional to population, so the headline unmet-demand reduction depends on that assumption. The provision part of the score agrees moderately with PTAI; the combined score only weakly. Overall service is nearly flat across the day.
