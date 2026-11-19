import pandas as pd
import streamlit as st

from fm import ui
from fm.calc import num
from fm.fmt import inr, pct

repo, model, snap = ui.page_setup(["Cash Flow"])
ui.show_flash()
mid = model["id"]
cf_set = snap["cf_settings"]
cf = snap["cf"]
years = snap["years"]

h1, h2 = st.columns([4, 1])
h1.subheader("Cash Flow Table")
rows = [
    ("Opening Balance", cf["opening"]),
    ("Profit after taxation", cf["pat"]),
    ("Add: Depreciation", cf["depreciation"]),
    ("Less: Receivable", cf["receivables"]),
    ("Net Income", cf["net"]),
]
df = pd.DataFrame([{"PARTICULARS": label, **{y: ("" if (label == "Opening Balance" and i == 0) else inr(v[i])) for i, y in enumerate(years)}} for label, v in rows])
st.dataframe(df, hide_index=True, width="stretch")

with h2.popover("✏️ Edit", width="stretch"):
    with st.form("cf_edit"):
        st.markdown("**Less: Receivable (₹) per year**")
        rec = list(cf_set.get("receivables") or [])
        cols = st.columns(2)
        vals = [cols[i % 2].number_input(y, value=float(num(rec[i]) if i < len(rec) else 0.0), min_value=0.0, key=f"rec_{i}") for i, y in enumerate(years)]
        if st.form_submit_button("Save Cash Flow", type="primary"):
            repo.save_setting(mid, "cash_flow", dict(cf_set) | {"receivables": vals, "saved": True})
            ui.flash("Cash flow saved")
            st.rerun()
st.caption("Profit after tax and depreciation come from the Profit & Loss page.")

st.divider()
st.subheader("Budgeting Plan for Surplus Cash Flow")
year_idx = st.selectbox("Surplus cash of year", range(len(years)), index=min(int(num(cf_set.get("budget_year"))), len(years) - 1), format_func=lambda i: f"{years[i]} · {inr(cf['net'][i])}")
surplus = max(cf["net"][year_idx], 0.0)
budget = list(cf_set.get("budget") or [])


def save_budget(new_budget, **extra):
    repo.save_setting(mid, "cash_flow", dict(cf_set) | {"budget": new_budget, "budget_year": year_idx} | extra)


widths = [3, 1.4, 2, 4, 1, 1]
ui.head(st.columns(widths), ["Category", "Percentage", "Amount (₹)", "Subcategories (comma separated)", "", ""])
with st.form("add_budget", clear_on_submit=True, border=False):
    cols = st.columns(widths, vertical_alignment="bottom")
    bn = cols[0].text_input("c", placeholder="Enter Category", label_visibility="collapsed")
    bp = cols[1].number_input("p", value=0.0, min_value=0.0, max_value=100.0, label_visibility="collapsed")
    bs = cols[3].text_input("s", placeholder="e.g. Expansion, Reserve fund", label_visibility="collapsed")
    if cols[4].form_submit_button("+ Add", type="primary", width="stretch") and bn.strip():
        save_budget(budget + [{"category": bn.strip(), "pct": bp, "subcategories": bs.strip()}])
        st.rerun()
if not budget:
    st.caption("No budget categories yet.")
for i, b in enumerate(budget):
    cols = st.columns(widths, vertical_alignment="center")
    n = cols[0].text_input("c", b["category"], key=f"bc_{i}", label_visibility="collapsed")
    p = cols[1].number_input("p", value=float(num(b["pct"])), min_value=0.0, max_value=100.0, key=f"bp_{i}", label_visibility="collapsed")
    ui.cell(cols[2], inr(surplus * p / 100))
    s = cols[3].text_input("s", b.get("subcategories", ""), key=f"bs_{i}", label_visibility="collapsed")
    if cols[4].button("Update", key=f"bu_{i}", width="stretch"):
        budget[i] = {"category": n, "pct": p, "subcategories": s}
        save_budget(budget)
        st.rerun()
    if cols[5].button("Delete", key=f"bd_{i}", width="stretch"):
        budget.pop(i)
        save_budget(budget)
        st.rerun()
tp = sum(num(b["pct"]) for b in budget)
cols = st.columns(widths)
ui.cell(cols[0], "TOTAL", bold=True)
ui.cell(cols[1], pct(tp), bold=True)
ui.cell(cols[2], inr(surplus * tp / 100), bold=True)
if tp > 100:
    st.warning("Budget allocation is more than 100% of the surplus.")
if st.button("Save Budget Details"):
    save_budget(budget)
    ui.flash("Budget saved")
    st.rerun()
