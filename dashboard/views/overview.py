import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
import streamlit.components.v1 as stc
from common import GAP, FREQ, CLUSTER_COL, BLACK, RED, hex2rgb, ramp

ctx = st.session_state["ctx"]
view, place, N, W = ctx["view"].copy(), ctx["place"], ctx["N"], ctx["w"]

# ---------- map controls ----------
layer = st.sidebar.selectbox("Map layer", ["Demand-gap score", "Service frequency", "Service pattern (cluster)",
                                           "Allocation change (vehicles)"])
band_label = "Morning (07-10)"
if layer == "Service frequency":
    band_label = st.sidebar.selectbox("Time band", ["Morning (07-10)", "Off-peak (10-16)", "Evening (16-19)"])
alloc_band = "All day (daily model)"
if layer == "Allocation change (vehicles)":
    alloc_band = st.sidebar.selectbox("Allocation for", ["All day (daily model)", "Morning (07-10)",
                                                          "Off-peak (10-16)", "Evening (16-19)"])
EXPLAIN = {"Demand-gap score": "How far bus service falls short of need. Darker = bigger gap.",
           "Service frequency": "How many buses an area gets per hour.",
           "Service pattern (cluster)": "Groups areas by when their buses run (morning, all day, none).",
           "Allocation change (vehicles)": "Where the model moves buses to and from."}
st.sidebar.caption(EXPLAIN[layer])
hl = st.sidebar.checkbox("Highlight the worst-served 10%", value=True,
                         help="Ranked within the area you selected. Other neighbourhoods are dimmed.")
top_pct = 10 if hl else 0
# True for the worst-served 10% of the current selection (ranked within the selection, not against all England)
view["is_top"] = view["gap"].rank(ascending=False, method="first") <= len(view) * top_pct / 100

first_visit = not st.session_state.get("seen_help", False)
with st.expander("How to use this dashboard", expanded=first_visit):
    h1, h2, h3, h4 = st.columns(4)
    h1.markdown("**1. Choose a place.** Pick a city or local authority, and urban or rural, above the map. Every page follows your choice.")
    h2.markdown("**2. Read the map.** Each dot is a neighbourhood. Darker red means a bigger gap between need and bus service. Hover for details. "
                "Switch the layer in the sidebar to see frequency, patterns or where buses move.")
    h3.markdown("**3. Look closer.** Search for a neighbourhood below the map to see what drives its score. "
                "Use the other pages for the priority list, the vehicle allocation, time-of-day patterns and the evaluation.")
    h4.markdown("**4. Test the weights.** The score weights in the sidebar are a judgement. Move them and watch whether the worst-served areas change.")
st.session_state["seen_help"] = True

mapcol, kpicol = st.columns([4.2, 1])
v = view.copy()
bar = None   # (colour stops, low label, high label) for a continuous legend
if layer == "Demand-gap score":
    # Stretch the colours between the 2nd and 98th percentile so a few extreme areas do not wash out the rest
    lo, hi = v["gap"].quantile([.02, .98])
    t = ((v["gap"] - lo) / max(hi - lo, 1e-9)).values
    rgb = ramp(t, GAP); v["value"] = "Gap score " + v["gap"].round(2).astype(str)
    bar = (GAP, "Small gap", "Large gap")
elif layer == "Service frequency":
    col = {"Morning (07-10)": "freq_morning", "Off-peak (10-16)": "freq_off_peak", "Evening (16-19)": "freq_evening"}[band_label]
    # Log scale: frequency is very skewed, so linear colours would show almost every area as "few buses"
    t = (np.log1p(v[col]) / max(np.log1p(v[col].quantile(.98)), 1e-9)).values
    rgb = ramp(t, FREQ); v["value"] = v[col].round(1).astype(str) + " departures/hour"
    bar = (FREQ, "Few departures", "Many (log scale)")
elif layer == "Service pattern (cluster)":
    rgb = np.array([hex2rgb(CLUSTER_COL[c]) for c in v["cluster_name"]], dtype=np.uint8)
    v["value"] = v["cluster_name"]
else:
    _b = {"Morning (07-10)": "morning", "Off-peak (10-16)": "off_peak", "Evening (16-19)": "evening"}.get(alloc_band)
    # Change in vehicles = suggested minus today (daily model, or the chosen time band)
    dlt = (v["x_opt"] - v["x0"]) if _b is None else (v[f"xopt_{_b}"] - v[f"x0_{_b}"])
    # Scale by the 98th percentile of the absolute change so colours balance either side of zero ("or 1" avoids dividing by zero)
    m = dlt.abs().quantile(.98) or 1
    t = (dlt / m).clip(-1, 1).values
    # Buses removed shade black, buses added shade red
    rgb = np.where(t[:, None] < 0, ramp(-t, ["#eeeeee", "#141414"]), ramp(t, ["#eeeeee", "#c1121f"]))
    v["value"] = dlt.round(2).astype(str) + " vehicles"
    bar = (["#141414", "#eeeeee", "#c1121f"], "Vehicles removed", "Vehicles added")
# Worst-served dots are drawn solid and the rest faded (one opacity for all when the highlight is off)
alpha = np.where(v["is_top"].values, 235, 70) if top_pct else np.full(len(v), 200)
v["r"], v["g"], v["b"], v["a"] = rgb[:, 0], rgb[:, 1], rgb[:, 2], alpha
v["pop"] = v["population"].astype(int)
v["name"] = v["LSOA21NM"]
v["code"] = v["LSOA21CD"]

# zoom so the whole selection fits the map box (deck.gl world = 512 px at zoom 0)
MAP_W, MAP_H = 800, 560
if place == "All England":
    lat0, lon0, zoom, rad, rmin, rmax = 52.9, -2.0, 5.25, 260, 1.8, 8
else:
    la_, lo_ = v["lat"].quantile([.02, .98]), v["lon"].quantile([.02, .98])
    lat0, lon0 = float((la_.iloc[0] + la_.iloc[1]) / 2), float((lo_.iloc[0] + lo_.iloc[1]) / 2)
    lat_span = max(la_.iloc[1] - la_.iloc[0], 0.01) / np.cos(np.radians(lat0))   # Mercator stretch
    lon_span = max(lo_.iloc[1] - lo_.iloc[0], 0.01)
    zoom = float(np.clip(min(np.log2(MAP_H * 360 / (512 * lat_span)), np.log2(MAP_W * 360 / (512 * lon_span))) - 0.25, 5, 13))
    rad, rmin, rmax = 90, 3, 14

pts = pdk.Layer("ScatterplotLayer", id="lsoa", data=v[["lon", "lat", "r", "g", "b", "a", "name", "code", "value", "pop"]],
                get_position="[lon, lat]", get_fill_color="[r, g, b, a]", get_radius=rad,
                radius_min_pixels=rmin, radius_max_pixels=rmax, pickable=True)

# ---------- legend row + pin toggle ----------
_l, _r = mapcol.columns([5, 1.2])
if bar:
    grad = ", ".join(bar[0])
    legend = (f"<span style='font-size:.78rem'>{bar[1]}</span> <span style='display:inline-block;vertical-align:middle;width:150px;height:9px;"
              f"border-radius:5px;background:linear-gradient(90deg,{grad});margin:0 .35rem'></span><span style='font-size:.78rem'>{bar[2]}</span>")
else:
    legend = " &nbsp;".join(f"<span style='font-size:.78rem'><span style='color:{c}'>●</span> {n}</span>" for n, c in CLUSTER_COL.items())
_l.markdown(f"<div style='padding-top:.3rem'>{legend}<span style='font-size:.78rem;color:#6b7378'> &nbsp;·&nbsp; one dot per neighbourhood. Hover for details.</span></div>",
            unsafe_allow_html=True)
unpinned = _r.toggle("Unpin map", value=False, key="unpin_map",
                     help="The map is pinned by default so it does not move while you scroll. Unpin it to zoom and pan.")
deck = pdk.Deck(layers=[pts], map_provider="carto", map_style="light",
                initial_view_state=pdk.ViewState(latitude=float(lat0), longitude=float(lon0), zoom=zoom),
                tooltip={"html": "<b>{name}</b><br/>{value}<br/>Residents: {pop}"})
mapcol.pydeck_chart(deck, width="stretch", height=MAP_H)

# Pin the map: while pinned, scrolling, dragging and double-click zoom on the map are blocked. Hover tooltips still work.
# (Streamlit ignores pydeck's own controller switch, so this is done in the page.)
if not unpinned:
    st.markdown("""<style>button[aria-label="Zoom In"],button[aria-label="Zoom Out"],
    button[title="Zoom In"],button[title="Zoom Out"]{opacity:.35;pointer-events:none}</style>""", unsafe_allow_html=True)
stc.html(f"""<script>
const P = window.parent; P.__busMapPinned = {str(not unpinned).lower()};
if (!P.__busMapGuard) {{
  P.__busMapGuard = true;
  const inMap = (e) => e.target && e.target.closest && e.target.closest('[data-testid="stDeckGlJsonChart"]') && !e.target.closest('button');
  const block = (e) => {{ if (P.__busMapPinned && inMap(e)) e.stopPropagation(); }};
  // wheel and double-click always; movement only while a button is held (that is a drag) so hover and click still work
  const drag = (e) => {{ if (P.__busMapPinned && inMap(e) && (e.buttons > 0 || e.type === 'touchmove')) e.stopPropagation(); }};
  ['wheel','dblclick'].forEach(n => P.document.addEventListener(n, block, true));
  ['pointermove','mousemove','touchmove'].forEach(n => P.document.addEventListener(n, drag, true));
}}
</script>""", height=1)

# ---------- KPIs ----------
top_view = view[view["is_top"]] if top_pct else view.nlargest(max(int(len(view) * 0.1), 1), "gap")
_p = top_view["population"].sum()
kpicol.metric("Residents in biggest-gap areas", f"{_p / 1e6:.2f} M" if _p > 1e6 else f"{_p / 1e3:.0f} k",
              help="Top % set in the sidebar (10% if no highlight), ranked within the selection.")
kpicol.metric("No morning bus service", f"{(view['freq_morning'] == 0).sum():,}", help="LSOAs with no departures 07-10 on the sample weekday.")
kpicol.metric("Median departures/hour", f"{view[['freq_morning', 'freq_off_peak', 'freq_evening']].mean(axis=1).median():.1f}",
              help="Per neighbourhood, averaged over the three time bands.")
# Share of estimated unmet demand removed by the reallocation, for the selected area
red = 1 - view["unmet_opt"].sum() / max(view["unmet0"].sum(), 1)
kpicol.metric("Unmet demand cut (model estimate)", f"-{red:.0%}",
              help="Estimated, under the model's assumptions (population-based demand, fixed fleet). The model works per region type "
                   "(London, metropolitan, other), so for one city this is that city's share of the regional result. See Vehicle allocation.")

# ---------- key findings (change with the selection) ----------
d_all = ctx["d"]
B3 = ["freq_morning", "freq_off_peak", "freq_evening"]
no_am, eng_no_am = (view["freq_morning"] == 0).mean(), (d_all["freq_morning"] == 0).mean()
med_view, med_eng = view[B3].mean(axis=1).median(), d_all[B3].mean(axis=1).median()
worst = view.nlargest(1, "gap").iloc[0]
cut = d_all["gap"].quantile(0.9)
if place == "All England" and ctx["area"] == "All":
    worst10 = view[view["gap"] >= cut]
    f1 = (f"The worst-served 10% of neighbourhoods hold **{worst10['population'].sum() / 1e6:.1f} million** residents, "
          f"**{(worst10['Urban_rura'] == 'Rural').mean():.0%}** of them in rural neighbourhoods.")
else:
    f1 = f"**{(view['gap'] >= cut).mean():.0%}** of neighbourhoods here are in the worst-served 10% of England (England overall: 10%)."
with st.container(border=True):
    st.markdown("##### Key findings for this selection")
    st.markdown(f"- {f1}\n"
                f"- **{no_am:.1%}** have no bus service between 07:00 and 10:00 on the sample weekday (England: {eng_no_am:.1%}).\n"
                f"- Typical service is **{med_view:.1f}** departures an hour, against **{med_eng:.1f}** across England.\n"
                f"- Biggest gap: **{worst['LSOA21NM']}** (score {worst['gap']:.2f}).")

# ---------- inspect one neighbourhood ----------
st.markdown("##### Look up a neighbourhood")
q1, q2 = st.columns([1.2, 2])
query = q1.text_input("Search by name", placeholder="e.g. Leeds 054A, or part of a name", label_visibility="collapsed")
pool = view[view["LSOA21NM"].str.contains(query.strip(), case=False, regex=False)] if query.strip() else view.nlargest(30, "gap")
pool = pool.nlargest(30, "gap")
label = lambda r: f"{r['LSOA21NM']}  (gap {r['gap']:.2f})"
opts = {r["LSOA21CD"]: label(r) for _, r in pool.iterrows()}
sel = None
if opts:
    sel = q2.selectbox("Neighbourhood", list(opts), format_func=lambda c: opts[c], label_visibility="collapsed",
                       help="Shows the 30 biggest-gap matches. With no search text, the 30 worst-served areas in your selection.")
else:
    q2.caption("No neighbourhood matches that name in the selected area.")
if sel and sel in set(view["LSOA21CD"]):
    r = view[view["LSOA21CD"] == sel].iloc[0]
    n_all = len(ctx["d"])
    rank = int(ctx["d"]["gap"].rank(ascending=False, method="min")[ctx["d"]["LSOA21CD"] == sel].iloc[0])
    st.markdown(f"##### {r['LSOA21NM']}")
    c1, c2, c3 = st.columns([1.1, 1.3, 1.1])
    with c1:
        st.metric("Gap score (0-1)", f"{r['gap']:.2f}", help=f"Ranked {rank:,} of {n_all:,} neighbourhoods in England (1 = biggest gap).")
        st.caption(f"Ranked **{rank:,}** of {n_all:,} in England · {int(r['population']):,} residents · {r['Urban_rura'].lower()} · "
                   f"IMD decile {int(r['imd_decile'])} (1 = most deprived)")
    with c2:
        idx = ctx["d"].index[ctx["d"]["LSOA21CD"] == sel][0]
        parts = (N.loc[idx] * W).rename({"access": "Far from a stop", "supply": "Few buses per person", "density": "Crowded", "deprivation": "Deprived"})
        fig = go.Figure(go.Bar(x=parts.values, y=parts.index, orientation="h", marker_color=BLACK,
                               text=[f"{x:.2f}" for x in parts.values], textposition="outside"))
        fig.update_layout(title=dict(text="What drives this score (weighted)", font=dict(size=12)), height=190, margin=dict(l=10, r=30, t=30, b=5),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(range=[0, max(parts.max() * 1.3, .1)], showgrid=False),
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, width="stretch")
    with c3:
        st.markdown(
            f"**Service.** {r['freq_morning']:.1f} / {r['freq_off_peak']:.1f} / {r['freq_evening']:.1f} departures per hour "
            f"(morning / off-peak / evening). Nearest stop {r['dist_nearest_stop_m']:,.0f} m away. Pattern: {r['cluster_name']}.\n\n"
            f"**Model allocation.** {r['x0']:.2f} → {r['x_opt']:.2f} vehicles ({r['x_opt'] - r['x0']:+.2f}).")
