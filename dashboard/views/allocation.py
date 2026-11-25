import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import DATA, BLACK, RED, GREY

ctx = st.session_state["ctx"]
d, view, place = ctx["d"], ctx["view"], ctx["place"]

st.markdown("#### Where could a fixed fleet do more?")
st.caption("A linear programme moves buses between neighbourhoods inside each region type (London, metropolitan, other) to cut estimated unmet "
           "demand. The total fleet in each region type stays the same. Fleet and journey totals are calibrated to DfT figures for the year ending March 2025. "
           "Results use the default score weights.")

DEM = st.segmented_control("Demand assumption", ["Population-based", "Observed bus use"], default="Population-based", key="alloc_demand",
                           help="Population-based: demand follows population inside each region type (default). Observed bus use: demand follows real DfT "
                                "journeys per head where published (unitary authorities and metropolitan areas). Totals and fleets are the same in both.") or "Population-based"
OBS = DEM == "Observed bus use"
# Column suffix: the "_obs" columns hold results for the observed-bus-use demand assumption
SFX = "_obs" if OBS else ""
if OBS:
    st.caption("Observed bus use: demand is scaled to DfT journeys per head for unitary authorities and the six metropolitan areas. London boroughs and districts "
               "in two-tier counties are not published, so they share what is left of their region type's total.")
t1, t2, t3, t4 = st.tabs(["Before and after", "Where buses move", "What if…", "Compare assumptions"])

# ---------------------------------------------------------------- before / after
with t1:
    s = view.groupby("region")[[f"unmet0{SFX}", f"unmet_opt{SFX}"]].sum().rename(columns={f"unmet0{SFX}": "unmet0", f"unmet_opt{SFX}": "unmet_opt"}).reindex(
        [r for r in ["London", "Metropolitan", "Non-metropolitan"] if r in view["region"].unique()]).reset_index()
    tot0, tot1 = s["unmet0"].sum(), s["unmet_opt"].sum()
    a, b, c = st.columns(3)
    a.metric("Unmet trips a day today (est.)", f"{tot0 / 1e3:,.0f}k", help="Trips the current service cannot carry, estimated from population-based demand.")
    b.metric("After reallocation (est.)", f"{tot1 / 1e3:,.0f}k")
    c.metric("Reduction", f"-{1 - tot1 / max(tot0, 1):.0%}",
             help="For a single city this is its share of the regional result, because the model runs per region type.")
    st.caption("An estimate, not a forecast. It assumes demand is spread as described in the Demand assumption above, that today's buses are spread by timetable frequency, "
               "and that each area keeps at least 50% of its buses and gets at most 120% of what its demand needs. It shows what the method can do, not what operators could achieve.")
    fig = go.Figure()
    fig.add_bar(x=s["region"], y=s["unmet0"], name="Today (baseline)", marker_color=GREY)
    fig.add_bar(x=s["region"], y=s["unmet_opt"], name="After reallocation", marker_color=RED)
    fig.update_layout(barmode="group", yaxis_title="Unmet trips/day (est.)", height=330,
                      margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      title=dict(text=f"Estimated unmet demand: {place}, by region type", font=dict(size=13)),
                      legend=dict(orientation="h", y=-0.12))
    st.plotly_chart(fig, width="stretch")
    st.markdown('<div class="note"><b>How to read this.</b> "Unmet" means trips the estimated demand needs but the current bus capacity cannot carry. '
                'The model moves capacity to where it is short while keeping each region type\'s fleet fixed. The size of the reduction depends on the '
                'assumptions: see the "What if…" tab.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- where buses move
with t2:
    band = st.segmented_control("Time of day", ["All day", "Morning", "Off-peak", "Evening"], default="All day", key="alloc_band")
    bk = {"All day": ("x0", f"x_opt{SFX}"), "Morning": ("x0_morning", f"xopt_morning{SFX}"), "Off-peak": ("x0_off_peak", f"xopt_off_peak{SFX}"),
          "Evening": ("x0_evening", f"xopt_evening{SFX}")}[band or "All day"]
    d = view.copy()
    if place == "All England":
        g = d.groupby("la", as_index=False).agg(today=(bk[0], "sum"), rec=(bk[1], "sum")).rename(columns={"la": "Area"})
        unit, dec = "local authorities", "%.0f"
    else:
        g = d.rename(columns={"LSOA21NM": "Area"}).assign(today=d[bk[0]], rec=d[bk[1]])[["Area", "today", "rec"]]
        unit, dec = "neighbourhoods", "%.1f"
    g["change"] = g["rec"] - g["today"]
    # Percentage change; areas with no buses today have no percentage (NaN)
    g["pct"] = (g["change"] / g["today"].where(g["today"] > 0)) * 100
    cols = {"Area": "Area", "today": "Today", "rec": "Suggested", "change": "Change", "pct": "%"}
    fmt = {"Today": st.column_config.NumberColumn(format=dec), "Suggested": st.column_config.NumberColumn(format=dec),
           "Change": st.column_config.NumberColumn(format=dec.replace("%", "%+")), "%": st.column_config.NumberColumn(format="%+.0f%%")}
    n = 8
    l, r = st.columns(2)
    for col, ttl, top in [(l, "Gain the most buses", g.nlargest(n, "change")), (r, "Lose the most buses", g.nsmallest(n, "change"))]:
        col.markdown(f"**{ttl}** ({unit}, {band.lower() if band else 'all day'})")
        col.dataframe(top[list(cols)].rename(columns=cols), hide_index=True, width="stretch", column_config=fmt)
        fig = go.Figure(go.Bar(x=top["change"][::-1], y=top["Area"][::-1], orientation="h", marker_color=RED if ttl.startswith("Gain") else BLACK))
        fig.update_layout(height=250, margin=dict(l=10, r=10, t=5, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          xaxis_title="Change in buses (model units)")
        col.plotly_chart(fig, width="stretch")
    st.markdown('<div class="note"><b>Read this as a screening result, not a timetable.</b> Demand is assumed to follow population within each region '
                'type, so places that already carry many journeys per head (strong networks in some large cities) show up as losing buses, while large '
                'areas with thin service show up as gaining. "Buses" are fleet-equivalents in the model, not real vehicles on real routes.</div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- what if
with t3:
    st.markdown("**Try different assumptions.** The result depends on how many buses there are and how many journeys each can carry. "
                "Choose a scenario to see the effect on England as a whole.")
    sens = pd.read_csv(DATA / f"allocation_sensitivity{SFX}.csv")
    c1, c2 = st.columns(2)
    fleet = c1.select_slider("Fleet size compared with today", [80, 100, 120], value=100, format_func=lambda x: f"{x}%", key="wi_fleet")
    prod = c2.select_slider("Journeys each bus can carry", [80, 100, 120], value=100, format_func=lambda x: f"{x}%", key="wi_prod",
                            help="Capacity per bus compared with today's DfT average for each region type.")
    row = sens[(sens["fleet_pct"] == fleet) & (sens["productivity_pct"] == prod)].iloc[0]
    a, b, c = st.columns(3)
    a.metric("Unmet trips/day, no reallocation", f"{row['unmet baseline'] / 1e3:,.0f}k")
    b.metric("After reallocation", f"{row['unmet optimised'] / 1e3:,.0f}k")
    c.metric("Reduction", f"-{row['reduction']:.0%}")
    if row["reduction"] > 0.999:
        st.success("In this scenario the fleet could meet all estimated demand once it is reallocated.")
    elif fleet == 100 and prod == 100:
        st.info("This is the base case used everywhere else in the dashboard.")
    elif row["reduction"] < 0.5:
        st.warning("In this scenario reallocation alone leaves a large share of demand unmet. More buses or higher capacity would be needed.")
    pv = sens.pivot(index="fleet_pct", columns="productivity_pct", values="reduction")
    fig = go.Figure(go.Heatmap(z=pv.values * 100, x=[f"{c}%" for c in pv.columns], y=[f"{i}%" for i in pv.index],
                               colorscale=[[0, "#f6efe0"], [1, "#c1121f"]], text=[[f"{v:.0%}" for v in r] for r in pv.values],
                               texttemplate="%{text}", showscale=False, hovertemplate="Fleet %{y}, journeys per bus %{x}: %{text}<extra></extra>"))
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      title=dict(text="Reduction in unmet demand, all scenarios", font=dict(size=13)),
                      xaxis_title="Journeys each bus can carry", yaxis_title="Fleet size")
    st.plotly_chart(fig, width="stretch")
    up = pd.read_csv(DATA / f"allocation_bands_sensitivity{SFX}.csv").set_index("peak_uplift")["reduction"]
    if 1.25 in up.index and 1.0 in up.index:
        st.markdown(f'<div class="note"><b>Peak demand matters.</b> The base case assumes demand is the same all day (07-19). If peak-time demand were 25% higher, '
                    f'the reduction would fall from {up[1.0]:.0%} to {up[1.25]:.0%}, because reallocating buses gets harder when demand is bunched.</div>',
                    unsafe_allow_html=True)

# ---------------------------------------------------------------- compare assumptions
with t4:
    st.markdown("**Does the answer depend on the demand assumption?** Both versions use the same fleet and the same total journeys. They differ only in where demand is placed.")
    rows = []
    for nm, sf in [("Population-based", ""), ("Observed bus use", "_obs")]:
        d1 = pd.read_csv(DATA / f"allocation_sensitivity{sf}.csv"); base = d1[(d1.fleet_pct == 100) & (d1.productivity_pct == 100)].iloc[0]
        d2 = pd.read_csv(DATA / f"allocation_bands_sensitivity{sf}.csv").set_index("peak_uplift")["reduction"]
        rows.append({"Demand assumption": nm, "Daily model": base["reduction"] * 100, "By time of day, flat demand": d2[1.0] * 100,
                     "By time of day, peak demand +25%": d2[1.25] * 100})
    tb = pd.DataFrame(rows)
    st.dataframe(tb, hide_index=True, width="stretch",
                 column_config={c: st.column_config.NumberColumn(c, format="%.0f%%") for c in tb.columns[1:]})
    st.caption("Reduction in estimated unmet demand after reallocation, England.")
    la = d.groupby("la").agg(today=("x0", "sum"), pop_=("x_opt", "sum"), obs_=("x_opt_obs", "sum"), residents=("population", "sum")).reset_index()
    la = la[la["today"] > 0]
    la["Population-based"] = (la["pop_"] / la["today"] - 1) * 100
    la["Observed bus use"] = (la["obs_"] / la["today"] - 1) * 100
    la["Difference"] = la["Observed bus use"] - la["Population-based"]
    # Ignore small authorities (under 50,000 residents), where a few neighbourhoods can swing the percentage
    big = la[la["residents"] > 50000].reindex(la["Difference"].abs().sort_values(ascending=False).index).dropna().head(10).rename(columns={"la": "Local authority"})
    st.markdown("**Where the assumption matters most** (change in buses, local authorities with 50,000+ residents)")
    fmt = {c: st.column_config.NumberColumn(c, format="%+.0f%%") for c in ["Population-based", "Observed bus use", "Difference"]}
    st.dataframe(big[["Local authority", "Population-based", "Observed bus use", "Difference"]], hide_index=True, width="stretch", column_config=fmt)
    st.markdown('<div class="note"><b>How to read this.</b> The England-wide reduction is similar under both assumptions, so the headline is not driven by it. '
                'But individual places change a lot: a city with a strong bus network (such as Nottingham) loses far fewer buses once its real use is counted. '
                'Treat place-level results as indicative and check them against local knowledge.</div>', unsafe_allow_html=True)
