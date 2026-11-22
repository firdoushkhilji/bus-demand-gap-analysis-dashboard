# Bus Route Demand and Vehicle Allocation Dashboard (England)

MSc Data Science dissertation project (7005SCN). An open-data dashboard that identifies where bus provision falls short of likely demand and suggests vehicle allocation by time of day.

## Method (short)
- Weighted demand-gap score per LSOA (distance to nearest stop, service frequency, population density, deprivation)
- K-means clustering of areas by time-of-day service patterns (morning, evening, off-peak)
- Linear programming (PuLP) for vehicle allocation under stated assumptions
- Evaluation against PTAI-2022 and sensitivity analysis. No predictive machine learning.

## Data sources (secondary, open; not stored in this repository)
| Dataset | Publisher | URL | Licence | Date downloaded |
|---|---|---|---|---|
| NaPTAN bus stops | Department for Transport | beta-naptan.dft.gov.uk | | |
| Bus timetables (GTFS), pilot region | DfT Bus Open Data Service | data.bus-data.dft.gov.uk | | |
| LSOA 2021 boundaries (BGC) | Office for National Statistics | geoportal.statistics.gov.uk | | |
| LSOA population-weighted centroids | Office for National Statistics | geoportal.statistics.gov.uk | | |
| LSOA population estimates | Office for National Statistics | | | |
| Index of Multiple Deprivation | MHCLG | | | |
| PTAI-2022 | Urban Big Data Centre | | | |

## Folder structure
- `data/raw`, `data/clean`: downloaded and processed data (not committed)
- `notebooks`: exploration and analysis
- `src`: reusable code
- `dashboard`: Streamlit app
- `tests`: checks and tests
- `report`: report files and ethics certificate

## Setup
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python check_setup.py
```

## Run the dashboard
To be completed once the dashboard is built.
