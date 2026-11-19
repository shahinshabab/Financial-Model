import streamlit as st

from fm import ui
from fm.engine import SECTION_LABELS

_repo = ui.get_repo()
_cat_id = st.session_state.get("detail_category")
_cat = _repo.get_category(_cat_id) if (_repo and _cat_id) else None
_crumb = [SECTION_LABELS[_cat["section"]], _cat["name"]] if _cat else ["Category"]

repo, model, snap = ui.page_setup(_crumb)
ui.show_flash()

cat_id = _cat_id
category = _cat
if not category or category["model_id"] != model["id"]:
    st.info("Pick a category from Fixed Assets, Pre-Operating Capital, Operating Capital or COGS.")
    st.stop()
section = category["section"]

back, title, gen = st.columns([1, 4, 1.4], vertical_alignment="center")
if back.button("← Back", width="stretch"):
    ui.go(section)
items = [i for i in snap["items"] if i["category_id"] == category["id"]]
if gen.button("✨ Generate sub-categories", width="stretch", disabled=not ui.openai_configured(),
              help="Suggest sub-categories and items for this category from your business description"):
    ui.generate_items_dialog(repo, model, section, category, [f"{i['sub_category']} - {i['item']}" for i in items])

st.subheader(category["name"].upper())
ui.item_table(repo, model, section, category, items)
if section == "fixed_asset":
    st.caption("Amount = Qty × Approx. cost")
else:
    st.caption("Amount = Months × Qty × Monthly cost (Qty defaults to 1)")
