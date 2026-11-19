"""Configuration helpers.

Every credential is read from Streamlit secrets (``.streamlit/secrets.toml``)
first and then from environment variables. Nothing is hardcoded.
"""

from __future__ import annotations

import os
from typing import Any

import streamlit as st


def get_secret(name: str, default: Any = None) -> Any:
    try:
        if name in st.secrets:
            value = st.secrets[name]
            if value not in (None, ""):
                return value
    except Exception:  # no secrets.toml present
        pass
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def supabase_configured() -> bool:
    return bool(get_secret("SUPABASE_URL") and get_secret("SUPABASE_KEY"))


def openai_configured() -> bool:
    return bool(get_secret("OPENAI_API_KEY"))
