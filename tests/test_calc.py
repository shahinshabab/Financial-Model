"""Checks the calculations against the numbers shown in the design PDFs (Techno Lab demo)."""

import pytest

from fm import calc


def test_item_amounts():
    assert calc.item_amount("fixed_asset", "Cent", 5, 200000) == 1_000_000
    assert calc.item_amount("pre_operating", "1", "", 18000) == 18000
    assert calc.item_amount("operating", "3 months", 2, 1000) == 6000


def test_depreciation_matches_fixed_asset_page():
    assets = [(1_000_000, 60), (75_000, 10), (200_000, 3), (70_000, 15), (30_000, 10)]
    sched = calc.depreciation_schedule(assets, 5)
    assert sched[0] == pytest.approx(98_500, abs=0.05)
    # computers (3 years) are fully depreciated after year 3
    assert sched[3] == pytest.approx(98_500 - 66_666.67, abs=0.05)


def test_sales_forecast_flat():
    out = calc.sales_forecast({"first_day_customers": 1, "first_day_avt": 1000, "start_date": "2026-12-01"})
    rows = out["rows"]
    assert rows[0]["period"].startswith("Tuesday")
    assert out["first_year_customers"] == pytest.approx(365)
    week1 = next(r for r in rows if r["period"] == "Week 1")
    assert week1["sales"] == pytest.approx(7000)
    quarters = [r for r in rows if r["level"] == "quarter"]
    assert [q["customers"] for q in quarters] == pytest.approx([90] * 4)
    years = [r for r in rows if r["level"] == "year"]
    # Only December counts in 2026, then 10 full years 2027-2036.
    assert years[0]["period"].startswith("2026 (Dec")
    assert years[0]["customers"] == pytest.approx(31)
    assert [y["period"] for y in years[1:]] == [str(y) for y in range(2027, 2037)]
    assert all(y["customers"] == pytest.approx(365) for y in years[1:])


def test_sales_forecast_starting_1_january_has_no_part_year():
    out = calc.sales_forecast({"first_day_customers": 1, "first_day_avt": 1000, "start_date": "2026-01-01",
                               "annual_customer_growth": 10, "years": 3})
    years = [r for r in out["rows"] if r["level"] == "year"]
    assert [y["period"] for y in years] == ["2026", "2027", "2028"]
    assert years[1]["customers"] == pytest.approx(365 * 1.1)


def test_cogs_table():
    cats = [{"name": "3D Printing", "cogs_percent": 10}, {"name": "Raw Materials", "cogs_percent": 30}]
    t = calc.cogs_table({"basic": 2000, "economic": 2500, "premium": 3000}, cats)
    assert t["total_pct"] == 40
    assert t["rows"][1]["basic"] == 600
    assert t["contribution"]["premium"] == 1800
    assert t["gp_pct"]["basic"] == pytest.approx(60)


def _pl():
    indirect = [
        {"name": "Staff Salaries & Wages", "annual": 300000, "growth_pct": 10},
        {"name": "Rent & Utilities", "annual": 96000, "growth_pct": 0},
        {"name": "Raw Materials & Consumables", "annual": 144000, "growth_pct": 5},
        {"name": "Equipment Maintenance", "annual": 54000, "growth_pct": 5},
        {"name": "Internet & Software", "annual": 72000, "growth_pct": 5},
    ]
    return calc.profit_and_loss(
        n_years=8,
        first_year_customers=336,
        channels=[
            {"name": "Product Building", "split_pct": 75, "avg_vot": 10000},
            {"name": "Research and Development", "split_pct": 25, "avg_vot": 500},
        ],
        customer_growth_pct=10,
        inflation_pct=10,
        other_income=[],
        direct_expense_pct=40,
        coco_pct=0,
        indirect=indirect,
        depreciation=[98500] * 8,
        tax_rate_pct=25,
        valuation_multiple=8,
        total_capital=1_567_500,
    )


def test_profit_and_loss_matches_pdf():
    pl = _pl()
    assert pl["revenue"][0] == pytest.approx(2_562_000)
    assert pl["revenue"][1] == pytest.approx(3_100_020)
    assert pl["revenue"][2] == pytest.approx(3_751_024.20)
    assert pl["direct"][0] == pytest.approx(1_024_800)
    assert pl["contribution"][0] == pytest.approx(1_537_200)
    assert pl["pbt"][0] == pytest.approx(772_700)
    assert pl["tax"][0] == pytest.approx(193_175)
    assert pl["pat"][0] == pytest.approx(579_525)
    assert pl["pat"][1] == pytest.approx(789_009)
    assert pl["roi"][0] == pytest.approx(36.97, abs=0.01)
    assert pl["valuation"][0] == pytest.approx(4_636_200)


def test_cash_flow_matches_pdf():
    pl = _pl()
    cf = calc.cash_flow(pl["pat"], pl["depreciation"])
    assert cf["net"][0] == pytest.approx(678_025)
    assert cf["opening"][1] == pytest.approx(678_025)
    assert cf["net"][1] == pytest.approx(1_565_534)
    assert cf["net"][2] == pytest.approx(2_710_613.64)


def test_break_even_matches_pdf():
    be = calc.break_even(55_500, 60)
    assert be["bep"] == pytest.approx(92_500)
    assert be["target"] == pytest.approx(185_000)
    assert be["bep_day"] == pytest.approx(15)
    assert be["total_cost"][14] == pytest.approx(be["revenue"][14])
