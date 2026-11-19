# Business Financial Model

A Streamlit app for building a business financial model (capital structure, sales forecast, COGS,
profit & loss, cash flow, working capital, break even and KPIs). Data is stored in Supabase.
OpenAI "Generate" buttons suggest categories and line items from your business description.

## Pages

| Page | What it does |
|---|---|
| **Financial Model** (home) | Capital Structure grand-total donut plus Fixed Assets, Pre-Operating and Operating donuts. Hover any slice to see the amount, its % share and the chart total. Click a slice to open its page (the grand-total chart opens the Capital Structure report). Click legend items to hide or show slices. |
| **Capital Structure Report** | Grand total by section and category: sunburst chart you can zoom into, a table, and CSV download. |
| **Fixed Assets** | Category summary (add, rename, delete, View) and year-wise straight-line depreciation. |
| **Pre-Operating Capital** / **Operating Capital** | Category summary with **Add to P&L** and **Add to BE** ticks that feed those pages. |
| **Category (View)** | Sub-category line items: sub-category, asset/item/role, measure/unit, qty, cost, amount, remarks. |
| **Sales Forecast** | Daily, weekly, quarterly and yearly growth of customers and average transaction value. |
| **COGS** | Direct cost categories, % of sales price and contribution for Basic / Economic / Premium prices. |
| **Profit & Loss** | Channel-wise first-year forecast, revenue projection (growth and inflation) and the P&L statement. |
| **Cash Flow** | Opening balance, PAT, depreciation, receivables, net income and a surplus budgeting plan. |
| **Working Capital** | Operating reserve plus receivable and inventory days, less payable days. |
| **Break Even** | Break-even point, sales target, variable costs and an interactive chart. |
| **KPI Dashboard** | Capital, revenue, PAT, ROI, margins, break-even and payback. |

### How the pages are linked

- **Fixed Assets** → depreciation → P&L and Cash Flow.
- **Operating** categories ticked *Add to P&L* → indirect expenses in P&L (monthly total × 12, with a yearly growth % you set in P&L → Edit).
- **Pre-Operating** categories ticked *Add to P&L* → one-time expense in the first P&L year.
- **Operating** categories ticked *Add to BE* → *Monthly Fixed Operating Expense* in Break Even.
- **Pre-Operating** categories ticked *Add to BE* → added to *Monthly Overheads* spread over 12 months.
- **Sales Forecast** first-year customers → P&L channel-wise forecast.
- **COGS** total % → P&L direct expenses and the Contribution % (GP) used in Break Even.
- **ROI** = PAT ÷ grand total capital. **Minimum valuation** = PAT × multiple (8 by default).

## AI Generate

Every category page and every category's View page has a **✨ Generate** button. The first time, the popup asks for a
business description and saves it on the model in Supabase (`financial_models.business_description`). Every other
Generate popup shows the same description so you can reuse or edit it.

Each section (Fixed Assets, Pre-Operating, Operating, COGS) has its own system prompt for categories and for
sub-categories (see `fm/ai.py`). The model's answer comes back as structured output based on a Pydantic schema
for that section, and Pydantic checks it again before anything is shown. You review the suggestions in an
editable table, untick what you don't want, and add the rest.

## Setup

1. **Python 3.10+**, then:
   ```bash
   pip install -r requirements.txt
   ```
2. **Create the tables in Supabase.** Either let GitHub do it (see
   [Database migrations](#database-migrations-auto-deploy) below), or open your project → SQL Editor → New query, paste
   [`supabase/migrations/20261119000000_initial_schema.sql`](supabase/migrations/20261119000000_initial_schema.sql)
   and run it. The SQL is safe to run more than once.
3. **Add your credentials.** Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` (git-ignored) and fill it
   in. Environment variables with the same names also work.
   - `SUPABASE_URL`: Project Settings → API → Project URL.
   - `SUPABASE_KEY` and `SUPABASE_USER_ID`, either:
     - **Single user (simplest):** the `service_role` key and your user's UUID (Authentication → Users). All rows are
       saved under that UUID. Keep this key private and don't use this option on a public deployment.
     - **Sign-in with row level security:** the `anon` key and leave `SUPABASE_USER_ID` empty. The app shows an
       email/password sign-in and RLS keeps each user's data separate.
   - `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`, default `gpt-4o-mini`) to turn on the Generate buttons.
4. **Run:**
   ```bash
   streamlit run app.py
   ```
5. In the sidebar, create a financial model, or click **Load sample model (Techno Lab)** to load the example from the design.

Without Supabase credentials the app runs in a local demo mode that saves to `data/local_db.json`, which is handy for
trying it out.

## Database migrations (auto-deploy)

Database changes live in `supabase/migrations/` as timestamped SQL files. The GitHub Action
[`deploy-migrations.yml`](.github/workflows/deploy-migrations.yml) runs `supabase db push` whenever a change to that
folder is merged into `main`, so new tables or columns reach your Supabase project automatically. You can also run it
by hand from the **Actions** tab (**Deploy Supabase migrations → Run workflow**).

One-time setup, in GitHub → repository **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Where to find it |
|---|---|
| `SUPABASE_ACCESS_TOKEN` | supabase.com → your avatar → **Account preferences → Access Tokens → Generate new token** |
| `SUPABASE_PROJECT_ID` | Project **Settings → General → Project ID** (the `xxxx` in `https://xxxx.supabase.co`) |
| `SUPABASE_DB_PASSWORD` | The database password you set when creating the project (reset it under **Settings → Database** if needed) |

To change the schema later:

```bash
# install the CLI: https://supabase.com/docs/guides/cli
supabase migration new add_something      # creates supabase/migrations/<timestamp>_add_something.sql
# write the SQL in that file, commit, open a PR, merge into main -> the Action applies it
```

Never edit a migration that has already been applied; add a new one instead.

## Tests

```bash
python -m pytest -q
```

The tests check the calculations against the numbers in the design (P&L, cash flow, break even, COGS, depreciation,
sales forecast).

## Project layout

```
app.py              entry point and page registry
views/              one file per page
fm/calc.py          pure financial calculations (unit tested)
fm/engine.py        builds every page's numbers for a model
fm/db.py            Supabase repository (+ local JSON fallback)
fm/ai.py            OpenAI prompts and Pydantic schemas
fm/ui.py            sidebar, shared forms, Generate popups
fm/charts.py        Plotly donuts and the click-to-open bridge
supabase/migrations/   database schema (RLS), auto-deployed by GitHub Actions
```
