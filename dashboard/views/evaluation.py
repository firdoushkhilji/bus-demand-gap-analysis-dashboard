"""Evaluation: how well does the demand-gap score hold up against independent evidence?"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import read_csv_optional, BLACK, RED, GREY

LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=30, b=10))

st.markdown("#### Does the score hold up?")
st.caption("Four checks: against an independent accessibility dataset (PTAI-2022), against DfT bus journeys, against changes to the score weights, "
           "and on the clustering choice. Spearman rank correlation (rho) is used: 0 = no relationship, +1 or -1 = perfect.")

ptai = read_csv_optional("validation_ptai.csv")
dft = read_csv_optional("validation_dft_la.csv")
sens = read_csv_optional("sensitivity.csv")
ksel = read_csv_optional("kmeans_selection.csv")

t1, t2, t3, t4 = st.tabs(["1. PTAI-2022", "2. DfT bus journeys", "3. Weight sensitivity", "4. Clustering choice"])

with t1:
    if ptai is None:
        st.info("validation_ptai.csv is not in dashboard/data. Re-run notebook 07, then notebook 06.")
    else:
        grp = st.segmented_control("Areas", ["All", "Urban", "Rural"], default="All", key="ev_grp") or "All"
        col = f"rho {grp}"
        exp = ptai["expected sign"]
        # True where rho has the sign we expected (negative for "reachable" measures, positive for "minutes to" measures)
        good = [(r < 0) if s == "-" else (r > 0) for r, s in zip(ptai[col], exp)]
        # |rho| under 0.1 is too weak to call a direction
        weak = ptai[col].abs() < 0.1
        colors = [GREY if w else (BLACK if g else RED) for w, g in zip(weak, good)]
        fig = go.Figure(go.Bar(x=ptai[col], y=ptai["PTAI measure"], orientation="h", marker_color=colors,
                               text=[f"{v:+.2f}" for v in ptai[col]], textposition="outside"))
        fig.update_layout(height=340, xaxis=dict(title="Spearman rho with the gap score", range=[-.6, .6], zeroline=True, zerolinecolor="#141414"),
                          yaxis=dict(autorange="reversed"), title=dict(text=f"Agreement with PTAI-2022: {grp.lower()} areas", font=dict(size=13)), **LAYOUT)
        st.plotly_chart(fig, width="stretch")
        st.caption("Black = points the expected way. Red = points the wrong way. Grey = too weak to call (|rho| below 0.1).")
        a, b, c = st.columns(3)
        a.metric("Strongest agreement (this view)", f"{ptai[col].abs().max():.2f}")
        b.metric("Measures pointing the expected way", f"{sum(g and not w for g, w in zip(good, weak))} of {len(ptai)}")
        c.metric("LSOAs compared", f"{int(ptai['n'].max()):,}", help="2011 and 2021 LSOA codes match for 94.2% of areas; the rest are excluded.")
        var = read_csv_optional("validation_ptai_variants.csv")
        if var is not None:
            st.markdown("**Further tests, added after the first result.** The full score agreed only weakly, so these variants were tried afterwards to see why. They explain the weak result; "
                        "they do not replace it. Each bar is the average agreement with the expected direction across all seven PTAI measures (positive = points the expected way).")
            v = var[var["group"] == grp].copy()
            # Signed strength: +|rho| if it points the expected way, -|rho| if not, so the average across measures is meaningful
            v["agree"] = v["rho"].abs() * v["right_way"].map({True: 1, False: -1})
            sm = v.groupby("test")["agree"].mean().sort_values()
            fv = go.Figure(go.Bar(x=sm.values, y=sm.index, orientation="h", marker_color=[RED if t.startswith("Provision") else BLACK for t in sm.index],
                                  text=[f"{x:+.2f}" for x in sm.values], textposition="outside"))
            fv.update_layout(height=300, xaxis=dict(title="Average agreement with PTAI", range=[min(-0.05, sm.min() - .05), max(0.5, sm.max() + .1)], zeroline=True, zerolinecolor="#141414"),
                             title=dict(text=f"Different ways of testing the score: {grp.lower()} areas", font=dict(size=13)), **LAYOUT)
            st.plotly_chart(fv, width="stretch")
            st.markdown('<div class="note"><b>What this shows.</b> Agreement is much stronger when only provision (distance to a stop and buses per person) is compared, '
                        'including in towns and cities. Adding need (density and deprivation) lowers it, which is expected because PTAI measures reach, not need. '
                        'This is consistent with the provision part of the score, but because these variants were chosen after seeing the first result, it is supporting evidence, not proof. The need part cannot be tested with PTAI and rests on the literature. '
                        'Comparing neighbourhoods only within the same local authority gives similar results.</div>', unsafe_allow_html=True)
        with st.expander("Show the full table"):
            tb = ptai[["PTAI measure", "expected sign", "rho All", "rho Urban", "rho Rural", "n"]].copy()
            tb["expected sign"] = tb["expected sign"].map({"-": "negative", "+": "positive"})
            st.dataframe(tb.round(2), hide_index=True, width="stretch")
        st.markdown('<div class="note"><b>How to read this.</b> Across England the score agrees only weakly with PTAI, but in rural areas every measure points the expected way '
                    '(weak to moderate). In urban areas there is almost no relationship. That is partly expected: PTAI measures what can be <i>reached</i> in 45 minutes on a weekday '
                    'morning in November 2021, while the score measures how well an area\'s own service matches its likely need, using 2026 timetables.</div>', unsafe_allow_html=True)

with t2:
    if dft is None:
        st.info("validation_dft_la.csv is not in dashboard/data. Run notebook 08, then notebook 06.")
    else:
        n = int(dft["n"].iloc[0])
        cols = st.columns(len(dft))
        for c, (_, r) in zip(cols, dft.iterrows()):
            c.metric(str(r.iloc[0]), f"{r['Spearman rho']:+.2f}")
        with st.expander("Show the table"):
            d2 = dft.copy(); d2["Spearman rho"] = d2["Spearman rho"].map(lambda x: f"{x:+.2f}")
            st.dataframe(d2.rename(columns={"n": "Local authorities"}), hide_index=True, width="stretch")
        pts = read_csv_optional("validation_dft_la_points.csv")
        if pts is not None:
            fig = go.Figure(go.Scatter(x=pts["freq_per_1000"], y=pts["dft_per_head"], mode="markers", text=pts["la"],
                                       marker=dict(color=RED, size=9, opacity=.8, line=dict(color=BLACK, width=1))))
            fig.update_layout(xaxis_title="GTFS departures per hour per 1,000 residents", yaxis_title="DfT bus journeys per head",
                              height=330, title=dict(text="Timetabled service against real bus use", font=dict(size=13)), **LAYOUT)
            st.plotly_chart(fig, width="stretch")
        else:
            st.caption("The scatter plot appears after notebooks 08 and 06 are re-run.")
        st.markdown(f'<div class="note"><b>How to read this.</b> DfT bus journeys (year ending March 2025) were compared with the model for the {n} unitary authorities matched by name '
                    '(about a quarter of England\'s population). Timetabled service tracks real bus use closely (rho 0.88), so the frequency data are sound. '
                    'Population-based demand is only a moderate predictor of real totals (rho 0.53): places with strong networks, such as Brighton and Hove, carry far more journeys per head than the model assumes. '
                    'The gap score is negatively related to journeys per head (rho -0.42), as expected, but it is not a measure of observed use.</div>', unsafe_allow_html=True)

with t3:
    if sens is None:
        st.info("sensitivity.csv is not in dashboard/data.")
    else:
        med_rho, med_ov = sens["spearman_vs_base"].median(), sens["top10_overlap"].median()
        share = (sens["spearman_vs_base"] >= 0.8).mean()
        a, b, c = st.columns(3)
        a.metric("Median rank agreement with base weights", f"{med_rho:.2f}")
        b.metric("Median overlap of the worst-served 10%", f"{med_ov:.0%}")
        c.metric("Weight sets with rho of 0.8 or more", f"{share:.0%}", help=f"Out of {len(sens)} random weight sets.")
        f1 = go.Figure(go.Histogram(x=sens["spearman_vs_base"], nbinsx=30, marker_color=BLACK))
        f1.update_layout(title=dict(text="Rank agreement with base weights", font=dict(size=13)), xaxis_title="Spearman rho", yaxis_title="Weight sets", height=280, **LAYOUT)
        f2 = go.Figure(go.Histogram(x=sens["top10_overlap"] * 100, nbinsx=30, marker_color=RED))
        f2.update_layout(title=dict(text="Overlap of the worst-served 10%", font=dict(size=13)), xaxis_title="% of the same areas", yaxis_title="Weight sets", height=280, **LAYOUT)
        l, r = st.columns(2)
        l.plotly_chart(f1, width="stretch"); r.plotly_chart(f2, width="stretch")
        same = st.session_state["ctx"]["same_top10"]
        st.markdown(f'<div class="note"><b>How to read this.</b> {len(sens)} random sets of the four weights were drawn (any mix, including extreme ones) and the ranking compared with the base weights (30/30/20/20). '
                    'The overall pattern is fairly stable, but the exact list of worst-served areas moves a lot, so the score is best used to screen for where to look, not to rank neighbourhoods one by one. '
                    f'<br><b>Your current sidebar weights</b> keep {same:.0%} of the default worst-served 10%.</div>', unsafe_allow_html=True)

with t4:
    if ksel is None:
        st.info("kmeans_selection.csv is not in dashboard/data.")
    else:
        fig = go.Figure(go.Bar(x=ksel["k"].astype(str), y=ksel["silhouette"], marker_color=[RED if k == 4 else GREY for k in ksel["k"]],
                               text=[f"{v:.2f}" for v in ksel["silhouette"]], textposition="outside"))
        fig.update_layout(xaxis_title="Number of clusters (k)", yaxis_title="Silhouette score", height=300, **LAYOUT)
        l, r = st.columns([1.3, 1])
        l.plotly_chart(fig, width="stretch")
        r.markdown('<div class="note"><b>How to read this.</b> k = 2 scores highest, but it only separates well-served from poorly served areas. From k = 3 the scores are low and flat (about 0.3): the groups overlap. '
                   'k = 4 (red) was chosen by judgement, not by silhouette, because it adds two small but meaningful groups (off-peak only and morning-heavy). '
                   'Read the clusters as a useful description, not as sharply separate types.</div>', unsafe_allow_html=True)

st.divider()
st.caption("Not tested: predicted demand against passenger counts at neighbourhood level (open data are not available), and recommendations against what operators actually run.")
