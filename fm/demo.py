"""Creates the 'Techno Lab' sample model shown in the design PDFs."""

from __future__ import annotations

from fm import calc

FIXED = [
    ("Land & Building", 60, [("Land", "Land Purchase", "Cent", 5, 200000, "Owned")]),
    ("Furniture & Fixed Assets", 10, [("Furniture", "Work tables & chairs", "Set", 5, 15000, "New")]),
    ("Computers & IT Equipment", 3, [("Computers", "Design workstations", "Nos", 4, 50000, "New")]),
    ("Laboratory Equipment & Machinery", 15, [("3D Printers", "FDM 3D printer", "Nos", 2, 35000, "New")]),
    ("Electrical & Electronic Equipment", 10, [("Electricals", "Wiring, UPS & lighting", "Lot", 1, 30000, "New")]),
]
PRE_OP = [
    ("Business Registration & Legal", [("Legal & Registration", "Company registration", "1", 1, 18000, "Same month")]),
    ("Feasibility & Project Planning", [("Consulting", "Project report", "1", 1, 25000, "")]),
    ("Recruitment & Staff Training", [("Training", "Staff onboarding", "1", 1, 24000, "")]),
    ("Pre-Launch Marketing", [("Marketing", "Launch campaign", "1", 1, 30000, "")]),
    ("Pre-Opening Rent & Utilities", [("Rent", "Advance rent", "5", 1, 8000, "")]),
]
OPERATING = [
    ("Staff Salaries & Wages", 10, [("Technical Staff", "Lab Technician", "1", 1, 25000, "Recurring")]),
    ("Rent & Utilities", 0, [("Rent", "Lab rent", "1", 1, 8000, "Recurring")]),
    ("Raw Materials & Consumables", 5, [("Filament", "PLA filament", "1", 1, 12000, "Recurring")]),
    ("Equipment Maintenance", 5, [("AMC", "Printer maintenance", "1", 1, 4500, "Recurring")]),
    ("Internet & Software", 5, [("Software", "CAD licences & internet", "1", 1, 6000, "Recurring")]),
]
COGS = [("3D Printing", 10), ("Raw Materials", 30)]


def create_demo(repo) -> dict:
    m = repo.create_model(
        name="Techno Lab",
        start_year=2026,
        business_description="Techno Lab is a 3D printing and electronics prototyping lab in Kochi, Kerala that builds "
        "products for startups and runs research & development projects for students.",
    )
    mid = m["id"]

    def add(section, name, items, **fields):
        c = repo.add_category(mid, section, name, **fields)
        for sub, item, measure, qty, cost, rem in items:
            repo.add_item(mid, c["id"], sub_category=sub, item=item, measure_unit=measure, qty=qty, unit_cost=cost,
                          amount=calc.item_amount(section, measure, qty, cost), remarks=rem)

    for i, (name, years, items) in enumerate(FIXED):
        add("fixed_asset", name, items, depreciation_years=years, sort_order=i)
    for i, (name, items) in enumerate(PRE_OP):
        add("pre_operating", name, items, sort_order=i)
    for i, (name, growth, items) in enumerate(OPERATING):
        add("operating", name, items, add_to_pl=True, add_to_be=True, pl_growth_pct=growth, sort_order=i)
    for i, (name, pct) in enumerate(COGS):
        repo.add_category(mid, "cogs", name, cogs_percent=pct, sort_order=i)

    repo.save_setting(mid, "sales_forecast", {"first_day_customers": 1, "first_day_avt": 1000, "start_date": "2026-12-01", "years": 10})
    repo.save_setting(mid, "cogs_pricing", {"basic": 2000, "economic": 2500, "premium": 3000})
    repo.save_setting(mid, "profit_loss", {
        "channels": [
            {"name": "Product Building", "split_pct": 75, "avg_vot": 10000},
            {"name": "Research and Development", "split_pct": 25, "avg_vot": 500},
        ],
        "customer_growth_pct": 10, "inflation_pct": 10, "tax_rate_pct": 25, "valuation_multiple": 8, "years": 8,
    })
    return m
