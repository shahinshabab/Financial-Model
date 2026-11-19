"""Pure financial calculations (no Streamlit, no database) so they can be unit tested."""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Iterable


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def num(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        f = float(value)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


def months_of(measure: str | float | None) -> float:
    """Pre-Operating / Operating 'MEASURE / UNIT (MONTHS)' -> number of months (default 1)."""
    if isinstance(measure, (int, float)):
        return float(measure) if measure > 0 else 1.0
    m = re.search(r"\d+(\.\d+)?", str(measure or ""))
    return float(m.group()) if m and float(m.group()) > 0 else 1.0


def item_amount(section: str, measure_unit, qty, unit_cost) -> float:
    """Amount of one sub-category line.

    * Fixed assets: QTY x APPROX. COST
    * Pre-operating / Operating / COGS: MONTHS x QTY x MONTHLY COST
    """
    q = num(qty, 1.0)
    cost = num(unit_cost)
    if section == "fixed_asset":
        return round(q * cost, 2)
    return round(months_of(measure_unit) * q * cost, 2)


def category_totals(items: Iterable[dict]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for it in items:
        totals[it["category_id"]] = totals.get(it["category_id"], 0.0) + num(it.get("amount"))
    return totals


def fiscal_labels(start_year: int, n: int) -> list[str]:
    return [f"{start_year + i}-{str(start_year + i + 1)[-2:]}" for i in range(n)]


def growth_series(base: float, growth_pct: float, n: int) -> list[float]:
    g = num(growth_pct) / 100
    return [base * (1 + g) ** i for i in range(n)]


# ---------------------------------------------------------------------------
# Fixed asset depreciation (straight line)
# ---------------------------------------------------------------------------
def yearly_depreciation(total: float, years: float) -> float:
    years = num(years)
    return total / years if years > 0 else 0.0


def depreciation_schedule(assets: Iterable[tuple[float, float]], n_years: int) -> list[float]:
    """assets: (category_total, useful_life_years). Returns depreciation per projection year."""
    out = [0.0] * n_years
    for total, life in assets:
        per_year = yearly_depreciation(total, life)
        if per_year <= 0:
            continue
        remaining = total
        for i in range(n_years):
            dep = min(per_year, remaining)
            out[i] += dep
            remaining -= dep
            if remaining <= 1e-9:
                break
    return out


# ---------------------------------------------------------------------------
# Sales forecast
# ---------------------------------------------------------------------------
SALES_DEFAULTS = {
    "daily_customer_growth": 0.0,
    "daily_avt_growth": 0.0,
    "weekly_customer_growth": 0.0,
    "weekly_avt_growth": 0.0,
    "quarterly_customer_growth": 0.0,
    "quarterly_avt_growth": 0.0,
    "annual_customer_growth": 0.0,
    "annual_avt_growth": 0.0,
    "first_day_customers": 1.0,
    "first_day_avt": 1000.0,
    "start_date": None,
    "years": 10,
    "weeks_per_quarter": 12,
}


def sales_forecast(params: dict) -> dict:
    """Builds Daily (7) -> Weekly (12) -> Quarterly (4) -> Yearly (N) forecast rows.

    * Day n = first day x (1 + daily growth)^(n-1)
    * Week 1 = sum of the 7 days; week n grows by the weekly rate
    * Quarter 1 = sum of the weeks in a quarter; quarter n grows by the quarterly rate
    * Year 1 = sum of the 4 quarters; year n grows by the annual rate
    """
    p = SALES_DEFAULTS | {k: v for k, v in (params or {}).items() if v is not None}
    start = p["start_date"]
    if isinstance(start, str) and start:
        start = date.fromisoformat(start[:10])
    if not isinstance(start, date):
        start = date.today()

    def g(key):
        return num(p[key]) / 100

    rows: list[dict] = []
    c0, a0 = num(p["first_day_customers"]), num(p["first_day_avt"])

    days = []
    for i in range(7):
        c = c0 * (1 + g("daily_customer_growth")) ** i
        a = a0 * (1 + g("daily_avt_growth")) ** i
        days.append((c, c * a))
        rows.append({"period": (start + timedelta(days=i)).strftime("%A"), "level": "day", "customers": c, "avt": a, "sales": c * a})

    w_c = sum(d[0] for d in days)
    w_s = sum(d[1] for d in days)
    w_a = w_s / w_c if w_c else 0.0
    weeks_per_q = int(num(p["weeks_per_quarter"], 12)) or 12
    weeks = []
    for i in range(weeks_per_q):
        c = w_c * (1 + g("weekly_customer_growth")) ** i
        a = w_a * (1 + g("weekly_avt_growth")) ** i
        weeks.append((c, c * a))
        rows.append({"period": f"Week {i + 1}", "level": "week", "customers": c, "avt": a, "sales": c * a})

    q_c = sum(w[0] for w in weeks)
    q_s = sum(w[1] for w in weeks)
    q_a = q_s / q_c if q_c else 0.0
    quarters = []
    for i in range(4):
        c = q_c * (1 + g("quarterly_customer_growth")) ** i
        a = q_a * (1 + g("quarterly_avt_growth")) ** i
        quarters.append((c, c * a))
        rows.append({"period": f"Quarter {i + 1}", "level": "quarter", "customers": c, "avt": a, "sales": c * a})

    y_c = sum(q[0] for q in quarters)
    y_s = sum(q[1] for q in quarters)
    y_a = y_s / y_c if y_c else 0.0
    for i in range(int(num(p["years"], 10))):
        c = y_c * (1 + g("annual_customer_growth")) ** i
        a = y_a * (1 + g("annual_avt_growth")) ** i
        rows.append({"period": str(start.year + i), "level": "year", "customers": c, "avt": a, "sales": c * a})

    return {
        "rows": rows,
        "first_day_sales": c0 * a0,
        "first_year_customers": y_c,
        "first_year_sales": y_s,
        "start_date": start,
    }


# ---------------------------------------------------------------------------
# COGS
# ---------------------------------------------------------------------------
def cogs_table(prices: dict, categories: list[dict]) -> dict:
    tiers = ("basic", "economic", "premium")
    price = {t: num(prices.get(t)) for t in tiers}
    rows = []
    total_pct = 0.0
    for c in categories:
        pct = num(c.get("cogs_percent"))
        total_pct += pct
        rows.append({"name": c["name"], "id": c.get("id"), "pct": pct} | {t: price[t] * pct / 100 for t in tiers})
    contribution = {t: price[t] - sum(r[t] for r in rows) for t in tiers}
    gp = {t: (contribution[t] / price[t] * 100 if price[t] else 0.0) for t in tiers}
    return {"price": price, "rows": rows, "total_pct": total_pct, "contribution": contribution, "gp_pct": gp}


# ---------------------------------------------------------------------------
# Profit & Loss
# ---------------------------------------------------------------------------
def channel_split(total_customers: float, channels: list[dict]) -> list[dict]:
    out = []
    for ch in channels:
        split = num(ch.get("split_pct"))
        customers = total_customers * split / 100
        vot = num(ch.get("avg_vot"))
        out.append(ch | {"customers": customers, "amount": customers * vot})
    return out


def profit_and_loss(
    *,
    n_years: int,
    first_year_customers: float,
    channels: list[dict],
    customer_growth_pct: float,
    inflation_pct: float,
    other_income: list[float] | None,
    direct_expense_pct: float,
    coco_pct: float,
    indirect: list[dict],
    depreciation: list[float],
    tax_rate_pct: float,
    valuation_multiple: float,
    total_capital: float,
) -> dict:
    """indirect items: {name, annual, growth_pct, one_time}. One-time items hit year 1 only."""
    n = n_years
    g = num(customer_growth_pct) / 100
    inf = num(inflation_pct) / 100
    split = channel_split(first_year_customers, channels)

    channel_years = []
    for ch in split:
        yrs = []
        for i in range(n):
            c = ch["customers"] * (1 + g) ** i
            v = num(ch.get("avg_vot")) * (1 + inf) ** i
            yrs.append({"customers": c, "vot": v, "amount": c * v})
        channel_years.append({"name": ch.get("name", ""), "years": yrs})

    revenue = [sum(cy["years"][i]["amount"] for cy in channel_years) for i in range(n)]
    other = [num((other_income or [])[i]) if i < len(other_income or []) else 0.0 for i in range(n)]
    total_income = [revenue[i] + other[i] for i in range(n)]
    direct = [revenue[i] * num(direct_expense_pct) / 100 for i in range(n)]
    coco = [revenue[i] * num(coco_pct) / 100 for i in range(n)]
    contribution = [total_income[i] - direct[i] - coco[i] for i in range(n)]

    indirect_rows = []
    for it in indirect:
        if it.get("one_time"):
            vals = [num(it.get("annual")) if i == 0 else 0.0 for i in range(n)]
        else:
            vals = growth_series(num(it.get("annual")), num(it.get("growth_pct")), n)
        indirect_rows.append({"name": it["name"], "values": vals, "growth_pct": num(it.get("growth_pct")), "one_time": bool(it.get("one_time")), "id": it.get("id")})

    dep = [num(depreciation[i]) if i < len(depreciation) else 0.0 for i in range(n)]
    pbt = [contribution[i] - sum(r["values"][i] for r in indirect_rows) - dep[i] for i in range(n)]
    tax = [max(pbt[i], 0.0) * num(tax_rate_pct) / 100 for i in range(n)]
    pat = [pbt[i] - tax[i] for i in range(n)]
    roi = [(pat[i] / total_capital * 100) if total_capital else 0.0 for i in range(n)]
    valuation = [pat[i] * num(valuation_multiple) for i in range(n)]

    return {
        "channels": split,
        "channel_years": channel_years,
        "revenue": revenue,
        "other_income": other,
        "total_income": total_income,
        "direct": direct,
        "coco": coco,
        "contribution": contribution,
        "indirect": indirect_rows,
        "depreciation": dep,
        "pbt": pbt,
        "tax": tax,
        "pat": pat,
        "roi": roi,
        "valuation": valuation,
    }


# ---------------------------------------------------------------------------
# Break even
# ---------------------------------------------------------------------------
def break_even(overheads_monthly: float, gp_pct: float, sales_target: float | None = None, days: int = 30) -> dict:
    gp = num(gp_pct) / 100
    bep = overheads_monthly / gp if gp > 0 else 0.0
    suggested = bep * 2
    target = num(sales_target) if num(sales_target) > 0 else suggested
    x = list(range(1, days + 1))
    revenue = [target / days * d for d in x]
    fixed = [overheads_monthly for _ in x]
    total_cost = [overheads_monthly + r * (1 - gp) for r in revenue]
    bep_day = (bep / target * days) if target else 0.0
    return {
        "bep": bep,
        "suggested_target": suggested,
        "target": target,
        "days": x,
        "revenue": revenue,
        "fixed": fixed,
        "total_cost": total_cost,
        "bep_day": bep_day,
    }


# ---------------------------------------------------------------------------
# Cash flow
# ---------------------------------------------------------------------------
def cash_flow(pat: list[float], depreciation: list[float], receivables: list[float] | None = None) -> dict:
    n = len(pat)
    rec = [num((receivables or [])[i]) if i < len(receivables or []) else 0.0 for i in range(n)]
    opening, net = [], []
    prev = 0.0
    for i in range(n):
        opening.append(prev)
        prev = prev + pat[i] + depreciation[i] - rec[i]
        net.append(prev)
    return {"opening": opening, "pat": pat, "depreciation": depreciation, "receivables": rec, "net": net}


def payback_years(capital: float, yearly_cash: list[float]) -> float | None:
    remaining = capital
    for i, c in enumerate(yearly_cash):
        if c <= 0:
            continue
        if c >= remaining:
            return i + remaining / c
        remaining -= c
    return None
