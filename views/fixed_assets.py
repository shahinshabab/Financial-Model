import streamlit as st

from fm import ui
from fm.calc import yearly_depreciation
from fm.fmt import inr

repo, model, snap = ui.page_setup(["Fixed Assets"])
ui.show_flash()
section = "fixed_asset"
cats = snap["categories"][section]

left, right = st.columns([3, 1], vertical_alignment="bottom")
left.subheader("Master Fixed Assets Summary")
left.caption("GRAND FIXED ASSETS – CATEGORY WISE SUMMARY")
if right.button("✨ Generate categories", key="gen_cat", width="stretch", disabled=not ui.openai_configured(),
                help="Suggest fixed asset categories from your business description"):
    ui.generate_categories_dialog(repo, model, section, [c["name"] for c in cats])

ui.category_list(repo, model, snap, section)

st.divider()
st.subheader("Fixed Asset – Year-wise Depreciation")
st.caption("CATEGORY LEVEL · straight-line: category total ÷ depreciation years. The total feeds Profit & Loss and Cash Flow.")
widths = [4, 2.2, 2, 2.2, 1]
ui.head(st.columns(widths), ["Category", "Category total (₹)", "Depreciation (years)", "Depreciation / year", ""])
for d in snap["depreciation_rows"]:
    cols = st.columns(widths, vertical_alignment="center")
    ui.cell(cols[0], d["name"])
    ui.cell(cols[1], inr(d["total"]))
    years = cols[2].number_input("years", value=float(d["years"]), min_value=0.0, step=1.0, key=f"dep_{d['id']}", label_visibility="collapsed")
    ui.cell(cols[3], inr(yearly_depreciation(d["total"], years)))
    if cols[4].button("Update", key=f"dep_upd_{d['id']}", width="stretch"):
        repo.update_category(d["id"], depreciation_years=years)
        ui.flash("Depreciation updated")
        st.rerun()
cols = st.columns(widths)
ui.cell(cols[0], "TOTAL", bold=True)
ui.cell(cols[1], inr(snap["section_totals"][section]), bold=True)
ui.cell(cols[3], inr(sum(d["yearly"] for d in snap["depreciation_rows"])), bold=True)
