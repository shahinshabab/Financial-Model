"""Builds every number the pages need for one financial model from the stored data."""

from __future__ import annotations

from fm import calc
from fm.calc import num

SECTION_LABELS = {
    "fixed_asset": "Fixed Assets",
    "pre_operating": "Pre-Operating Capital",
    "operating": "Operating Capital",
    "cogs": "COGS",
}

PL_DEFAULTS = {
    "channels": [],
    "customer_growth_pct": 10.0,
    "inflation_pct": 10.0,
    "other_income": [],
    "coco_pct": 0.0,
    "direct_expense_pct": 0.0,  # used only when no COGS categories exist
    "tax_rate_pct": 25.0,
    "valuation_multiple": 8.0,
    "years": 8,
}
BE_DEFAULTS = {"sales_target": 0.0, "variable_costs": []}
CF_DEFAULTS = {"receivables": [], "budget": [], "budget_year": 0}
COGS_PRICING_DEFAULTS = {"basic": 0.0, "economic": 0.0, "premium": 0.0, "tier": "basic"}
WC_DEFAULTS = {"months_cover": 3, "receivable_days": 0, "inventory_days": 0, "payable_days": 0}


def snapshot(repo, model: dict) -> dict:
    mid = model["id"]
    cats = repo.list_categories(mid)
    items = repo.list_items(mid)
    totals = calc.category_totals(items)

    by_section: dict[str, list[dict]] = {s: [] for s in SECTION_LABELS}
    for c in cats:
        c["total"] = totals.get(c["id"], 0.0)
        by_section.setdefault(c["section"], []).append(c)
    section_totals = {s: sum(c["total"] for c in cs) for s, cs in by_section.items()}
    capital_sections = ("fixed_asset", "pre_operating", "operating")
    grand_total = sum(section_totals[s] for s in capital_sections)

    # ---- settings
    pl_set = PL_DEFAULTS | repo.get_setting(mid, "profit_loss")
    sales_set = repo.get_setting(mid, "sales_forecast")
    if not sales_set.get("start_date"):
        sales_set["start_date"] = f"{int(model.get('start_year') or 2026)}-04-01"
    be_set = BE_DEFAULTS | repo.get_setting(mid, "break_even")
    cf_set = CF_DEFAULTS | repo.get_setting(mid, "cash_flow")
    cogs_pricing = COGS_PRICING_DEFAULTS | repo.get_setting(mid, "cogs_pricing")
    wc_set = WC_DEFAULTS | repo.get_setting(mid, "working_capital")

    # ---- sales forecast -> first year customers
    sales = calc.sales_forecast(sales_set)
    first_year_customers = sales["first_year_customers"]

    # ---- COGS -> direct expense % and GP %
    cogs = calc.cogs_table(cogs_pricing, by_section["cogs"])
    direct_pct = cogs["total_pct"] if by_section["cogs"] else num(pl_set.get("direct_expense_pct"))
    gp_pct = 100 - direct_pct

    # ---- depreciation
    n_years = int(num(pl_set.get("years"), 8)) or 8
    dep_rows = [
        {"id": c["id"], "name": c["name"], "total": c["total"], "years": num(c.get("depreciation_years")),
         "yearly": calc.yearly_depreciation(c["total"], c.get("depreciation_years"))}
        for c in by_section["fixed_asset"]
    ]
    dep_schedule = calc.depreciation_schedule([(d["total"], d["years"]) for d in dep_rows], n_years)

    # ---- indirect expenses for P&L (ticked "Add to P&L")
    indirect = []
    for c in by_section["operating"]:
        if c.get("add_to_pl"):
            indirect.append({"id": c["id"], "name": c["name"], "annual": c["total"] * 12, "growth_pct": num(c.get("pl_growth_pct")), "one_time": False})
    for c in by_section["pre_operating"]:
        if c.get("add_to_pl"):
            indirect.append({"id": c["id"], "name": f"{c['name']} (pre-operating)", "annual": c["total"], "growth_pct": 0, "one_time": True})

    start_year = int(str(sales["start_date"])[:4])
    labels = calc.fiscal_labels(start_year, n_years)
    pl = calc.profit_and_loss(
        n_years=n_years,
        first_year_customers=first_year_customers,
        channels=pl_set.get("channels") or [],
        customer_growth_pct=pl_set["customer_growth_pct"],
        inflation_pct=pl_set["inflation_pct"],
        other_income=pl_set.get("other_income") or [],
        direct_expense_pct=direct_pct,
        coco_pct=pl_set["coco_pct"],
        indirect=indirect,
        depreciation=dep_schedule,
        tax_rate_pct=pl_set["tax_rate_pct"],
        valuation_multiple=pl_set["valuation_multiple"],
        total_capital=grand_total,
    )

    # ---- break even (ticked "Add to BE")
    fixed_monthly = sum(c["total"] for c in by_section["operating"] if c.get("add_to_be"))
    preop_monthly = sum(c["total"] for c in by_section["pre_operating"] if c.get("add_to_be")) / 12
    variable_total = sum(num(v.get("value")) for v in be_set.get("variable_costs") or [])
    overheads = fixed_monthly + preop_monthly + variable_total
    be = calc.break_even(overheads, gp_pct, be_set.get("sales_target"))

    # ---- cash flow
    cf = calc.cash_flow(pl["pat"], pl["depreciation"], cf_set.get("receivables") or [])

    return {
        "model": model,
        "categories": by_section,
        "items": items,
        "section_totals": section_totals,
        "grand_total": grand_total,
        "sales": sales,
        "sales_settings": sales_set,
        "first_year_customers": first_year_customers,
        "cogs": cogs,
        "cogs_pricing": cogs_pricing,
        "direct_pct": direct_pct,
        "gp_pct": gp_pct,
        "depreciation_rows": dep_rows,
        "depreciation": dep_schedule,
        "years": labels,
        "pl_settings": pl_set,
        "pl": pl,
        "be_settings": be_set,
        "fixed_monthly": fixed_monthly,
        "preop_monthly": preop_monthly,
        "variable_total": variable_total,
        "overheads": overheads,
        "be": be,
        "cf_settings": cf_set,
        "cf": cf,
        "wc_settings": wc_set,
    }
