import plotly.graph_objects as go
import streamlit as st

from fm import charts, ui
from fm.calc import num
from fm.fmt import inr, pct

repo, model, snap = ui.page_setup(["Break Even"])
ui.show_flash()
mid = model["id"]
be_set = snap["be_settings"]
be = snap["be"]

st.subheader("Particulars")
c = st.columns(3)
c[0].text_input("Monthly Fixed Operating Expense", inr(snap["fixed_monthly"]), disabled=True,
                help="Operating Capital categories ticked 'Add to BE'")
c[1].text_input("Monthly Overheads", inr(snap["overheads"]), disabled=True,
                help="Fixed operating expense + Pre-Operating 'Add to BE' categories ÷ 12 + variable costs below")
c[2].text_input("Contribution %. GP", pct(snap["gp_pct"]), disabled=True, help="100% − COGS % (see COGS page)")

st.markdown(f"#### Break Even Point = {be['bep']:,.2f}")
st.caption(f"Calculated Sales Target (Break Even Point × 2) = {be['suggested_target']:,.2f}")
with st.form("target"):
    cc = st.columns([3, 1], vertical_alignment="bottom")
    target = cc[0].number_input("Sales Target (monthly, 0 = use calculated target)", value=float(num(be_set.get("sales_target"))), min_value=0.0, step=1000.0)
    if cc[1].form_submit_button("Update", width="stretch"):
        repo.save_setting(mid, "break_even", dict(be_set) | {"sales_target": target})
        st.rerun()
if snap["gp_pct"] <= 0:
    st.warning("Contribution % is 0. Add COGS categories with % of revenue (and keep the total below 100%).")

st.divider()
st.subheader("Variable costs")
variables = list(be_set.get("variable_costs") or [])
widths = [4, 3, 1, 1]
ui.head(st.columns(widths), ["Variable name", "Value", "", ""])
with st.form("add_var", clear_on_submit=True, border=False):
    cols = st.columns(widths, vertical_alignment="bottom")
    vn = cols[0].text_input("name", placeholder="Enter Variable", label_visibility="collapsed")
    vv = cols[1].number_input("value", value=0.0, min_value=0.0, label_visibility="collapsed")
    if cols[2].form_submit_button("Submit", type="primary", width="stretch") and vn.strip():
        repo.save_setting(mid, "break_even", dict(be_set) | {"variable_costs": variables + [{"name": vn.strip(), "value": vv}]})
        st.rerun()
for i, v in enumerate(variables):
    cols = st.columns(widths, vertical_alignment="center")
    n = cols[0].text_input("n", v["name"], key=f"vn_{i}", label_visibility="collapsed")
    val = cols[1].number_input("v", value=float(num(v["value"])), min_value=0.0, key=f"vv_{i}", label_visibility="collapsed")
    if cols[2].button("Update", key=f"vu_{i}", width="stretch"):
        variables[i] = {"name": n, "value": val}
        repo.save_setting(mid, "break_even", dict(be_set) | {"variable_costs": variables})
        st.rerun()
    if cols[3].button("Delete", key=f"vd_{i}", width="stretch"):
        variables.pop(i)
        repo.save_setting(mid, "break_even", dict(be_set) | {"variable_costs": variables})
        st.rerun()
cols = st.columns(widths)
ui.cell(cols[0], "Total Variable Value :", bold=True)
ui.cell(cols[1], f"{snap['variable_total']:,.2f}", bold=True)

st.divider()
st.subheader("Chart")
if be["target"] > 0:
    fig = go.Figure()
    hover = "Day %{x}<br>%{customdata}<extra>%{fullData.name}</extra>"
    fig.add_trace(go.Scatter(x=be["days"], y=be["fixed"], name="Fixed Cost", mode="lines", line=dict(color=charts.PALETTE[7], width=2, dash="dash"),
                             customdata=[inr(v) for v in be["fixed"]], hovertemplate=hover))
    fig.add_trace(go.Scatter(x=be["days"], y=be["total_cost"], name="Total Cost", mode="lines", line=dict(color=charts.PALETTE[1], width=2),
                             customdata=[inr(v) for v in be["total_cost"]], hovertemplate=hover))
    fig.add_trace(go.Scatter(x=be["days"], y=be["revenue"], name="Sales / Revenue", mode="lines", line=dict(color=charts.PALETTE[0], width=2),
                             customdata=[inr(v) for v in be["revenue"]], hovertemplate=hover))
    if be["bep"] > 0:
        fig.add_trace(go.Scatter(x=[be["bep_day"]], y=[be["bep"]], name="Break Even Point", mode="markers+text", marker=dict(size=12, color=charts.PALETTE[3], line=dict(color="white", width=2)),
                                 text=[f"Break-Even<br>{inr(be['bep'])}"], textposition="top center",
                                 hovertemplate=f"Break even on day {be['bep_day']:.1f}<br>{inr(be['bep'])}<extra></extra>"))
        fig.add_vline(x=be["bep_day"], line=dict(color="#a3a29c", dash="dot", width=1))
    fig.update_layout(height=460, hovermode="x unified", xaxis_title="Month days", yaxis_title="Amount (₹)",
                      legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center"), margin=dict(t=40, b=40))
    fig.update_xaxes(dtick=1)
    charts.show(fig, "be_chart")
else:
    st.info("Add Operating categories ticked 'Add to BE' and COGS percentages to see the chart.")
