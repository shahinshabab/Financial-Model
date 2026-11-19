"""OpenAI 'Generate' helpers.

Each section (Fixed Assets, Pre-Operating, Operating, COGS) has its own system
prompt and its own Pydantic schema, for both the category list and the
sub-category items inside a category. The model is asked for structured output
(JSON schema from Pydantic) and the response is validated again with Pydantic
before anything is shown or saved.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from fm.config import get_secret

Section = Literal["fixed_asset", "pre_operating", "operating", "cogs"]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class _Clean(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class FixedAssetCategory(_Clean):
    name: str = Field(description="Fixed asset category name, e.g. 'Computers & IT Equipment'")
    reason: str = Field(description="One short sentence on why this business needs it")
    depreciation_years: float = Field(description="Typical useful life in years for straight-line depreciation", ge=0, le=100)


class PreOperatingCategory(_Clean):
    name: str = Field(description="Pre-operating expense category, e.g. 'Business Registration & Legal'")
    reason: str = Field(description="One short sentence on why this business needs it")
    add_to_pl: bool = Field(description="True if this one-time cost should be expensed in the first year's Profit & Loss")
    add_to_be: bool = Field(description="True if this cost should be included in the monthly break-even overheads")


class OperatingCategory(_Clean):
    name: str = Field(description="Monthly operating expense category, e.g. 'Staff Salaries & Wages'")
    reason: str = Field(description="One short sentence on why this business needs it")
    add_to_pl: bool = Field(description="True if this is an indirect/fixed expense that belongs in Profit & Loss")
    add_to_be: bool = Field(description="True if this is a fixed monthly cost that belongs in break-even")
    yearly_growth_pct: float = Field(description="Expected yearly increase in % (e.g. 10 for salaries, 0 for fixed rent)", ge=0, le=100)


class CogsCategory(_Clean):
    name: str = Field(description="Direct cost category per unit sold, e.g. 'Raw Materials'")
    reason: str = Field(description="One short sentence on why this business needs it")
    percent_of_revenue: float = Field(description="Approximate share of the sales price, in %", ge=0, le=100)


class FixedAssetItem(_Clean):
    sub_category: str = Field(description="Sub-category, e.g. 'Land', 'Workstations'")
    item: str = Field(description="Specific asset / item to buy")
    measure_unit: str = Field(description="Unit of measure, e.g. 'Cent', 'Sq.ft', 'Nos', 'Set'")
    qty: float = Field(description="Quantity", ge=0)
    unit_cost: float = Field(description="Approximate cost per unit in INR", ge=0)
    remarks: str = Field(description="Short remark, e.g. 'Owned', 'Second-hand', 'Leased'")


class MonthlyItem(_Clean):
    sub_category: str = Field(description="Sub-category, e.g. 'Technical Staff', 'Legal & Registration'")
    item: str = Field(description="Asset / item / role")
    months: float = Field(description="Number of months this cost applies (1 for a monthly running cost)", ge=0)
    qty: float = Field(description="Quantity or head-count", ge=0)
    monthly_cost: float = Field(description="Cost per month per unit in INR", ge=0)
    remarks: str = Field(description="Short remark")


class FixedAssetCategoryList(BaseModel):
    categories: list[FixedAssetCategory] = Field(min_length=1, max_length=15)


class PreOperatingCategoryList(BaseModel):
    categories: list[PreOperatingCategory] = Field(min_length=1, max_length=15)


class OperatingCategoryList(BaseModel):
    categories: list[OperatingCategory] = Field(min_length=1, max_length=15)


class CogsCategoryList(BaseModel):
    categories: list[CogsCategory] = Field(min_length=1, max_length=15)


class FixedAssetItemList(BaseModel):
    items: list[FixedAssetItem] = Field(min_length=1, max_length=20)


class MonthlyItemList(BaseModel):
    items: list[MonthlyItem] = Field(min_length=1, max_length=20)


CATEGORY_SCHEMAS: dict[str, type[BaseModel]] = {
    "fixed_asset": FixedAssetCategoryList,
    "pre_operating": PreOperatingCategoryList,
    "operating": OperatingCategoryList,
    "cogs": CogsCategoryList,
}
ITEM_SCHEMAS: dict[str, type[BaseModel]] = {
    "fixed_asset": FixedAssetItemList,
    "pre_operating": MonthlyItemList,
    "operating": MonthlyItemList,
    "cogs": MonthlyItemList,
}


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------
BASE_PROMPT = (
    "You are a startup financial-planning analyst who prepares project reports and bank loan "
    "financial models for small and medium businesses in India. Amounts are in Indian Rupees (INR) "
    "with realistic present-day market prices. Be specific to the business described by the user, "
    "avoid generic filler, never repeat categories or items that already exist, and keep names short "
    "(2-6 words) like a line in a project report."
)

CATEGORY_PROMPTS = {
    "fixed_asset": (
        "Task: list the FIXED ASSET (capital expenditure) categories this business must buy before it "
        "can operate. Only long-lived tangible assets that are capitalised and depreciated: e.g. Land & "
        "Building, Furniture & Fixtures, Computers & IT Equipment, Plant & Machinery, Laboratory "
        "Equipment, Electrical & Electronic Equipment, Vehicles. Do NOT include salaries, rent, "
        "licences, marketing or other expenses. For each category give a typical straight-line useful "
        "life in years (Land & Building ~60, Furniture ~10, Computers ~3, Machinery ~15, Electricals ~10). "
        "Return 4-8 categories."
    ),
    "pre_operating": (
        "Task: list the PRE-OPERATING CAPITAL categories, i.e. one-time costs incurred BEFORE the business "
        "starts earning: e.g. Business Registration & Legal, Feasibility & Project Planning, Recruitment & "
        "Staff Training, Pre-Launch Marketing, Pre-Opening Rent & Utilities, Licences & Permits, Security "
        "Deposits. Do NOT include fixed assets (equipment, furniture, buildings) or regular monthly running "
        "costs after launch. Set add_to_pl true for costs that should be expensed in year one, and "
        "add_to_be true only if the cost recurs and should be counted in monthly break-even overheads "
        "(usually false). Return 4-8 categories."
    ),
    "operating": (
        "Task: list the OPERATING CAPITAL categories, i.e. recurring MONTHLY running costs once the business "
        "is open: e.g. Staff Salaries & Wages, Rent & Utilities, Raw Materials & Consumables, Equipment "
        "Maintenance, Internet & Software, Marketing, Insurance. Do NOT include one-time setup costs or fixed "
        "assets. Indirect/fixed costs go to P&L (add_to_pl true) and to break-even (add_to_be true). Give a "
        "realistic yearly growth % (salaries ~10, rent 0-5, consumables ~5). Return 4-8 categories."
    ),
    "cogs": (
        "Task: list the COST OF GOODS SOLD categories, i.e. DIRECT costs that vary with each unit sold or "
        "service delivered: e.g. Raw Materials, Packaging, Direct Labour, Printing, Shipping, Payment Gateway "
        "Fees. Do NOT include rent, salaries of admin staff or other fixed overheads. Give each category's "
        "approximate % of the selling price; the total should usually be between 20% and 70%. Return 2-6 "
        "categories."
    ),
}

ITEM_PROMPTS = {
    "fixed_asset": (
        "Task: break the given FIXED ASSET category into sub-categories and concrete assets to purchase. "
        "For each line give sub_category, item, measure_unit (Cent, Sq.ft, Nos, Set, Lot...), qty and "
        "approximate unit_cost in INR, plus a short remark (Owned, Leased, New, Refurbished...). "
        "Return 2-8 lines sized for this business."
    ),
    "pre_operating": (
        "Task: break the given PRE-OPERATING category into sub-categories and items / roles. For each line "
        "give sub_category, item, months (how many months before launch the cost applies, 1 for a one-off "
        "payment), qty, monthly_cost in INR (for one-off payments put the full fee here with months=1) and "
        "a short remark. Return 2-8 lines."
    ),
    "operating": (
        "Task: break the given OPERATING category into sub-categories and items / roles that are paid EVERY "
        "MONTH. For each line give sub_category, item (or job role), months=1, qty (head-count or units), "
        "monthly_cost in INR per unit and a short remark (e.g. 'Recurring'). Return 2-8 lines."
    ),
    "cogs": (
        "Task: break the given COST OF GOODS SOLD category into direct cost items consumed in a typical "
        "month of production. For each line give sub_category, item, months=1, qty, monthly_cost in INR "
        "and a short remark. Return 2-8 lines."
    ),
}

SECTION_TITLES = {
    "fixed_asset": "Fixed Assets",
    "pre_operating": "Pre-Operating Capital",
    "operating": "Operating Capital",
    "cogs": "COGS",
}


class AIError(RuntimeError):
    pass


def _client():
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise AIError("OPENAI_API_KEY is not set. Add it to .streamlit/secrets.toml or the environment.")
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _parse(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    client = _client()
    model = get_secret("OPENAI_MODEL", "gpt-4o-mini")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        parse = getattr(client.chat.completions, "parse", None) or client.beta.chat.completions.parse
        completion = parse(model=model, messages=messages, response_format=schema)
    except Exception as exc:  # network, auth, schema errors
        raise AIError(f"OpenAI request failed: {exc}") from exc
    msg = completion.choices[0].message
    if getattr(msg, "refusal", None):
        raise AIError(f"The model refused: {msg.refusal}")
    data = msg.parsed if msg.parsed is not None else msg.content
    try:
        # Validate again with Pydantic so bad data never reaches the database.
        if isinstance(data, BaseModel):
            return schema.model_validate(data.model_dump())
        return schema.model_validate_json(data)
    except ValidationError as exc:
        raise AIError(f"The AI response did not match the expected structure: {exc}") from exc


def _context(description: str, business: str, model_name: str) -> str:
    return (
        ""
        f"Project / financial model: {model_name or '-'}\n"
        f"Business description:\n{description.strip()}\n"
    )


def generate_categories(section: Section, description: str, business: str, model_name: str, existing: list[str]) -> BaseModel:
    system = f"{BASE_PROMPT}\n\n{CATEGORY_PROMPTS[section]}"
    user = _context(description, business, model_name) + (
        f"\nAlready added {SECTION_TITLES[section]} categories (do not repeat): {', '.join(existing) or 'none'}"
    )
    return _parse(system, user, CATEGORY_SCHEMAS[section])


def generate_items(
    section: Section,
    description: str,
    business: str,
    model_name: str,
    category: str,
    existing: list[str],
) -> BaseModel:
    system = f"{BASE_PROMPT}\n\n{ITEM_PROMPTS[section]}"
    user = _context(description, business, model_name) + (
        f"\n{SECTION_TITLES[section]} category: {category}"
        f"\nAlready added lines in this category (do not repeat): {', '.join(existing) or 'none'}"
    )
    return _parse(system, user, ITEM_SCHEMAS[section])
