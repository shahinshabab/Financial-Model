"""Configuration helpers.

Every credential is read from Streamlit secrets (``.streamlit/secrets.toml``)
first and then from environment variables. Nothing is hardcoded.
"""

from __future__ import annotations

import os
from typing import Any

import streamlit as st


def _is_placeholder(value: Any) -> bool:
    """True for empty values and the example placeholders (YOUR-..., sk-...)."""
    if value in (None, ""):
        return True
    s = str(value).strip()
    return s.upper().startswith("YOUR-") or "YOUR-PROJECT" in s.upper() or s in ("sk-...", "sk-")


def get_secret(name: str, default: Any = None) -> Any:
    try:
        if name in st.secrets:
            value = st.secrets[name]
            if not _is_placeholder(value):
                return value
    except Exception:  # no secrets.toml present
        pass
    value = os.environ.get(name)
    return default if _is_placeholder(value) else value


def supabase_configured() -> bool:
    return bool(get_secret("SUPABASE_URL") and get_secret("SUPABASE_KEY"))


def openai_configured() -> bool:
    return bool(get_secret("OPENAI_API_KEY"))
