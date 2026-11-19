"""Shared Streamlit UI: backend connection, sidebar, header and reusable forms."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from fm import ai, calc
from fm.calc import num
from fm.config import get_secret, openai_configured, supabase_configured
from fm.db import CachedRepo, LocalRepo, SupabaseRepo
from fm.engine import SECTION_LABELS, snapshot
from fm.fmt import inr

PAGES: dict[str, st.Page] = {}

SECTION_PAGE = {"fixed_asset": "fixed_asset", "pre_operating": "pre_operating", "operating": "operating", "cogs": "cogs"}

CSS = """
<style>
.block-container {padding-top: 4.2rem; max-width: 1250px;}
.fm-crumb {color:#2a78d6; font-size:0.9rem; margin-bottom:0.4rem;}
.fm-crumb b {color:#0b0b0b;}
.fm-head {font-size:0.78rem; font-weight:700; letter-spacing:0.04em; color:#52514e; text-transform:uppercase; padding-top:0.3rem;}
.fm-total {font-weight:700;}
.fm-cell {}
.fm-card-title {text-align:center; font-weight:700; letter-spacing:0.05em; margin:0.2rem 0 0.4rem;}
div[data-testid="stMetricValue"] {font-size:1.35rem;}
</style>
"""


# ---------------------------------------------------------------------------
# navigation
# ---------------------------------------------------------------------------
def go(page_key: str, **state) -> None:
    for k, v in state.items():
        st.session_state[k] = v
    st.switch_page(PAGES[page_key])


def open_category(section: str, category_id: str) -> None:
    go("category", detail_section=section, detail_category=category_id)


# ---------------------------------------------------------------------------
# backend
# ---------------------------------------------------------------------------
def _supabase_client():
    from supabase import create_client

    return create_client(get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY"))


def get_repo() -> CachedRepo | None:
    """Returns the data repository for this browser session (None while waiting for login)."""
    repo = st.session_state.get("_repo")
    if repo is not None:
        return repo

    if not supabase_configured():
        path = Path(get_secret("LOCAL_DB_PATH", "data/local_db.json"))
        repo = CachedRepo(LocalRepo(path))
        st.session_state["_repo"] = repo
        return repo

    user_id = get_secret("SUPABASE_USER_ID")
    if user_id:
        repo = CachedRepo(SupabaseRepo(_supabase_client(), str(user_id)))
        st.session_state["_repo"] = repo
        return repo

    # No fixed user id: sign in with Supabase Auth (email + password); RLS applies.
    _login_form()
    return None


def _login_form() -> None:
    st.title("Business Financial Model")
    st.caption("Sign in with your Supabase account.")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in", type="primary"):
            try:
                client = _supabase_client()
                res = client.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["_repo"] = CachedRepo(SupabaseRepo(client, res.user.id))
                st.rerun()
            except Exception as exc:
                st.error(f"Sign-in failed: {exc}")


# ---------------------------------------------------------------------------
# page frame
# ---------------------------------------------------------------------------
def current_model(repo) -> dict | None:
    mid = st.session_state.get("model_id")
    if mid:
        m = repo.get_model(mid)
        if m:
            return m
    models = repo.list_models()
    if models:
        st.session_state["model_id"] = models[0]["id"]
        return models[0]
    return None


def sidebar(repo, model: dict | None) -> None:
    with st.sidebar:
        st.markdown("### 📊 Financial Models")
        with st.popover("➕ Create new financial model", width="stretch"):
            with st.form("new_model", clear_on_submit=True):
                name = st.text_input("Model / project name", placeholder="e.g. Techno Lab")
                business = st.text_input("Business name", placeholder="e.g. DemoBiz")
                year = st.number_input("First financial year starts", min_value=2000, max_value=2100, value=2026, step=1)
                desc = st.text_area("Business description (used by AI Generate)", placeholder="What does the business do, where, for whom, at what scale?")
                if st.form_submit_button("Create", type="primary"):
                    if not name.strip():
                        st.error("Enter a model name.")
                    else:
                        m = repo.create_model(name=name.strip(), business_name=business.strip(), start_year=int(year), business_description=desc.strip())
                        st.session_state["model_id"] = m["id"]
                        go("home")

        models = repo.list_models()
        if models:
            ids = [m["id"] for m in models]
            names = {m["id"]: f"{m['name']}" + (f" · {m['business_name']}" if m.get("business_name") else "") for m in models}
            idx = ids.index(model["id"]) if model and model["id"] in ids else 0
            chosen = st.radio("Your models", ids, index=idx, format_func=lambda i: names[i], key=f"model_pick_{idx}_{len(ids)}")
            if model is None or chosen != model["id"]:
                st.session_state["model_id"] = chosen
                go("home")
        else:
            st.info("No models yet. Create your first one above.")
        if not models and st.button("Load sample model (Techno Lab)", width="stretch", help="Adds the example from the design so you can explore every page"):
            from fm.demo import create_demo

            m = create_demo(repo)
            st.session_state["model_id"] = m["id"]
            go("home")

        if model:
            st.divider()
            st.markdown("**This model**")
            for key, label, icon in [
                ("home", "Financial Model", "🏠"),
                ("grand_total", "Capital Structure Report", "🧾"),
                ("fixed_asset", "Fixed Assets", "🏗️"),
                ("pre_operating", "Pre-Operating Capital", "🚀"),
                ("operating", "Operating Capital (OPEX)", "⚙️"),
                ("sales", "Sales Forecast", "📈"),
                ("cogs", "COGS", "📦"),
                ("pl", "Profit & Loss", "💹"),
                ("cf", "Cash Flow", "💵"),
                ("wc", "Working Capital", "🔄"),
                ("be", "Break Even", "⚖️"),
                ("kpi", "KPI Dashboard", "🎯"),
            ]:
                st.page_link(PAGES[key], label=label, icon=icon)

            with st.expander("Model settings"):
                with st.form("edit_model"):
                    name = st.text_input("Model name", model["name"])
                    business = st.text_input("Business name", model.get("business_name", ""))
                    year = st.number_input("First financial year starts", 2000, 2100, int(model.get("start_year") or 2026))
                    desc = st.text_area("Business description", model.get("business_description", ""), height=140)
                    if st.form_submit_button("Save"):
                        repo.update_model(model["id"], name=name, business_name=business, start_year=int(year), business_description=desc)
                        st.rerun()
                with st.popover("🗑️ Delete this model"):
                    st.warning("This deletes the model and all its data.")
                    if st.button("Yes, delete", type="primary", key="del_model"):
                        repo.delete_model(model["id"])
                        st.session_state.pop("model_id", None)
                        go("home")

        st.divider()
        backend = "Supabase" if repo.backend == "supabase" else "Local demo file (Supabase not configured)"
        st.caption(f"Storage: {backend}")
        st.caption(f"AI Generate: {'on' if openai_configured() else 'off (set OPENAI_API_KEY)'}")
        if st.button("↻ Refresh data", width="stretch"):
            repo.clear()
            st.rerun()


def page_setup(title_parts: list[str] | None = None, require_model: bool = True):
    """Common start of every page. Returns (repo, model, snapshot) or stops the script."""
    st.markdown(CSS, unsafe_allow_html=True)
    repo = get_repo()
    if repo is None:
        st.stop()
    model = current_model(repo)
    sidebar(repo, model)
    if require_model and model is None:
        st.title("Business Financial Model")
        st.info("Create your first financial model from the sidebar to get started.")
        st.stop()
    snap = snapshot(repo, model) if model else None
    if model:
        crumb = ["Business Financial Model"]
        if model.get("business_name"):
            crumb.append(model["business_name"])
        crumb.append(model["name"])
        crumb += title_parts or []
        html = " / ".join(crumb[:-1]) + f" / <b>{crumb[-1]}</b>"
        st.markdown(f"<div class='fm-crumb'>{html}</div>", unsafe_allow_html=True)
    return repo, model, snap


def head(cols, labels: list[str]) -> None:
    for c, label in zip(cols, labels):
        c.markdown(f"<div class='fm-head'>{label}</div>", unsafe_allow_html=True)


def cell(col, text: str, bold: bool = False) -> None:
    col.markdown(f"<div class='{'fm-total' if bold else 'fm-cell'}'>{text}</div>", unsafe_allow_html=True)


def flash(msg: str) -> None:
    st.session_state["_flash"] = msg


def show_flash() -> None:
    msg = st.session_state.pop("_flash", None)
    if msg:
        st.toast(msg, icon="✅")


# ---------------------------------------------------------------------------
# Category list (Fixed Assets / Pre-Operating / Operating / COGS main pages)
# ---------------------------------------------------------------------------
def category_list(repo, model: dict, snap: dict, section: str, *, flags: bool = False, total_label: str = "CATEGORY TOTAL (₹)") -> None:
    cats = snap["categories"][section]
    widths = [3.4, 0.9, 0.9, 1, 1.9, 1, 1.2] if flags else [5, 1.1, 2.4, 1, 1]
    cols = st.columns(widths, vertical_alignment="center")
    labels = ["Category", "Add to P&L", "Add to BE", "", total_label, "", ""] if flags else ["Category", "", total_label, "", ""]
    head(cols, labels)

    with st.form(f"add_cat_{section}", clear_on_submit=True, border=False):
        cols = st.columns(widths, vertical_alignment="bottom")
        new_name = cols[0].text_input("Category", placeholder="Enter Category Name", label_visibility="collapsed")
        new_pl = cols[1].checkbox("P&L", value=True, key=f"new_pl_{section}", label_visibility="collapsed") if flags else False
        new_be = cols[2].checkbox("BE", value=section == "operating", key=f"new_be_{section}", label_visibility="collapsed") if flags else False
        if cols[-2].form_submit_button("Save", type="primary", width="stretch"):
            if new_name.strip():
                repo.add_category(model["id"], section, new_name.strip(), add_to_pl=bool(new_pl), add_to_be=bool(new_be), sort_order=len(cats))
                flash(f"Added {new_name.strip()}")
                st.rerun()
            else:
                st.warning("Enter a category name.")

    for c in cats:
        cols = st.columns(widths, vertical_alignment="center")
        name = cols[0].text_input("Name", c["name"], key=f"cat_name_{c['id']}", label_visibility="collapsed")
        if flags:
            pl = cols[1].checkbox("P&L", bool(c.get("add_to_pl")), key=f"cat_pl_{c['id']}", label_visibility="collapsed")
            be = cols[2].checkbox("BE", bool(c.get("add_to_be")), key=f"cat_be_{c['id']}", label_visibility="collapsed")
            view_col, total_col = cols[3], cols[4]
        else:
            pl = be = None
            view_col, total_col = cols[1], cols[2]
        if view_col.button("View", key=f"cat_view_{c['id']}", width="stretch"):
            open_category(section, c["id"])
        cell(total_col, inr(c["total"]))
        if cols[-2].button("Update", key=f"cat_upd_{c['id']}", width="stretch"):
            fields = {"name": name.strip() or c["name"]}
            if flags:
                fields |= {"add_to_pl": bool(pl), "add_to_be": bool(be)}
            repo.update_category(c["id"], **fields)
            flash("Category updated")
            st.rerun()
        with cols[-1].popover("Delete", width="stretch"):
            st.write(f"Delete **{c['name']}** and all its sub-categories?")
            if st.button("Confirm delete", key=f"cat_del_{c['id']}", type="primary"):
                repo.delete_category(c["id"])
                flash("Category deleted")
                st.rerun()

    cols = st.columns(widths)
    cell(cols[-4] if flags else cols[1], "TOTAL AMOUNT", bold=True)
    cell(cols[-3], inr(snap["section_totals"][section]), bold=True)


# ---------------------------------------------------------------------------
# Sub-category items (category "View" page)
# ---------------------------------------------------------------------------
def item_table(repo, model: dict, section: str, category: dict, items: list[dict]) -> float:
    fixed = section == "fixed_asset"
    measure_label = "MEASURE / UNIT" if fixed else "MEASURE / UNIT (MONTHS)"
    cost_label = "APPROX. COST (₹)" if fixed else "MONTHLY COST (₹)"
    item_label = "ASSET / ITEM" if fixed else "ASSET / ITEM / ROLE"
    widths = [1.6, 1.8, 1.3, 0.8, 1.3, 1.4, 1.4, 0.95, 0.95]
    head(st.columns(widths), ["Sub-category", item_label, measure_label, "Qty", cost_label, "Amount (₹)", "Remarks", "", ""])

    total = 0.0
    for it in items:
        k = it["id"]
        cols = st.columns(widths, vertical_alignment="center")
        sub = cols[0].text_input("sub", it["sub_category"], key=f"it_sub_{k}", label_visibility="collapsed")
        name = cols[1].text_input("item", it["item"], key=f"it_item_{k}", label_visibility="collapsed")
        measure = cols[2].text_input("measure", str(it.get("measure_unit") or ""), key=f"it_meas_{k}", label_visibility="collapsed")
        qty = cols[3].number_input("qty", value=float(num(it.get("qty"), 1)), min_value=0.0, key=f"it_qty_{k}", label_visibility="collapsed")
        cost = cols[4].number_input("cost", value=float(num(it.get("unit_cost"))), min_value=0.0, step=100.0, key=f"it_cost_{k}", label_visibility="collapsed")
        amount = calc.item_amount(section, measure, qty, cost)
        total += num(it.get("amount"))
        cell(cols[5], inr(amount))
        remarks = cols[6].text_input("remarks", it.get("remarks") or "", key=f"it_rem_{k}", label_visibility="collapsed")
        if cols[7].button("Update", key=f"it_upd_{k}", width="stretch"):
            repo.update_item(k, sub_category=sub, item=name, measure_unit=measure, qty=qty, unit_cost=cost, amount=amount, remarks=remarks)
            flash("Item updated")
            st.rerun()
        if cols[8].button("Delete", key=f"it_del_{k}", width="stretch"):
            repo.delete_item(k)
            flash("Item deleted")
            st.rerun()

    with st.form(f"add_item_{category['id']}", clear_on_submit=True, border=False):
        cols = st.columns(widths, vertical_alignment="bottom")
        sub = cols[0].text_input("sub", placeholder="Enter Sub-Category", label_visibility="collapsed")
        name = cols[1].text_input("item", placeholder=f"Enter {item_label.title()}", label_visibility="collapsed")
        measure = cols[2].text_input("measure", placeholder="Enter Measure / Unit" if fixed else "Months, e.g. 1", label_visibility="collapsed")
        qty = cols[3].number_input("qty", value=1.0, min_value=0.0, label_visibility="collapsed")
        cost = cols[4].number_input("cost", value=0.0, min_value=0.0, step=100.0, label_visibility="collapsed")
        cell(cols[5], "<span style='color:#888'>auto</span>")
        remarks = cols[6].text_input("remarks", placeholder="Enter Remarks", label_visibility="collapsed")
        if cols[7].form_submit_button("Save", type="primary", width="stretch"):
            if not (sub.strip() or name.strip()):
                st.warning("Enter a sub-category or item.")
            else:
                repo.add_item(model["id"], category["id"], sub_category=sub.strip(), item=name.strip(), measure_unit=measure.strip() or ("" if fixed else "1"),
                              qty=qty, unit_cost=cost, amount=calc.item_amount(section, measure, qty, cost), remarks=remarks.strip())
                flash("Item added")
                st.rerun()

    cols = st.columns(widths)
    cell(cols[4], "CATEGORY TOTAL", bold=True)
    cell(cols[5], inr(total), bold=True)
    return total


# ---------------------------------------------------------------------------
# AI Generate popup
# ---------------------------------------------------------------------------
def _description_box(repo, model: dict, key: str) -> str:
    saved = model.get("business_description") or ""
    if saved:
        st.caption("Using the business description saved for this model. Edit it here if needed; changes are saved.")
    else:
        st.caption("Describe the business once. It is saved to this model and reused by every Generate button.")
    return st.text_area("Business description", saved, height=150, key=key, placeholder="e.g. A 3D printing and electronics prototyping lab in Kochi serving students and startups...")


def _save_description(repo, model: dict, desc: str) -> None:
    if desc.strip() and desc.strip() != (model.get("business_description") or "").strip():
        repo.update_model(model["id"], business_description=desc.strip())
        model["business_description"] = desc.strip()


@st.dialog("✨ Generate categories with AI", width="large")
def generate_categories_dialog(repo, model: dict, section: str, existing: list[str]) -> None:
    st.markdown(f"**{SECTION_LABELS[section]}**: suggestions are based on your business description.")
    desc = _description_box(repo, model, f"gen_desc_cat_{section}")
    state_key = f"gen_cat_{section}"
    if st.button("Generate", type="primary", disabled=not desc.strip()):
        _save_description(repo, model, desc)
        with st.spinner("Asking OpenAI..."):
            try:
                result = ai.generate_categories(section, desc, model.get("business_name", ""), model["name"], existing)
                st.session_state[state_key] = [c.model_dump() for c in result.categories]
            except ai.AIError as exc:
                st.error(str(exc))
    rows = st.session_state.get(state_key)
    if rows:
        df = pd.DataFrame(rows)
        df.insert(0, "add", True)
        cfg = {"add": st.column_config.CheckboxColumn("Add", width="small"), "name": "Category", "reason": "Why"}
        if section == "fixed_asset":
            cfg["depreciation_years"] = st.column_config.NumberColumn("Depreciation (yrs)", min_value=0)
        if section in ("pre_operating", "operating"):
            cfg["add_to_pl"] = st.column_config.CheckboxColumn("Add to P&L")
            cfg["add_to_be"] = st.column_config.CheckboxColumn("Add to BE")
        if section == "operating":
            cfg["yearly_growth_pct"] = st.column_config.NumberColumn("P&L growth %", min_value=0)
        if section == "cogs":
            cfg["percent_of_revenue"] = st.column_config.NumberColumn("% of price", min_value=0, max_value=100)
        edited = st.data_editor(df, column_config=cfg, hide_index=True, width="stretch", key=f"{state_key}_editor")
        if st.button("Add selected categories", type="primary"):
            n = 0
            for r in edited.to_dict("records"):
                if not r.get("add") or not str(r.get("name", "")).strip():
                    continue
                fields = {}
                if section == "fixed_asset":
                    fields["depreciation_years"] = num(r.get("depreciation_years"))
                if section in ("pre_operating", "operating"):
                    fields |= {"add_to_pl": bool(r.get("add_to_pl")), "add_to_be": bool(r.get("add_to_be"))}
                if section == "operating":
                    fields["pl_growth_pct"] = num(r.get("yearly_growth_pct"))
                if section == "cogs":
                    fields["cogs_percent"] = num(r.get("percent_of_revenue"))
                repo.add_category(model["id"], section, str(r["name"]).strip(), sort_order=len(existing) + n, **fields)
                n += 1
            st.session_state.pop(state_key, None)
            flash(f"Added {n} categories")
            st.rerun()


@st.dialog("✨ Generate sub-categories with AI", width="large")
def generate_items_dialog(repo, model: dict, section: str, category: dict, existing: list[str]) -> None:
    st.markdown(f"**{SECTION_LABELS[section]} / {category['name']}**: suggestions are based on your business description.")
    desc = _description_box(repo, model, f"gen_desc_item_{category['id']}")
    state_key = f"gen_items_{category['id']}"
    if st.button("Generate", type="primary", disabled=not desc.strip()):
        _save_description(repo, model, desc)
        with st.spinner("Asking OpenAI..."):
            try:
                result = ai.generate_items(section, desc, model.get("business_name", ""), model["name"], category["name"], existing)
                st.session_state[state_key] = [i.model_dump() for i in result.items]
            except ai.AIError as exc:
                st.error(str(exc))
    rows = st.session_state.get(state_key)
    if rows:
        df = pd.DataFrame(rows)
        df.insert(0, "add", True)
        cfg = {"add": st.column_config.CheckboxColumn("Add", width="small"), "sub_category": "Sub-category", "item": "Item / role", "remarks": "Remarks", "qty": st.column_config.NumberColumn("Qty", min_value=0)}
        if section == "fixed_asset":
            cfg |= {"measure_unit": "Unit", "unit_cost": st.column_config.NumberColumn("Approx. cost ₹", min_value=0)}
        else:
            cfg |= {"months": st.column_config.NumberColumn("Months", min_value=0), "monthly_cost": st.column_config.NumberColumn("Monthly cost ₹", min_value=0)}
        edited = st.data_editor(df, column_config=cfg, hide_index=True, width="stretch", key=f"{state_key}_editor")
        if st.button("Add selected items", type="primary"):
            n = 0
            for r in edited.to_dict("records"):
                if not r.get("add"):
                    continue
                if section == "fixed_asset":
                    measure, cost = str(r.get("measure_unit") or ""), num(r.get("unit_cost"))
                else:
                    measure, cost = f"{num(r.get('months'), 1):g}", num(r.get("monthly_cost"))
                qty = num(r.get("qty"), 1)
                repo.add_item(model["id"], category["id"], sub_category=str(r.get("sub_category") or ""), item=str(r.get("item") or ""),
                              measure_unit=measure, qty=qty, unit_cost=cost, amount=calc.item_amount(section, measure, qty, cost), remarks=str(r.get("remarks") or ""))
                n += 1
            st.session_state.pop(state_key, None)
            flash(f"Added {n} items")
            st.rerun()


def generate_button(label: str = "✨ Generate", key: str = "gen") -> bool:
    return st.button(label, key=key, help="Use OpenAI and your saved business description to suggest entries", disabled=not openai_configured())
