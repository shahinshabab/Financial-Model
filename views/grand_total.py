import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fm import charts, ui
from fm.engine import SECTION_LABELS
from fm.fmt import inr, pct

repo, model, snap = ui.page_setup(["Capital Structure – Grand Total"])

st.subheader("Capital Structure – Grand Total Report")
grand = snap["grand_total"]
capital = ["fixed_asset", "pre_operating", "operating"]

m = st.columns(4)
m[0].metric("Grand Total", inr(grand))
for col, s in zip(m[1:], capital):
    share = snap["section_totals"][s] / grand * 100 if grand else 0
    col.metric(SECTION_LABELS[s], inr(snap["section_totals"][s]), f"{share:.1f}% of total", delta_color="off")

# Sunburst: section -> category, hover shows amount and share of grand total
ids, labels, parents, values = [], [], [], []
for s in capital:
    ids.append(s)
    labels.append(SECTION_LABELS[s])
    parents.append("")
    values.append(snap["section_totals"][s])
    for c in snap["categories"][s]:
        ids.append(c["id"])
        labels.append(c["name"])
        parents.append(s)
        values.append(c["total"])
if grand > 0:
    fig = go.Figure(
        go.Sunburst(
            ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
            marker=dict(colors=[charts.PALETTE[capital.index(p or i)] if (p or i) in capital else "#ccc" for i, p in zip(ids, parents)]),
            customdata=[inr(v) for v in values],
            hovertemplate="<b>%{label}</b><br>Amount: %{customdata}<br>%{percentRoot:.1%} of grand total<br>%{percentParent:.1%} of parent<extra></extra>",
            insidetextorientation="radial",
        )
    )
    fig.update_layout(height=520, margin=dict(t=10, b=10, l=10, r=10))
    st.markdown("<div class='fm-card-title'>BREAKDOWN BY SECTION AND CATEGORY</div>", unsafe_allow_html=True)
    st.caption("Click a section to zoom in, click the centre to zoom out.")
    charts.show(fig, "sunburst")

rows = []
for s in capital:
    for c in snap["categories"][s]:
        rows.append({"Section": SECTION_LABELS[s], "Category": c["name"], "Amount (₹)": c["total"],
                     "% of section": c["total"] / snap["section_totals"][s] * 100 if snap["section_totals"][s] else 0,
                     "% of grand total": c["total"] / grand * 100 if grand else 0})
    rows.append({"Section": SECTION_LABELS[s], "Category": "Section total", "Amount (₹)": snap["section_totals"][s],
                 "% of section": 100 if snap["section_totals"][s] else 0, "% of grand total": snap["section_totals"][s] / grand * 100 if grand else 0})
rows.append({"Section": "GRAND TOTAL", "Category": "", "Amount (₹)": grand, "% of section": None, "% of grand total": 100 if grand else 0})
df = pd.DataFrame(rows)
st.dataframe(
    df.style.format({"Amount (₹)": inr, "% of section": lambda v: "" if pd.isna(v) else pct(v), "% of grand total": pct}),
    hide_index=True, width="stretch", height=min(40 + 35 * len(df), 700),
)
st.download_button("Download CSV", df.to_csv(index=False).encode(), file_name=f"{model['name']}_capital_structure.csv", mime="text/csv")

cols = st.columns(3)
for col, s in zip(cols, capital):
    if col.button(f"Open {SECTION_LABELS[s]} →", width="stretch"):
        ui.go(s)
