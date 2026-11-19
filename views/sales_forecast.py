from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fm import charts, ui
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
with st.form("sales_params"), st.container(key="sf_inputs"):
    rates = [
        ("daily_customer_growth", "Daily Customer Growth Rate (%)"),
        ("daily_avt_growth", "Daily Average Value of Transaction Growth Rate (%)"),
        ("weekly_customer_growth", "Weekly Customer Growth Rate (%)"),
        ("weekly_avt_growth", "Weekly Average Value of Transaction Growth Rate (%)"),
        ("quarterly_customer_growth", "Quarterly Customer Growth Rate (%)"),
        ("quarterly_avt_growth", "Quarterly Average Value of Transaction Growth Rate (%)"),
        ("annual_customer_growth", "Annual Customer Growth Rate (%)"),
        ("annual_avt_growth", "Annual Average Value of Transaction Growth Rate (%)"),
    ]
    values = {}
    for row in range(0, len(rates), 4):
        cols = st.columns(4)
        for col, (key, label) in zip(cols, rates[row : row + 4]):
            values[key] = col.number_input(label, value=float(num(p.get(key))), step=0.5, format="%.2f")
    cols = st.columns(4)
    values["first_day_customers"] = cols[0].number_input("First Day No. of Customers", value=float(num(p.get("first_day_customers"), 1)), min_value=0.0)
    values["first_day_avt"] = cols[1].number_input("First Day Average Value of Transaction", value=float(num(p.get("first_day_avt"), 1000)), min_value=0.0, step=100.0)
    cols[2].text_input("First Day Sales", inr(values["first_day_customers"] * values["first_day_avt"]), disabled=True)
    start = cols[3].date_input("Date", value=date.fromisoformat(str(p.get("start_date"))[:10]), format="DD-MM-YYYY")
    c = st.columns(4)
    values["years"] = c[0].number_input("Years to forecast", value=int(num(p.get("years"), 10)), min_value=1, max_value=30,
                                        help="Each forecast year is 12 months from the start date. The yearly table splits them by calendar year.")
    if st.form_submit_button("Update", type="primary"):
        values["start_date"] = start.isoformat()
        repo.save_setting(model["id"], "sales_forecast", values)
        ui.flash("Sales forecast saved")
        st.rerun()

m = st.columns(3)
m[0].metric("Total # of customers, first 12 months", f"{sales['first_year_customers']:,.0f}")
m[1].metric("Sales, first 12 months", inr(sales["first_year_sales"]))
m[2].metric("Average value of transaction", inr(sales["first_year_sales"] / sales["first_year_customers"] if sales["first_year_customers"] else 0))
st.caption("Quarters are 3 calendar months from the start date and a year is 365 days (366 in a leap year). "
           "The yearly table is by calendar year, so a partial first or last year only counts its own months. "
           "The first-12-months customer count feeds the channel-wise forecast on the Profit & Loss page.")

df = pd.DataFrame(sales["rows"])
table = pd.DataFrame({
    "PERIOD": df["period"],
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
