import plotly.graph_objects as go
import streamlit as st
from common import BLACK, RED, GREY

ctx = st.session_state["ctx"]
view, place = ctx["view"], ctx["place"]

st.markdown("#### Which neighbourhoods need attention first?")
st.caption("The 100 neighbourhoods with the biggest gap between need and bus service in your selection. "
           "Search by name, or re-rank by a different measure to see who is affected in different ways.")

RANK = {"Gap score (default)": ("gap", False), "Most residents": ("population", False),
        "Furthest from a bus stop": ("dist_nearest_stop_m", False), "Fewest morning departures": ("freq_morning", True)}
c1, c2, c3 = st.columns([1.3, 1.1, 1])
q = c1.text_input("Search by name", placeholder="e.g. Leeds 054A, or part of a name")
rank_by = c2.selectbox("Rank by", list(RANK), help="Only changes the order. The list is always the 100 neighbourhoods with the biggest gap "
                       "that match your search, then re-ordered by this measure.")

pool = view[view["LSOA21NM"].str.contains(q.strip(), case=False, regex=False)] if q.strip() else view
top = pool.nlargest(100, "gap")
col, asc = RANK[rank_by]
top = top.sort_values(col, ascending=asc)
c3.download_button("Download this list (CSV)", top.assign(la=top["la"]).drop(columns=["lat", "lon"], errors="ignore").to_csv(index=False).encode(),
                   "priority_areas.csv", "text/csv", use_container_width=True)

if len(top) == 0:
    st.info("No neighbourhood matches that name in the selected area.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Neighbourhoods listed", f"{len(top):,}")
k2.metric("Residents affected", f"{top['population'].sum():,.0f}")
k3.metric("Rural share", f"{(top['Urban_rura'] == 'Rural').mean():.0%}", help="Share of the listed neighbourhoods that are rural.")
k4.metric("No morning service", f"{(top['freq_morning'] == 0).sum():,}", help="How many of the listed neighbourhoods have no bus 07:00-10:00 on the sample weekday.")

left, right = st.columns([2.2, 1])
tbl = top[["LSOA21NM", "Urban_rura", "population", "gap", "freq_morning", "freq_off_peak", "freq_evening",
           "dist_nearest_stop_m", "imd_decile", "cluster_name"]].rename(columns={
    "LSOA21NM": "Neighbourhood", "Urban_rura": "Area type", "population": "Residents", "gap": "Gap score",
    "freq_morning": "Morning", "freq_off_peak": "Off-peak", "freq_evening": "Evening",
    "dist_nearest_stop_m": "Nearest stop (m)", "imd_decile": "IMD decile", "cluster_name": "Service pattern"})
left.dataframe(tbl, hide_index=True, width="stretch", height=470, column_config={
    "Gap score": st.column_config.ProgressColumn("Gap score", min_value=0, max_value=1, format="%.2f", help="0 = no gap, 1 = largest gap in England"),
    "Residents": st.column_config.NumberColumn(format="%d"),
    "Morning": st.column_config.NumberColumn("Morning dep/h", format="%.1f", help="Departures per hour, 07-10"),
    "Off-peak": st.column_config.NumberColumn("Off-peak dep/h", format="%.1f", help="Departures per hour, 10-16"),
    "Evening": st.column_config.NumberColumn("Evening dep/h", format="%.1f", help="Departures per hour, 16-19"),
    "Nearest stop (m)": st.column_config.NumberColumn(format="%d"),
    "IMD decile": st.column_config.NumberColumn(format="%d", help="1 = most deprived 10% of England")})

with right:
    if place == "All England" and top["la"].nunique() > 1:
        cnt = top["la"].value_counts().head(8).sort_values()
        title = "Where are they? (local authorities)"
    else:
        cnt = top["cluster_name"].value_counts().sort_values()
        title = "What service do they get?"
    fig = go.Figure(go.Bar(x=cnt.values, y=cnt.index, orientation="h", marker_color=RED))
    fig.update_layout(title=dict(text=title, font=dict(size=13)), height=470, margin=dict(l=10, r=10, t=35, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Neighbourhoods in the list")
    st.plotly_chart(fig, width="stretch")
