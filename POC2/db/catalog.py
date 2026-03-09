"""
db/catalog.py
AI Data Assistant — POC2

Loads the database catalog from config/databases.json and exposes
helper functions used by the DB router and SQL tools.

The catalog is loaded once at import time (module-level singleton).
Databases with "available": false are excluded from LLM routing and
schema discovery — they remain in the file for documentation purposes only.
"""

import json
from pathlib import Path
from typing import Optional
from loguru import logger


# ── Load catalog at import time ───────────────────────────────────────────────

_CATALOG_PATH = Path(__file__).parent.parent / "config" / "databases.json"


def _load_catalog() -> dict:
    if not _CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"Database catalog not found at {_CATALOG_PATH}. "
            "Create config/databases.json before starting the application."
        )
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    logger.info(
        f"[CATALOG] Loaded {len(raw['databases'])} databases from {_CATALOG_PATH}"
    )
    return raw


_raw_catalog = _load_catalog()

# All databases (including unavailable) — used for connection lookups
DATABASES: list[dict] = _raw_catalog["databases"]

# Only available databases — exposed to the LLM router and tools
AVAILABLE_DATABASES: list[dict] = [db for db in DATABASES if db.get("available", True)]

_unavailable_keys = [db["key"] for db in DATABASES if not db.get("available", True)]
if _unavailable_keys:
    logger.info(
        f"[CATALOG] Databases excluded from routing (available=false): {_unavailable_keys}"
    )


# ── Public helpers ────────────────────────────────────────────────────────────

def get_all_database_keys() -> list[str]:
    """Returns the keys of all AVAILABLE databases (routing targets only)."""
    return [db["key"] for db in AVAILABLE_DATABASES]


def get_database_entry(key: str) -> Optional[dict]:
    """
    Returns the catalog entry for a given database key, or None if not found.
    Searches ALL databases including unavailable ones — used for connection
    lookups and administrative checks.
    Key matching is case-insensitive.
    """
    key_lower = key.lower()
    for db in DATABASES:
        if db["key"].lower() == key_lower:
            return db
    return None


def get_available_database_entry(key: str) -> Optional[dict]:
    """
    Returns the catalog entry only if the database key is known AND available.
    Returns None if the key is unknown or if available=false.
    Use this in tools and routing code — never in admin/test utilities.
    """
    entry = get_database_entry(key)
    if entry is None:
        return None
    if not entry.get("available", True):
        logger.warning(
            f"[CATALOG] Database '{key}' is in the catalog but marked available=false. "
            "It cannot be queried until it is marked available."
        )
        return None
    return entry


def get_schemas_for_database(key: str) -> list[str]:
    """Returns the list of allowed schema names for a database key."""
    entry = get_database_entry(key)
    if entry is None:
        return []
    return entry.get("schemas", [])


def build_catalog_context() -> str:
    """
    Builds a concise plain-text description of all AVAILABLE databases
    and their schemas. Injected into the DB router's LLM prompt so the
    model knows what exists before choosing a routing target.

    Format:
        DATABASE: edw_landing
        Description: ...
        Schemas: STDNT (...), EMP (...), ...
        Example questions: ... | ...

        DATABASE: edw_staging
        ...
    """
    lines = []
    for db in AVAILABLE_DATABASES:
        lines.append(f"DATABASE: {db['key']}")
        lines.append(f"Description: {db['description']}")

        schema_parts = []
        for schema_name in db.get("schemas", []):
            schema_desc = db.get("schema_descriptions", {}).get(schema_name, "")
            if schema_desc:
                schema_parts.append(f"{schema_name} ({schema_desc})")
            else:
                schema_parts.append(schema_name)

        if schema_parts:
            lines.append(f"Schemas: {', '.join(schema_parts)}")

        extras = []
        if db.get("dimension_table_note"):
            extras.append(f"Note: {db['dimension_table_note']}")
        if db.get("snapshot_table_note"):
            extras.append(f"Note: {db['snapshot_table_note']}")
        for note in extras:
            lines.append(note)

        examples = db.get("example_questions", [])
        if examples:
            lines.append(f"Example questions: {' | '.join(examples[:2])}")

        lines.append("")  # blank line between databases

    return "\n".join(lines).strip()


def build_schema_filter_sql(schemas: list[str]) -> str:
    """
    Builds the SQL IN clause for filtering INFORMATION_SCHEMA queries to
    only the allowed schemas for a database.

    Returns a fragment like: ('STDNT', 'EMP', 'FIN', 'OTHR', 'dbo')
    """
    quoted = ", ".join(f"'{s}'" for s in schemas)
    return f"({quoted})"
