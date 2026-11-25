import pandas as pd
import streamlit as st

ctx = st.session_state["ctx"]
view, N, W, place = ctx["view"], ctx["N"], ctx["w"], ctx["place"]

st.markdown("#### Method and limits")
st.caption("A decision-support prototype built for an MSc dissertation (Coventry University). Not an operational planning tool.")

st.markdown("**From open data to a vehicle allocation**")
steps = [("1. Collect", "Bus stops, timetables, boundaries, population, deprivation: open data only"),
         ("2. Score", "Four measures per neighbourhood, scaled 0-1 and combined into a gap score"),
         ("3. Group", "K-means groups neighbourhoods by when their buses run"),
         ("4. Allocate", "A linear programme moves a fixed fleet to cut unmet demand"),
         ("5. Check", "Compare with PTAI-2022, DfT journeys and different weights")]
for c, (t, b) in zip(st.columns(5), steps):
    with c.container(border=True):
        st.markdown(f"**{t}**")
        st.caption(b)

st.markdown("#### Worked example: how one score is built")
pick = st.segmented_control("Neighbourhood", ["Worst-served", "Median", "Best-served"], default="Worst-served", key="wx_pick") or "Worst-served"
# Pick the worst, median or best neighbourhood in the current selection
v = view.sort_values("gap")
row = v.iloc[{"Worst-served": -1, "Median": len(v) // 2, "Best-served": 0}[pick]]
idx = row.name
raw = {"access": (f"{row['dist_nearest_stop_m']:,.0f} m to nearest stop", "Far from a bus stop"),
       "supply": (f"{row['freq_per_1000']:.1f} departures/hour per 1,000 people", "Few buses per person"),
       "density": (f"{row['pop_density']:,.0f} people per sq km", "Crowded area"),
       "deprivation": (f"IMD score {row['imd_score']:.1f}", "Deprived area")}
tb = pd.DataFrame({"Measure": [raw[k][1] for k in N.columns], "Raw value": [raw[k][0] for k in N.columns],
                   "Scaled 0-1": [N.loc[idx, k] for k in N.columns], "Weight": [W[k] * 100 for k in N.columns],
                   "Contribution": [N.loc[idx, k] * W[k] for k in N.columns]})
st.markdown(f"**{row['LSOA21NM']}** ({row['la']}), {pick.lower()} in {place}")
st.dataframe(tb, hide_index=True, width="stretch", column_config={
    "Scaled 0-1": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=1),
    "Weight": st.column_config.NumberColumn(format="%.0f%%"),
    "Contribution": st.column_config.NumberColumn(format="%.3f")})
st.markdown(f'<div class="note">Gap score = sum of the contributions = <b>{tb["Contribution"].sum():.2f}</b>. '
            'Scaled 0-1 means the value relative to the rest of England (0 = best 1%, 1 = worst 1%). The weights are the ones set in the sidebar.</div>',
            unsafe_allow_html=True)

st.markdown('#### Details and limits')

with st.expander("1. How the gap score is calculated", expanded=True):
    st.markdown("""
Each neighbourhood (LSOA 2021) gets a score from 0 to 1. Higher means a bigger gap between need and bus provision. It combines four measures,
each trimmed at the 1st and 99th percentile and scaled from 0 to 1:

| Measure | Meaning | Base weight |
|---|---|---|
| Far from a bus stop | Distance from the area's centre to the nearest stop | 30% |
| Few buses per person | Weekday departures per hour per 1,000 residents (inverted, log scale) | 30% |
| Crowded area | Population density | 20% |
| Deprived area | Index of Multiple Deprivation 2025 score | 20% |

The weights are a judgement, not an estimate. Change them in the sidebar, and see the **Evaluation** page for how much the ranking moves.
No machine learning is used for prediction.
""")
with st.expander("2. Time-of-day patterns"):
    st.markdown("""
Departures per hour are counted for a representative Tuesday (6 October 2026) in three bands: morning 07-10, off-peak 10-16, evening 16-19.
Neighbourhoods are grouped with K-means (k = 4) on the share of service in each band plus the overall service level. Areas with no service are kept as a separate group.
""")
with st.expander("3. Vehicle allocation"):
    st.markdown("""
A linear programme (PuLP with the HiGHS solver) runs separately for London, metropolitan and other areas, and for each time band. It minimises
unmet demand weighted by the gap score, subject to a fixed fleet. Each area keeps at least half of its baseline share of buses and gets at most 20% above what its estimated
demand needs. Demand is population-based and calibrated to DfT journeys for the year ending March 2025; the baseline fleet is spread in proportion to current service.
""")
with st.expander("4. Data (all open) and dates"):
    st.markdown("""
| Data | Source | Date |
|---|---|---|
| Bus stops | NaPTAN | 2026 |
| Timetables (GTFS) | Bus Open Data Service (DfT), topped up with the Traveline National Dataset | Sample weekday 6 Oct 2026 |
| Neighbourhood boundaries | ONS, LSOA 2021 | 2021 |
| Population | ONS mid-year estimates | Mid-2024 |
| Deprivation | English Indices of Deprivation 2025 (MHCLG) | 2025 |
| Bus journeys and fleet | DfT annual bus statistics (BUS01, BUS02 and others) | Year ending March 2025 |
| Independent accessibility check | PTAI-2022 (Verduzco Torres and McArthur, 2024) | 2021 timetables |

Contains public sector information licensed under the Open Government Licence v3.0.
""")
with st.expander("5. Limits you should know about", expanded=True):
    st.markdown("""
- **Demand is estimated, not observed.** By default it follows population, calibrated to DfT totals for each region type, so it misses differences in bus use between places. The Vehicle allocation page lets you switch to demand scaled to observed DfT journeys per head (unitary authorities and metropolitan areas only; elsewhere it shares what is left). The England-wide result is about the same, but place-level results move a lot.
- **One sample weekday drives the score.** Service frequency comes from one weekday in the timetable feed, counting departures at all stops in an area. Saturday and Sunday are shown on the Service patterns page but are not used in the score or allocation.
- **Distance to the nearest stop** is measured as a straight line from a single point in each area (its geometric centre unless population-weighted centres are loaded), not as a walking route.
- **Demand is assumed flat** across 07-19 in the time-band model. Real peaks would reduce the benefit of reallocation (see Vehicle allocation).
- **Allocation results are model outputs.** They show where service looks least matched to population-based demand. They are not a proposal for real routes or timetables.
- **"City" means local authority area,** which does not always match the built-up city.
- **No validation against passenger counts** at neighbourhood level, because open data for that do not exist.
""")
