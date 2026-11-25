"""Shared constants, colour helpers and data loading for the dashboard."""
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

DATA = Path(__file__).parent / "data"

# ---------- palettes: black, beige and red ----------
BLACK, RED, BEIGE, GREY = "#141414", "#c1121f", "#faf7f1", "#a39a8c"
ASSETS = Path(__file__).parent / "assets"
GAP = ["#f6efe0", "#f2b9a0", "#e8603f", "#c1121f", "#5c0a12"]          # beige -> red -> dark red
FREQ = ["#efe8d8", "#b9ad98", "#6e6657", "#2e2a24", "#0d0d0d"]         # beige -> black
CLUSTER_COL = {"High frequency, all day": "#141414", "Low frequency, all day": "#8f877c",
               "Morning-peak heavy": "#d62828", "Off-peak only": "#8a5a2b", "No service": "#d9d2c5"}


def hex2rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def ramp(t, stops):
    """t in 0-1 (array) -> N x 3 uint8 colours interpolated along stops."""
    t = np.clip(np.nan_to_num(t), 0, 1)
    pts = np.array([hex2rgb(s) for s in stops], dtype=float)
    x = np.linspace(0, 1, len(pts))
    return np.stack([np.interp(t, x, pts[:, k]) for k in range(3)], axis=1).astype(np.uint8)


# ---------- data ----------
@st.cache_data
def load():
    df = pd.read_parquet(DATA / "lsoa.parquet")
    # LSOA names are "<local authority> <code>", e.g. "Manchester 014C"
    df["la"] = df["LSOA21NM"].str.rsplit(" ", n=1).str[0]
    return df


@st.cache_data
def components(df):
    """Same normalisation as notebook 02 (winsorise 1-99%, scale 0-1). Higher = worse provision / higher need."""
    raw = pd.DataFrame({
        "access": df["dist_nearest_stop_m"],
        "supply": -np.log1p(df["freq_per_1000"]),
        "density": df["pop_density"],
        "deprivation": df["imd_score"],
    })

    def norm(s):
        a, b = s.quantile([0.01, 0.99])
        return (s.clip(a, b) - a) / (b - a)

    return raw.apply(norm)


def read_csv_optional(name):
    """Read a csv from dashboard/data; None if it is not there (older exports)."""
    p = DATA / name
    return pd.read_csv(p) if p.exists() else None


def logo_svg():
    return (ASSETS / "bus_logo.svg").read_text()
