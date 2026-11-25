#!/usr/bin/env bash
# Re-runs the whole pipeline in the right order, then the tests.
# Usage (from the project folder):   bash run_all.sh
# Notebook 04 reads the 1 GB timetable and takes the longest. Stops at the first error.
set -e
cd "$(dirname "$0")/notebooks"
for nb in 01_cleaning 04_gtfs_frequency 02_scoring 05_clustering 03_optimisation 06_export_dashboard_data 07_validation 08_demand_validation 06_export_dashboard_data; do
  echo "=== $nb  ($(date +%H:%M:%S))"
  python3 -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=-1 "$nb.ipynb"
done
cd ..
echo "=== tests"
python3 -m pytest tests -q
echo "Done. Start the dashboard with:  streamlit run dashboard/app.py"
