import plotly.graph_objects as go
import streamlit as st
from common import CLUSTER_COL, BLACK, RED, GREY, read_csv_optional

ctx = st.session_state["ctx"]
d, view, place = ctx["d"], ctx["view"], ctx["place"]
BANDS = ["freq_morning", "freq_off_peak", "freq_evening"]
LBL = ["Morning 07-10", "Off-peak 10-16", "Evening 16-19"]
LAY = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=30, b=10))

st.markdown("#### When do buses run?")
st.caption("Every neighbourhood is placed in one of five service patterns by K-means (k = 4, plus a separate group for no service) on its share of "
           "departures in each time band and its overall level. Pattern describes *when* buses run, not how good the service is.")
t1, t2, t3 = st.tabs(["Service patterns", "My area compared with England", "Weekday and weekend"])

with t1:
    left, right = st.columns([1.4, 1])
    with left:
        prof = d[d["cluster"] >= 0].groupby("cluster_name")[BANDS].mean()
        cnt = d["cluster_name"].value_counts()
        fig = go.Figure()
        for name, row in prof.iterrows():
            fig.add_scatter(x=LBL, y=row.values, mode="lines+markers", name=f"{name} ({cnt[name]:,})",
                            line=dict(color=CLUSTER_COL.get(name), width=3), marker=dict(size=8))
        fig.update_layout(yaxis_title="Departures per hour (mean)", height=380, legend=dict(orientation="h", y=-0.18),
                          title=dict(text="Average departures per hour, by service pattern (England)", font=dict(size=13)), **LAY)
        st.plotly_chart(fig, width="stretch")
    with right:
        mix = view["cluster_name"].value_counts().rename_axis("Service pattern").reset_index(name="Neighbourhoods")
        mix["Share"] = mix["Neighbourhoods"] / mix["Neighbourhoods"].sum() * 100
        st.markdown(f"**{place}: how neighbourhoods split**")
        st.dataframe(mix, hide_index=True, width="stretch",
                     column_config={"Neighbourhoods": st.column_config.NumberColumn(format="%d"),
                                    "Share": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100)})
        st.markdown('<div class="note"><b>What stands out.</b> For nine in ten neighbourhoods, service is almost flat across the day: the two big groups differ in '
                    '<i>how much</i> service they get, not <i>when</i>. Only about 3% have a clear peak or off-peak pattern, and about 7% have no service on the sample weekday.</div>',
                    unsafe_allow_html=True)

with t2:
    st.markdown(f"**{place}** against all of England")
    order = ["High frequency, all day", "Low frequency, all day", "Morning-peak heavy", "Off-peak only", "No service"]
    a = view["cluster_name"].value_counts(normalize=True).reindex(order).fillna(0) * 100
    b = d["cluster_name"].value_counts(normalize=True).reindex(order).fillna(0) * 100
    l, r = st.columns(2)
    f1 = go.Figure()
    f1.add_bar(x=order, y=b.values, name="England", marker_color=GREY)
    f1.add_bar(x=order, y=a.values, name=place, marker_color=RED)
    f1.update_layout(barmode="group", yaxis_title="% of neighbourhoods", height=330, legend=dict(orientation="h", y=-0.3),
                     title=dict(text="Share in each service pattern", font=dict(size=13)), **LAY)
    l.plotly_chart(f1, width="stretch")
    f2 = go.Figure()
    f2.add_bar(x=LBL, y=[d[c].mean() for c in BANDS], name="England", marker_color=GREY)
    f2.add_bar(x=LBL, y=[view[c].mean() for c in BANDS], name=place, marker_color=BLACK)
    f2.update_layout(barmode="group", yaxis_title="Departures per hour (mean)", height=330, legend=dict(orientation="h", y=-0.3),
                     title=dict(text="Average departures per hour", font=dict(size=13)), **LAY)
    r.plotly_chart(f2, width="stretch")
    m_now, m_all = view["freq_morning"].mean(), d["freq_morning"].mean()
    e_now, e_all = view["freq_evening"].mean(), d["freq_evening"].mean()
    # How much busier the morning is than the off-peak, in %
    peak = (m_now / max(view["freq_off_peak"].mean(), 1e-9) - 1) * 100
    st.markdown(f'<div class="note"><b>In {place}:</b> an average neighbourhood has {m_now:.1f} departures an hour in the morning '
                f'(England {m_all:.1f}) and {e_now:.1f} in the evening (England {e_all:.1f}). Morning service is '
                f'{abs(peak):.0f}% {"above" if peak >= 0 else "below"} the off-peak level, which shows how peaked the local timetable is. '
                f'{a["No service"]:.0f}% of neighbourhoods have no service on the sample weekday (England {b["No service"]:.0f}%).</div>',
                unsafe_allow_html=True)

# ---------------------------------------------------------------- weekday vs weekend
with t3:
    if "freq_sat_mean" not in d.columns:
        st.info("Weekend timetables have not been added yet. Run notebook 04 (it now counts a Saturday and a Sunday in the same pass), then notebook 02 onwards and 06.")
    else:
        dates = read_csv_optional("gtfs_dates.csv")
        lab = ""
        if dates is not None:
            dd = dates[dates["snapshot"] == 1].set_index("day")["date"].to_dict()
            lab = f" (weekday {dd.get('weekday', '')}, Saturday {dd.get('saturday', '')}, Sunday {dd.get('sunday', '')})"
        st.markdown(f"**{place}: service on a weekday, Saturday and Sunday**{lab}")
        cols = ["freq_mean", "freq_sat_mean", "freq_sun_mean"]; nm = ["Weekday", "Saturday", "Sunday"]
        a, b, c = st.columns(3)
        wk = view["freq_mean"].mean()
        a.metric("Saturday service, % of weekday", f"{view['freq_sat_mean'].mean() / max(wk, 1e-9):.0%}", help="Mean departures per hour across 07-19, averaged over neighbourhoods.")
        b.metric("Sunday service, % of weekday", f"{view['freq_sun_mean'].mean() / max(wk, 1e-9):.0%}")
        c.metric("No Sunday service", f"{(view['freq_sun_mean'] == 0).mean():.0%}", delta=f"{(view['freq_sun_mean'] == 0).mean() - (view['freq_mean'] == 0).mean():+.0%} vs weekday",
                 delta_color="inverse", help="Share of neighbourhoods with no departures between 07 and 19.")
        l, r = st.columns(2)
        f1 = go.Figure()
        f1.add_bar(x=nm, y=[d[c_].mean() for c_ in cols], name="England", marker_color=GREY)
        f1.add_bar(x=nm, y=[view[c_].mean() for c_ in cols], name=place, marker_color=RED)
        f1.update_layout(barmode="group", yaxis_title="Departures per hour (mean)", height=320, legend=dict(orientation="h", y=-0.2),
                         title=dict(text="Average departures per hour, 07-19", font=dict(size=13)), **LAY)
        l.plotly_chart(f1, width="stretch")
        # Weekend service as a % of weekday service, for each service pattern
        g = d[d["cluster"] >= 0].groupby("cluster_name")[cols].mean()
        g = (g[["freq_sat_mean", "freq_sun_mean"]].div(g["freq_mean"], axis=0) * 100).reindex(
            ["High frequency, all day", "Low frequency, all day", "Morning-peak heavy", "Off-peak only"]).dropna()
        f2 = go.Figure()
        f2.add_bar(x=g.index, y=g["freq_sat_mean"], name="Saturday", marker_color=BLACK)
        f2.add_bar(x=g.index, y=g["freq_sun_mean"], name="Sunday", marker_color=RED)
        f2.update_layout(barmode="group", yaxis_title="% of weekday service", height=360, legend=dict(orientation="h", y=-0.55),
                         title=dict(text="Weekend service by service pattern (England)", font=dict(size=13)), **LAY)
        r.plotly_chart(f2, width="stretch")
        st.markdown('<div class="note"><b>How to read this.</b> The gap score and the vehicle allocation use the weekday only. This view shows how much thinner service is at the weekend. '
                    'Areas where Sunday is far below the weekday are weak for people who work or travel then.</div>', unsafe_allow_html=True)
