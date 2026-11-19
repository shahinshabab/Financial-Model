"""Business Financial Model: Streamlit entry point.

Run with:  streamlit run app.py
"""

import streamlit as st
from postgrest.exceptions import APIError

from fm import ui

st.set_page_config(page_title="Business Financial Model", page_icon="📊", layout="wide")

_pages = {
    "home": st.Page("views/home.py", title="Financial Model", icon="🏠", url_path="home", default=True),
    "grand_total": st.Page("views/grand_total.py", title="Capital Structure Report", url_path="capital-structure"),
    "fixed_asset": st.Page("views/fixed_assets.py", title="Fixed Assets", url_path="fixed-assets"),
    "pre_operating": st.Page("views/pre_operating.py", title="Pre-Operating Capital", url_path="pre-operating-capital"),
    "operating": st.Page("views/operating.py", title="Operating Capital", url_path="operating-capital"),
    "category": st.Page("views/category_detail.py", title="Category", url_path="category"),
    "sales": st.Page("views/sales_forecast.py", title="Sales Forecast", url_path="sales-forecast"),
    "cogs": st.Page("views/cogs.py", title="COGS", url_path="cogs"),
    "pl": st.Page("views/profit_loss.py", title="Profit & Loss", url_path="profit-and-loss"),
    "cf": st.Page("views/cash_flow.py", title="Cash Flow", url_path="cash-flow"),
    "wc": st.Page("views/working_capital.py", title="Working Capital", url_path="working-capital"),
    "be": st.Page("views/break_even.py", title="Break Even", url_path="break-even"),
    "kpi": st.Page("views/kpi.py", title="KPI Dashboard", url_path="kpi-dashboard"),
}
ui.PAGES.update(_pages)

try:
    st.navigation(list(_pages.values()), position="hidden").run()
except APIError as exc:  # explain Supabase errors instead of a redacted traceback
    ui.database_error(exc)
