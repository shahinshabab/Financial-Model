import streamlit as st

from fm import ui
from fm.fmt import inr

repo, model, snap = ui.page_setup(["Operating Capital"])
ui.show_flash()
section = "operating"
cats = snap["categories"][section]

left, right = st.columns([3, 1], vertical_alignment="bottom")
left.subheader("Operating Capital Requirement")
left.caption("Monthly running costs. Tick **Add to P&L** to include a category (× 12) as an indirect expense in Profit & Loss, "
             "and **Add to BE** to count it as a monthly fixed cost in Break Even. Press Update to save the ticks.")
if right.button("✨ Generate categories", key="gen_cat", width="stretch", disabled=not ui.openai_configured(),
                help="Suggest operating cost categories from your business description"):
    ui.generate_categories_dialog(repo, model, section, [c["name"] for c in cats])

ui.category_list(repo, model, snap, section, flags=True, total_label="MONTHLY TOTAL (₹)")

st.divider()
c = st.columns(3)
c[0].metric("Monthly operating cost", inr(snap["section_totals"][section]))
c[1].metric("Sent to Profit & Loss (yearly)", inr(sum(x["total"] for x in cats if x.get("add_to_pl")) * 12))
c[2].metric("Sent to Break Even (monthly)", inr(snap["fixed_monthly"]))
