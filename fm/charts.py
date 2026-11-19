"""Plotly chart builders + a tiny bridge that turns pie-slice clicks into Streamlit events."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from fm.fmt import inr

# Fixed-order categorical palette (validated for colour-vision deficiency); never cycled.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER_COLOR = "#a3a29c"
MAX_SLICES = 8


def pie(labels: list[str], values: list[float], *, chart_id: str, height: int = 380, hole: float = 0.5, center_title: str = "Total") -> go.Figure:
    """Donut chart: hover shows amount, % share and the chart total; centre shows the total."""
    pairs = [(l, float(v or 0)) for l, v in zip(labels, values)]
    colors = PALETTE[: len(pairs)]
    if len(pairs) > MAX_SLICES:
        head, tail = pairs[: MAX_SLICES - 1], pairs[MAX_SLICES - 1 :]
        pairs = head + [("Other", sum(v for _, v in tail))]
        colors = PALETTE[: MAX_SLICES - 1] + [OTHER_COLOR]
    total = sum(v for _, v in pairs)
    labels = [p[0] for p in pairs]
    values = [p[1] for p in pairs]
    empty = total <= 0
    if empty:
        labels, values, colors = ["No data yet"], [1], ["#e4e3df"]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            name=f"fm:{chart_id}",  # used by the click bridge to know which chart was clicked
            hole=hole,
            sort=False,
            direction="clockwise",
            marker=dict(colors=colors, line=dict(color="#fcfcfb", width=2)),
            textinfo="none" if empty else "percent",
            textposition="inside",
            insidetextorientation="horizontal",
            hovertext=[inr(v) for v in values],
            hovertemplate=(
                "<b>%{label}</b><br>Amount: %{hovertext}<br>Share: %{percent}"
                f"<br>Total: {inr(total)}<br><i>Click to open</i><extra></extra>"
            )
            if not empty
            else "Add categories to see the split<extra></extra>",
        )
    )
    fig.update_layout(
        height=height,
        margin=dict(t=10, b=10, l=10, r=10),
        showlegend=not empty,
        legend=dict(orientation="h", yanchor="top", y=-0.02, xanchor="center", x=0.5),
        annotations=[
            dict(
                text=f"<span style='font-size:12px'>{center_title}</span><br><b>{inr(total)}</b>",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=15),
            )
        ],
        hoverlabel=dict(bgcolor="white", font_size=13),
    )
    return fig


_BRIDGE_JS = """
export default function(component) {
  const { setTriggerValue } = component;
  const attach = () => {
    document.querySelectorAll('.js-plotly-plot').forEach((gd) => {
      if (gd.__fmClick || typeof gd.on !== 'function') return;
      gd.__fmClick = true;
      gd.on('plotly_click', (ev) => {
        const p = ev && ev.points && ev.points[0];
        if (!p || !p.data || !String(p.data.name || '').startsWith('fm:')) return;
        setTriggerValue('clicked', {chart: p.data.name, label: String(p.label), ts: Date.now()});
      });
      gd.style.cursor = 'pointer';
    });
  };
  attach();
  const timer = setInterval(attach, 400);
  return () => clearInterval(timer);
}
"""


@st.cache_resource
def _bridge():
    return st.components.v2.component("fm_plotly_click_bridge", js=_BRIDGE_JS)


def click_bridge(key: str = "fm_click_bridge") -> dict | None:
    """Mount once per page. Returns {'chart': ..., 'label': ...} on the rerun after a slice click."""
    result = _bridge()(key=key, on_clicked_change=lambda: None)
    return getattr(result, "clicked", None)


def show(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, key=key, config={"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]})
