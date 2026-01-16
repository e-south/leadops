from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TYPE_MAP = {
    "uuid": "TEXT",
    "text": "TEXT",
    "number": "REAL",
    "datetime": "TEXT",
    "date": "TEXT",
    "enum": "TEXT",
    "bool": "INTEGER",
}


@dataclass(frozen=True)
class Schema:
    version: int
    enums: dict[str, list[str]]
    tables: dict[str, Any]


class SchemaError(RuntimeError):
    pass


def load_schema(schema_path: Path) -> Schema:
    data = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    version = data.get("version", 1)
    enums = data.get("enums", {})
    tables = data.get("tables", {})
    if not isinstance(tables, dict):
        raise SchemaError("Schema tables must be a mapping.")
    return Schema(version=version, enums=enums, tables=tables)


def apply_schema(conn, schema_path: Path) -> None:
    schema = load_schema(schema_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS __schema_meta (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )

    for table_name, table_def in schema.tables.items():
        _create_table(conn, table_name, table_def)
        _create_indexes(conn, table_name, table_def)

    conn.execute(
        "INSERT OR REPLACE INTO __schema_meta (version, applied_at) VALUES (?, datetime('now'))",
        (schema.version,),
    )
    conn.commit()


def _create_table(conn, table_name: str, table_def: dict[str, Any]) -> None:
    fields = table_def.get("fields")
    if not isinstance(fields, dict):
        raise SchemaError(f"Table {table_name} fields must be a mapping.")

    primary_key = table_def.get("primary_key")
    columns: list[str] = []
    foreign_keys: list[str] = []

    for field_name, spec in fields.items():
        column = _column_sql(field_name, spec, primary_key)
        columns.append(column)
        ref = spec.get("ref") if isinstance(spec, dict) else None
        if ref:
            ref_table, ref_field = ref.split(".")
            foreign_keys.append(f"FOREIGN KEY ({field_name}) REFERENCES {ref_table}({ref_field})")

    if isinstance(primary_key, list):
        columns.append(f"PRIMARY KEY ({', '.join(primary_key)})")

    columns.extend(foreign_keys)
    ddl = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns)});"
    conn.execute(ddl)


def _column_sql(field_name: str, spec: dict[str, Any], primary_key: str | list[str]) -> str:
    field_type = spec.get("type")
    if field_type not in TYPE_MAP:
        raise SchemaError(f"Unknown field type {field_type} for {field_name}.")
    sql_type = TYPE_MAP[field_type]
    required = spec.get("required", False)
    parts = [field_name, sql_type]
    if required:
        parts.append("NOT NULL")
    if isinstance(primary_key, str) and field_name == primary_key:
        parts.append("PRIMARY KEY")
    return " ".join(parts)


def _create_indexes(conn, table_name: str, table_def: dict[str, Any]) -> None:
    indexes = table_def.get("indexes") or []
    for index_fields in indexes:
        if not isinstance(index_fields, list) or not index_fields:
            continue
        idx_name = f"idx_{table_name}_{'_'.join(index_fields)}"
        cols = ", ".join(index_fields)
        conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} ({cols});")
