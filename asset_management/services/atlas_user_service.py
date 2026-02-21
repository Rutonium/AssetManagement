from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


DEFAULT_PASSWORD = "1234"
DEFAULT_ROLE = "User"

RIGHTS_BY_ROLE = {
    "Admin": {
        "manageUsers": True,
        "manageRentals": True,
        "manageWarehouse": True,
        "manageEquipment": True,
        "checkout": True,
    },
    "User": {
        "manageUsers": False,
        "manageRentals": False,
        "manageWarehouse": False,
        "manageEquipment": False,
        "checkout": True,
    },
}


def _normalize_role(raw_role: str | None) -> str:
    role = (raw_role or "").strip()
    if role in RIGHTS_BY_ROLE:
        return role
    return DEFAULT_ROLE


def _normalize_rights(raw_rights: dict[str, Any] | None, role: str) -> dict[str, bool]:
    baseline = dict(RIGHTS_BY_ROLE.get(role, RIGHTS_BY_ROLE[DEFAULT_ROLE]))
    if not isinstance(raw_rights, dict):
        return baseline
    for key in list(baseline.keys()):
        if key in raw_rights:
            baseline[key] = bool(raw_rights.get(key))
    return baseline


def _password_hash(password: str, salt: str) -> str:
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    )
    return raw.hex()


def _to_json(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    as_text = str(value).strip()
    return as_text or None


def _from_json_dict(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fetch_atlas_user_row(db: Session, employee_id: int) -> dict[str, Any] | None:
    try:
        row = db.execute(
            text(
                """
                SELECT
                    EmployeeID,
                    AssetManagementRole,
                    AssetManagementRights,
                    TimeAppRights,
                    PeoplePlannerRights,
                    PasswordHash,
                    PasswordSalt
                FROM dbo.AtlasUsers
                WHERE EmployeeID = :employee_id
                """
            ),
            {"employee_id": int(employee_id)},
        ).mappings().first()
    except Exception:
        return None
    return dict(row) if row else None


def get_user_record(db: Session, employee_id: int) -> dict[str, Any]:
    row = _fetch_atlas_user_row(db, int(employee_id))
    if not row:
        role = DEFAULT_ROLE
        rights = _normalize_rights(None, role)
        return {
            "employeeID": int(employee_id),
            "role": role,
            "rights": rights,
            "assetManagementRights": rights,
            "timeAppRights": {},
            "peoplePlannerRights": {},
            "hasCustomPassword": False,
            "isProvisioned": False,
        }

    role = _normalize_role(row.get("AssetManagementRole"))
    asset_rights = _normalize_rights(_from_json_dict(row.get("AssetManagementRights")), role)
    return {
        "employeeID": int(employee_id),
        "role": role,
        "rights": asset_rights,
        "assetManagementRights": asset_rights,
        "timeAppRights": _from_json_dict(row.get("TimeAppRights")),
        "peoplePlannerRights": _from_json_dict(row.get("PeoplePlannerRights")),
        "hasCustomPassword": bool(row.get("PasswordHash")),
        "isProvisioned": True,
    }


def list_user_records(db: Session, employee_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    for row in employee_rows:
        try:
            employee_id = int(row.get("normalizedNumber") or row.get("employeeID") or 0)
        except (TypeError, ValueError):
            continue
        if employee_id <= 0:
            continue
        access = get_user_record(db, employee_id)
        users.append(
            {
                "employeeID": employee_id,
                "employeeNumber": row.get("number") or str(employee_id),
                "name": row.get("name") or "",
                "initials": row.get("initials") or "",
                "displayName": row.get("displayName") or row.get("name") or str(employee_id),
                "departmentCode": row.get("departmentCode") or "",
                "role": access["role"],
                "rights": access["rights"],
                "assetManagementRights": access["assetManagementRights"],
                "timeAppRights": access["timeAppRights"],
                "peoplePlannerRights": access["peoplePlannerRights"],
                "hasCustomPassword": access["hasCustomPassword"],
                "isProvisioned": access["isProvisioned"],
            }
        )
    users.sort(key=lambda item: (item["name"].lower(), item["employeeID"]))
    return users


def list_provisioned_users(db: Session) -> list[dict[str, Any]]:
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    EmployeeID,
                    AssetManagementRole,
                    AssetManagementRights,
                    TimeAppRights,
                    PeoplePlannerRights,
                    PasswordHash
                FROM dbo.AtlasUsers
                ORDER BY EmployeeID
                """
            )
        ).mappings().all()
    except Exception:
        return []

    users: list[dict[str, Any]] = []
    for row in rows:
        employee_id = int(row.get("EmployeeID") or 0)
        if employee_id <= 0:
            continue
        role = _normalize_role(row.get("AssetManagementRole"))
        rights = _normalize_rights(_from_json_dict(row.get("AssetManagementRights")), role)
        users.append(
            {
                "employeeID": employee_id,
                "employeeNumber": str(employee_id),
                "name": "",
                "initials": "",
                "displayName": f"Employee #{employee_id}",
                "departmentCode": "",
                "role": role,
                "rights": rights,
                "assetManagementRights": rights,
                "timeAppRights": _from_json_dict(row.get("TimeAppRights")),
                "peoplePlannerRights": _from_json_dict(row.get("PeoplePlannerRights")),
                "hasCustomPassword": bool(row.get("PasswordHash")),
                "isProvisioned": True,
            }
        )
    return users


def create_user_record(
    db: Session,
    *,
    employee_id: int,
    role: str | None = None,
    asset_management_rights: dict[str, Any] | None = None,
    timeapp_rights: dict[str, Any] | None = None,
    peopleplanner_rights: dict[str, Any] | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    existing = _fetch_atlas_user_row(db, int(employee_id))
    if existing:
        raise ValueError("Atlas user already exists.")

    next_role = _normalize_role(role)
    next_rights = _normalize_rights(asset_management_rights, next_role)
    password_hash = None
    password_salt = None
    password_updated_at = None
    if password is not None and str(password).strip():
        trimmed = str(password).strip()
        if len(trimmed) < 4:
            raise ValueError("Password must be at least 4 characters.")
        password_salt = secrets.token_hex(16)
        password_hash = _password_hash(trimmed, password_salt)
        password_updated_at = int(time.time())

    try:
        db.execute(
            text(
                """
                INSERT INTO dbo.AtlasUsers (
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
                ) VALUES (
                    :employee_id,
                    :role,
                    :asset_rights,
                    :timeapp_rights,
                    :peopleplanner_rights,
                    :password_hash,
                    :password_salt,
                    :password_updated_at,
                    SYSUTCDATETIME(),
                    SYSUTCDATETIME()
                )
                """
            ),
            {
                "employee_id": int(employee_id),
                "role": next_role,
                "asset_rights": _to_json(next_rights),
                "timeapp_rights": _to_json(timeapp_rights or {}),
                "peopleplanner_rights": _to_json(peopleplanner_rights or {}),
                "password_hash": password_hash,
                "password_salt": password_salt,
                "password_updated_at": password_updated_at,
            },
        )
    except Exception as exc:
        db.rollback()
        raise ValueError("AtlasUsers table unavailable. Run SQL migration 20260221_1605_atlas_users.sql.") from exc
    db.commit()
    return get_user_record(db, int(employee_id))


def update_user_record(
    db: Session,
    employee_id: int,
    *,
    role: str | None = None,
    rights: dict[str, Any] | None = None,
    timeapp_rights: dict[str, Any] | None = None,
    peopleplanner_rights: dict[str, Any] | None = None,
    password: str | None = None,
    reset_password: bool = False,
) -> dict[str, Any]:
    current = _fetch_atlas_user_row(db, int(employee_id))
    current_role = _normalize_role(current.get("AssetManagementRole") if current else None)
    next_role = _normalize_role(role if role is not None else current_role)
    next_rights = _normalize_rights(
        rights if rights is not None else _from_json_dict(current.get("AssetManagementRights") if current else None),
        next_role,
    )

    next_timeapp = timeapp_rights if timeapp_rights is not None else _from_json_dict(current.get("TimeAppRights") if current else None)
    next_peopleplanner = (
        peopleplanner_rights
        if peopleplanner_rights is not None
        else _from_json_dict(current.get("PeoplePlannerRights") if current else None)
    )

    password_hash = current.get("PasswordHash") if current else None
    password_salt = current.get("PasswordSalt") if current else None
    password_updated_at = None

    if reset_password:
        password_hash = None
        password_salt = None
    elif password is not None:
        trimmed = str(password).strip()
        if len(trimmed) < 4:
            raise ValueError("Password must be at least 4 characters.")
        password_salt = secrets.token_hex(16)
        password_hash = _password_hash(trimmed, password_salt)
        password_updated_at = int(time.time())

    try:
        db.execute(
            text(
                """
                MERGE dbo.AtlasUsers AS target
                USING (SELECT :employee_id AS EmployeeID) AS source
                ON target.EmployeeID = source.EmployeeID
                WHEN MATCHED THEN UPDATE SET
                    AssetManagementRole = :role,
                    AssetManagementRights = :asset_rights,
                    TimeAppRights = :timeapp_rights,
                    PeoplePlannerRights = :peopleplanner_rights,
                    PasswordHash = :password_hash,
                    PasswordSalt = :password_salt,
                    PasswordUpdatedAt = COALESCE(:password_updated_at, target.PasswordUpdatedAt),
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
                        :timeapp_rights,
                        :peopleplanner_rights,
                        :password_hash,
                        :password_salt,
                        :password_updated_at,
                        SYSUTCDATETIME(),
                        SYSUTCDATETIME()
                    );
                """
            ),
            {
                "employee_id": int(employee_id),
                "role": next_role,
                "asset_rights": _to_json(next_rights),
                "timeapp_rights": _to_json(next_timeapp),
                "peopleplanner_rights": _to_json(next_peopleplanner),
                "password_hash": password_hash,
                "password_salt": password_salt,
                "password_updated_at": password_updated_at,
            },
        )
    except Exception as exc:
        db.rollback()
        raise ValueError("AtlasUsers table unavailable. Run SQL migration 20260221_1605_atlas_users.sql.") from exc
    db.commit()
    return get_user_record(db, int(employee_id))


def verify_password(db: Session, employee_id: int, pin_code: str) -> bool:
    candidate = (pin_code or "").strip()
    if len(candidate) < 4:
        return False
    row = _fetch_atlas_user_row(db, int(employee_id))
    if not row:
        return candidate == DEFAULT_PASSWORD
    stored_hash = row.get("PasswordHash")
    stored_salt = row.get("PasswordSalt")
    if not stored_hash or not stored_salt:
        return candidate == DEFAULT_PASSWORD
    return _password_hash(candidate, str(stored_salt)) == str(stored_hash)


def delete_user_record(db: Session, employee_id: int) -> bool:
    try:
        result = db.execute(
            text("DELETE FROM dbo.AtlasUsers WHERE EmployeeID = :employee_id"),
            {"employee_id": int(employee_id)},
        )
    except Exception as exc:
        db.rollback()
        raise ValueError("AtlasUsers table unavailable. Run SQL migration 20260221_1605_atlas_users.sql.") from exc
    db.commit()
    return (result.rowcount or 0) > 0
