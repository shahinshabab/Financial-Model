"""Number formatting (Indian digit grouping: 25,20,000.00)."""

from __future__ import annotations


def indian_group(n: float, decimals: int = 2) -> str:
    neg = n < 0
    s = f"{abs(n):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    out = whole + (f".{frac}" if decimals else "")
    return f"-{out}" if neg else out


def inr(n, decimals: int = 2) -> str:
    try:
        return f"₹ {indian_group(float(n or 0), decimals)}"
    except (TypeError, ValueError):
        return "₹ 0.00"


def pct(n, decimals: int = 2) -> str:
    try:
        return f"{float(n or 0):.{decimals}f}%"
    except (TypeError, ValueError):
        return "0%"
