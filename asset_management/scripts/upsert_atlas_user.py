#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import time

from sqlalchemy import create_engine, text


ADMIN_RIGHTS = {
    "manageUsers": True,
    "manageRentals": True,
    "manageWarehouse": True,
    "manageEquipment": True,
    "checkout": True,
}

USER_RIGHTS = {
    "manageUsers": False,
    "manageRentals": False,
    "manageWarehouse": False,
    "manageEquipment": False,
    "checkout": True,
}


def _password_hash(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    )
    return raw.hex()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create/update one AtlasUsers record directly from terminal.",
    )
    parser.add_argument("--employee-id", type=int, required=True, help="EmployeeID in dbo.AtlasUsers")
    parser.add_argument("--role", choices=["Admin", "User"], default="Admin", help="AssetManagementRole")
    parser.add_argument(
        "--password",
        default=None,
        help="Optional PIN/code to set. Omit to keep existing PIN state.",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Reset to default login code behavior (PasswordHash/PasswordSalt NULL => default 1234).",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("ASSET_MANAGEMENT_DB_URL", "").strip(),
        help="SQLAlchemy DB URL; defaults to ASSET_MANAGEMENT_DB_URL env var.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.employee_id <= 0:
        parser.error("--employee-id must be > 0")
    if not args.db_url:
        parser.error("Missing DB URL. Set ASSET_MANAGEMENT_DB_URL or pass --db-url.")
    if args.password is not None and len(args.password.strip()) < 4:
        parser.error("--password must be at least 4 characters.")
    if args.password is not None and args.reset_password:
        parser.error("Use either --password or --reset-password, not both.")

    rights = ADMIN_RIGHTS if args.role == "Admin" else USER_RIGHTS
    rights_json = json.dumps(rights, ensure_ascii=True)

    if args.reset_password:
        password_hash = None
        password_salt = None
        password_updated_at = None
    elif args.password is not None:
        password_salt = secrets.token_hex(16)
        password_hash = _password_hash(args.password.strip(), password_salt)
        password_updated_at = int(time.time())
    else:
        password_hash = None
        password_salt = None
        password_updated_at = None

    sql = text(
        """
        MERGE dbo.AtlasUsers AS target
        USING (SELECT :employee_id AS EmployeeID) AS source
        ON target.EmployeeID = source.EmployeeID
        WHEN MATCHED THEN UPDATE SET
            AssetManagementRole = :role,
            AssetManagementRights = :asset_rights,
            TimeAppRights = COALESCE(target.TimeAppRights, '{}'),
            PeoplePlannerRights = COALESCE(target.PeoplePlannerRights, '{}'),
            PasswordHash = CASE
                WHEN :set_password = 1 THEN :password_hash
                WHEN :reset_password = 1 THEN NULL
                ELSE target.PasswordHash
            END,
            PasswordSalt = CASE
                WHEN :set_password = 1 THEN :password_salt
                WHEN :reset_password = 1 THEN NULL
                ELSE target.PasswordSalt
            END,
            PasswordUpdatedAt = CASE
                WHEN :set_password = 1 THEN :password_updated_at
                WHEN :reset_password = 1 THEN NULL
                ELSE target.PasswordUpdatedAt
            END,
            UpdatedAt = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (
                EmployeeID,
                AssetManagementRole,
                AssetManagementRights,
                TimeAppRights,
                PeoplePlannerRights,
                PasswordHash,
                PasswordSalt,
                PasswordUpdatedAt,
                CreatedAt,
                UpdatedAt
            )
            VALUES (
                :employee_id,
                :role,
                :asset_rights,
                '{}',
                '{}',
                CASE WHEN :set_password = 1 THEN :password_hash ELSE NULL END,
                CASE WHEN :set_password = 1 THEN :password_salt ELSE NULL END,
                CASE WHEN :set_password = 1 THEN :password_updated_at ELSE NULL END,
                SYSUTCDATETIME(),
                SYSUTCDATETIME()
            );

        SELECT
            EmployeeID,
            AssetManagementRole,
            AssetManagementRights,
            PasswordHash,
            PasswordSalt,
            UpdatedAt
        FROM dbo.AtlasUsers
        WHERE EmployeeID = :employee_id;
        """
    )

    engine = create_engine(args.db_url, pool_pre_ping=True, future=True)
    with engine.begin() as conn:
        row = conn.execute(
            sql,
            {
                "employee_id": args.employee_id,
                "role": args.role,
                "asset_rights": rights_json,
                "set_password": 1 if args.password is not None else 0,
                "reset_password": 1 if args.reset_password else 0,
                "password_hash": password_hash,
                "password_salt": password_salt,
                "password_updated_at": password_updated_at,
            },
        ).mappings().first()

    if not row:
        raise RuntimeError("Upsert finished but no row returned.")

    has_custom_password = bool(row.get("PasswordHash") and row.get("PasswordSalt"))
    print(
        f"OK employee_id={row['EmployeeID']} role={row['AssetManagementRole']} "
        f"has_custom_password={has_custom_password} updated_at={row.get('UpdatedAt')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
