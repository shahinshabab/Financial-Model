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
                year = st.number_input("First financial year starts", min_value=2000, max_value=2100, value=2026, step=1)
                desc = st.text_area("Business description (used by AI Generate)", placeholder="What does the business do, where, for whom, at what scale?")
                if st.form_submit_button("Create", type="primary"):
                    if not name.strip():
                        st.error("Enter a model name.")
                    else:
                        m = repo.create_model(name=name.strip(), start_year=int(year), business_description=desc.strip())
                        st.session_state["model_id"] = m["id"]
                        go("home")

        models = repo.list_models()
        if models:
            ids = [m["id"] for m in models]
            names = {m["id"]: m["name"] for m in models}
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
                    year = st.number_input("First financial year starts", 2000, 2100, int(model.get("start_year") or 2026))
                    desc = st.text_area("Business description", model.get("business_description", ""), height=140)
                    if st.form_submit_button("Save"):
                        repo.update_model(model["id"], name=name, start_year=int(year), business_description=desc)
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


def _explain_supabase_error(exc: Exception) -> None:
    """Shows a plain-language reason for the most common Supabase setup problems."""
    code = str(getattr(exc, "code", "") or "")
    message = str(getattr(exc, "message", "") or exc)
    details = str(getattr(exc, "details", "") or "")
    text = f"{code} {message} {details}".lower()
    if code in ("PGRST205", "42P01") or "could not find the table" in text or "does not exist" in text:
        st.markdown(
            "**The database tables don't exist yet.** Run the migration: either re-run the "
            "*Deploy Supabase migrations* GitHub Action (after adding its three secrets), or paste "
            "`supabase/migrations/20261119000000_initial_schema.sql` into the Supabase SQL Editor and run it."
        )
    elif code == "22P02" or "invalid input syntax for type uuid" in text:
        st.markdown("**`SUPABASE_USER_ID` is not a valid UUID.** Copy your user's UID from Supabase → Authentication → Users.")
    elif code == "23503" or "foreign key" in text:
        st.markdown(
            "**`SUPABASE_USER_ID` doesn't match any user in this Supabase project.** Open Supabase → "
            "Authentication → Users, create a user if there is none (Add user → Create new user), copy its "
            "**UID** and put it in `SUPABASE_USER_ID` in your Streamlit secrets."
        )
    elif code == "42501" or "permission denied" in text or "row-level security" in text:
        st.markdown(
            "**Row level security blocked the save.** With `SUPABASE_USER_ID` set, `SUPABASE_KEY` must be the "
            "`service_role` key (Project Settings → API Keys), not the `anon` / publishable key. Or remove "
            "`SUPABASE_USER_ID` and keep the `anon` key to use the sign-in page."
        )
    elif "jwt" in text or "api key" in text or "apikey" in text or code in ("401", "PGRST301"):
        st.markdown("**`SUPABASE_KEY` was rejected.** Use the `service_role` key (or `anon` key) from Project Settings → API.")
    else:
        st.markdown("Check `SUPABASE_URL`, `SUPABASE_KEY` and `SUPABASE_USER_ID` in your Streamlit secrets.")
    st.caption(f"Details: {code} {message} {details}"[:500])


def _connection_help(exc: Exception) -> None:
    """Explains why the data couldn't be loaded instead of showing a raw traceback."""
    st.session_state.pop("_repo", None)
    st.title("Business Financial Model")
    st.error("Couldn't load your data from Supabase.")
    _explain_supabase_error(exc)
    if st.button("Try again", type="primary"):
        st.rerun()


def database_error(exc: Exception) -> None:
    """Shown when a save or load fails while using a page."""
    st.error("Supabase refused this request.")
    _explain_supabase_error(exc)


def page_setup(title_parts: list[str] | None = None, require_model: bool = True):
    """Common start of every page. Returns (repo, model, snapshot) or stops the script."""
    st.markdown(CSS, unsafe_allow_html=True)
    repo = get_repo()
    if repo is None:
        st.stop()
    try:
        model = current_model(repo)
    except Exception as exc:  # Supabase not reachable / not set up yet
        _connection_help(exc)
        st.stop()
    sidebar(repo, model)
    if require_model and model is None:
        st.title("Business Financial Model")
        st.info("Create your first financial model from the sidebar to get started.")
        st.stop()
    snap = snapshot(repo, model) if model else None
    if model:
        crumb = ["Business Financial Model", model["name"]]
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
# Editable rows helpers: "+ Add row" creates an unsaved row, "Remove" deletes a row,
# "Save all" writes every changed or new row in one go.
# ---------------------------------------------------------------------------
def _pending(key: str) -> list[str]:
    return st.session_state.setdefault(key, [])


def _new_row(key: str) -> None:
    import uuid

    _pending(key).append(uuid.uuid4().hex[:8])


# ---------------------------------------------------------------------------
# Category list (Fixed Assets / Pre-Operating / Operating / COGS main pages)
# ---------------------------------------------------------------------------
def category_list(repo, model: dict, snap: dict, section: str, *, flags: bool = False, total_label: str = "CATEGORY TOTAL (₹)") -> None:
    cats = snap["categories"][section]
    pkey = f"pending_cats_{section}_{model['id']}"
    pending = _pending(pkey)
    widths = [3.4, 0.9, 0.9, 1, 1.9, 1.3] if flags else [5, 1.1, 2.4, 1.3]
    labels = ["Category", "Add to P&L", "Add to BE", "", total_label, ""] if flags else ["Category", "", total_label, ""]
    head(st.columns(widths, vertical_alignment="center"), labels)

    def row(row_key: str, name: str, pl: bool, be: bool, saved: dict | None):
        cols = st.columns(widths, vertical_alignment="center")
        n = cols[0].text_input("Name", name, key=f"cat_name_{row_key}", placeholder="Enter Category Name", label_visibility="collapsed")
        p = b = False
        if flags:
            p = cols[1].checkbox("P&L", pl, key=f"cat_pl_{row_key}", label_visibility="collapsed")
            b = cols[2].checkbox("BE", be, key=f"cat_be_{row_key}", label_visibility="collapsed")
        view_col, total_col = (cols[3], cols[4]) if flags else (cols[1], cols[2])
        if saved:
            if view_col.button("View", key=f"cat_view_{row_key}", width="stretch"):
                open_category(section, saved["id"])
            cell(total_col, inr(saved["total"]))
            with cols[-1].popover("✕ Remove", width="stretch"):
                st.write(f"Remove **{saved['name']}** and all its sub-categories?")
                if st.button("Confirm remove", key=f"cat_del_{row_key}", type="primary"):
                    repo.delete_category(saved["id"])
                    flash("Row removed")
                    st.rerun()
        else:
            cell(total_col, "<span style='color:#888'>new row</span>")
            if cols[-1].button("✕ Remove", key=f"cat_rm_{row_key}", width="stretch"):
                pending.remove(row_key)
                st.rerun()
        return n.strip(), bool(p), bool(b)

    edits = []
    for c in cats:
        edits.append((c, *row(c["id"], c["name"], bool(c.get("add_to_pl")), bool(c.get("add_to_be")), c)))
    new_rows = []
    for rk in list(pending):
        new_rows.append((rk, *row(rk, "", True, section == "operating", None)))

    cols = st.columns(widths)
    cell(cols[3] if flags else cols[1], "TOTAL AMOUNT", bold=True)
    cell(cols[4] if flags else cols[2], inr(snap["section_totals"][section]), bold=True)

    a, s, _ = st.columns([1.2, 1.2, 5])
    if a.button("➕ Add row", key=f"add_row_{section}", width="stretch"):
        _new_row(pkey)
        st.rerun()
    if s.button("💾 Save", key=f"save_rows_{section}", type="primary", width="stretch"):
        changed = 0
        for c, n, p, b in edits:
            fields = {}
            if n and n != c["name"]:
                fields["name"] = n
            if flags and (p != bool(c.get("add_to_pl")) or b != bool(c.get("add_to_be"))):
                fields |= {"add_to_pl": p, "add_to_be": b}
            if fields:
                repo.update_category(c["id"], **fields)
                changed += 1
        for rk, n, p, b in new_rows:
            if n:
                repo.add_category(model["id"], section, n, add_to_pl=p, add_to_be=b, sort_order=len(cats) + changed)
                changed += 1
            pending.remove(rk)
        flash(f"Saved {changed} row(s)")
        st.rerun()


# ---------------------------------------------------------------------------
# Sub-category items (category "View" page)
# ---------------------------------------------------------------------------
def item_table(repo, model: dict, section: str, category: dict, items: list[dict]) -> float:
    fixed = section == "fixed_asset"
    measure_label = "MEASURE / UNIT" if fixed else "MEASURE / UNIT (MONTHS)"
    cost_label = "APPROX. COST (₹)" if fixed else "MONTHLY COST (₹)"
    item_label = "ASSET / ITEM" if fixed else "ASSET / ITEM / ROLE"
    pkey = f"pending_items_{category['id']}"
    pending = _pending(pkey)
    widths = [1.6, 1.8, 1.3, 0.8, 1.3, 1.4, 1.4, 1.2]
    head(st.columns(widths), ["Sub-category", item_label, measure_label, "Qty", cost_label, "Amount (₹)", "Remarks", ""])

    def row(k: str, it: dict, saved: bool):
        cols = st.columns(widths, vertical_alignment="center")
        sub = cols[0].text_input("sub", it.get("sub_category", ""), key=f"it_sub_{k}", placeholder="Enter Sub-Category", label_visibility="collapsed")
        name = cols[1].text_input("item", it.get("item", ""), key=f"it_item_{k}", placeholder=f"Enter {item_label.title()}", label_visibility="collapsed")
        measure = cols[2].text_input("measure", str(it.get("measure_unit") or ""), key=f"it_meas_{k}",
                                     placeholder="Enter Measure / Unit" if fixed else "Months, e.g. 1", label_visibility="collapsed")
        qty = cols[3].number_input("qty", value=float(num(it.get("qty"), 1)), min_value=0.0, key=f"it_qty_{k}", label_visibility="collapsed")
        cost = cols[4].number_input("cost", value=float(num(it.get("unit_cost"))), min_value=0.0, step=100.0, key=f"it_cost_{k}", label_visibility="collapsed")
        amount = calc.item_amount(section, measure, qty, cost)
        cell(cols[5], inr(amount))
        remarks = cols[6].text_input("remarks", it.get("remarks") or "", key=f"it_rem_{k}", placeholder="Enter Remarks", label_visibility="collapsed")
        if cols[7].button("✕ Remove", key=f"it_del_{k}", width="stretch"):
            if saved:
                repo.delete_item(k)
                flash("Row removed")
            else:
                pending.remove(k)
            st.rerun()
        return {"sub_category": sub.strip(), "item": name.strip(), "measure_unit": measure.strip() or ("" if fixed else "1"),
                "qty": qty, "unit_cost": cost, "amount": amount, "remarks": remarks.strip()}

    edits = [(it, row(it["id"], it, True)) for it in items]
    new_rows = [(k, row(k, {"qty": 1}, False)) for k in list(pending)]
    total = sum(v["amount"] for _, v in edits)

    cols = st.columns(widths)
    cell(cols[4], "CATEGORY TOTAL", bold=True)
    cell(cols[5], inr(total), bold=True)

    a, s, _ = st.columns([1.2, 1.2, 5])
    if a.button("➕ Add row", key=f"add_item_row_{category['id']}", width="stretch"):
        _new_row(pkey)
        st.rerun()
    if s.button("💾 Save", key=f"save_items_{category['id']}", type="primary", width="stretch"):
        n = 0
        for it, v in edits:
            if any(str(v[f]) != str(it.get(f) if f not in ("qty", "unit_cost", "amount") else num(it.get(f))) for f in v):
                repo.update_item(it["id"], **v)
                n += 1
        for k, v in new_rows:
            if v["sub_category"] or v["item"]:
                repo.add_item(model["id"], category["id"], **v)
                n += 1
            pending.remove(k)
        flash(f"Saved {n} row(s)")
        st.rerun()
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
