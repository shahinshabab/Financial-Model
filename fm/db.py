"""Data access layer.

``SupabaseRepo`` talks to Supabase (the real backend). ``LocalRepo`` stores the
same tables in a JSON file and is only used for local demos/tests when no
Supabase credentials are configured.

All reads go through a small per-session cache that is cleared after every
write, so pages stay fast while Streamlit reruns the script.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECTIONS = ("fixed_asset", "pre_operating", "operating", "cogs")

CATEGORY_FIELDS = (
    "name",
    "sort_order",
    "add_to_pl",
    "add_to_be",
    "depreciation_years",
    "pl_growth_pct",
    "cogs_percent",
)
ITEM_FIELDS = ("sub_category", "item", "measure_unit", "qty", "unit_cost", "amount", "remarks")
MODEL_FIELDS = ("name", "business_name", "business_description", "start_year")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick(data: dict, allowed: tuple[str, ...]) -> dict:
    return {k: v for k, v in data.items() if k in allowed}


class BaseRepo:
    user_id: str

    # models
    def list_models(self) -> list[dict]: ...
    def get_model(self, model_id: str) -> dict | None: ...
    def create_model(self, **fields) -> dict: ...
    def update_model(self, model_id: str, **fields) -> None: ...
    def delete_model(self, model_id: str) -> None: ...

    # categories
    def list_categories(self, model_id: str, section: str | None = None) -> list[dict]: ...
    def get_category(self, category_id: str) -> dict | None: ...
    def add_category(self, model_id: str, section: str, name: str, **fields) -> dict: ...
    def update_category(self, category_id: str, **fields) -> None: ...
    def delete_category(self, category_id: str) -> None: ...

    # items
    def list_items(self, model_id: str) -> list[dict]: ...
    def add_item(self, model_id: str, category_id: str, **fields) -> dict: ...
    def update_item(self, item_id: str, **fields) -> None: ...
    def delete_item(self, item_id: str) -> None: ...

    # settings
    def get_setting(self, model_id: str, key: str) -> dict: ...
    def save_setting(self, model_id: str, key: str, data: dict) -> None: ...


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
class SupabaseRepo(BaseRepo):
    def __init__(self, client: Any, user_id: str):
        self.sb = client
        self.user_id = user_id

    def _t(self, name: str):
        return self.sb.table(name)

    # models -----------------------------------------------------------------
    def list_models(self) -> list[dict]:
        res = (
            self._t("financial_models")
            .select("*")
            .eq("user_id", self.user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

    def get_model(self, model_id: str) -> dict | None:
        res = (
            self._t("financial_models")
            .select("*")
            .eq("user_id", self.user_id)
            .eq("id", model_id)
            .limit(1)
            .execute()
        )
        return (res.data or [None])[0]

    def create_model(self, **fields) -> dict:
        row = _pick(fields, MODEL_FIELDS) | {"user_id": self.user_id}
        res = self._t("financial_models").insert(row).execute()
        return res.data[0]

    def update_model(self, model_id: str, **fields) -> None:
        self._t("financial_models").update(_pick(fields, MODEL_FIELDS)).eq("user_id", self.user_id).eq(
            "id", model_id
        ).execute()

    def delete_model(self, model_id: str) -> None:
        self._t("financial_models").delete().eq("user_id", self.user_id).eq("id", model_id).execute()

    # categories ---------------------------------------------------------------
    def list_categories(self, model_id: str, section: str | None = None) -> list[dict]:
        q = self._t("categories").select("*").eq("user_id", self.user_id).eq("model_id", model_id)
        if section:
            q = q.eq("section", section)
        res = q.order("sort_order").order("created_at").execute()
        return res.data or []

    def get_category(self, category_id: str) -> dict | None:
        res = (
            self._t("categories")
            .select("*")
            .eq("user_id", self.user_id)
            .eq("id", category_id)
            .limit(1)
            .execute()
        )
        return (res.data or [None])[0]

    def add_category(self, model_id: str, section: str, name: str, **fields) -> dict:
        row = _pick(fields, CATEGORY_FIELDS) | {
            "user_id": self.user_id,
            "model_id": model_id,
            "section": section,
            "name": name,
        }
        res = self._t("categories").insert(row).execute()
        return res.data[0]

    def update_category(self, category_id: str, **fields) -> None:
        self._t("categories").update(_pick(fields, CATEGORY_FIELDS)).eq("user_id", self.user_id).eq(
            "id", category_id
        ).execute()

    def delete_category(self, category_id: str) -> None:
        self._t("categories").delete().eq("user_id", self.user_id).eq("id", category_id).execute()

    # items ------------------------------------------------------------------
    def list_items(self, model_id: str) -> list[dict]:
        res = (
            self._t("category_items")
            .select("*")
            .eq("user_id", self.user_id)
            .eq("model_id", model_id)
            .order("created_at")
            .execute()
        )
        return res.data or []

    def add_item(self, model_id: str, category_id: str, **fields) -> dict:
        row = _pick(fields, ITEM_FIELDS) | {
            "user_id": self.user_id,
            "model_id": model_id,
            "category_id": category_id,
        }
        res = self._t("category_items").insert(row).execute()
        return res.data[0]

    def update_item(self, item_id: str, **fields) -> None:
        self._t("category_items").update(_pick(fields, ITEM_FIELDS)).eq("user_id", self.user_id).eq(
            "id", item_id
        ).execute()

    def delete_item(self, item_id: str) -> None:
        self._t("category_items").delete().eq("user_id", self.user_id).eq("id", item_id).execute()

    # settings ---------------------------------------------------------------
    def get_setting(self, model_id: str, key: str) -> dict:
        res = (
            self._t("model_settings")
            .select("data")
            .eq("user_id", self.user_id)
            .eq("model_id", model_id)
            .eq("key", key)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return dict(rows[0]["data"] or {}) if rows else {}

    def save_setting(self, model_id: str, key: str, data: dict) -> None:
        self._t("model_settings").upsert(
            {"model_id": model_id, "key": key, "user_id": self.user_id, "data": data},
            on_conflict="model_id,key",
        ).execute()


# ---------------------------------------------------------------------------
# Local JSON file (demo mode, no Supabase configured)
# ---------------------------------------------------------------------------
class LocalRepo(BaseRepo):
    _lock = threading.Lock()

    def __init__(self, path: str | Path, user_id: str = "00000000-0000-0000-0000-000000000000"):
        self.path = Path(path)
        self.user_id = user_id
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._write({"financial_models": [], "categories": [], "category_items": [], "model_settings": []})

    def _read(self) -> dict:
        return json.loads(self.path.read_text())

    def _write(self, data: dict) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, default=str))
        tmp.replace(self.path)

    def _mine(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("user_id") == self.user_id]

    # models
    def list_models(self) -> list[dict]:
        rows = self._mine(self._read()["financial_models"])
        return sorted(rows, key=lambda r: r["created_at"], reverse=True)

    def get_model(self, model_id: str) -> dict | None:
        return next((r for r in self.list_models() if r["id"] == model_id), None)

    def create_model(self, **fields) -> dict:
        with self._lock:
            db = self._read()
            row = {
                "id": str(uuid.uuid4()),
                "user_id": self.user_id,
                "name": "",
                "business_name": "",
                "business_description": "",
                "start_year": datetime.now().year,
                "created_at": _now(),
            } | _pick(fields, MODEL_FIELDS)
            db["financial_models"].append(row)
            self._write(db)
            return row

    def _update(self, table: str, row_id: str, fields: dict) -> None:
        with self._lock:
            db = self._read()
            for r in db[table]:
                if r["id"] == row_id and r["user_id"] == self.user_id:
                    r.update(fields)
            self._write(db)

    def update_model(self, model_id: str, **fields) -> None:
        self._update("financial_models", model_id, _pick(fields, MODEL_FIELDS))

    def delete_model(self, model_id: str) -> None:
        with self._lock:
            db = self._read()
            db["financial_models"] = [r for r in db["financial_models"] if r["id"] != model_id]
            for t in ("categories", "category_items", "model_settings"):
                db[t] = [r for r in db[t] if r.get("model_id") != model_id]
            self._write(db)

    # categories
    def list_categories(self, model_id: str, section: str | None = None) -> list[dict]:
        rows = [
            r
            for r in self._mine(self._read()["categories"])
            if r["model_id"] == model_id and (section is None or r["section"] == section)
        ]
        return sorted(rows, key=lambda r: (r.get("sort_order", 0), r["created_at"]))

    def get_category(self, category_id: str) -> dict | None:
        return next((r for r in self._mine(self._read()["categories"]) if r["id"] == category_id), None)

    def add_category(self, model_id: str, section: str, name: str, **fields) -> dict:
        with self._lock:
            db = self._read()
            row = {
                "id": str(uuid.uuid4()),
                "user_id": self.user_id,
                "model_id": model_id,
                "section": section,
                "name": name,
                "sort_order": 0,
                "add_to_pl": False,
                "add_to_be": False,
                "depreciation_years": 0,
                "pl_growth_pct": 0,
                "cogs_percent": 0,
                "created_at": _now(),
            } | _pick(fields, CATEGORY_FIELDS)
            db["categories"].append(row)
            self._write(db)
            return row

    def update_category(self, category_id: str, **fields) -> None:
        self._update("categories", category_id, _pick(fields, CATEGORY_FIELDS))

    def delete_category(self, category_id: str) -> None:
        with self._lock:
            db = self._read()
            db["categories"] = [r for r in db["categories"] if r["id"] != category_id]
            db["category_items"] = [r for r in db["category_items"] if r["category_id"] != category_id]
            self._write(db)

    # items
    def list_items(self, model_id: str) -> list[dict]:
        rows = [r for r in self._mine(self._read()["category_items"]) if r["model_id"] == model_id]
        return sorted(rows, key=lambda r: r["created_at"])

    def add_item(self, model_id: str, category_id: str, **fields) -> dict:
        with self._lock:
            db = self._read()
            row = {
                "id": str(uuid.uuid4()),
                "user_id": self.user_id,
                "model_id": model_id,
                "category_id": category_id,
                "sub_category": "",
                "item": "",
                "measure_unit": "",
                "qty": 1,
                "unit_cost": 0,
                "amount": 0,
                "remarks": "",
                "created_at": _now(),
            } | _pick(fields, ITEM_FIELDS)
            db["category_items"].append(row)
            self._write(db)
            return row

    def update_item(self, item_id: str, **fields) -> None:
        self._update("category_items", item_id, _pick(fields, ITEM_FIELDS))

    def delete_item(self, item_id: str) -> None:
        with self._lock:
            db = self._read()
            db["category_items"] = [r for r in db["category_items"] if r["id"] != item_id]
            self._write(db)

    # settings
    def get_setting(self, model_id: str, key: str) -> dict:
        for r in self._mine(self._read()["model_settings"]):
            if r["model_id"] == model_id and r["key"] == key:
                return dict(r["data"])
        return {}

    def save_setting(self, model_id: str, key: str, data: dict) -> None:
        with self._lock:
            db = self._read()
            for r in db["model_settings"]:
                if r["model_id"] == model_id and r["key"] == key and r["user_id"] == self.user_id:
                    r["data"] = data
                    break
            else:
                db["model_settings"].append(
                    {"model_id": model_id, "key": key, "user_id": self.user_id, "data": data}
                )
            self._write(db)


# ---------------------------------------------------------------------------
# Cache wrapper
# ---------------------------------------------------------------------------
_READS = {"list_models", "get_model", "list_categories", "get_category", "list_items", "get_setting"}


class CachedRepo:
    """Memoises read calls; any write clears the cache."""

    def __init__(self, repo: BaseRepo):
        self._repo = repo
        self._cache: dict[tuple, Any] = {}

    @property
    def user_id(self) -> str:
        return self._repo.user_id

    @property
    def backend(self) -> str:
        return "supabase" if isinstance(self._repo, SupabaseRepo) else "local"

    def clear(self) -> None:
        self._cache.clear()

    def __getattr__(self, name: str):
        fn = getattr(self._repo, name)
        if not callable(fn):
            return fn
        if name in _READS:

            def cached(*args, **kwargs):
                key = (name, args, tuple(sorted(kwargs.items())))
                if key not in self._cache:
                    self._cache[key] = fn(*args, **kwargs)
                value = self._cache[key]
                # hand out copies so callers can't mutate the cache
                if isinstance(value, list):
                    return [dict(v) for v in value]
                if isinstance(value, dict):
                    return json.loads(json.dumps(value, default=str))
                return value

            return cached

        def write(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            finally:
                self._cache.clear()

        return write
