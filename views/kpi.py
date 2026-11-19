import plotly.graph_objects as go
import streamlit as st

from fm import calc, charts, ui
from fm.fmt import inr, pct

repo, model, snap = ui.page_setup(["KPI Dashboard"])
pl, cf, years = snap["pl"], snap["cf"], snap["years"]
rev0 = pl["revenue"][0] if pl["revenue"] else 0

st.subheader("KPI Dashboard")
r1 = st.columns(4)
r1[0].metric("Total capital required", inr(snap["grand_total"]))
r1[1].metric("Year 1 revenue", inr(rev0))
r1[2].metric("Year 1 profit after tax", inr(pl["pat"][0] if pl["pat"] else 0))
r1[3].metric("Year 1 ROI", pct(pl["roi"][0] if pl["roi"] else 0))
r2 = st.columns(4)
r2[0].metric("Gross margin (GP %)", pct(snap["gp_pct"]))
r2[1].metric("Net margin, year 1", pct((pl["pat"][0] / rev0 * 100) if rev0 else 0))
r2[2].metric("Monthly break-even sales", inr(snap["be"]["bep"]))
payback = calc.payback_years(snap["grand_total"], [p + d for p, d in zip(pl["pat"], pl["depreciation"])])
r2[3].metric("Payback period", f"{payback:.1f} years" if payback else "Beyond projection")

fig = go.Figure()
fig.add_trace(go.Bar(x=years, y=pl["revenue"], name="Revenue", marker_color=charts.PALETTE[0], customdata=[inr(v) for v in pl["revenue"]],
                     hovertemplate="%{x}<br>Revenue: %{customdata}<extra></extra>"))
fig.add_trace(go.Bar(x=years, y=pl["pat"], name="Profit after tax", marker_color=charts.PALETTE[2], customdata=[inr(v) for v in pl["pat"]],
                     hovertemplate="%{x}<br>PAT: %{customdata}<extra></extra>"))
fig.update_layout(barmode="group", height=380, margin=dict(t=30, b=20), legend=dict(orientation="h", y=1.1), yaxis_title="₹", bargap=0.3)
st.markdown("**Revenue and profit by year**")
charts.show(fig, "kpi_bars")

fig2 = go.Figure(go.Scatter(x=years, y=cf["net"], mode="lines+markers", line=dict(color=charts.PALETTE[6], width=2), marker=dict(size=8),
                            customdata=[inr(v) for v in cf["net"]], hovertemplate="%{x}<br>Cumulative cash: %{customdata}<extra></extra>"))
fig2.update_layout(height=320, margin=dict(t=20, b=20), yaxis_title="₹")
st.markdown("**Cumulative cash (Cash Flow net income)**")
charts.show(fig2, "kpi_cash")
