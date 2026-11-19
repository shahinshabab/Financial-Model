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
}


QUARTER_DAYS = 90
YEAR_DAYS = 365


def _month_span(a: date, b: date) -> str:
    """Label for the dates a .. b (inclusive), e.g. 'Dec' or 'Jan–Nov'."""
    if a.month == b.month and a.year == b.year:
        return a.strftime("%b")
    return f"{a.strftime('%b')}–{b.strftime('%b')}"


PERIOD_DAYS = {"daily": 1, "weekly": 7, "quarterly": QUARTER_DAYS, "annual": YEAR_DAYS}


def active_growth(params: dict, what: str) -> tuple[str | None, float]:
    """The one growth rate in use for `what` ('customer' or 'avt'): the first non-zero of
    daily, weekly, quarterly, annual. Returns (period, rate %) or (None, 0)."""
    for period in PERIOD_DAYS:
        rate = num((params or {}).get(f"{period}_{what}_growth"))
        if rate:
            return period, rate
    return None, 0.0


def daily_rate(period: str | None, rate_pct: float) -> float:
    """Converts a growth % per period into the same growth compounded every day."""
    if not period or not rate_pct:
        return 0.0
    return (1 + rate_pct / 100) ** (1 / PERIOD_DAYS[period]) - 1


def growth_total(first: float, r: float, n: float) -> float:
    """T = C x ((1 + r)^n - 1) / r : total of n days that start at `first` and grow r a day."""
    if n <= 0:
        return 0.0
    if abs(r) < 1e-12:
        return first * n
    try:
        return first * ((1 + r) ** n - 1) / r
    except OverflowError:
        return math.inf


def sales_forecast(params: dict) -> dict:
    """Forecast built from one daily growth curve.

    Customers on day d = C x (1 + r)^(d-1), and the total of days 1..n is
    T(n) = C x ((1 + r)^n - 1) / r. A period covering days a+1..b is T(b) - T(a), so every
    week, quarter (90 days) and year (365 days) comes from the same curve.

    Only one customer growth rate is used (daily, weekly, quarterly or annual, the first
    one filled in); it is converted to a daily rate. The average value of transaction (AVT)
    works the same way with its own rate, so daily sales grow by (1 + r)(1 + s) - 1.
    If the start date isn't 1 January, the start year is shown as a part year and the N
    full calendar years follow it.
    """
    p = SALES_DEFAULTS | {k: v for k, v in (params or {}).items() if v is not None}
    start = p["start_date"]
    if isinstance(start, str) and start:
        start = date.fromisoformat(start[:10])
    if not isinstance(start, date):
        start = date.today()

    c_period, c_rate = active_growth(p, "customer")
    a_period, a_rate = active_growth(p, "avt")
    r = daily_rate(c_period, c_rate)
    s = daily_rate(a_period, a_rate)
    rs = (1 + r) * (1 + s) - 1
    c0, a0 = num(p["first_day_customers"]), num(p["first_day_avt"])

    def customers(n: float) -> float:
        return growth_total(c0, r, n)

    def sales(n: float) -> float:
        return growth_total(c0 * a0, rs, n)

    rows: list[dict] = []

    def add(label: str, level: str, first_day: int, last_day: int) -> dict:
        """Row for days first_day..last_day (1 = start date), as T(last) - T(first - 1)."""
        c = customers(last_day) - customers(first_day - 1)
        sv = sales(last_day) - sales(first_day - 1)
        row = {"period": label, "level": level, "days": f"{first_day}-{last_day}" if last_day > first_day else str(first_day),
               "customers": c, "avt": sv / c if c else 0.0, "sales": sv}
        rows.append(row)
        return row

    for i in range(7):
        d = start + timedelta(days=i)
        add(f"{d.strftime('%A')} ({d.strftime('%d-%m-%Y')})", "day", i + 1, i + 1)
    for k in range(13):
        add(f"Week {k + 1}", "week", 7 * k + 1, 7 * (k + 1))
    for k in range(4):
        add(f"Quarter {k + 1}", "quarter", QUARTER_DAYS * k + 1, QUARTER_DAYS * (k + 1))

    day = 0
    first_full_year = start.year
    if (start.month, start.day) != (1, 1):
        part_days = min((date(start.year + 1, 1, 1) - start).days, YEAR_DAYS)
        add(f"{start.year} ({_month_span(start, date(start.year, 12, 31))}, {part_days} days)", "year", 1, part_days)
        day = part_days
        first_full_year += 1
    for k in range(int(num(p["years"], 10)) or 10):
        add(str(first_full_year + k), "year", day + 1, day + YEAR_DAYS)
        day += YEAR_DAYS

    y_c, y_s = customers(YEAR_DAYS), sales(YEAR_DAYS)
    return {
        "rows": rows,
        "first_day_sales": c0 * a0,
        "first_year_customers": y_c,
        "first_year_sales": y_s,
        "start_date": start,
        "customer_growth": (c_period, c_rate, r),
        "avt_growth": (a_period, a_rate, s),
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
