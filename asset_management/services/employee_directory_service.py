from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


class EmployeeDirectoryError(RuntimeError):
    pass


_CACHE_TTL_SECONDS = 300
_EMPLOYEE_CACHE: dict[str, dict[str, str]] = {}
_CACHE_EXPIRES_AT = 0.0


def _require_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise EmployeeDirectoryError(f"Missing required environment variable: {name}")
    return value


def _build_auth_header_value(token: str, scheme: str) -> str:
    if not scheme:
        return token
    return f"{scheme} {token}"


def _normalize_employee_number(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise ValueError("employee number is empty")
    if not value.isdigit():
        raise ValueError("employee number must be numeric for current system")
    return str(int(value))


def _to_employee_entry(item: dict[str, Any]) -> dict[str, str] | None:
    number_raw = str(item.get("number") or "").strip()
    name = str(item.get("name") or "").strip()
    initials = str(item.get("initials") or "").strip()
    email = str(item.get("eMail") or "").strip()
    department_code = str(item.get("departmentCode") or "").strip()
    if not number_raw or not name:
        return None
    try:
        normalized_number = _normalize_employee_number(number_raw)
    except ValueError:
        return None
    display_name = f"{initials} - {name}" if initials else name
    return {
        "number": number_raw,
        "normalizedNumber": normalized_number,
        "name": name,
        "initials": initials,
        "displayName": display_name,
        "email": email,
        "departmentCode": department_code,
    }


def _fetch_employee_rows() -> list[dict[str, Any]]:
    base_url = _require_env("EMPLOYEE_API_BASE_URL").rstrip("/")
    token = _require_env("EMPLOYEE_API_TOKEN")
    auth_header_name = (os.environ.get("EMPLOYEE_API_AUTH_HEADER") or "Authorization").strip()
    auth_scheme = (os.environ.get("EMPLOYEE_API_AUTH_SCHEME") or "").strip()
    auth_value = _build_auth_header_value(token, auth_scheme)
    request = urllib.request.Request(
        url=f"{base_url}/Employees/all",
        headers={auth_header_name: auth_value},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise EmployeeDirectoryError(f"Employee API returned status {response.status}")
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, list):
                raise EmployeeDirectoryError("Employee API payload is not a list")
            return payload
    except urllib.error.HTTPError as exc:
        raise EmployeeDirectoryError(f"Employee API HTTP error: {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise EmployeeDirectoryError(f"Employee API connection error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise EmployeeDirectoryError("Employee API returned invalid JSON") from exc


def get_employee_directory(force_refresh: bool = False) -> dict[str, dict[str, str]]:
    global _CACHE_EXPIRES_AT
    now = time.time()
    if not force_refresh and _EMPLOYEE_CACHE and now < _CACHE_EXPIRES_AT:
        return dict(_EMPLOYEE_CACHE)

    rows = _fetch_employee_rows()
    parsed: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        entry = _to_employee_entry(row)
        if not entry:
            continue
        parsed[entry["normalizedNumber"]] = entry

    _EMPLOYEE_CACHE.clear()
    _EMPLOYEE_CACHE.update(parsed)
    _CACHE_EXPIRES_AT = now + _CACHE_TTL_SECONDS
    return dict(_EMPLOYEE_CACHE)


def get_employees_list(force_refresh: bool = False) -> list[dict[str, str]]:
    directory = get_employee_directory(force_refresh=force_refresh)
    rows = list(directory.values())
    rows.sort(key=lambda item: (item["name"].lower(), item["normalizedNumber"]))
    return rows
