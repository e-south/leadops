from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from openpyxl import Workbook

from crm.store.sqlite import SqliteStore

TABLES = [
    "organizations",
    "people",
    "sponsor_opps",
    "campaigns",
    "campaign_members",
    "touches",
    "tasks",
]


def export_excel(store: SqliteStore, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    wb.remove(wb.active)

    for table in TABLES:
        rows = store.fetch_all(f"SELECT * FROM {table}")
        ws = wb.create_sheet(title=table)
        _write_sheet(ws, rows)

    wb.save(out_path)


def export_csv_tables(store: SqliteStore, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        rows = store.fetch_all(f"SELECT * FROM {table}")
        if not rows:
            headers: list[str] = []
        else:
            headers = list(rows[0].keys())
        csv_path = out_dir / f"{table}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            for row in rows:
                writer.writerow([row[h] for h in headers])


def _write_sheet(ws, rows: Iterable) -> None:
    rows = list(rows)
    if not rows:
        return
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row[h] for h in headers])
