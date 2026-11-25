"""Bus Demand and Vehicle Allocation across England (LSOA level).
Run from the project root:  streamlit run dashboard/app.py
Data: dashboard/data/lsoa.parquet (made by notebooks/06_export_dashboard_data.ipynb)
This file is the entry point: shared header, filters and score weights, then the selected page from dashboard/views/.
"""
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as stc
from common import ASSETS, load, components, logo_svg

st.set_page_config(page_title="Bus Demand and Vehicle Allocation", page_icon=str(ASSETS / "bus_icon.png"),
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.hdr{background:#141414;border-bottom:4px solid #c1121f;border-radius:8px;padding:.7rem 1.1rem;margin:0 0 .6rem 0;
  display:flex;align-items:center;gap:.9rem}
.hdr svg{height:44px;width:auto;flex:none}
.hdr-t{color:#faf7f1;font-size:1.45rem;font-weight:800;line-height:1.15}
.hdr-s{color:#d9cfbb;font-size:.85rem;margin-top:.1rem}
@media (max-width:900px){.hdr-t{font-size:1.1rem}.hdr-s{display:none}}
.block-container{padding-top:3.4rem;padding-bottom:0.4rem;max-width:100%}
[data-testid="stMetricValue"]{font-size:1.45rem}
[data-testid="stMetricLabel"] p{font-size:0.74rem;white-space:normal;line-height:1.15}
[data-testid="stSidebar"] .block-container{padding-top:1.2rem}
[data-testid="stSidebarHeader"]{height:2.2rem;min-height:0;padding:.3rem .8rem 0}
[data-testid="stSidebarUserContent"]{padding-top:.3rem!important}
h3{padding:0 0 .1rem 0!important;margin:0!important}
h4{color:#141414;border-left:5px solid #c1121f;padding-left:.6rem!important}
.note{background:#efe7d6;border-left:4px solid #141414;border-radius:6px;padding:.55rem .8rem;font-size:.9rem}
[data-testid="stAppDeployButton"],[data-testid="stToolbarActions"],[data-testid="stMainMenu"],.stDeployButton,#MainMenu{display:none!important}
</style>""", unsafe_allow_html=True)

try:
    df = load()
except FileNotFoundError:
    st.error("Dashboard data not found. Run notebook 06 (export dashboard data) first, or check that dashboard/data/lsoa.parquet exists.")
    st.stop()
N = components(df)

pages = [
    st.Page("views/overview.py", title="Overview", icon=":material/map:", default=True),
    st.Page("views/priority.py", title="Priority areas", icon=":material/format_list_numbered:"),
    st.Page("views/allocation.py", title="Vehicle allocation", icon=":material/directions_bus:"),
    st.Page("views/patterns.py", title="Service patterns", icon=":material/schedule:"),
    st.Page("views/evaluation.py", title="Evaluation", icon=":material/fact_check:"),
    st.Page("views/about.py", title="Method and limits", icon=":material/info:"),
]
pg = st.navigation(pages, position="top")

# ---------- header: banner, then city and area type (apply to every page) ----------
st.markdown(f"""<div class="hdr">{logo_svg()}<div><div class="hdr-t">Bus demand and vehicle allocation across England</div>
<div class="hdr-s">Where bus service falls short of need, and how a fixed fleet could be reallocated &middot; 33,755 neighbourhoods (LSOAs)</div></div></div>""",
            unsafe_allow_html=True)
las = ["All England"] + sorted(df["la"].unique())
pc1, pc2, pc3 = st.columns([1.3, 1.5, 3])
place = pc1.selectbox("City / local authority", las, label_visibility="collapsed", key="place_sel",
                      help="Type to search, e.g. Manchester, Leeds, Bristol. Applies to every page.")
area = pc2.radio("Area type", ["All", "Urban", "Rural"], horizontal=True, label_visibility="collapsed", key="area_sel")

# ---------- score weights (sidebar, apply to every page) ----------
DEFAULT_W = {"access": 30, "supply": 30, "density": 20, "deprivation": 20}
with st.sidebar.expander("Score weights: test the ranking", expanded=True):
    st.caption("The gap score mixes four things. How much each counts is a judgement, so test it: move a slider and see whether the "
               "worst-served areas stay the same. Weights are rescaled to add up to 100%.")
    if st.button("Reset to default weights", use_container_width=True):
        for k in DEFAULT_W:
            st.session_state[f"w_{k}"] = DEFAULT_W[k]
    W = {
        "access": st.slider("Far from a bus stop", 0, 100, DEFAULT_W["access"], key="w_access",
                            help="Distance from the middle of the area to its nearest bus stop. Raise it to put more weight on places with a long walk to a bus."),
        "supply": st.slider("Few buses per person", 0, 100, DEFAULT_W["supply"], key="w_supply",
                            help="Weekday departures per hour for every 1,000 residents (fewer = worse). Raise it to focus on thinly served areas."),
        "density": st.slider("Crowded area", 0, 100, DEFAULT_W["density"], key="w_density",
                             help="Population density. Raise it to favour dense areas where many people share few buses."),
        "deprivation": st.slider("Deprived area", 0, 100, DEFAULT_W["deprivation"], key="w_deprivation",
                                 help="Index of Multiple Deprivation 2025 score. Raise it to give more priority to more deprived areas."),
    }
    if sum(W.values()) == 0:
        st.warning("All weights are 0, so the defaults are used.")
        W = DEFAULT_W
    diag = st.empty()

w = pd.Series(W)[N.columns]
d = df.copy()
# Recompute the gap score with the current weights (they are rescaled to add up to 1)
d["gap"] = (N * (w / w.sum())).sum(axis=1)

# how far do the current weights change the answer? (worst-served 10% of England, against the default weights)
k10 = int(len(d) * 0.10)
w0 = pd.Series(DEFAULT_W)[N.columns]
base_gap = (N * (w0 / w0.sum())).sum(axis=1)
# argsort of the negative score lists the highest-scoring neighbourhoods first
i_now, i_base = np.argsort(-d["gap"].values)[:k10], np.argsort(-base_gap.values)[:k10]
# Share of the default worst-served 10% that is still in the worst 10% with the new weights
same = len(set(i_now) & set(i_base)) / k10
rural_now, rural_base = (d["Urban_rura"].values[i_now] == "Rural").mean(), (d["Urban_rura"].values[i_base] == "Rural").mean()
share = (w / w.sum() * 100).round(0).astype(int)
if (share == pd.Series(DEFAULT_W)[N.columns]).all():
    diag.markdown("**These are the default weights** (30 / 30 / 20 / 20). Move a slider to see how the answer changes.")
else:
    diag.markdown(
        f"**Effective weights:** {share['access']}% / {share['supply']}% / {share['density']}% / {share['deprivation']}%\n\n"
        f"**Same worst-served 10% as the default weights:** {same:.0%}\n\n"
        f"**Rural share of that group:** {rural_now:.0%} (default {rural_base:.0%})")
st.sidebar.caption("Weights change the score, map and lists. The vehicle allocation is pre-computed with the default weights and does not change.")

# Apply the city and area-type filters; every page works from this filtered "view"
view = d
if place != "All England":
    view = view[view["la"] == place]
if area != "All":
    view = view[view["Urban_rura"] == area]
view = view.copy()
if len(view) == 0:
    st.warning("No neighbourhoods match these filters. Try 'All' area type.")
    st.stop()
pc3.caption(f"Showing **{place}** · {len(view):,} neighbourhoods. Higher score = bigger gap between need and provision.")

# a refresh (new session) on another page goes back to Overview: click the Overview tab once.
# (Streamlit's frame can't change the browser URL itself, so this uses the in-app navigation link.)
if "_boot" not in st.session_state:
    st.session_state["_boot"] = True
    if pg.title != "Overview":
        stc.html("""<script>
        const doc = window.parent.document; let n = 0;
        const t = setInterval(() => {
          const a = [...doc.querySelectorAll('a[data-testid="stTopNavLink"]')].find(x => x.textContent.endsWith("Overview"));
          n++; if (a) { a.click(); clearInterval(t); } else if (n > 40) clearInterval(t);
        }, 150);
        </script>""", height=0)

# sidebar open on Overview, collapsed on the other pages (once per page change, so a manual open/close is respected)
if st.session_state.get("_last_page") != pg.title:
    st.session_state["_last_page"] = pg.title
    want = "true" if pg.title == "Overview" else "false"
    stc.html(f"""<script>
    const want = "{want}", doc = window.parent.document;
    let tries = 0;
    const t = setInterval(() => {{
      const sb = doc.querySelector('[data-testid="stSidebar"]'); tries++;
      if (sb) {{
        if (sb.getAttribute("aria-expanded") !== want) {{
          const b = want === "false" ? sb.querySelector('[data-testid="stSidebarCollapseButton"] button, button[kind="headerNoPadding"]')
                                     : doc.querySelector('[data-testid="stExpandSidebarButton"] button, [data-testid="stExpandSidebarButton"]');
          if (b) b.click();
        }}
        if (sb.getAttribute("aria-expanded") === want || tries > 30) clearInterval(t);
      }} else if (tries > 30) clearInterval(t);
    }}, 150);
    </script>""", height=0)

st.session_state["ctx"] = {"d": d, "view": view, "place": place, "area": area, "N": N, "w": w / w.sum(), "same_top10": same}
# Run the page chosen in the top navigation
pg.run()

st.divider()
st.caption("Prototype built for an MSc dissertation at Coventry University, not an operational planning tool. "
           "Open data: DfT, ONS, MHCLG, NaPTAN and Bus Open Data Service, under the Open Government Licence v3.0.")
