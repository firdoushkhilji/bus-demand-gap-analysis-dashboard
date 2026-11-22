"""Step 1: clean and join raw data into one row per LSOA (England).
Run from the project root:  python3 src/01_clean.py
Output: data/clean/lsoa_base.parquet
"""
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree

RAW = Path("data/raw")
OUT = Path("data/clean")
OUT.mkdir(parents=True, exist_ok=True)

# 1. Boundaries (England only), projected to British National Grid (metres)
lsoa = gpd.read_file(RAW / "lsoa_boundaries_2021_bsc.geojson")
lsoa = lsoa[lsoa["LSOA21CD"].str.startswith("E")].to_crs(27700)
lsoa = lsoa[["LSOA21CD", "LSOA21NM", "RUC21CD", "Urban_rura", "geometry"]]
lsoa["area_km2"] = lsoa.geometry.area / 1e6
lsoa["cent_x"] = lsoa.geometry.centroid.x  # geometric centroid (limitation)
lsoa["cent_y"] = lsoa.geometry.centroid.y
print("LSOAs (England):", len(lsoa))

# 2. Population (mid-2024)
pop = pd.read_excel(RAW / "lsoa_population_2022_2024.xlsx",
                    sheet_name="Mid-2024 LSOA 2021", header=3,
                    usecols=["LSOA 2021 Code", "Total"])
pop.columns = ["LSOA21CD", "population"]

# 3. IMD 2025
imd = pd.read_csv(RAW / "imd_2025.csv")
imd = imd.rename(columns={
    "LSOA code (2021)": "LSOA21CD",
    "Index of Multiple Deprivation (IMD) Score": "imd_score",
    "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)": "imd_decile",
})[["LSOA21CD", "imd_score", "imd_decile"]]

# 4. NaPTAN: active bus stops only
stops = pd.read_csv(RAW / "naptan.csv", low_memory=False,
                    usecols=["ATCOCode", "StopType", "Status", "Easting", "Northing"])
stops = stops[(stops.Status == "active") & stops.StopType.isin(["BCT", "BCS"])]
stops = stops.dropna(subset=["Easting", "Northing"])
print("Active bus stops:", len(stops))
sg = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(stops.Easting, stops.Northing),
                      crs=27700)

# 5. Stops per LSOA (spatial join) and distance from centroid to nearest stop
j = gpd.sjoin(sg, lsoa[["LSOA21CD", "geometry"]], how="inner", predicate="within")
counts = j.groupby("LSOA21CD").size().rename("n_stops")
tree = cKDTree(np.c_[stops.Easting, stops.Northing])
dist, _ = tree.query(np.c_[lsoa["cent_x"], lsoa["cent_y"]])
lsoa["dist_nearest_stop_m"] = dist

# 6. Join everything
df = (lsoa.drop(columns="geometry")
      .merge(pop, on="LSOA21CD", how="left")
      .merge(imd, on="LSOA21CD", how="left")
      .merge(counts, on="LSOA21CD", how="left"))
df["n_stops"] = df["n_stops"].fillna(0).astype(int)
df["pop_density"] = df["population"] / df["area_km2"]

# 7. Checks
print(df.isna().sum()[lambda s: s > 0])
assert df["LSOA21CD"].is_unique
df.to_parquet(OUT / "lsoa_base.parquet", index=False)
print(df.describe().T[["min", "50%", "max"]])
print("Saved", OUT / "lsoa_base.parquet")
