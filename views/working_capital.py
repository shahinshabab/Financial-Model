import pandas as pd
import streamlit as st

from fm import ui
from fm.calc import num
from fm.fmt import inr

repo, model, snap = ui.page_setup(["Working Capital"])
ui.show_flash()
wc = snap["wc_settings"]
pl = snap["pl"]
years = snap["years"]

st.subheader("Working Capital Requirement")
st.caption("Cash needed to keep the business running: months of operating cost held in reserve, plus money tied up in "
           "receivables and stock, less what suppliers let you pay later.")
with st.form("wc"):
    c = st.columns(4)
    months = c[0].number_input("Months of operating cost to hold", value=float(num(wc["months_cover"], 3)), min_value=0.0)
    rec = c[1].number_input("Receivable days (of revenue)", value=float(num(wc["receivable_days"])), min_value=0.0)
    inv = c[2].number_input("Inventory days (of direct cost)", value=float(num(wc["inventory_days"])), min_value=0.0)
    pay = c[3].number_input("Payable days (of direct cost)", value=float(num(wc["payable_days"])), min_value=0.0)
    if st.form_submit_button("Update", type="primary"):
        repo.save_setting(model["id"], "working_capital", {"months_cover": months, "receivable_days": rec, "inventory_days": inv, "payable_days": pay})
        st.rerun()

monthly_opex = snap["section_totals"]["operating"]
rows = []
for i, y in enumerate(years):
    opex_year = sum(r["values"][i] for r in pl["indirect"] if not r["one_time"]) or monthly_opex * 12
    reserve = opex_year / 12 * months
    receivables = pl["revenue"][i] * rec / 365
    inventory = pl["direct"][i] * inv / 365
    payables = pl["direct"][i] * pay / 365
    rows.append({"Year": y, "Operating reserve": reserve, "Receivables": receivables, "Inventory": inventory,
                 "Less: Payables": payables, "Working capital": reserve + receivables + inventory - payables})
df = pd.DataFrame(rows)
st.metric("Working capital needed in year 1", inr(df["Working capital"].iloc[0]) if len(df) else inr(0))
st.dataframe(df.style.format({c: inr for c in df.columns if c != "Year"}), hide_index=True, width="stretch")
