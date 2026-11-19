import streamlit as st

from fm import charts, ui
from fm.engine import SECTION_LABELS
from fm.fmt import inr

repo, model, snap = ui.page_setup()
ui.show_flash()

clicked = charts.click_bridge()
if clicked and clicked.get("ts") != st.session_state.get("_last_click_ts"):
    st.session_state["_last_click_ts"] = clicked.get("ts")
    target = {"fm:grand": "grand_total", "fm:fixed_asset": "fixed_asset", "fm:pre_operating": "pre_operating", "fm:operating": "operating"}.get(clicked.get("chart"))
    if target:
        ui.go(target)

st.subheader("Capital Structure")
st.markdown("<div class='fm-card-title'>CAPITAL STRUCTURE – GRAND TOTAL OVERVIEW</div>", unsafe_allow_html=True)
capital = ["fixed_asset", "pre_operating", "operating"]
fig = charts.pie([SECTION_LABELS[s] for s in capital], [snap["section_totals"][s] for s in capital], chart_id="grand", height=430, center_title="Grand Total")
charts.show(fig, "pie_grand")
c1, c2, c3 = st.columns([1, 1, 1])
c2.markdown(f"<h3 style='text-align:center;margin:0'>{inr(snap['grand_total'])}</h3>", unsafe_allow_html=True)
if c2.button("View Grand Total Report →", width="stretch", type="primary"):
    ui.go("grand_total")
st.caption("Hover a slice for amount and share, click a slice (or the button) to open its report. Click legend items to hide or show a slice.")

st.divider()
cols = st.columns(3)
for col, section, title in zip(cols, capital, ["FIXED ASSETS", "PRE-OPERATING CAPITAL", "OPERATING CAPITAL"]):
    with col.container(border=True):
        st.markdown(f"<div class='fm-card-title'>{title}</div>", unsafe_allow_html=True)
        cats = snap["categories"][section]
        f = charts.pie([c["name"] for c in cats], [c["total"] for c in cats], chart_id=section, height=340, hole=0.45)
        charts.show(f, f"pie_{section}")
        st.markdown(f"<h4 style='text-align:center;margin:0'>{inr(snap['section_totals'][section])}</h4>", unsafe_allow_html=True)
        if st.button("View Details →", key=f"view_{section}", width="stretch"):
            ui.go(section)

st.divider()
cards = [
    ("📈", "SALES FORECAST", "sales"),
    ("📦", "COGS", "cogs"),
    ("⚙️", "OPEX", "operating"),
    ("💹", "PROFIT & LOSS", "pl"),
    ("💵", "CASH FLOW", "cf"),
    ("🔄", "WORKING CAPITAL", "wc"),
    ("⚖️", "BREAK-EVEN", "be"),
    ("🎯", "KPI DASHBOARD", "kpi"),
]
for row in range(0, len(cards), 4):
    cols = st.columns(4)
    for col, (icon, title, key) in zip(cols, cards[row : row + 4]):
        with col.container(border=True):
            st.markdown(f"<div style='text-align:center;font-size:1.8rem'>{icon}</div><div class='fm-card-title'>{title}</div>", unsafe_allow_html=True)
            if st.button("View Details →", key=f"card_{key}_{title}", width="stretch"):
                ui.go(key)
