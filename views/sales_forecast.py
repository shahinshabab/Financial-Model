import math
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fm import charts, ui
from fm import calc
from fm.calc import num
from fm.fmt import inr

repo, model, snap = ui.page_setup(["Sales Forecast"])
ui.show_flash()
p = snap["sales_settings"]
sales = snap["sales"]

st.subheader("Sales Forecast")
# Give every input label the same height so all inputs in a row sit on one line.
st.markdown(
    "<style>.st-key-sf_inputs [data-testid='stWidgetLabel']{min-height:2.9rem;display:flex;align-items:flex-end;}</style>",
    unsafe_allow_html=True,
)
PERIODS = {"daily": "Daily", "weekly": "Weekly", "quarterly": "Quarterly (90 days)", "annual": "Yearly (365 days)"}
c_period0, c_rate0 = calc.active_growth(p, "customer")
a_period0, a_rate0 = calc.active_growth(p, "avt")
period0 = c_period0 or a_period0 or "daily"

with st.form("sales_params"), st.container(key="sf_inputs"):
    cols = st.columns(4)
    period = cols[0].selectbox("Growth rate per", list(PERIODS), index=list(PERIODS).index(period0),
                               format_func=PERIODS.get,
                               help="Pick the period your growth rates are for. They are turned into a daily rate, "
                                    "and the weeks, quarters and years are worked out from it.")
    c_rate = cols[1].number_input("Customer Growth Rate (%)", value=float(c_rate0), step=0.5, format="%.2f", min_value=-99.0)
    a_rate = cols[2].number_input("Avg. Transaction Value Growth (%)", help="Growth of the average value of a transaction (AVT)", value=float(a_rate0), step=0.5, format="%.2f", min_value=-99.0)
    years = cols[3].number_input("Years to forecast", value=int(num(p.get("years"), 10)), min_value=1, max_value=30,
                                 help="Full calendar years. If the start date isn't 1 January, the rest of the start year is shown first as a part year.")
    cols = st.columns(4)
    c0 = cols[0].number_input("First Day No. of Customers", value=float(num(p.get("first_day_customers"), 1)), min_value=0.0)
    a0 = cols[1].number_input("First Day Average Value of Transaction", value=float(num(p.get("first_day_avt"), 1000)), min_value=0.0, step=100.0)
    cols[2].text_input("First Day Sales", inr(c0 * a0), disabled=True)
    start = cols[3].date_input("Date", value=date.fromisoformat(str(p.get("start_date"))[:10]), format="DD-MM-YYYY")
    if st.form_submit_button("Update", type="primary"):
        values = {f"{per}_{what}_growth": 0.0 for per in PERIODS for what in ("customer", "avt")}
        values[f"{period}_customer_growth"] = float(c_rate)
        values[f"{period}_avt_growth"] = float(a_rate)
        values |= {"first_day_customers": float(c0), "first_day_avt": float(a0),
                   "start_date": start.isoformat(), "years": int(years)}
        repo.save_setting(model["id"], "sales_forecast", values)
        ui.flash("Sales forecast saved")
        st.rerun()

m = st.columns(3)
m[0].metric("Total # of customers, first 365 days", f"{sales['first_year_customers']:,.0f}")
m[1].metric("Sales, first 365 days", inr(sales["first_year_sales"]))
m[2].metric("Average value of transaction", inr(sales["first_year_sales"] / sales["first_year_customers"] if sales["first_year_customers"] else 0))
c_period, c_rate, c_daily = sales["customer_growth"]
a_period, a_rate, a_daily = sales["avt_growth"]
st.caption(
    "Customers on day n = C × (1 + r)^(n−1), and the total of the first n days is "
    "T = C × ((1 + r)^n − 1) ÷ r. Each week, quarter (90 days) and year (365 days) is T at its last day minus T at "
    "the day before it starts, so every period comes from the same daily curve. "
    + (f"Customer growth: {c_rate:g}% {c_period} = {c_daily * 100:.4f}% a day. " if c_period else "Customer growth: none. ")
    + (f"Average value growth: {a_rate:g}% {a_period} = {a_daily * 100:.4f}% a day. " if a_period else "Average value growth: none. ")
    + "The first 365 days' customer count feeds the channel-wise forecast on the Profit & Loss page."
)
if not all(map(math.isfinite, (sales["first_year_customers"], sales["first_year_sales"]))) or not all(
        math.isfinite(r["sales"]) for r in sales["rows"]):
    st.warning("The growth rate is too high: the numbers grow beyond what can be shown. Lower the rate.")

df = pd.DataFrame(sales["rows"])
table = pd.DataFrame({
    "PERIOD": df["period"],
    "DAYS": df["days"],
    "NO. OF CUSTOMERS": df["customers"].map(lambda v: f"{v:,.2f}"),
    "AVERAGE VALUE OF TRANSACTION": df["avt"].map(lambda v: f"{v:,.2f}"),
    "SALES": df["sales"].map(lambda v: f"{v:,.2f}"),
})
tab1, tab2 = st.tabs(["Table", "Chart"])
with tab1:
    st.dataframe(table, hide_index=True, width="stretch", height=min(40 + 35 * len(table), 900))
with tab2:
    yearly = df[df["level"] == "year"]
    fig = go.Figure(go.Bar(x=yearly["period"], y=yearly["sales"], marker_color=charts.PALETTE[0],
                           customdata=[[inr(s), f"{c:,.0f}"] for s, c in zip(yearly["sales"], yearly["customers"])],
                           hovertemplate="<b>%{x}</b><br>Sales: %{customdata[0]}<br>Customers: %{customdata[1]}<extra></extra>"))
    fig.update_layout(height=380, margin=dict(t=20, b=20), yaxis_title="Sales (₹)", bargap=0.35)
    charts.show(fig, "sales_bar")
