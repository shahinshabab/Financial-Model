import streamlit as st

from fm import ui

repo, model, snap = ui.page_setup(["Pre-Operating Capital"])
ui.show_flash()
section = "pre_operating"
cats = snap["categories"][section]

left, right = st.columns([3, 1], vertical_alignment="bottom")
left.subheader("Pre-Operating Capital Requirement")
left.caption("Tick **Add to P&L** to expense a category in the first year's Profit & Loss, and **Add to BE** to spread it "
             "over 12 months in the Break Even overheads. Press Update to save the ticks.")
if right.button("✨ Generate categories", key="gen_cat", width="stretch", disabled=not ui.openai_configured(),
                help="Suggest pre-operating categories from your business description"):
    ui.generate_categories_dialog(repo, model, section, [c["name"] for c in cats])

ui.category_list(repo, model, snap, section, flags=True)
