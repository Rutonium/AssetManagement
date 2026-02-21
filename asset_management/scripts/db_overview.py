#!/usr/bin/env python3
"""Database overview and integrity checks for AssetManagement."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


EXPECTED_TABLES = [
    "Tools",
    "Categories",
    "Warehouses",
    "WarehouseLocations",
    "Rental",
    "RentalItems",
    "Service",
    "Certificates",
    "ToolLocations",
    "ToolInstances",
    "AuditLogs",
    "NotificationQueue",
    "AtlasUsers",
]

EXPECTED_COLUMNS: dict[str, list[str]] = {
    "ToolInstances": [
        "ToolInstanceID",
        "ToolID",
        "SerialNumber",
        "InstanceNumber",
        "Status",
        "Condition",
        "WarehouseID",
        "LocationCode",
        "RequiresCertification",
        "CalibrationInterval",
        "LastCalibration",
        "NextCalibration",
        "ImagePath",
        "CreatedDate",
        "UpdatedDate",
    ],
    "RentalItems": ["RentalItemID", "RentalID", "ToolID", "ToolInstanceID", "Quantity"],
    "Rental": ["RentalID", "RentalNumber", "Status", "EmployeeID", "LossAmount", "LossCalculatedAt", "LossReason"],
    "AuditLogs": ["AuditID", "EntityType", "EntityID", "Action", "Details", "UserID", "CreatedAt"],
    "AtlasUsers": [
        "EmployeeID",
        "AssetManagementRole",
        "AssetManagementRights",
        "TimeAppRights",
        "PeoplePlannerRights",
        "PasswordHash",
        "PasswordSalt",
        "PasswordUpdatedAt",
        "IsActive",
        "CreatedAt",
        "UpdatedAt",
    ],
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _get_engine(db_url: str) -> Engine:
    return create_engine(db_url, pool_pre_ping=True, future=True)


def _scalar(engine: Engine, sql: str, params: dict | None = None):
    with engine.connect() as conn:
        return conn.execute(text(sql), params or {}).scalar()


def _rows(engine: Engine, sql: str, params: dict | None = None):
    with engine.connect() as conn:
        return conn.execute(text(sql), params or {}).all()


def _table_exists(engine: Engine, table_name: str) -> bool:
    sql = """
        SELECT 1
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = :table_name
    """
    return bool(_scalar(engine, sql, {"table_name": table_name}))


def _column_names(engine: Engine, table_name: str) -> set[str]:
    sql = """
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo' AND TABLE_NAME = :table_name
    """
    return {str(row[0]) for row in _rows(engine, sql, {"table_name": table_name})}


def _index_rows(engine: Engine, table_name: str):
    sql = """
        SELECT i.name,
               i.is_unique,
               STRING_AGG(c.name, ',') WITHIN GROUP (ORDER BY ic.key_ordinal) AS cols
        FROM sys.indexes i
        JOIN sys.index_columns ic
          ON ic.object_id = i.object_id AND ic.index_id = i.index_id
        JOIN sys.columns c
          ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE i.object_id = OBJECT_ID(:qualified_table)
          AND i.name IS NOT NULL
          AND i.is_hypothetical = 0
        GROUP BY i.name, i.is_unique
        ORDER BY i.name
    """
    return _rows(engine, sql, {"qualified_table": f"dbo.{table_name}"})


def _run_existence_checks(engine: Engine) -> list[CheckResult]:
    results: list[CheckResult] = []
    for table in EXPECTED_TABLES:
        exists = _table_exists(engine, table)
        results.append(CheckResult(f"table:{table}", exists, "present" if exists else "missing"))
    return results


def _run_column_checks(engine: Engine) -> list[CheckResult]:
    results: list[CheckResult] = []
    for table, expected in EXPECTED_COLUMNS.items():
        if not _table_exists(engine, table):
            results.append(CheckResult(f"columns:{table}", False, "table missing"))
            continue
        actual = _column_names(engine, table)
        missing = [name for name in expected if name not in actual]
        results.append(
            CheckResult(
                f"columns:{table}",
                not missing,
                "ok" if not missing else f"missing={','.join(missing)}",
            )
        )
    return results


def _run_integrity_checks(engine: Engine) -> list[CheckResult]:
    checks: list[CheckResult] = []

    if _table_exists(engine, "ToolInstances"):
        duplicate_instance = _scalar(
            engine,
            """
            SELECT COUNT(*)
            FROM (
                SELECT ToolID, InstanceNumber
                FROM dbo.ToolInstances
                GROUP BY ToolID, InstanceNumber
                HAVING COUNT(*) > 1
            ) d
            """,
        )
        checks.append(
            CheckResult(
                "toolinstances:duplicate_tool_instance_number",
                int(duplicate_instance or 0) == 0,
                f"count={int(duplicate_instance or 0)}",
            )
        )

        null_instance = _scalar(
            engine,
            "SELECT COUNT(*) FROM dbo.ToolInstances WHERE InstanceNumber IS NULL",
        )
        checks.append(
            CheckResult(
                "toolinstances:null_instance_number",
                int(null_instance or 0) == 0,
                f"count={int(null_instance or 0)}",
            )
        )

        orphan_tool = _scalar(
            engine,
            """
            SELECT COUNT(*)
            FROM dbo.ToolInstances ti
            LEFT JOIN dbo.Tools t ON t.ToolID = ti.ToolID
            WHERE t.ToolID IS NULL
            """,
        )
        checks.append(
            CheckResult(
                "toolinstances:orphan_toolid",
                int(orphan_tool or 0) == 0,
                f"count={int(orphan_tool or 0)}",
            )
        )

    if _table_exists(engine, "RentalItems") and _table_exists(engine, "ToolInstances"):
        orphan_instance_fk = _scalar(
            engine,
            """
            SELECT COUNT(*)
            FROM dbo.RentalItems ri
            LEFT JOIN dbo.ToolInstances ti ON ti.ToolInstanceID = ri.ToolInstanceID
            WHERE ri.ToolInstanceID IS NOT NULL AND ti.ToolInstanceID IS NULL
            """,
        )
        checks.append(
            CheckResult(
                "rentalitems:orphan_toolinstanceid",
                int(orphan_instance_fk or 0) == 0,
                f"count={int(orphan_instance_fk or 0)}",
            )
        )

    return checks


def _print_results(title: str, rows: Iterable[CheckResult]) -> None:
    _print_section(title)
    for row in rows:
        status = "OK" if row.ok else "FAIL"
        print(f"[{status}] {row.name} :: {row.detail}")


def _print_row_counts(engine: Engine) -> None:
    _print_section("Row Counts")
    for table in EXPECTED_TABLES:
        if not _table_exists(engine, table):
            print(f"{table}: missing")
            continue
        count = _scalar(engine, f"SELECT COUNT(*) FROM dbo.{table}")
        print(f"{table}: {int(count or 0)}")


def _print_index_summary(engine: Engine) -> None:
    _print_section("Index Summary (key tables)")
    for table in ["ToolInstances", "RentalItems", "AuditLogs", "AtlasUsers"]:
        if not _table_exists(engine, table):
            print(f"{table}: missing")
            continue
        print(f"{table}:")
        for name, is_unique, cols in _index_rows(engine, table):
            print(f"  - {name} unique={bool(is_unique)} cols={cols}")


def _print_samples(engine: Engine, sample_size: int) -> None:
    _print_section("Sample Values")
    sample_size = max(1, sample_size)

    if _table_exists(engine, "ToolInstances"):
        rows = _rows(
            engine,
            """
            SELECT TOP (:n) ToolInstanceID, ToolID, InstanceNumber, SerialNumber, Status
            FROM dbo.ToolInstances
            ORDER BY ToolInstanceID DESC
            """,
            {"n": sample_size},
        )
        print("ToolInstances (recent):")
        for row in rows:
            print(f"  - {tuple(row)}")

    if _table_exists(engine, "AuditLogs"):
        rows = _rows(
            engine,
            """
            SELECT TOP (:n) AuditID, EntityType, Action, UserID, CreatedAt
            FROM dbo.AuditLogs
            ORDER BY AuditID DESC
            """,
            {"n": sample_size},
        )
        print("AuditLogs (recent):")
        for row in rows:
            print(f"  - {tuple(row)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AssetManagement DB overview")
    parser.add_argument("--db-url", default=os.environ.get("ASSET_MANAGEMENT_DB_URL", ""))
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()

    db_url = (args.db_url or "").strip()
    if not db_url:
        print("ASSET_MANAGEMENT_DB_URL is not set. Provide --db-url or export env first.")
        return 2

    try:
        engine = _get_engine(db_url)
        # Force a quick connectivity check first.
        _scalar(engine, "SELECT 1")
    except Exception as exc:
        print(f"Could not connect to DB: {exc}")
        return 3

    _print_results("Table Existence", _run_existence_checks(engine))
    _print_results("Column Checks", _run_column_checks(engine))
    _print_results("Integrity Checks", _run_integrity_checks(engine))
    _print_row_counts(engine)
    _print_index_summary(engine)
    _print_samples(engine, args.samples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
