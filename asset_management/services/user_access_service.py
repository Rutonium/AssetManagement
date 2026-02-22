from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
import base64
import hmac
from pathlib import Path
from typing import Any
import os


DEFAULT_PASSWORD = "1234"
SESSION_TTL_SECONDS = 60 * 60 * 12
DEFAULT_ROLE = "Admin"

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

_BASE_DIR = Path(__file__).resolve().parent.parent
_DATA_DIR = _BASE_DIR / "data"
_STORE_PATH = _DATA_DIR / "user_access.json"
_REVOKED_TOKENS_PATH = _DATA_DIR / "revoked_sessions.json"
_LOCK = threading.Lock()
_SESSIONS: dict[str, dict[str, Any]] = {}


def _require_session_secret() -> bytes:
    raw = (os.environ.get("SESSION_SIGNING_SECRET") or "").strip()
    if len(raw) < 32:
        raise RuntimeError("SESSION_SIGNING_SECRET must be set and at least 32 characters long.")
    return raw.encode("utf-8")


_SESSION_SECRET = _require_session_secret()


def _ensure_data_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


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


def _load_store_unlocked() -> dict[str, Any]:
    _ensure_data_dir()
    if not _STORE_PATH.exists():
        return {"users": {}}
    try:
        payload = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {"users": {}}
    if not isinstance(payload, dict):
        return {"users": {}}
    if not isinstance(payload.get("users"), dict):
        payload["users"] = {}
    return payload


def _save_store_unlocked(store: dict[str, Any]) -> None:
    _ensure_data_dir()
    _STORE_PATH.write_text(json.dumps(store, ensure_ascii=True, indent=2), encoding="utf-8")


def _load_revoked_tokens_unlocked() -> dict[str, float]:
    _ensure_data_dir()
    if not _REVOKED_TOKENS_PATH.exists():
        return {}
    try:
        payload = json.loads(_REVOKED_TOKENS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, float] = {}
    for token, expires_at in payload.items():
        try:
            out[str(token)] = float(expires_at)
        except (TypeError, ValueError):
            continue
    return out


def _save_revoked_tokens_unlocked(tokens: dict[str, float]) -> None:
    _ensure_data_dir()
    _REVOKED_TOKENS_PATH.write_text(json.dumps(tokens, ensure_ascii=True, indent=2), encoding="utf-8")


def get_user_record(employee_id: int) -> dict[str, Any]:
    employee_key = str(int(employee_id))
    with _LOCK:
        store = _load_store_unlocked()
        raw_user = store.get("users", {}).get(employee_key) or {}
    role = _normalize_role(raw_user.get("role"))
    return {
        "employeeID": int(employee_id),
        "role": role,
        "rights": _normalize_rights(raw_user.get("rights"), role),
        "hasCustomPassword": bool(raw_user.get("passwordHash")),
    }


def list_user_records(employee_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    for row in employee_rows:
        try:
            employee_id = int(row.get("normalizedNumber") or row.get("employeeID") or 0)
        except (TypeError, ValueError):
            continue
        if employee_id <= 0:
            continue
        access = get_user_record(employee_id)
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
                "hasCustomPassword": access["hasCustomPassword"],
            }
        )
    users.sort(key=lambda item: (item["name"].lower(), item["employeeID"]))
    return users


def update_user_record(
    employee_id: int,
    *,
    role: str | None = None,
    rights: dict[str, Any] | None = None,
    password: str | None = None,
    reset_password: bool = False,
) -> dict[str, Any]:
    employee_key = str(int(employee_id))
    with _LOCK:
        store = _load_store_unlocked()
        users = store.setdefault("users", {})
        existing = users.get(employee_key) or {}

        current_role = _normalize_role(existing.get("role"))
        next_role = _normalize_role(role if role is not None else current_role)
        next_rights = _normalize_rights(rights if rights is not None else existing.get("rights"), next_role)
        existing["role"] = next_role
        existing["rights"] = next_rights

        if reset_password:
            existing.pop("passwordHash", None)
            existing.pop("passwordSalt", None)
            existing.pop("passwordUpdatedAt", None)
        elif password is not None:
            trimmed = str(password).strip()
            if len(trimmed) < 4:
                raise ValueError("Password must be at least 4 characters.")
            salt = secrets.token_hex(16)
            existing["passwordSalt"] = salt
            existing["passwordHash"] = _password_hash(trimmed, salt)
            existing["passwordUpdatedAt"] = int(time.time())

        users[employee_key] = existing
        _save_store_unlocked(store)

    return get_user_record(int(employee_id))


def verify_password(employee_id: int, pin_code: str) -> bool:
    candidate = (pin_code or "").strip()
    if len(candidate) < 4:
        return False
    employee_key = str(int(employee_id))
    with _LOCK:
        store = _load_store_unlocked()
        existing = store.get("users", {}).get(employee_key) or {}
        stored_hash = existing.get("passwordHash")
        stored_salt = existing.get("passwordSalt")

    if not stored_hash or not stored_salt:
        return candidate == DEFAULT_PASSWORD
    return _password_hash(candidate, stored_salt) == stored_hash


def create_session(payload: dict[str, Any]) -> str:
    expires_at = time.time() + SESSION_TTL_SECONDS
    session_payload = dict(payload)
    session_payload["expiresAt"] = expires_at
    body = json.dumps(session_payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(body).decode("ascii").rstrip("=")
    signature = hmac.new(_SESSION_SECRET, encoded.encode("ascii"), hashlib.sha256).digest()
    encoded_sig = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    token = f"{encoded}.{encoded_sig}"
    with _LOCK:
        _SESSIONS[token] = session_payload
    return token


def get_session(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    now = time.time()
    try:
        encoded, encoded_sig = token.split(".", 1)
        expected_sig = hmac.new(_SESSION_SECRET, encoded.encode("ascii"), hashlib.sha256).digest()
        supplied_sig = base64.urlsafe_b64decode(encoded_sig + "=" * (-len(encoded_sig) % 4))
        if not hmac.compare_digest(expected_sig, supplied_sig):
            return None
        payload_raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        decoded_session = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return None

    if not isinstance(decoded_session, dict):
        return None

    expires_at = float(decoded_session.get("expiresAt") or 0.0)
    if now >= expires_at:
        with _LOCK:
            _SESSIONS.pop(token, None)
        return None

    with _LOCK:
        revoked = _load_revoked_tokens_unlocked()
        changed = False
        for revoked_token, revoked_exp in list(revoked.items()):
            if now >= float(revoked_exp):
                revoked.pop(revoked_token, None)
                changed = True
        if token in revoked:
            if changed:
                _save_revoked_tokens_unlocked(revoked)
            _SESSIONS.pop(token, None)
            return None
        if changed:
            _save_revoked_tokens_unlocked(revoked)

        # Cache for this process; cross-process validation remains token-based.
        _SESSIONS[token] = decoded_session
        return dict(decoded_session)


def remove_session(token: str | None) -> None:
    if not token:
        return
    with _LOCK:
        _SESSIONS.pop(token, None)
        now = time.time()
        revoked = _load_revoked_tokens_unlocked()
        try:
            encoded = token.split(".", 1)[0]
            payload_raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            decoded = json.loads(payload_raw.decode("utf-8"))
            expires_at = float(decoded.get("expiresAt") or 0.0)
        except Exception:
            expires_at = now + SESSION_TTL_SECONDS
        if expires_at <= now:
            return
        revoked[token] = expires_at
        _save_revoked_tokens_unlocked(revoked)
