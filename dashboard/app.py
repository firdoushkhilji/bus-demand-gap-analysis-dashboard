"""Bus Route Demand & Vehicle Allocation Dashboard (England, LSOA level).
Run from the project root:  streamlit run dashboard/app.py
Data: dashboard/data/lsoa.parquet (made by notebooks/06_export_dashboard_data.ipynb)
"""
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="Bus Demand Gap Dashboard", page_icon="🚌", layout="wide")
DATA = Path(__file__).parent / "data"

st.markdown("""<style>
.block-container{padding-top:2.4rem;padding-bottom:0.4rem;max-width:100%}
header[data-testid="stHeader"]{height:2rem;background:transparent}
[data-testid="stMetricValue"]{font-size:1.45rem}
[data-testid="stMetricLabel"] p{font-size:0.74rem;white-space:normal;line-height:1.15}
[data-testid="stSidebar"] .block-container{padding-top:1.2rem}
h3{padding:0 0 .1rem 0!important;margin:0!important}
</style>""", unsafe_allow_html=True)

# ---------- palettes ----------
GAP = ["#f3ecdd", "#f0c27b", "#e0883d", "#b8442f", "#6e1f3a"]
FREQ = ["#eef3f2", "#9ccbc4", "#3d8f8c", "#1d5a63", "#0e2f3d"]
CLUSTER_COL = {"High frequency, all day": "#1d5a63", "Low frequency, all day": "#8fc1bb",
               "Morning-peak heavy": "#e0883d", "Off-peak only": "#6e1f3a", "No service": "#a6a6a6"}


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


df = load()
N = components(df)

# ---------- sidebar ----------
st.sidebar.markdown("**Controls**")
las = ["All England"] + sorted(df["la"].unique())
place = st.sidebar.selectbox("City / local authority", las, help="Type to search, e.g. Manchester, Leeds, Bristol.")
area = st.sidebar.radio("Area type", ["All", "Urban", "Rural"], horizontal=True)
layer = st.sidebar.selectbox("Map layer", ["Demand-gap score", "Service frequency", "Service pattern (cluster)",
                                           "Allocation change (vehicles)"])
band_label = "Morning (07-10)"
if layer == "Service frequency":
    band_label = st.sidebar.selectbox("Time band", ["Morning (07-10)", "Off-peak (10-16)", "Evening (16-19)"])
alloc_band = "All day (daily model)"
if layer == "Allocation change (vehicles)":
    alloc_band = st.sidebar.selectbox("Allocation for", ["All day (daily model)", "Morning (07-10)",
                                                          "Off-peak (10-16)", "Evening (16-19)"])
top_pct = st.sidebar.slider("Highlight biggest-gap areas (top %)", 0, 30, 10, step=5,
                            help="Ranked within the area you selected. 0 = no highlight; others are dimmed.")

with st.sidebar.expander("Score weights (sensitivity)"):
    st.caption("Change the weights to see how the ranking moves. They are rescaled to sum to 1.")
    DEFAULT_W = {"access": 30, "supply": 30, "density": 20, "deprivation": 20}
    if st.button("Reset weights"):
        for k in DEFAULT_W:
            st.session_state[f"w_{k}"] = DEFAULT_W[k]
    W = {
        "access": st.slider("Distance to nearest stop", 0, 100, DEFAULT_W["access"], key="w_access"),
        "supply": st.slider("Low service per person", 0, 100, DEFAULT_W["supply"], key="w_supply"),
        "density": st.slider("Population density", 0, 100, DEFAULT_W["density"], key="w_density"),
        "deprivation": st.slider("Deprivation (IMD 2025)", 0, 100, DEFAULT_W["deprivation"], key="w_deprivation"),
    }
if sum(W.values()) == 0:
    st.sidebar.warning("All weights are 0: using the defaults.")
    W = DEFAULT_W
w = pd.Series(W)[N.columns]
d = df.copy()
d["gap"] = (N * (w / w.sum())).sum(axis=1)

view = d
if place != "All England":
    view = view[view["la"] == place]
if area != "All":
    view = view[view["Urban_rura"] == area]
view = view.copy()
if len(view) == 0:
    st.warning("No neighbourhoods match these filters. Try 'All' area type.")
    st.stop()
view["is_top"] = view["gap"].rank(ascending=False, method="first") <= len(view) * top_pct / 100

# ---------- header + KPIs on one row ----------
c0, c1, c2, c3, c4 = st.columns([2.3, 1, 1, 1, 1])
c0.markdown("### Where does bus service fall short of need?")
c0.caption(f"{place} · {len(view):,} neighbourhoods (LSOAs). Higher score = bigger gap between need and provision.")
top_view = view[view["is_top"]] if top_pct else view.nlargest(max(int(len(view) * 0.1), 1), "gap")
c1.metric("Residents in biggest-gap areas", f"{top_view['population'].sum() / 1e6:.2f} M" if top_view['population'].sum() > 1e6
          else f"{top_view['population'].sum() / 1e3:.0f} k", help="Top % set in the sidebar (10% if no highlight), ranked within the selection.")
c2.metric("No morning bus service", f"{(view['freq_morning'] == 0).sum():,}", help="LSOAs with no departures 07-10 on the sample weekday.")
c3.metric("Median departures/hour", f"{view[['freq_morning', 'freq_off_peak', 'freq_evening']].mean(axis=1).median():.1f}",
          help="Per neighbourhood, averaged over the three time bands.")
red = 1 - view["unmet_opt"].sum() / max(view["unmet0"].sum(), 1)
c4.metric("Unmet demand cut by reallocation", f"-{red:.0%}", help="Estimated, under the model's assumptions. See the Allocation tab.")

tab_map, tab_list, tab_alloc, tab_pat, tab_about = st.tabs(
    ["Map", "Priority areas", "Vehicle allocation", "Service patterns", "Method & limits"])

# ---------- map ----------
with tab_map:
    v = view.copy()
    if layer == "Demand-gap score":
        lo, hi = v["gap"].quantile([.02, .98])
        t = ((v["gap"] - lo) / max(hi - lo, 1e-9)).values
        rgb = ramp(t, GAP); v["value"] = "Gap score " + v["gap"].round(2).astype(str)
        legend = "Pale = small gap, dark red = large gap"
    elif layer == "Service frequency":
        col = {"Morning (07-10)": "freq_morning", "Off-peak (10-16)": "freq_off_peak", "Evening (16-19)": "freq_evening"}[band_label]
        t = (np.log1p(v[col]) / max(np.log1p(v[col].quantile(.98)), 1e-9)).values
        rgb = ramp(t, FREQ); v["value"] = v[col].round(1).astype(str) + " departures/hour"
        legend = "Pale = few departures, dark = many (log scale)"
    elif layer == "Service pattern (cluster)":
        rgb = np.array([hex2rgb(CLUSTER_COL[c]) for c in v["cluster_name"]], dtype=np.uint8)
        v["value"] = v["cluster_name"]
        legend = " · ".join(f"<span style='color:{c}'>●</span> {n}" for n, c in CLUSTER_COL.items())
    else:
        _b = {"Morning (07-10)": "morning", "Off-peak (10-16)": "off_peak", "Evening (16-19)": "evening"}.get(alloc_band)
        dlt = (v["x_opt"] - v["x0"]) if _b is None else (v[f"xopt_{_b}"] - v[f"x0_{_b}"])
        m = dlt.abs().quantile(.98) or 1
        t = (dlt / m).clip(-1, 1).values
        rgb = np.where(t[:, None] < 0, ramp(-t, ["#eeeeee", "#2b6cb0"]), ramp(t, ["#eeeeee", "#d9480f"]))
        v["value"] = dlt.round(2).astype(str) + " vehicles"
        legend = "<span style='color:#2b6cb0'>●</span> vehicles removed · <span style='color:#d9480f'>●</span> vehicles added"
    alpha = np.where(v["is_top"].values, 235, 70) if top_pct else np.full(len(v), 200)
    v["r"], v["g"], v["b"], v["a"] = rgb[:, 0], rgb[:, 1], rgb[:, 2], alpha
    v["pop"] = v["population"].astype(int)
    v["name"] = v["LSOA21NM"]

    # zoom to the selection
    if place == "All England":
        lat0, lon0, zoom, rad, rmin, rmax = 52.9, -1.6, 5.3, 260, 1.5, 7
    else:
        la_, lo_ = v["lat"].quantile([.03, .97]), v["lon"].quantile([.03, .97])
        lat0, lon0 = v["lat"].median(), v["lon"].median()
        span = max(la_.iloc[1] - la_.iloc[0], (lo_.iloc[1] - lo_.iloc[0]) * np.cos(np.radians(lat0)), 0.02)
        zoom = float(np.clip(np.log2(360 / span) - 0.9, 6, 12.5))
        rad, rmin, rmax = 90, 3, 14

    pts = pdk.Layer("ScatterplotLayer", data=v[["lon", "lat", "r", "g", "b", "a", "name", "value", "pop"]],
                    get_position="[lon, lat]", get_fill_color="[r, g, b, a]", get_radius=rad,
                    radius_min_pixels=rmin, radius_max_pixels=rmax, pickable=True)
    deck = pdk.Deck(layers=[pts], map_provider="carto", map_style="light",
                    initial_view_state=pdk.ViewState(latitude=float(lat0), longitude=float(lon0), zoom=zoom),
                    tooltip={"html": "<b>{name}</b><br/>{value}<br/>Residents: {pop}"})
    st.pydeck_chart(deck, width="stretch", height=405)
    st.markdown(f"<div style='font-size:0.8rem'>{legend} &nbsp;·&nbsp; one dot per neighbourhood, at its centre</div>",
                unsafe_allow_html=True)

# ---------- priority list ----------
with tab_list:
    cl1, cl2 = st.columns([4, 1])
    n_show = cl1.slider("Rows", 10, 200, 100, step=10)
    tbl = view.nlargest(n_show, "gap")[["LSOA21NM", "Urban_rura", "population", "gap", "freq_morning", "freq_off_peak",
                                       "freq_evening", "dist_nearest_stop_m", "imd_decile", "cluster_name"]].rename(columns={
        "LSOA21NM": "Neighbourhood", "Urban_rura": "Area type", "population": "Residents", "gap": "Gap score",
        "freq_morning": "Dep/h morning", "freq_off_peak": "Dep/h off-peak", "freq_evening": "Dep/h evening",
        "dist_nearest_stop_m": "Nearest stop (m)", "imd_decile": "IMD decile (1 = most deprived)", "cluster_name": "Service pattern"})
    cl2.download_button("Download CSV", tbl.to_csv(index=False).encode(), "priority_areas.csv", "text/csv")
    st.dataframe(tbl.round(2), hide_index=True, width="stretch", height=345)

# ---------- allocation ----------
with tab_alloc:
    left, right = st.columns([1.25, 1])
    with left:
        s = view.groupby("region")[["unmet0", "unmet_opt"]].sum().reindex(
            [r for r in ["London", "Metropolitan", "Non-metropolitan"] if r in view["region"].unique()]).reset_index()
        fig = go.Figure()
        fig.add_bar(x=s["region"], y=s["unmet0"], name="Today (baseline)", marker_color="#a6a6a6")
        fig.add_bar(x=s["region"], y=s["unmet_opt"], name="After reallocation", marker_color="#1d5a63")
        fig.update_layout(barmode="group", yaxis_title="Unmet trips/day (est.)", height=330,
                          margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          title=dict(text="Estimated unmet demand in the selected area, by region type", font=dict(size=13)),
                          legend=dict(orientation="h", y=-0.12))
        st.plotly_chart(fig, width="stretch")
    with right:
        bands = pd.read_csv(DATA / "allocation_bands.csv")[["band", "unmet/day baseline", "unmet/day optimised"]]
        bands["band"] = bands["band"].map({"morning": "Morning", "off_peak": "Off-peak", "evening": "Evening"})
        bands["unmet/day baseline"] = (bands["unmet/day baseline"] / 1e3).round(0).astype(int).astype(str) + "k"
        bands["unmet/day optimised"] = (bands["unmet/day optimised"] / 1e3).round(0).astype(int).astype(str) + "k"
        st.markdown("**England, by time of day** (estimated unmet trips per day)")
        st.dataframe(bands, hide_index=True, width="stretch", height=142)
        sens = pd.read_csv(DATA / "allocation_sensitivity.csv")
        pv = sens.pivot(index="fleet_pct", columns="productivity_pct", values="reduction").mul(100).round(0).astype(int).astype(str) + "%"
        pv.index = [f"{i}%" for i in pv.index]; pv.columns = [f"{c}%" for c in pv.columns]; pv.index.name = "Fleet"
        st.markdown("**Sensitivity**: reduction in unmet demand (rows = fleet size, columns = journeys per bus)")
        st.dataframe(pv, width="stretch", height=142)

# ---------- patterns ----------
with tab_pat:
    left, right = st.columns([1.4, 1])
    with left:
        prof = d[d["cluster"] >= 0].groupby("cluster_name")[["freq_morning", "freq_off_peak", "freq_evening"]].mean()
        cnt = d["cluster_name"].value_counts()
        fig = go.Figure()
        for name, row in prof.iterrows():
            fig.add_scatter(x=["Morning", "Off-peak", "Evening"], y=row.values, mode="lines+markers",
                            name=f"{name} ({cnt[name]:,})", line=dict(color=CLUSTER_COL.get(name)))
        fig.update_layout(yaxis_title="Departures per hour (mean)", height=380, margin=dict(l=10, r=10, t=10, b=10),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig, width="stretch")
    with right:
        st.caption("K-means (k = 4) on the share of service in each time band plus overall service level, over all England. "
                   "Below: how the selected area splits across the patterns.")
        mix = view["cluster_name"].value_counts().rename_axis("Service pattern").reset_index(name="Neighbourhoods")
        mix["Share"] = (mix["Neighbourhoods"] / mix["Neighbourhoods"].sum() * 100).round(0).astype(int).astype(str) + "%"
        st.dataframe(mix, hide_index=True, width="stretch", height=215)

# ---------- about ----------
with tab_about:
    a, b = st.columns(2)
    a.markdown("""
**What this is.** A decision-support prototype built for an MSc dissertation (Coventry University). Not an operational planning tool.

**Method.** Weighted demand-gap score per LSOA, K-means clustering of service by time of day, and a linear programme that reallocates a fixed fleet within each region type (London, metropolitan, other) using DfT fleet and journey figures.

**Data (all open).** NaPTAN bus stops and Bus Open Data Service GTFS timetables (DfT, topped up with Traveline National Dataset); LSOA 2021 boundaries and mid-2024 population (ONS); Indices of Deprivation 2025 (MHCLG); DfT annual bus statistics. Contains public sector information licensed under the Open Government Licence v3.0.
""")
    b.markdown("""
**Limits**
- Demand is estimated from population, calibrated to DfT journeys for each region type (London, metropolitan, other). Within a region it does not reflect differences in bus use between neighbourhoods.
- Service frequency is one sample weekday from the GTFS feed and counts departures at all stops in an area.
- Distance to the nearest stop is from each area's geometric centre, not its population-weighted centre.
- Score weights are judgement-based; use the sliders to test them.
- Demand is assumed flat across the 07-19 day in the time-band model.
- "City" selection uses local authority areas, which do not always match built-up city boundaries.
""")
