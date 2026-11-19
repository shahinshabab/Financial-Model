import streamlit as st

from fm import ui
from fm.fmt import inr, pct

repo, model, snap = ui.page_setup(["COGS"])
ui.show_flash()
section = "cogs"
cats = snap["categories"][section]

left, right = st.columns([3, 1], vertical_alignment="bottom")
left.subheader("COGS Requirement")
left.caption("Direct costs that vary with every sale. Use **View** to list the monthly items of a category.")
if right.button("✨ Generate categories", key="gen_cat", width="stretch", disabled=not ui.openai_configured()):
    ui.generate_categories_dialog(repo, model, section, [c["name"] for c in cats])
ui.category_list(repo, model, snap, section, total_label="CATEGORY MONTHLY TOTAL (₹)")

st.divider()
st.subheader("COGS")
st.caption("Set each category's % of the sales price. The total % becomes the Direct Expenses % in Profit & Loss and "
           "the Contribution % (GP) used by Break Even.")
cogs = snap["cogs"]
price = snap["cogs_pricing"]
widths = [3, 1.6, 1.6, 1.6, 1.6, 1.1]
ui.head(st.columns(widths), ["Particulars", "% of revenue", "Basic", "Economic", "Premium", ""])

cols = st.columns(widths, vertical_alignment="center")
ui.cell(cols[0], "Sales Price", bold=True)
b = cols[2].number_input("basic", value=float(price["basic"]), min_value=0.0, step=100.0, key="price_basic", label_visibility="collapsed")
e = cols[3].number_input("economic", value=float(price["economic"]), min_value=0.0, step=100.0, key="price_eco", label_visibility="collapsed")
p = cols[4].number_input("premium", value=float(price["premium"]), min_value=0.0, step=100.0, key="price_pre", label_visibility="collapsed")
if cols[5].button("Save", type="primary", width="stretch", key="save_price"):
    repo.save_setting(model["id"], "cogs_pricing", {"basic": b, "economic": e, "premium": p})
    ui.flash("Prices saved")
    st.rerun()

ui.cell(st.columns(widths)[0], "Less: Direct Expenses", bold=True)
for r in cogs["rows"]:
    cols = st.columns(widths, vertical_alignment="center")
    ui.cell(cols[0], r["name"])
    v = cols[1].number_input("pct", value=float(r["pct"]), min_value=0.0, max_value=100.0, step=1.0, key=f"cogs_pct_{r['id']}", label_visibility="collapsed")
    for col, tier in zip(cols[2:5], ("basic", "economic", "premium")):
        ui.cell(col, f"{cogs['price'][tier] * v / 100:,.2f}")
    if cols[5].button("Update", key=f"cogs_upd_{r['id']}", width="stretch"):
        repo.update_category(r["id"], cogs_percent=v)
        ui.flash("Updated")
        st.rerun()

cols = st.columns(widths)
ui.cell(cols[1], pct(cogs["total_pct"]), bold=True)
cols = st.columns(widths)
ui.cell(cols[0], "Contribution 1", bold=True)
for col, tier in zip(cols[2:5], ("basic", "economic", "premium")):
    ui.cell(col, f"{cogs['contribution'][tier]:,.2f}", bold=True)
cols = st.columns(widths)
ui.cell(cols[0], "Contribution %. GP", bold=True)
for col, tier in zip(cols[2:5], ("basic", "economic", "premium")):
    ui.cell(col, pct(cogs["gp_pct"][tier]), bold=True)
