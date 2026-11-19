import pandas as pd
import streamlit as st

from fm import ui
from fm.calc import num
from fm.fmt import inr, pct

repo, model, snap = ui.page_setup(["Profit & Loss"])
ui.show_flash()
mid = model["id"]
settings = snap["pl_settings"]
pl = snap["pl"]
years = snap["years"]
channels = list(settings.get("channels") or [])


def save(**changes):
    data = dict(settings) | changes
    repo.save_setting(mid, "profit_loss", data)


# ---------------------------------------------------------------------------
# Channel-wise forecast
# ---------------------------------------------------------------------------
top_l, top_r = st.columns([3, 1])
top_l.subheader("Channel-Wise Forecast – First Year")
top_r.metric("Total # of customers 1st year", f"{snap['first_year_customers']:,.0f}", help="From the Sales Forecast page")

widths = [3, 1.4, 1.3, 1.6, 2, 1, 1]
ui.head(st.columns(widths), ["Channel", "% Split", "#OC", "Avg VOT", "Amount", "", ""])
with st.form("add_channel", clear_on_submit=True, border=False):
    cols = st.columns(widths, vertical_alignment="bottom")
    name = cols[0].text_input("channel", placeholder="Enter Channel", label_visibility="collapsed")
    split = cols[1].number_input("split", value=0.0, min_value=0.0, max_value=100.0, label_visibility="collapsed")
    vot = cols[3].number_input("vot", value=0.0, min_value=0.0, step=100.0, label_visibility="collapsed")
    if cols[5].form_submit_button("Save", type="primary", width="stretch"):
        if name.strip():
            save(channels=channels + [{"name": name.strip(), "split_pct": split, "avg_vot": vot}])
            ui.flash("Channel added")
            st.rerun()

for i, ch in enumerate(pl["channels"]):
    cols = st.columns(widths, vertical_alignment="center")
    n = cols[0].text_input("n", ch["name"], key=f"ch_n_{i}", label_visibility="collapsed")
    s = cols[1].number_input("s", value=float(num(ch["split_pct"])), min_value=0.0, max_value=100.0, key=f"ch_s_{i}", label_visibility="collapsed")
    ui.cell(cols[2], f"{snap['first_year_customers'] * s / 100:,.0f}")
    v = cols[3].number_input("v", value=float(num(ch["avg_vot"])), min_value=0.0, step=100.0, key=f"ch_v_{i}", label_visibility="collapsed")
    ui.cell(cols[4], inr(snap["first_year_customers"] * s / 100 * v))
    if cols[5].button("Update", key=f"ch_u_{i}", width="stretch"):
        channels[i] = {"name": n, "split_pct": s, "avg_vot": v}
        save(channels=channels)
        st.rerun()
    if cols[6].button("Delete", key=f"ch_d_{i}", width="stretch"):
        channels.pop(i)
        save(channels=channels)
        st.rerun()

total_split = sum(num(c["split_pct"]) for c in channels)
yearly = sum(c["amount"] for c in pl["channels"])
cols = st.columns(widths)
ui.cell(cols[0], "Total", bold=True)
ui.cell(cols[1], pct(total_split, 0), bold=True)
ui.cell(cols[3], "Yearly<br>Monthly<br>Daily", bold=True)
ui.cell(cols[4], f"{inr(yearly)}<br>{inr(yearly / 12)}<br>{inr(yearly / 365)}", bold=True)
if channels and abs(total_split - 100) > 0.01:
    st.warning(f"Channel split adds up to {total_split:g}%, not 100%.")

# ---------------------------------------------------------------------------
# Revenue from operations (annexure)
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Revenue from operations")
with st.form("growth"):
    c = st.columns([2, 2, 1], vertical_alignment="bottom")
    growth = c[0].number_input("Growth (customers, % per year)", value=float(settings["customer_growth_pct"]), step=0.5)
    infl = c[1].number_input("Inflation Rate (avg VOT, % per year)", value=float(settings["inflation_pct"]), step=0.5)
    if c[2].form_submit_button("Update", width="stretch"):
        save(customer_growth_pct=growth, inflation_pct=infl)
        st.rerun()

rows = []
for cy in pl["channel_years"]:
    r = {"PARTICULARS": cy["name"]}
    for y, v in zip(years, cy["years"]):
        r[(y, "NO. OF CUSTOMERS")] = f"{v['customers']:,.0f}"
        r[(y, "AVG VOT")] = f"{v['vot']:,.2f}"
        r[(y, "AMOUNT")] = inr(v["amount"])
    rows.append(r)
if rows:
    tot = {"PARTICULARS": "Total"}
    for i, y in enumerate(years):
        tot[(y, "NO. OF CUSTOMERS")] = ""
        tot[(y, "AVG VOT")] = ""
        tot[(y, "AMOUNT")] = inr(pl["revenue"][i])
    rows.append(tot)
    ann = pd.DataFrame(rows).set_index("PARTICULARS")
    ann.columns = pd.MultiIndex.from_tuples(ann.columns)
    st.dataframe(ann, width="stretch")
else:
    st.info("Add sales channels above to project revenue.")

# ---------------------------------------------------------------------------
# Profit and Loss statement
# ---------------------------------------------------------------------------
st.divider()
h1, h2 = st.columns([4, 1])
h1.subheader("Profit And Loss")
rev0 = pl["revenue"][0] if pl["revenue"] else 0


def line(label, values, show_pct=True, fmt=inr):
    r = {"Particulars": label}
    for i, y in enumerate(years):
        r[y] = fmt(values[i])
        if i == 0:
            r["%"] = pct(values[0] / rev0 * 100) if (show_pct and rev0) else ""
    return r


table = [
    line("Revenue from operations", pl["revenue"], show_pct=False),
    line("Other income", pl["other_income"], show_pct=False),
    line("Total Income", pl["total_income"], show_pct=False),
    line("Less: Direct Expenses", pl["direct"]),
    line("COCO RS Sharing", pl["coco"]),
    line("Contribution (Gross Profit)", pl["contribution"]),
    {"Particulars": "Less: Indirect / Fixed Expenses"},
]
table += [line(f"{r['name']}", r["values"]) for r in pl["indirect"]]
table += [
    line("Depreciation", pl["depreciation"]),
    line("Profit before taxation", pl["pbt"]),
    line("Taxation", pl["tax"]),
    line("Profit after taxation", pl["pat"]),
    {"Particulars": "ROI (%)", **{y: pct(v) for y, v in zip(years, pl["roi"])}, "%": ""},
    {"Particulars": f"Minimum Valuation ({num(settings['valuation_multiple']):g}x PAT)", **{y: inr(v) for y, v in zip(years, pl["valuation"])}, "%": ""},
]
df = pd.DataFrame(table).fillna("")
df = df[["Particulars", years[0], "%"] + years[1:]]
st.dataframe(df, hide_index=True, width="stretch", height=40 + 35 * len(df))
st.caption(
    f"Direct expenses = {pct(snap['direct_pct'])} of revenue "
    + ("(from COGS)." if snap["categories"]["cogs"] else "(set below; add COGS categories to derive it).")
    + " Indirect expenses come from Operating (× 12, growing yearly) and Pre-Operating (year 1 only) categories ticked **Add to P&L**. "
    "Depreciation comes from Fixed Assets. ROI = PAT ÷ grand total capital."
)

with h2.popover("✏️ Edit", width="stretch"):
    with st.form("pl_edit"):
        st.markdown("**Assumptions**")
        n_years = st.number_input("Years to project", value=int(settings["years"]), min_value=1, max_value=15)
        tax = st.number_input("Tax rate (%)", value=float(settings["tax_rate_pct"]), min_value=0.0, max_value=100.0)
        mult = st.number_input("Valuation multiple (× PAT)", value=float(settings["valuation_multiple"]), min_value=0.0)
        coco = st.number_input("COCO RS sharing (% of revenue)", value=float(settings["coco_pct"]), min_value=0.0, max_value=100.0)
        direct = st.number_input("Direct expenses (% of revenue, used when no COGS categories)", value=float(settings["direct_expense_pct"]),
                                 min_value=0.0, max_value=100.0, disabled=bool(snap["categories"]["cogs"]))
        st.markdown("**Other income per year (₹)**")
        other = list(settings.get("other_income") or [])
        other_vals = []
        oc = st.columns(4)
        for i, y in enumerate(years):
            other_vals.append(oc[i % 4].number_input(y, value=float(num(other[i]) if i < len(other) else 0.0), min_value=0.0, key=f"oi_{i}"))
        st.markdown("**Yearly growth % of indirect expenses**")
        growth_vals = {}
        for c in snap["categories"]["operating"]:
            if c.get("add_to_pl"):
                growth_vals[c["id"]] = st.number_input(c["name"], value=float(num(c.get("pl_growth_pct"))), min_value=0.0, step=1.0, key=f"g_{c['id']}")
        if st.form_submit_button("Save", type="primary"):
            for cid, g in growth_vals.items():
                repo.update_category(cid, pl_growth_pct=g)
            save(years=int(n_years), tax_rate_pct=tax, valuation_multiple=mult, coco_pct=coco, direct_expense_pct=direct, other_income=other_vals)
            ui.flash("P&L assumptions saved")
            st.rerun()

st.download_button("Download P&L (CSV)", df.to_csv(index=False).encode(), file_name=f"{model['name']}_profit_and_loss.csv", mime="text/csv")
