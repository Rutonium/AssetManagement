import os
import uuid
import base64
import binascii
import json
import logging
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, selectinload
from starlette.middleware.sessions import SessionMiddleware

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from db.deps import get_asset_db
from models.asset_models import AuditLog, NotificationQueue, Rental, RentalItem, Tool, ToolInstance, Warehouse, WarehouseLocation
from schemas.equipment import EquipmentUpsert, ToolInstanceUpsert
from schemas.rentals import (
    CreateRentalDto,
    ExtensionRequest,
    KioskLendRequest,
    MarkItemsForRentalRequest,
    OfferCheckoutRequest,
    ReservationDecisionRequest,
    ReceiveMarkedItemsRequest,
    ReturnRequest,
)
from schemas.warehouse import ToolLocationAssignmentDto
from services.equipment_service import (
    apply_certification_schedule,
    apply_instance_certification_schedule,
    build_instance_serial,
    generate_next_registration_number,
    generate_next_instance_number,
    serialize_instance,
    serialize_tool,
)
from services.employee_directory_service import EmployeeDirectoryError, get_directory_status, get_employee_directory, get_employees_list
from services.atlas_user_service import (
    create_user_record,
    delete_user_record,
    get_user_record,
    list_provisioned_users,
    list_user_records,
    update_user_record,
    verify_password,
)
from services.user_access_service import create_session, get_session, remove_session
from services.rental_service import (
    apply_return_updates,
    generate_offer_number,
    generate_rental_number,
    recalc_total_cost,
    serialize_rental,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads" / "tools"
RENTAL_UPLOADS_DIR = STATIC_DIR / "uploads" / "rentals"

app = FastAPI()

def _parse_csv_env(name: str, default: str) -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in str(raw).split(",") if item.strip()]


_CORS_ALLOW_ORIGINS = _parse_csv_env(
    "CORS_ALLOW_ORIGINS",
    "http://127.0.0.1,http://localhost,http://127.0.0.1:5001,http://localhost:5001",
)
_CORS_ALLOW_CREDENTIALS = str(os.environ.get("CORS_ALLOW_CREDENTIALS", "true")).strip().lower() in {"1", "true", "yes", "on"}
if "*" in _CORS_ALLOW_ORIGINS:
    # Browsers reject wildcard origins with credentials; force safe behavior.
    _CORS_ALLOW_CREDENTIALS = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ALLOW_ORIGINS,
    allow_credentials=_CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"]
)
_APP_SESSION_SECRET = (os.environ.get("SESSION_SIGNING_SECRET") or "").strip()
if len(_APP_SESSION_SECRET) >= 32:
    app.add_middleware(
        SessionMiddleware,
        secret_key=_APP_SESSION_SECRET,
        session_cookie="asset_management_session",
        same_site="lax",
        https_only=False,
    )

STATE_ALIASES = {
    "Pending": "Reserved",
    "Approved": "Reserved",
}
RESERVATION_STATES = {"Offer", "Reserved", "Active", "Overdue", "Returned", "Closed"}
TERMINAL_STATES = {"Closed", "Cancelled", "Lost"}
BLOCKING_STATES = {"Reserved", "Active", "Overdue"}
STATE_TRANSITIONS = {
    "Offer": {"Reserved", "Closed"},
    "Reserved": {"Active", "Closed"},
    "Active": {"Overdue", "Returned", "Closed"},
    "Overdue": {"Active", "Returned", "Closed"},
    "Returned": {"Closed"},
    "Closed": set(),
}
LOCAL_ADMIN_USERNAME = "admin"
LOCAL_ADMIN_PASSWORD = (os.environ.get("LOCAL_ADMIN_PASSWORD") or "").strip()
LOCAL_ADMIN_EMPLOYEE_ID = 999999
LOCAL_ADMIN_RIGHTS = {
    "manageUsers": True,
    "manageRentals": True,
    "manageWarehouse": True,
    "manageEquipment": True,
    "checkout": True,
}
AUTH_ATTEMPT_WINDOW_SECONDS = int(os.environ.get("AUTH_ATTEMPT_WINDOW_SECONDS") or "300")
AUTH_MAX_ATTEMPTS_PER_IP = int(os.environ.get("AUTH_MAX_ATTEMPTS_PER_IP") or "50")
AUTH_MAX_ATTEMPTS_PER_ACCOUNT = int(os.environ.get("AUTH_MAX_ATTEMPTS_PER_ACCOUNT") or "8")
AUTH_LOCKOUT_SECONDS = int(os.environ.get("AUTH_LOCKOUT_SECONDS") or "900")
AUTH_LOGGER = logging.getLogger("asset_management.auth")
_AUTH_GUARD_LOCK = threading.Lock()
_AUTH_ATTEMPTS_BY_IP: dict[str, list[float]] = {}
_AUTH_ATTEMPTS_BY_ACCOUNT: dict[str, list[float]] = {}
_AUTH_LOCKOUT_UNTIL_BY_ACCOUNT: dict[str, float] = {}


class AuthLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = None
    password: str | None = None
    employeeID: int | str | None = None
    pinCode: str | None = None

def log_audit(db: Session, entity_type: str, entity_id: int, action: str, details: str | None = None, user_id: int | None = None) -> None:
    db.add(
        AuditLog(
            EntityType=entity_type,
            EntityID=entity_id,
            Action=action,
            Details=details,
            UserID=user_id,
            CreatedAt=datetime.now(),
        )
    )


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        if candidate:
            return candidate
    return request.client.host if request.client and request.client.host else "unknown"


def _prune_attempts(attempts: list[float], now_ts: float) -> list[float]:
    cutoff = now_ts - max(AUTH_ATTEMPT_WINDOW_SECONDS, 1)
    return [ts for ts in attempts if ts >= cutoff]


def _check_login_guard(client_ip: str, account_key: str) -> int | None:
    now_ts = time.time()
    with _AUTH_GUARD_LOCK:
        lockout_until = _AUTH_LOCKOUT_UNTIL_BY_ACCOUNT.get(account_key)
        if lockout_until and lockout_until > now_ts:
            return max(1, int(lockout_until - now_ts))
        if lockout_until and lockout_until <= now_ts:
            _AUTH_LOCKOUT_UNTIL_BY_ACCOUNT.pop(account_key, None)

        ip_attempts = _prune_attempts(_AUTH_ATTEMPTS_BY_IP.get(client_ip, []), now_ts)
        account_attempts = _prune_attempts(_AUTH_ATTEMPTS_BY_ACCOUNT.get(account_key, []), now_ts)
        _AUTH_ATTEMPTS_BY_IP[client_ip] = ip_attempts
        _AUTH_ATTEMPTS_BY_ACCOUNT[account_key] = account_attempts

        if len(ip_attempts) >= max(AUTH_MAX_ATTEMPTS_PER_IP, 1):
            oldest = ip_attempts[0]
            retry_after = max(1, int((oldest + AUTH_ATTEMPT_WINDOW_SECONDS) - now_ts))
            return retry_after
        if len(account_attempts) >= max(AUTH_MAX_ATTEMPTS_PER_ACCOUNT, 1):
            _AUTH_LOCKOUT_UNTIL_BY_ACCOUNT[account_key] = now_ts + max(AUTH_LOCKOUT_SECONDS, 1)
            return max(AUTH_LOCKOUT_SECONDS, 1)
    return None


def _record_login_failure(client_ip: str, account_key: str) -> None:
    now_ts = time.time()
    with _AUTH_GUARD_LOCK:
        ip_attempts = _prune_attempts(_AUTH_ATTEMPTS_BY_IP.get(client_ip, []), now_ts)
        account_attempts = _prune_attempts(_AUTH_ATTEMPTS_BY_ACCOUNT.get(account_key, []), now_ts)
        ip_attempts.append(now_ts)
        account_attempts.append(now_ts)
        _AUTH_ATTEMPTS_BY_IP[client_ip] = ip_attempts
        _AUTH_ATTEMPTS_BY_ACCOUNT[account_key] = account_attempts
        if len(account_attempts) >= max(AUTH_MAX_ATTEMPTS_PER_ACCOUNT, 1):
            _AUTH_LOCKOUT_UNTIL_BY_ACCOUNT[account_key] = now_ts + max(AUTH_LOCKOUT_SECONDS, 1)


def _record_login_success(account_key: str) -> None:
    with _AUTH_GUARD_LOCK:
        _AUTH_ATTEMPTS_BY_ACCOUNT.pop(account_key, None)
        _AUTH_LOCKOUT_UNTIL_BY_ACCOUNT.pop(account_key, None)


def _audit_auth_event(db: Session, *, action: str, details: str, user_id: int | None = None) -> None:
    try:
        log_audit(db, "Auth", int(user_id or 0), action, details, user_id=user_id)
        db.commit()
    except Exception:
        db.rollback()


def _invalid_login_error() -> HTTPException:
    return HTTPException(status_code=401, detail="Invalid credentials.")

@app.get("/healthz")
def healthcheck():
    return {"status": "ok"}


@app.get("/api/healthz")
def healthcheck_api(db: Session = Depends(get_asset_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"db_unavailable: {exc}") from exc


@app.get("/api/employees")
def get_employees(force_refresh: bool = Query(False, alias="forceRefresh")):
    try:
        rows = get_employees_list(force_refresh=force_refresh)
    except EmployeeDirectoryError as exc:
        status = get_directory_status()
        raise HTTPException(
            status_code=503,
            detail=f"Employee directory unavailable: {exc}. cacheCount={status['cacheCount']} cacheExpiresInSeconds={status['cacheExpiresInSeconds']}",
        ) from exc
    return [
        {
            "employeeID": int(row["normalizedNumber"]),
            "employeeNumber": row["number"],
            "name": row["name"],
            "initials": row["initials"],
            "displayName": row["displayName"],
            "email": row["email"],
            "departmentCode": row["departmentCode"],
        }
        for row in rows
    ]


@app.get("/api/employees/status")
def get_employees_status():
    return get_directory_status()


@app.get("/api/projects/search")
def search_projects(
    q: str = Query("", min_length=0, alias="q"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_asset_db),
):
    query = (q or "").strip()
    stmt = select(Rental.ProjectCode).where(Rental.ProjectCode.is_not(None))
    if query:
        stmt = stmt.where(Rental.ProjectCode.ilike(f"%{query}%"))
    rows = db.execute(stmt.order_by(Rental.ProjectCode.desc()).limit(limit * 3)).all()

    seen: set[str] = set()
    output: list[dict[str, str]] = []
    for row in rows:
        code = str(row[0] or "").strip()
        if not code:
            continue
        key = code.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append({"projectCode": code, "display": code})
        if len(output) >= limit:
            break
    return output


@app.post("/api/auth/login")
def auth_login(payload: dict, request: Request, db: Session = Depends(get_asset_db)):
    client_ip = _get_client_ip(request)
    try:
        parsed = AuthLoginRequest.model_validate(payload)
    except ValidationError:
        _audit_auth_event(db, action="LoginRejected", details=f"ip={client_ip} reason=invalid_payload", user_id=None)
        raise HTTPException(status_code=400, detail="Invalid login request.")

    username = str(parsed.username or "").strip().lower()
    password = str(parsed.password or parsed.pinCode or "")
    raw_employee_id = parsed.employeeID

    if not username and raw_employee_id in (None, ""):
        _audit_auth_event(db, action="LoginRejected", details=f"ip={client_ip} reason=missing_identity", user_id=None)
        raise HTTPException(status_code=400, detail="Invalid login request.")

    account_key: str
    if username:
        account_key = f"user:{username}"
    else:
        account_key = f"employee:{str(raw_employee_id).strip()}"

    retry_after = _check_login_guard(client_ip, account_key)
    if retry_after is not None:
        _audit_auth_event(db, action="LoginThrottled", details=f"ip={client_ip} key={account_key} retry_after={retry_after}", user_id=None)
        AUTH_LOGGER.warning("Login throttled ip=%s key=%s retry_after=%s", client_ip, account_key, retry_after)
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    if username:
        if username != LOCAL_ADMIN_USERNAME or not LOCAL_ADMIN_PASSWORD:
            _record_login_failure(client_ip, account_key)
            _audit_auth_event(db, action="LoginFailed", details=f"ip={client_ip} key={account_key} reason=invalid_admin_identity", user_id=None)
            AUTH_LOGGER.warning("Login failed ip=%s key=%s reason=invalid_admin_identity", client_ip, account_key)
            raise _invalid_login_error()
        if password != LOCAL_ADMIN_PASSWORD:
            _record_login_failure(client_ip, account_key)
            _audit_auth_event(db, action="LoginFailed", details=f"ip={client_ip} key={account_key} reason=invalid_admin_password", user_id=None)
            AUTH_LOGGER.warning("Login failed ip=%s key=%s reason=invalid_admin_password", client_ip, account_key)
            raise _invalid_login_error()

        session_payload = {
            "employeeID": LOCAL_ADMIN_EMPLOYEE_ID,
            "displayName": "Administrator",
            "name": "Administrator",
            "initials": "ADM",
            "role": "Admin",
            "rights": dict(LOCAL_ADMIN_RIGHTS),
            "isLocalAdmin": True,
        }
        token = create_session(session_payload)
        request.session["user"] = dict(session_payload)
        _record_login_success(account_key)
        _audit_auth_event(db, action="LoginSuccess", details=f"ip={client_ip} key={account_key} method=admin", user_id=LOCAL_ADMIN_EMPLOYEE_ID)
        AUTH_LOGGER.info("Login success ip=%s key=%s user_id=%s", client_ip, account_key, LOCAL_ADMIN_EMPLOYEE_ID)
        return {"sessionToken": token, "user": session_payload}

    employee_id: int
    try:
        employee_id = _resolve_employee_number_or_400(raw_employee_id or 0)
    except HTTPException:
        _record_login_failure(client_ip, account_key)
        _audit_auth_event(db, action="LoginFailed", details=f"ip={client_ip} key={account_key} reason=invalid_employee_id", user_id=None)
        AUTH_LOGGER.warning("Login failed ip=%s key=%s reason=invalid_employee_id", client_ip, account_key)
        raise HTTPException(status_code=400, detail="Invalid login request.")

    account_key = f"employee:{employee_id}"
    retry_after = _check_login_guard(client_ip, account_key)
    if retry_after is not None:
        _audit_auth_event(db, action="LoginThrottled", details=f"ip={client_ip} key={account_key} retry_after={retry_after}", user_id=employee_id)
        AUTH_LOGGER.warning("Login throttled ip=%s key=%s retry_after=%s", client_ip, account_key, retry_after)
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    access = get_user_record(db, employee_id)
    if not access.get("isProvisioned"):
        _record_login_failure(client_ip, account_key)
        _audit_auth_event(db, action="LoginFailed", details=f"ip={client_ip} key={account_key} reason=employee_not_provisioned", user_id=employee_id)
        AUTH_LOGGER.warning("Login failed ip=%s key=%s reason=employee_not_provisioned", client_ip, account_key)
        raise _invalid_login_error()

    pin_code = str(parsed.pinCode or parsed.password or "")
    if not verify_password(db, employee_id, pin_code):
        _record_login_failure(client_ip, account_key)
        _audit_auth_event(db, action="LoginFailed", details=f"ip={client_ip} key={account_key} reason=invalid_employee_pin", user_id=employee_id)
        AUTH_LOGGER.warning("Login failed ip=%s key=%s reason=invalid_employee_pin", client_ip, account_key)
        raise _invalid_login_error()

    directory_entry = _safe_employee_directory().get(str(employee_id)) or {}
    session_payload = {
        "employeeID": employee_id,
        "displayName": directory_entry.get("displayName") or directory_entry.get("name") or f"Employee #{employee_id}",
        "name": directory_entry.get("name") or "",
        "initials": directory_entry.get("initials") or "",
        "role": access.get("role") or "User",
        "rights": access.get("rights") or {},
    }
    token = create_session(session_payload)
    request.session["user"] = dict(session_payload)
    _record_login_success(account_key)
    _audit_auth_event(db, action="LoginSuccess", details=f"ip={client_ip} key={account_key} method=employee", user_id=employee_id)
    AUTH_LOGGER.info("Login success ip=%s key=%s user_id=%s", client_ip, account_key, employee_id)
    return {"sessionToken": token, "user": session_payload}


@app.post("/api/auth/logout")
def auth_logout(request: Request, x_session_token: str | None = Header(None, alias="X-Session-Token")):
    request.session.clear()
    remove_session(x_session_token)
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(request: Request, x_session_token: str | None = Header(None, alias="X-Session-Token")):
    session = _require_session_or_401(request, x_session_token)
    return {"user": session}


@app.get("/api/auth/users")
def auth_users(db: Session = Depends(get_asset_db)):
    users = list_provisioned_users(db)
    # Login lookup must only use provisioned AtlasUsers, no employee directory expansion.
    return [
        {
            "employeeID": int(item.get("employeeID") or 0),
            "displayName": str(item.get("displayName") or f"Employee #{int(item.get('employeeID') or 0)}"),
        }
        for item in users
        if int(item.get("employeeID") or 0) > 0
    ]


@app.get("/api/admin/users")
def list_admin_users(
    request: Request,
    force_refresh: bool = Query(False, alias="forceRefresh"),
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    _require_admin_session_or_403(request, x_session_token)
    try:
        rows = get_employees_list(force_refresh=force_refresh)
    except EmployeeDirectoryError as exc:
        return list_provisioned_users(db)
    return list_user_records(db, rows)


@app.post("/api/admin/users")
def create_admin_user(
    request: Request,
    payload: dict,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    _require_admin_session_or_403(request, x_session_token)
    employee_id = _resolve_employee_number_or_400(payload.get("employeeID") or 0)
    _require_employee_or_400(employee_id)
    role = payload.get("role")
    rights = payload.get("rights")
    timeapp_rights = payload.get("timeAppRights")
    peopleplanner_rights = payload.get("peoplePlannerRights")
    password = payload.get("password")

    existing = get_user_record(db, employee_id)
    try:
        if existing.get("isProvisioned"):
            created = update_user_record(
                db,
                employee_id=employee_id,
                role=str(role) if role is not None else None,
                rights=rights if isinstance(rights, dict) else None,
                timeapp_rights=timeapp_rights if isinstance(timeapp_rights, dict) else None,
                peopleplanner_rights=peopleplanner_rights if isinstance(peopleplanner_rights, dict) else None,
                password=str(password) if password is not None and str(password).strip() else None,
                reset_password=False,
            )
        else:
            created = create_user_record(
                db,
                employee_id=employee_id,
                role=str(role) if role is not None else None,
                asset_management_rights=rights if isinstance(rights, dict) else None,
                timeapp_rights=timeapp_rights if isinstance(timeapp_rights, dict) else {},
                peopleplanner_rights=peopleplanner_rights if isinstance(peopleplanner_rights, dict) else {},
                password=str(password) if password is not None and str(password).strip() else None,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return created


@app.put("/api/admin/users/{employee_id}")
def update_admin_user(
    request: Request,
    employee_id: int,
    payload: dict,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    _require_admin_session_or_403(request, x_session_token)
    _require_employee_or_400(employee_id)
    role = payload.get("role")
    rights = payload.get("rights")
    timeapp_rights = payload.get("timeAppRights")
    peopleplanner_rights = payload.get("peoplePlannerRights")
    password = payload.get("password")
    reset_password = bool(payload.get("resetPassword"))
    try:
        updated = update_user_record(
            db,
            employee_id=employee_id,
            role=str(role) if role is not None else None,
            rights=rights if isinstance(rights, dict) else None,
            timeapp_rights=timeapp_rights if isinstance(timeapp_rights, dict) else None,
            peopleplanner_rights=peopleplanner_rights if isinstance(peopleplanner_rights, dict) else None,
            password=str(password) if password is not None and str(password).strip() else None,
            reset_password=reset_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return updated


@app.delete("/api/admin/users/{employee_id}")
def delete_admin_user(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    _require_admin_session_or_403(request, x_session_token)
    try:
        deleted = delete_user_record(db, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Atlas user not found.")
    return {"ok": True}


@app.get("/api/equipment")
def get_equipment(db: Session = Depends(get_asset_db)):
    tools = db.execute(select(Tool).order_by(Tool.ToolName)).scalars().all()
    counts = dict(
        db.execute(
            select(ToolInstance.ToolID, func.count(ToolInstance.ToolInstanceID))
            .group_by(ToolInstance.ToolID)
        ).all()
    )
    min_next = dict(
        db.execute(
            select(ToolInstance.ToolID, func.min(ToolInstance.NextCalibration))
            .where(ToolInstance.RequiresCertification == True)
            .group_by(ToolInstance.ToolID)
        ).all()
    )
    payloads = []
    for tool in tools:
        payload = serialize_tool(tool, counts.get(tool.ToolID, 0))
        payload["instanceNextCalibrationMin"] = min_next.get(tool.ToolID)
        payloads.append(payload)
    return payloads


@app.get("/api/equipment/calibration-alerts")
def get_calibration_alerts(db: Session = Depends(get_asset_db)):
    today = date.today()
    warning_date = today + timedelta(days=30)

    stmt = (
        select(ToolInstance, Tool)
        .join(Tool, Tool.ToolID == ToolInstance.ToolID)
        .where(ToolInstance.NextCalibration.is_not(None))
        .where(ToolInstance.NextCalibration <= warning_date)
    )
    rows = db.execute(stmt).all()

    alerts = []
    for instance, tool in rows:
        alerts.append(
            {
                "toolID": tool.ToolID,
                "toolInstanceID": instance.ToolInstanceID,
                "toolName": tool.ToolName,
                "serialNumber": instance.SerialNumber,
                "nextCalibration": instance.NextCalibration,
            }
        )

    alerts.sort(key=lambda item: item["nextCalibration"] or date.max)
    return alerts


@app.get("/api/equipment/{tool_id}")
def get_equipment_item(tool_id: int, db: Session = Depends(get_asset_db)):
    tool = db.get(Tool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    count = db.execute(
        select(func.count(ToolInstance.ToolInstanceID)).where(ToolInstance.ToolID == tool_id)
    ).scalar()
    min_next = db.execute(
        select(func.min(ToolInstance.NextCalibration))
        .where(ToolInstance.ToolID == tool_id)
        .where(ToolInstance.RequiresCertification == True)
    ).scalar()
    payload = serialize_tool(tool, count or 0)
    payload["instanceNextCalibrationMin"] = min_next
    return payload


@app.post("/api/equipment")
def create_equipment(payload: EquipmentUpsert, db: Session = Depends(get_asset_db)):
    tool = Tool()

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tool, _map_tool_field(field), value)

    if not tool.SerialNumber:
        tool.SerialNumber = generate_next_registration_number(db)

    tool.UpdatedDate = datetime.now()
    tool.CreatedDate = datetime.now()
    apply_certification_schedule(tool)

    db.add(tool)
    db.commit()
    db.refresh(tool)
    instance_number = generate_next_instance_number(db, tool.ToolID)
    instance_serial = build_instance_serial(tool.SerialNumber, instance_number)
    instance = ToolInstance(
        ToolID=tool.ToolID,
        SerialNumber=instance_serial,
        InstanceNumber=instance_number,
        Status=tool.Status or "Available",
        Condition=tool.Condition,
        WarehouseID=tool.WarehouseID,
        LocationCode=tool.LocationCode,
        RequiresCertification=tool.RequiresCertification,
        CalibrationInterval=tool.CalibrationInterval,
        LastCalibration=tool.LastCalibration,
        NextCalibration=tool.NextCalibration,
        ImagePath=tool.ImagePath,
        CreatedDate=datetime.now(),
        UpdatedDate=datetime.now(),
    )
    apply_instance_certification_schedule(instance)
    db.add(instance)
    db.commit()
    return serialize_tool(tool, 1)


@app.put("/api/equipment/{tool_id}")
def update_equipment(tool_id: int, payload: EquipmentUpsert, db: Session = Depends(get_asset_db)):
    tool = db.get(Tool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "toolID":
            continue
        setattr(tool, _map_tool_field(field), value)

    tool.UpdatedDate = datetime.now()
    apply_certification_schedule(tool)

    db.commit()
    db.refresh(tool)
    count = db.execute(
        select(func.count(ToolInstance.ToolInstanceID)).where(ToolInstance.ToolID == tool_id)
    ).scalar()
    return serialize_tool(tool, count or 0)


@app.delete("/api/equipment/{tool_id}")
def delete_equipment(tool_id: int, db: Session = Depends(get_asset_db)):
    tool = db.get(Tool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    db.delete(tool)
    db.commit()
    return {"message": "Deleted"}


@app.get("/api/equipment/{tool_id}/instances")
def get_tool_instances(tool_id: int, db: Session = Depends(get_asset_db)):
    instances = db.execute(
        select(ToolInstance).where(ToolInstance.ToolID == tool_id).order_by(ToolInstance.SerialNumber)
    ).scalars().all()
    return [serialize_instance(instance) for instance in instances]


@app.post("/api/equipment/{tool_id}/instances")
def create_tool_instance(tool_id: int, payload: ToolInstanceUpsert, db: Session = Depends(get_asset_db)):
    tool = db.get(Tool, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")

    instance_number = generate_next_instance_number(db, tool.ToolID)
    instance_serial = build_instance_serial(tool.SerialNumber, instance_number)

    instance = ToolInstance(
        ToolID=tool.ToolID,
        SerialNumber=payload.serialNumber or instance_serial,
        InstanceNumber=instance_number,
        Status=payload.status or tool.Status or "Available",
        Condition=payload.condition or tool.Condition,
        WarehouseID=payload.warehouseID or tool.WarehouseID,
        LocationCode=payload.locationCode or tool.LocationCode,
        RequiresCertification=tool.RequiresCertification,
        CalibrationInterval=tool.CalibrationInterval,
        LastCalibration=payload.lastCalibration or tool.LastCalibration,
        NextCalibration=payload.nextCalibration or tool.NextCalibration,
        ImagePath=payload.imagePath or tool.ImagePath,
        CreatedDate=datetime.now(),
        UpdatedDate=datetime.now(),
    )
    apply_instance_certification_schedule(instance)
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return serialize_instance(instance)


@app.put("/api/equipment/instances/{instance_id}")
def update_tool_instance(instance_id: int, payload: ToolInstanceUpsert, db: Session = Depends(get_asset_db)):
    instance = db.get(ToolInstance, instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Tool instance not found")

    tool = db.get(Tool, instance.ToolID)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "toolInstanceID":
            continue
        setattr(instance, _map_instance_field(field), value)

    if tool:
        instance.RequiresCertification = tool.RequiresCertification
        instance.CalibrationInterval = tool.CalibrationInterval

    if not instance.InstanceNumber:
        instance.InstanceNumber = generate_next_instance_number(db, instance.ToolID)
    if not instance.SerialNumber and instance.InstanceNumber:
        instance.SerialNumber = build_instance_serial(tool.SerialNumber if tool else None, instance.InstanceNumber)

    instance.UpdatedDate = datetime.now()
    apply_instance_certification_schedule(instance)
    db.commit()
    db.refresh(instance)
    return serialize_instance(instance)


@app.delete("/api/equipment/instances/{instance_id}")
def delete_tool_instance(instance_id: int, db: Session = Depends(get_asset_db)):
    instance = db.get(ToolInstance, instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Tool instance not found")

    db.delete(instance)
    db.commit()
    return {"message": "Deleted"}


@app.post("/api/equipment/upload-image")
def upload_equipment_image(file: UploadFile = File(...)):
    if file.content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload an image (jpg, png, webp, gif).")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    target = UPLOADS_DIR / filename

    with target.open("wb") as output:
        output.write(file.file.read())

    return {"path": f"/uploads/tools/{filename}"}


@app.get("/api/rentals")
def get_rentals(db: Session = Depends(get_asset_db)):
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.Tool))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .order_by(Rental.CreatedDate.desc())
    )
    rentals = db.execute(stmt).scalars().all()
    for rental in rentals:
        _apply_runtime_state(rental)
    employee_directory = _safe_employee_directory()
    db.commit()
    return [_serialize_rental_with_employee(rental, employee_directory) for rental in rentals]


@app.get("/api/rentals/{rental_id}")
def get_rental(rental_id: int, db: Session = Depends(get_asset_db)):
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.Tool))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    _apply_runtime_state(rental)
    employee_directory = _safe_employee_directory()
    db.commit()
    return _serialize_rental_with_employee(rental, employee_directory)


@app.get("/api/offers/{offer_number}")
def get_offer_by_number(offer_number: str, db: Session = Depends(get_asset_db)):
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.Tool))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalNumber == offer_number.upper())
    )
    offer = db.execute(stmt).scalars().first()
    if not offer or _normalize_state(offer.Status) != "Offer":
        raise HTTPException(status_code=404, detail="Offer not found")
    return _serialize_rental_with_employee(offer, _safe_employee_directory())


@app.post("/api/offers/{offer_number}/checkout")
def checkout_offer(
    request: Request,
    offer_number: str,
    payload: OfferCheckoutRequest,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .where(Rental.RentalNumber == offer_number.upper())
    )
    offer = db.execute(stmt).scalars().first()
    if not offer or _normalize_state(offer.Status) != "Offer":
        raise HTTPException(status_code=404, detail="Offer not found")

    session = _get_active_session(request, x_session_token)
    actor_employee_id = int(session.get("employeeID")) if session else None
    checkout_payload = CreateRentalDto(
        employeeID=actor_employee_id or payload.employeeID,
        purpose=payload.purpose or offer.Purpose,
        projectCode=payload.projectCode or offer.ProjectCode,
        startDate=payload.startDate,
        endDate=payload.endDate,
        notes=payload.notes or f"Checked out from offer {offer.RentalNumber}",
        status="Reserved",
        rentalItems=[
            {
                "toolID": item.ToolID,
                "quantity": int(item.Quantity or 1),
                "dailyCost": float(item.DailyCost or 0),
                "assignmentMode": "auto",
                "allowDeficit": True,
            }
            for item in offer.RentalItems
        ],
    )

    created = create_rental(request, checkout_payload, db, x_session_token)
    _transition_state(offer, "Closed")
    offer.UpdatedDate = datetime.now()
    db.commit()
    log_audit(
        db,
        "Rental",
        offer.RentalID,
        "OfferCheckout",
        f"Offer converted to reservation {created['rentalNumber']}",
        user_id=actor_employee_id,
    )
    db.commit()
    return created


@app.get("/api/rentals/availability/by-tool")
def get_rental_availability(
    tool_id: int = Query(..., alias="toolID"),
    start_date: date = Query(..., alias="startDate"),
    end_date: date = Query(..., alias="endDate"),
    quantity: int = Query(1, alias="quantity"),
    db: Session = Depends(get_asset_db),
):
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="endDate must be on or after startDate.")

    wanted = max(1, int(quantity))
    available_instances = _get_available_instances(db, tool_id, start_date, end_date)
    return {
        "toolID": tool_id,
        "startDate": start_date,
        "endDate": end_date,
        "requestedQuantity": wanted,
        "availableCount": len(available_instances),
        "deficit": max(0, wanted - len(available_instances)),
        "availableInstanceIDs": [instance.ToolInstanceID for instance in available_instances],
    }


@app.post("/api/kiosk/lend")
def kiosk_lend(request: Request, payload: KioskLendRequest, db: Session = Depends(get_asset_db)):
    employee_id = _resolve_employee_number_or_400(payload.employeeID)
    employee_entry = _require_employee_or_400(employee_id)
    pin = (payload.pinCode or "").strip()
    if len(pin) < 4:
        raise HTTPException(status_code=400, detail="PIN code must be at least 4 characters.")
    if not verify_password(db, employee_id, pin):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    if payload.endDate < payload.startDate:
        raise HTTPException(status_code=400, detail="endDate must be on or after startDate.")
    if not payload.rentalItems:
        raise HTTPException(status_code=400, detail="No rental items supplied.")

    base_notes = f"Kiosk lend by employee {employee_id}"
    photo_path = None
    if payload.photoDataUrl:
        photo_path = _save_data_url_image(payload.photoDataUrl, RENTAL_UPLOADS_DIR, "kiosk")
        base_notes = f"{base_notes}\nPickupPhoto={photo_path}"

    create_payload = CreateRentalDto(
        employeeID=employee_id,
        purpose=payload.purpose or "Kiosk lend",
        projectCode=payload.projectCode,
        startDate=payload.startDate,
        endDate=payload.endDate,
        notes=base_notes,
        status="Reserved",
        rentalItems=[
            {
                "toolID": item.toolID,
                "toolInstanceID": item.toolInstanceID,
                "quantity": item.quantity,
                "dailyCost": item.dailyCost,
                "assignmentMode": item.assignmentMode or ("manual" if item.toolInstanceID else "auto"),
                "allowDeficit": item.allowDeficit,
            }
            for item in payload.rentalItems
        ],
    )

    created = create_rental(request, create_payload, db, None)

    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.Tool))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == int(created["rentalID"]))
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=500, detail="Could not create kiosk rental.")

    _activate_rental(db, rental, approved_by=employee_id)
    if photo_path:
        rental.CheckoutCondition = f"Kiosk photo: {photo_path}"
    db.commit()
    log_audit(db, "Rental", rental.RentalID, "KioskLend", f"Employee {employee_id}")
    db.commit()

    pickup_lines = []
    for item in rental.RentalItems:
        if not item.ToolInstance:
            continue
        pickup_lines.append(
            {
                "toolID": item.ToolID,
                "toolName": item.Tool.ToolName if item.Tool else f"Tool {item.ToolID}",
                "toolInstanceID": item.ToolInstanceID,
                "serialNumber": item.ToolInstance.SerialNumber,
                "locationCode": item.ToolInstance.LocationCode,
                "warehouseID": item.ToolInstance.WarehouseID,
                "quantity": int(item.Quantity or 1),
            }
        )

    return {
        "rental": _serialize_rental_with_employee(rental, {str(employee_id): employee_entry}),
        "pickupItems": pickup_lines,
        "photoPath": photo_path,
    }


@app.post("/api/rentals")
def create_rental(
    request: Request,
    payload: CreateRentalDto,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    session = _get_active_session(request, x_session_token)
    requested_employee = int(session.get("employeeID")) if session else payload.employeeID
    employee_id = _resolve_employee_number_or_400(requested_employee)
    employee_entry = _require_employee_or_400(employee_id)
    if payload.endDate < payload.startDate:
        raise HTTPException(status_code=400, detail="endDate must be on or after startDate.")

    initial_status = _normalize_state(payload.status or "Reserved")
    if initial_status not in {"Offer", "Reserved"}:
        raise HTTPException(status_code=400, detail="Initial status must be Offer or Reserved.")

    rental = Rental(
        EmployeeID=employee_id,
        Purpose=payload.purpose,
        ProjectCode=payload.projectCode,
        StartDate=payload.startDate,
        EndDate=payload.endDate,
        Notes=payload.notes,
        Status=initial_status,
        RentalNumber="TEMP",
        CreatedDate=datetime.now(),
        UpdatedDate=datetime.now(),
    )

    rental.RentalNumber = generate_offer_number(db) if initial_status == "Offer" else generate_rental_number(db, "RNT")

    for item in payload.rentalItems:
        tool = db.get(Tool, item.toolID)
        if not tool:
            raise HTTPException(status_code=400, detail=f"Tool {item.toolID} not found.")
        snapshot_daily_cost = float(item.dailyCost) if item.dailyCost is not None else float(tool.DailyRentalCost or 0)

        requested_quantity = max(1, int(item.quantity or 1))
        assignment_mode = (item.assignmentMode or ("manual" if item.toolInstanceID else "auto")).lower()
        if assignment_mode not in {"auto", "manual"}:
            raise HTTPException(status_code=400, detail="assignmentMode must be auto or manual.")

        if initial_status in {"Offer", "Reserved"}:
            request_state = "Offer" if initial_status == "Offer" else "Pending Approval"
            rental.RentalItems.append(
                RentalItem(
                    ToolID=item.toolID,
                    ToolInstanceID=None,
                    Quantity=requested_quantity,
                    DailyCost=snapshot_daily_cost,
                    CheckoutNotes="OFFER: not reserved" if initial_status == "Offer" else "REQUESTED: awaiting approval",
                    ReturnNotes=_build_lifecycle_payload(
                        state=request_state,
                        operator_user_id=employee_id,
                    ),
                )
            )
            continue

    recalc_total_cost(rental)
    db.add(rental)
    db.commit()
    db.refresh(rental)
    log_audit(db, "Rental", rental.RentalID, "CreateRental", f"Created with status {initial_status}", user_id=employee_id)
    db.commit()

    return _serialize_rental_with_employee(rental, {str(employee_id): employee_entry})


@app.post("/api/rentals/{rental_id}/approve")
def approve_rental(
    request: Request,
    rental_id: int,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    decision = ReservationDecisionRequest(
        decision="approve",
        operatorUserID=_resolve_actor_user_id(None, request, x_session_token),
    )
    return decide_rental(request, rental_id, decision, db, x_session_token)


@app.post("/api/rentals/{rental_id}/decide")
def decide_rental(
    request: Request,
    rental_id: int,
    payload: ReservationDecisionRequest,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    payload.operatorUserID = _resolve_actor_user_id(payload.operatorUserID, request, x_session_token)
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    current = _apply_runtime_state(rental)
    if current != "Reserved":
        raise HTTPException(status_code=400, detail="Reservation is not pending decision.")

    if payload.decision == "reject":
        reason = (payload.reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="Reject reason is required.")
        _transition_state(rental, "Closed")
        rental.Notes = (rental.Notes + "\n" if rental.Notes else "") + f"Rejected: {reason}"
        rental.UpdatedDate = datetime.now()
        _release_reserved_instances(db, rental)
        db.add(
            NotificationQueue(
                RentalID=rental.RentalID,
                NotificationType="ReservationRejected",
                Payload=f"Reservation {rental.RentalNumber} rejected: {reason}",
                CreatedAt=datetime.now(),
            )
        )
        db.commit()
        log_audit(db, "Rental", rental_id, "Reject", f"Rejected by {payload.operatorUserID}: {reason}", user_id=payload.operatorUserID)
        db.commit()
        return {"message": "Reservation rejected", "rentalNumber": rental.RentalNumber}

    # Approve flow: keep status Reserved (not invoiceable), allocate what is available.
    if not rental.ApprovalDate:
        rental.ApprovalDate = date.today()
    rental.ApprovedBy = payload.operatorUserID
    rental.UpdatedDate = datetime.now()
    _apply_shortage_actions(rental, payload.shortageActions, payload.operatorUserID)
    allocation = _allocate_reservation_lines(db, rental, payload.operatorUserID)

    db.add(
        NotificationQueue(
            RentalID=rental.RentalID,
            NotificationType="ReservationApproved",
            Payload=f"Reservation {rental.RentalNumber} approved. Reserved={allocation['reservedCount']} shortage={allocation['shortageCount']}",
            CreatedAt=datetime.now(),
        )
    )
    recalc_total_cost(rental)
    db.commit()
    log_audit(
        db,
        "Rental",
        rental_id,
        "ApproveReservation",
        f"Approved by {payload.operatorUserID}; reserved={allocation['reservedCount']} shortage={allocation['shortageCount']}",
        user_id=payload.operatorUserID,
    )
    db.commit()
    return {"message": "Reservation approved", "allocation": allocation, "rental": _serialize_rental_with_employee(rental, _safe_employee_directory())}


@app.post("/api/rentals/{rental_id}/mark-items-for-rental")
def mark_items_for_rental(
    request: Request,
    rental_id: int,
    payload: MarkItemsForRentalRequest,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    payload.operatorUserID = _resolve_actor_user_id(payload.operatorUserID, request, x_session_token)
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    current = _apply_runtime_state(rental)
    if current not in {"Reserved", "Active", "Overdue"}:
        raise HTTPException(status_code=400, detail="Rental is not in a pickable state.")
    if not payload.items:
        raise HTTPException(status_code=400, detail="No marked items supplied.")

    item_map = {item.RentalItemID: item for item in rental.RentalItems}
    picked_any = False
    now_iso = datetime.now().isoformat()
    seen_instance_ids: set[int] = set()

    for mark in payload.items:
        line = item_map.get(mark.rentalItemID)
        if not line:
            raise HTTPException(status_code=400, detail=f"RentalItem {mark.rentalItemID} not found in rental.")

        if int(line.Quantity or 0) <= 0:
            raise HTTPException(status_code=400, detail=f"RentalItem {line.RentalItemID} has no remaining quantity.")

        pick_qty = max(0, int(mark.pickedQuantity or 0))
        if pick_qty == 0 and mark.toolInstanceIDs:
            pick_qty = len(mark.toolInstanceIDs)
        if pick_qty <= 0:
            raise HTTPException(status_code=400, detail=f"Invalid picked quantity for line {line.RentalItemID}.")

        if line.ToolInstanceID:
            if pick_qty != 1:
                raise HTTPException(status_code=400, detail=f"RentalItem {line.RentalItemID} can only pick quantity 1.")
            line.Quantity = 0
            _mark_line_lifecycle(
                line,
                state="Picked Up",
                operator_user_id=payload.operatorUserID,
                extra={"pickedAt": now_iso, "notes": mark.notes, "serialInput": mark.serialInput},
            )
            instance = db.get(ToolInstance, line.ToolInstanceID)
            if instance:
                instance.Status = "In Rental"
                instance.UpdatedDate = datetime.now()
            picked_any = True
            continue

        available_qty = int(line.Quantity or 0)
        if pick_qty > available_qty:
            raise HTTPException(
                status_code=400,
                detail=f"Picked quantity {pick_qty} exceeds remaining {available_qty} on line {line.RentalItemID}.",
            )

        chosen_ids = [int(x) for x in (mark.toolInstanceIDs or [])]
        if len(chosen_ids) != len(set(chosen_ids)):
            raise HTTPException(status_code=400, detail=f"Duplicate instance IDs in line {line.RentalItemID}.")
        if len(chosen_ids) > pick_qty:
            raise HTTPException(status_code=400, detail=f"Too many instance IDs supplied for line {line.RentalItemID}.")
        for instance_id in chosen_ids:
            if instance_id in seen_instance_ids:
                raise HTTPException(status_code=400, detail=f"Duplicate instance ID {instance_id} across marked lines.")
            seen_instance_ids.add(instance_id)

        for instance_id in chosen_ids:
            _validate_manual_instance(
                db=db,
                tool_id=line.ToolID,
                tool_instance_id=instance_id,
                start_date=rental.StartDate,
                end_date=rental.EndDate,
            )

        for instance_id in chosen_ids:
            instance = db.get(ToolInstance, instance_id)
            if instance:
                instance.Status = "In Rental"
                instance.UpdatedDate = datetime.now()
            db.add(
                RentalItem(
                    RentalID=rental.RentalID,
                    ToolID=line.ToolID,
                    ToolInstanceID=instance_id,
                    Quantity=1,
                    DailyCost=line.DailyCost,
                    CheckoutNotes=f"ASSIGNED FROM LINE {line.RentalItemID}",
                    ReturnNotes=_build_lifecycle_payload(
                        state="Picked Up",
                        operator_user_id=payload.operatorUserID,
                        extra={"pickedAt": now_iso, "sourceRentalItemID": line.RentalItemID, "notes": mark.notes},
                    ),
                )
            )
            picked_any = True

        untracked_qty = pick_qty - len(chosen_ids)
        if untracked_qty > 0:
            db.add(
                RentalItem(
                    RentalID=rental.RentalID,
                    ToolID=line.ToolID,
                    ToolInstanceID=None,
                    Quantity=untracked_qty,
                    DailyCost=line.DailyCost,
                    CheckoutNotes=f"PICKED WITHOUT INSTANCE ID FROM LINE {line.RentalItemID}",
                    ReturnNotes=_build_lifecycle_payload(
                        state="Picked Up",
                        operator_user_id=payload.operatorUserID,
                        extra={"pickedAt": now_iso, "sourceRentalItemID": line.RentalItemID, "notes": mark.notes},
                    ),
                )
            )
            picked_any = True

        line.Quantity = available_qty - pick_qty
        _mark_line_lifecycle(
            line,
            state="Pending Pickup" if line.Quantity > 0 else "Fulfilled",
            operator_user_id=payload.operatorUserID,
            extra={"remainingQuantity": int(line.Quantity or 0)},
        )

    if picked_any and _normalize_state(rental.Status) == "Reserved":
        _transition_state(rental, "Active")
        rental.ActualStart = rental.ActualStart or date.today()
    rental.UpdatedDate = datetime.now()

    recalc_total_cost(rental)
    db.commit()
    db.refresh(rental)
    log_audit(
        db,
        "Rental",
        rental.RentalID,
        "MarkItemsForRental",
        f"Items marked by {payload.operatorUserID}",
        user_id=payload.operatorUserID,
    )
    db.commit()
    return _serialize_rental_with_employee(rental, _safe_employee_directory())


@app.post("/api/rentals/{rental_id}/extend")
def extend_rental(
    request: Request,
    rental_id: int,
    payload: ExtensionRequest,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    actor_user_id = _resolve_actor_user_id(None, request, x_session_token)
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    current = _apply_runtime_state(rental)
    if current != "Active":
        raise HTTPException(status_code=400, detail="Could not extend rental.")
    if payload.newEndDate < rental.StartDate:
        raise HTTPException(status_code=400, detail="newEndDate must be on or after StartDate.")

    for item in rental.RentalItems:
        if item.ToolInstance and item.ToolInstance.RequiresCertification:
            if not item.ToolInstance.NextCalibration or item.ToolInstance.NextCalibration < payload.newEndDate:
                raise HTTPException(status_code=400, detail="One or more items expire before the new end date.")
        if item.ToolInstanceID and _has_instance_overlap(
            db=db,
            tool_instance_id=item.ToolInstanceID,
            start_date=rental.StartDate,
            end_date=payload.newEndDate,
            exclude_rental_id=rental.RentalID,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Tool instance {item.ToolInstanceID} is already reserved for that extension range.",
            )

    rental.EndDate = payload.newEndDate
    rental.UpdatedDate = datetime.now()
    recalc_total_cost(rental)

    db.commit()
    log_audit(db, "Rental", rental_id, "Extend", f"Extended to {payload.newEndDate}", user_id=actor_user_id)
    db.commit()
    return {"message": "Rental Extended"}


@app.post("/api/rentals/{rental_id}/cancel")
def cancel_rental(
    request: Request,
    rental_id: int,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    actor_user_id = _resolve_actor_user_id(None, request, x_session_token)
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    current = _apply_runtime_state(rental)
    if current == "Reserved":
        decision = ReservationDecisionRequest(
            decision="reject",
            reason="Cancelled by warehouse dispatcher",
            operatorUserID=actor_user_id,
        )
        return decide_rental(request, rental_id, decision, db, x_session_token)
    if current not in {"Offer"}:
        raise HTTPException(status_code=400, detail="Only Offer/Reserved rentals can be closed by cancel.")

    _transition_state(rental, "Closed")
    rental.UpdatedDate = datetime.now()
    db.commit()
    log_audit(db, "Rental", rental_id, "Cancel", "Rental closed", user_id=actor_user_id)
    db.commit()
    return {"message": "Rental Closed"}


@app.post("/api/rentals/{rental_id}/return")
def return_rental(
    request: Request,
    rental_id: int,
    payload: ReturnRequest,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    actor_user_id = _resolve_actor_user_id(None, request, x_session_token)
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    current = _apply_runtime_state(rental)
    if current not in {"Active", "Overdue"}:
        raise HTTPException(status_code=400, detail="Could not process return. Check if rental is active.")

    apply_return_updates(db, rental, payload.condition, payload.notes)
    db.commit()
    log_audit(db, "Rental", rental_id, "Return", "Rental returned", user_id=actor_user_id)
    db.commit()
    return {"message": "Return processed successfully"}


@app.post("/api/rentals/{rental_id}/receive-marked-items")
def receive_marked_items(
    request: Request,
    rental_id: int,
    payload: ReceiveMarkedItemsRequest,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    payload.operatorUserID = _resolve_actor_user_id(payload.operatorUserID, request, x_session_token)
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    current = _apply_runtime_state(rental)
    if current not in {"Active", "Overdue"}:
        raise HTTPException(status_code=400, detail="Rental is not in a receivable state.")
    if not payload.items:
        raise HTTPException(status_code=400, detail="No marked items supplied.")

    item_map = {item.RentalItemID: item for item in rental.RentalItems}
    receive_iso = datetime.now().isoformat()

    for mark in payload.items:
        line = item_map.get(mark.rentalItemID)
        if not line:
            raise HTTPException(status_code=400, detail=f"RentalItem {mark.rentalItemID} not found in rental.")

        remaining = int(line.Quantity or 0)
        if remaining <= 0:
            raise HTTPException(status_code=400, detail=f"RentalItem {line.RentalItemID} has no remaining quantity.")

        returned_qty = max(0, int(mark.returnedQuantity or 0))
        not_returned_qty = max(0, int(mark.notReturnedQuantity or 0))
        if returned_qty + not_returned_qty <= 0:
            raise HTTPException(status_code=400, detail=f"No quantities set for line {line.RentalItemID}.")
        if returned_qty + not_returned_qty > remaining:
            raise HTTPException(
                status_code=400,
                detail=f"Returned+NotReturned exceeds remaining quantity on line {line.RentalItemID}.",
            )

        if line.ToolInstanceID:
            if returned_qty == 1:
                instance = db.get(ToolInstance, line.ToolInstanceID)
                if instance:
                    instance.Status = "Available"
                    instance.UpdatedDate = datetime.now()
                line.Quantity = 0
                _mark_line_lifecycle(
                    line,
                    state="Returned",
                    operator_user_id=payload.operatorUserID,
                    extra={"receivedAt": receive_iso, "condition": mark.condition, "notes": mark.notes},
                )
            elif not_returned_qty == 1:
                _mark_line_lifecycle(
                    line,
                    state="Not Returned",
                    operator_user_id=payload.operatorUserID,
                    extra={"receivedAt": receive_iso, "condition": mark.condition, "notes": mark.notes},
                )
            continue

        if returned_qty > 0:
            db.add(
                RentalItem(
                    RentalID=rental.RentalID,
                    ToolID=line.ToolID,
                    ToolInstanceID=None,
                    Quantity=returned_qty,
                    DailyCost=line.DailyCost,
                    CheckoutNotes=f"RETURNED FROM LINE {line.RentalItemID}",
                    ReturnNotes=_build_lifecycle_payload(
                        state="Returned",
                        operator_user_id=payload.operatorUserID,
                        extra={"receivedAt": receive_iso, "condition": mark.condition, "notes": mark.notes},
                    ),
                )
            )

        line.Quantity = remaining - returned_qty
        target_state = "Not Returned" if not_returned_qty > 0 else ("Pending Pickup" if line.Quantity > 0 else "Returned")
        _mark_line_lifecycle(
            line,
            state=target_state,
            operator_user_id=payload.operatorUserID,
            extra={"receivedAt": receive_iso, "condition": mark.condition, "notes": mark.notes, "remainingQuantity": int(line.Quantity or 0)},
        )

    rental.UpdatedDate = datetime.now()
    if not _rental_has_open_quantity(rental):
        apply_return_updates(db, rental, "Returned via marked items", None)
    recalc_total_cost(rental)
    db.commit()
    db.refresh(rental)
    log_audit(
        db,
        "Rental",
        rental.RentalID,
        "ReceiveMarkedItems",
        f"Items received by {payload.operatorUserID}",
        user_id=payload.operatorUserID,
    )
    db.commit()
    return _serialize_rental_with_employee(rental, _safe_employee_directory())


@app.post("/api/rentals/{rental_id}/force-extend")
def force_extend_rental(
    request: Request,
    rental_id: int,
    payload: ExtensionRequest,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    actor_user_id = _resolve_actor_user_id(None, request, x_session_token)
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    current = _apply_runtime_state(rental)
    if current in TERMINAL_STATES:
        raise HTTPException(status_code=400, detail="Cannot force-extend a terminal rental.")
    if payload.newEndDate < rental.StartDate:
        raise HTTPException(status_code=400, detail="newEndDate must be on or after StartDate.")

    rental.EndDate = payload.newEndDate
    if current == "Overdue" and payload.newEndDate >= date.today():
        _transition_state(rental, "Active")
    rental.UpdatedDate = datetime.now()
    recalc_total_cost(rental)
    db.commit()
    log_audit(db, "Rental", rental_id, "ForceExtend", f"Force-extended to {payload.newEndDate}", user_id=actor_user_id)
    db.commit()
    return {"message": "Rental Force Extended"}


@app.post("/api/rentals/{rental_id}/force-return")
def force_return_rental(
    request: Request,
    rental_id: int,
    payload: ReturnRequest,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    actor_user_id = _resolve_actor_user_id(None, request, x_session_token)
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
    current = _apply_runtime_state(rental)
    if current in TERMINAL_STATES:
        raise HTTPException(status_code=400, detail="Cannot force-return a terminal rental.")

    apply_return_updates(db, rental, payload.condition or "Forced Return", payload.notes)
    db.commit()
    log_audit(db, "Rental", rental_id, "ForceReturn", "Rental force returned", user_id=actor_user_id)
    db.commit()
    return {"message": "Rental Force Returned"}


@app.post("/api/rentals/{rental_id}/mark-lost")
def mark_rental_lost(
    request: Request,
    rental_id: int,
    db: Session = Depends(get_asset_db),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
):
    actor_user_id = _resolve_actor_user_id(None, request, x_session_token)
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.Tool))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    rental_days = max(1, (rental.EndDate - rental.StartDate).days)
    total_loss = 0
    for item in rental.RentalItems:
        tool = item.Tool
        tool_value = float(tool.CurrentValue or tool.PurchaseCost or 0)
        income = float(item.TotalCost or (float(item.DailyCost or 0) * rental_days * item.Quantity))
        loss = max(tool_value * 0.65, tool_value - income)
        total_loss += loss

    rental.Status = "Lost"
    rental.LossAmount = total_loss
    rental.LossCalculatedAt = datetime.now()
    rental.LossReason = "Not returned"
    rental.UpdatedDate = datetime.now()
    db.commit()
    log_audit(db, "Rental", rental_id, "MarkLost", f"Loss {total_loss:.2f}", user_id=actor_user_id)
    db.commit()
    return {"message": "Rental marked as lost", "lossAmount": total_loss}


@app.get("/api/warehouse")
def get_warehouses(db: Session = Depends(get_asset_db)):
    warehouses = db.execute(select(Warehouse).order_by(Warehouse.WarehouseName)).scalars().all()
    return [
        {
            "warehouseID": w.WarehouseID,
            "warehouseName": w.WarehouseName,
            "description": w.Description,
            "address": w.Address,
            "gridColumns": w.GridColumns or 26,
            "gridRows": w.GridRows or 50,
            "managerID": w.ManagerID,
            "contactPhone": w.ContactPhone,
            "isActive": w.IsActive,
        }
        for w in warehouses
    ]


@app.post("/api/warehouse")
def create_warehouse(payload: dict, db: Session = Depends(get_asset_db)):
    name = payload.get("warehouseName") or payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="warehouseName is required")

    warehouse = Warehouse(
        WarehouseName=name,
        Description=payload.get("description"),
        Address=payload.get("address"),
        GridColumns=payload.get("gridColumns"),
        GridRows=payload.get("gridRows"),
        ManagerID=payload.get("managerID"),
        ContactPhone=payload.get("contactPhone"),
        CreatedDate=datetime.now(),
        IsActive=payload.get("isActive", True),
    )
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    log_audit(db, "Warehouse", warehouse.WarehouseID, "Create", warehouse.WarehouseName)
    db.commit()
    return {
        "warehouseID": warehouse.WarehouseID,
        "warehouseName": warehouse.WarehouseName,
        "gridColumns": warehouse.GridColumns,
        "gridRows": warehouse.GridRows,
    }


@app.put("/api/warehouse/{warehouse_id}")
def update_warehouse(warehouse_id: int, payload: dict, db: Session = Depends(get_asset_db)):
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    for key, value in payload.items():
        if key == "warehouseName":
            warehouse.WarehouseName = value
        elif key == "description":
            warehouse.Description = value
        elif key == "address":
            warehouse.Address = value
        elif key == "gridColumns":
            warehouse.GridColumns = value
        elif key == "gridRows":
            warehouse.GridRows = value
        elif key == "managerID":
            warehouse.ManagerID = value
        elif key == "contactPhone":
            warehouse.ContactPhone = value
        elif key == "isActive":
            warehouse.IsActive = value

    db.commit()
    log_audit(db, "Warehouse", warehouse.WarehouseID, "Update", "Warehouse updated")
    db.commit()
    return {"message": "Updated"}


@app.get("/api/warehouse/{warehouse_id}/tools")
def get_warehouse_tools(warehouse_id: int, db: Session = Depends(get_asset_db)):
    stmt = (
        select(ToolInstance, Tool)
        .join(Tool, Tool.ToolID == ToolInstance.ToolID)
        .where(ToolInstance.WarehouseID == warehouse_id)
        .where(ToolInstance.Status != "Retired")
    )
    tools = db.execute(stmt).all()
    return [
        {
            "toolID": tool.ToolID,
            "toolInstanceID": instance.ToolInstanceID,
            "toolName": tool.ToolName,
            "serialNumber": instance.SerialNumber,
            "status": instance.Status,
            "locationCode": instance.LocationCode,
        }
        for instance, tool in tools
    ]


@app.get("/api/warehouse/{warehouse_id}/instances")
def get_warehouse_instances(warehouse_id: int, db: Session = Depends(get_asset_db)):
    instances = db.execute(
        select(ToolInstance, Tool)
        .join(Tool, Tool.ToolID == ToolInstance.ToolID)
        .where(or_(ToolInstance.WarehouseID == warehouse_id, ToolInstance.WarehouseID.is_(None)))
        .order_by(Tool.ToolName, ToolInstance.SerialNumber)
    ).all()

    payload = []
    for instance, tool in instances:
        payload.append(
            {
                "toolInstanceID": instance.ToolInstanceID,
                "toolID": tool.ToolID,
                "toolName": tool.ToolName,
                "serialNumber": instance.SerialNumber,
                "status": instance.Status,
                "condition": instance.Condition,
                "locationCode": instance.LocationCode,
            }
        )
    return payload


@app.get("/api/warehouse/{warehouse_id}/locations")
def get_warehouse_locations(warehouse_id: int, db: Session = Depends(get_asset_db)):
    locations = db.execute(
        select(WarehouseLocation).where(WarehouseLocation.WarehouseID == warehouse_id)
    ).scalars().all()

    instances = db.execute(
        select(ToolInstance).where(ToolInstance.WarehouseID == warehouse_id)
    ).scalars().all()

    occupancy = {}
    for inst in instances:
        if not inst.LocationCode:
            continue
        occupancy.setdefault(inst.LocationCode, {"total": 0, "out": 0})
        occupancy[inst.LocationCode]["total"] += 1
        if inst.Status and inst.Status != "Available":
            occupancy[inst.LocationCode]["out"] += 1

    payload = []
    for loc in locations:
        code = f"{loc.GridColumn}-{loc.GridRow}"
        info = occupancy.get(code, {"total": 0, "out": 0})
        payload.append(
            {
                "locationID": loc.LocationID,
                "warehouseID": loc.WarehouseID,
                "gridColumn": loc.GridColumn,
                "gridRow": loc.GridRow,
                "locationCode": code,
                "isActive": loc.IsActive,
                "totalItems": info["total"],
                "outItems": info["out"],
            }
        )
    return payload


@app.post("/api/warehouse/{warehouse_id}/locations/generate")
def generate_warehouse_locations(warehouse_id: int, payload: dict | None = None, db: Session = Depends(get_asset_db)):
    warehouse = db.get(Warehouse, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    payload = payload or {}
    if payload.get("gridColumns") is not None:
        warehouse.GridColumns = payload.get("gridColumns")
    if payload.get("gridRows") is not None:
        warehouse.GridRows = payload.get("gridRows")
    db.commit()

    columns = int(warehouse.GridColumns or 0)
    rows = int(warehouse.GridRows or 0)
    if columns <= 0 or rows <= 0:
        raise HTTPException(status_code=400, detail="Warehouse grid dimensions not set")

    existing = db.execute(
        select(WarehouseLocation).where(WarehouseLocation.WarehouseID == warehouse_id)
    ).scalars().all()
    existing_codes = {f"{loc.GridColumn}-{loc.GridRow}" for loc in existing}

    created = 0
    for c in range(columns):
        col = chr(ord("A") + c)
        for r in range(1, rows + 1):
            code = f"{col}-{r}"
            if code in existing_codes:
                continue
            db.add(
                WarehouseLocation(
                    WarehouseID=warehouse_id,
                    GridColumn=col,
                    GridRow=r,
                    IsActive=True,
                    CreatedDate=datetime.now(),
                )
            )
            created += 1

    db.commit()
    log_audit(db, "Warehouse", warehouse_id, "GenerateLocations", f"Created {created} locations")
    db.commit()
    return {"created": created}


@app.post("/api/warehouse/assign")
def assign_tool_location(payload: ToolLocationAssignmentDto, db: Session = Depends(get_asset_db)):
    instance = db.get(ToolInstance, payload.toolID)
    if not instance:
        raise HTTPException(status_code=404, detail="Tool instance not found")

    instance.LocationCode = payload.locationCode
    if payload.locationCode == "":
        instance.LocationCode = None
    instance.WarehouseID = payload.warehouseID
    instance.UpdatedDate = datetime.now()

    db.commit()
    log_audit(db, "ToolInstance", instance.ToolInstanceID, "AssignLocation", f"{payload.locationCode}")
    db.commit()
    return {"message": f"Tool assigned to {payload.locationCode}"}


@app.post("/api/notifications/run")
def run_notifications(db: Session = Depends(get_asset_db)):
    today = date.today()
    due_soon = today + timedelta(days=7)

    rentals = db.execute(select(Rental)).scalars().all()
    created = 0
    for rental in rentals:
        state = _apply_runtime_state(rental)
        if state not in {"Active", "Overdue"}:
            continue
        if rental.EndDate and today <= rental.EndDate <= due_soon:
            db.add(
                NotificationQueue(
                    RentalID=rental.RentalID,
                    NotificationType="DueSoon",
                    Payload=f"Rental {rental.RentalNumber} due {rental.EndDate}",
                    CreatedAt=datetime.now(),
                )
            )
            created += 1
        if state == "Overdue":
            db.add(
                NotificationQueue(
                    RentalID=rental.RentalID,
                    NotificationType="Overdue",
                    Payload=f"Rental {rental.RentalNumber} overdue {rental.EndDate}",
                    CreatedAt=datetime.now(),
                )
            )
            created += 1

    db.commit()
    return {"created": created}


@app.get("/api/notifications/pending")
def get_pending_notifications(db: Session = Depends(get_asset_db)):
    notifications = db.execute(
        select(NotificationQueue).where(NotificationQueue.SentAt.is_(None))
    ).scalars().all()
    return [
        {
            "notificationID": n.NotificationID,
            "rentalID": n.RentalID,
            "type": n.NotificationType,
            "payload": n.Payload,
            "createdAt": n.CreatedAt,
        }
        for n in notifications
    ]


def _map_tool_field(field: str) -> str:
    mapping = {
        "toolID": "ToolID",
        "toolName": "ToolName",
        "serialNumber": "SerialNumber",
        "modelNumber": "ModelNumber",
        "manufacturer": "Manufacturer",
        "categoryID": "CategoryID",
        "description": "Description",
        "purchaseDate": "PurchaseDate",
        "purchaseCost": "PurchaseCost",
        "currentValue": "CurrentValue",
        "calibrationInterval": "CalibrationInterval",
        "lastCalibration": "LastCalibration",
        "nextCalibration": "NextCalibration",
        "status": "Status",
        "condition": "Condition",
        "dailyRentalCost": "DailyRentalCost",
        "requiresCertification": "RequiresCertification",
        "warehouseID": "WarehouseID",
        "locationCode": "LocationCode",
        "imagePath": "ImagePath",
    }
    return mapping.get(field, field)


def _map_instance_field(field: str) -> str:
    mapping = {
        "toolInstanceID": "ToolInstanceID",
        "toolID": "ToolID",
        "serialNumber": "SerialNumber",
        "instanceNumber": "InstanceNumber",
        "status": "Status",
        "condition": "Condition",
        "warehouseID": "WarehouseID",
        "locationCode": "LocationCode",
        "requiresCertification": "RequiresCertification",
        "calibrationInterval": "CalibrationInterval",
        "lastCalibration": "LastCalibration",
        "nextCalibration": "NextCalibration",
        "imagePath": "ImagePath",
    }
    return mapping.get(field, field)


def _build_lifecycle_payload(
    state: str,
    operator_user_id: int | None = None,
    extra: dict | None = None,
    previous: dict | None = None,
) -> str:
    payload = dict(previous or {})
    history = list(payload.get("history", []))
    entry = {
        "state": state,
        "at": datetime.now().isoformat(),
        "operatorUserID": operator_user_id,
    }
    if extra:
        entry.update(extra)
    history.append(entry)
    payload["state"] = state
    payload["history"] = history
    return json.dumps(payload, ensure_ascii=True)


def _parse_lifecycle_payload(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _mark_line_lifecycle(
    line: RentalItem,
    state: str,
    operator_user_id: int | None = None,
    extra: dict | None = None,
) -> None:
    previous = _parse_lifecycle_payload(line.ReturnNotes)
    line.ReturnNotes = _build_lifecycle_payload(
        state=state,
        operator_user_id=operator_user_id,
        extra=extra,
        previous=previous,
    )


def _rental_has_open_quantity(rental: Rental) -> bool:
    for item in rental.RentalItems:
        if int(item.Quantity or 0) > 0:
            return True
    return False


def _rank_instances_for_allocation(
    db: Session,
    tool_id: int,
    candidate_instance_ids: list[int],
) -> list[int]:
    if not candidate_instance_ids:
        return []
    rows = db.execute(
        select(RentalItem.ToolInstanceID, Rental.StartDate, Rental.EndDate)
        .join(Rental, Rental.RentalID == RentalItem.RentalID)
        .where(RentalItem.ToolID == tool_id)
        .where(RentalItem.ToolInstanceID.in_(candidate_instance_ids))
        .where(Rental.Status.notin_(["Offer"]))
    ).all()
    days_by_instance: dict[int, int] = {iid: 0 for iid in candidate_instance_ids}
    for iid, start_date, end_date in rows:
        if iid is None:
            continue
        days_by_instance[iid] = days_by_instance.get(iid, 0) + max(1, (end_date - start_date).days)
    return sorted(candidate_instance_ids, key=lambda iid: (-days_by_instance.get(iid, 0), iid))


def _apply_shortage_actions(rental: Rental, shortage_actions: list, operator_user_id: int | None) -> None:
    if not shortage_actions:
        return
    action_map = {int(a.rentalItemID): a for a in shortage_actions}
    for line in rental.RentalItems:
        action = action_map.get(int(line.RentalItemID))
        if not action:
            continue
        if action.action == "exclude":
            line.Quantity = 0
        _mark_line_lifecycle(
            line,
            state="Excluded from Order" if action.action == "exclude" else "Shortage Action Set",
            operator_user_id=operator_user_id,
            extra={
                "shortageAction": action.action,
                "shortageOwner": action.owner,
                "shortageDueDate": action.dueDate.isoformat() if action.dueDate else None,
                "shortageNotes": action.notes,
            },
        )


def _allocate_reservation_lines(db: Session, rental: Rental, operator_user_id: int | None) -> dict:
    # Group only pending/shortage lines that still carry quantity
    request_lines = [line for line in rental.RentalItems if int(line.Quantity or 0) > 0]
    requested_by_tool: dict[int, int] = {}
    for line in request_lines:
        requested_by_tool[line.ToolID] = requested_by_tool.get(line.ToolID, 0) + int(line.Quantity or 0)

    reserved_count = 0
    shortage_count = 0
    now_iso = datetime.now().isoformat()

    for tool_id, qty in requested_by_tool.items():
        if qty <= 0:
            continue
        available_instances = _get_available_instances(db, tool_id, rental.StartDate, rental.EndDate)
        ranked_ids = _rank_instances_for_allocation(
            db,
            tool_id,
            [inst.ToolInstanceID for inst in available_instances],
        )
        selected_ids = ranked_ids[:qty]

        for instance_id in selected_ids:
            instance = db.get(ToolInstance, instance_id)
            if instance:
                instance.Status = "Reserved"
                instance.UpdatedDate = datetime.now()
            db.add(
                RentalItem(
                    RentalID=rental.RentalID,
                    ToolID=tool_id,
                    ToolInstanceID=instance_id,
                    Quantity=1,
                    DailyCost=_resolve_tool_daily_cost(rental, tool_id),
                    CheckoutNotes="AUTO RESERVED ON APPROVAL",
                    ReturnNotes=_build_lifecycle_payload(
                        state="Reserved",
                        operator_user_id=operator_user_id,
                        extra={"reservedAt": now_iso},
                    ),
                )
            )
            reserved_count += 1

        shortage_qty = max(0, qty - len(selected_ids))
        if shortage_qty > 0:
            shortage_count += shortage_qty
            db.add(
                RentalItem(
                    RentalID=rental.RentalID,
                    ToolID=tool_id,
                    ToolInstanceID=None,
                    Quantity=shortage_qty,
                    DailyCost=_resolve_tool_daily_cost(rental, tool_id),
                    CheckoutNotes=f"DEFICIT: {shortage_qty} pending shortage handling",
                    ReturnNotes=_build_lifecycle_payload(
                        state="Pending Pickup",
                        operator_user_id=operator_user_id,
                        extra={"deficit": True, "approvedWithShortage": True},
                    ),
                )
            )

    # Consume old request lines after allocation to avoid double counting.
    for line in request_lines:
        line.Quantity = 0
        _mark_line_lifecycle(
            line,
            state="Superseded",
            operator_user_id=operator_user_id,
            extra={"supersededByApproval": True},
        )

    return {"reservedCount": reserved_count, "shortageCount": shortage_count}


def _resolve_tool_daily_cost(rental: Rental, tool_id: int) -> float:
    for line in rental.RentalItems:
        if line.ToolID == tool_id and line.DailyCost is not None:
            return float(line.DailyCost)
    return 0.0


def _activate_rental(db: Session, rental: Rental, approved_by: int | None = None) -> None:
    _transition_state(rental, "Active")
    rental.ApprovedBy = approved_by
    rental.ApprovalDate = date.today()
    rental.ActualStart = rental.ActualStart or date.today()
    rental.UpdatedDate = datetime.now()

    for item in rental.RentalItems:
        if not item.ToolInstanceID:
            continue
        _mark_line_lifecycle(item, state="Picked Up", operator_user_id=approved_by, extra={"pickedAt": datetime.now().isoformat()})
        instance = db.get(ToolInstance, item.ToolInstanceID)
        if instance:
            instance.Status = "In Rental"
            instance.UpdatedDate = datetime.now()


def _save_data_url_image(data_url: str, destination_dir: Path, prefix: str) -> str:
    raw = (data_url or "").strip()
    if not raw.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Invalid image payload format.")

    parts = raw.split(",", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Invalid data URL payload.")

    meta, b64_data = parts
    ext = "jpg"
    if "image/png" in meta:
        ext = "png"
    elif "image/webp" in meta:
        ext = "webp"
    elif "image/gif" in meta:
        ext = "gif"

    try:
        binary = base64.b64decode(b64_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 image data.") from exc

    destination_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{uuid.uuid4().hex}.{ext}"
    target = destination_dir / filename
    with target.open("wb") as output:
        output.write(binary)
    return f"/uploads/rentals/{filename}"


def _safe_employee_directory() -> dict[str, dict[str, str]]:
    try:
        return get_employee_directory()
    except EmployeeDirectoryError:
        return {}


def _get_active_session(request: Request, session_token: str | None) -> dict | None:
    session_from_cookie = request.session.get("user")
    if isinstance(session_from_cookie, dict):
        return dict(session_from_cookie)
    session_from_token = get_session(session_token)
    if session_from_token:
        request.session["user"] = dict(session_from_token)
        return dict(session_from_token)
    return None


def _require_session_or_401(request: Request, session_token: str | None) -> dict:
    session = _get_active_session(request, session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return session


def _require_admin_session_or_403(request: Request, session_token: str | None) -> dict:
    session = _require_session_or_401(request, session_token)
    if str(session.get("role") or "").strip() != "Admin":
        raise HTTPException(status_code=403, detail="Admin role required.")
    return session


def _resolve_actor_user_id(candidate_user_id: int | None, request: Request, session_token: str | None) -> int | None:
    if candidate_user_id is not None:
        try:
            value = int(candidate_user_id)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    session = _get_active_session(request, session_token)
    if not session:
        return None
    try:
        value = int(session.get("employeeID") or 0)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _resolve_employee_number_or_400(raw_value: int | str) -> int:
    raw = str(raw_value).strip()
    if not raw or not raw.isdigit():
        raise HTTPException(status_code=400, detail="employeeID must be a numeric employee number.")
    value = int(raw)
    if value <= 0:
        raise HTTPException(status_code=400, detail="employeeID must be greater than zero.")
    return value


def _require_employee_or_400(employee_id: int) -> dict[str, str]:
    try:
        directory = get_employee_directory()
    except EmployeeDirectoryError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Employee directory unavailable: {exc}",
        ) from exc

    entry = directory.get(str(employee_id))
    if not entry:
        raise HTTPException(status_code=400, detail="employeeID is not found in employee directory.")
    return entry


def _serialize_rental_with_employee(rental: Rental, employee_directory: dict[str, dict[str, str]] | None = None) -> dict:
    payload = serialize_rental(rental)
    directory = employee_directory or {}
    employee_key = str(payload.get("employeeID"))
    employee_entry = directory.get(employee_key)
    if employee_entry:
        payload["employeeName"] = employee_entry.get("name")
        payload["employeeInitials"] = employee_entry.get("initials")
        payload["employeeDisplay"] = employee_entry.get("displayName")
    else:
        fallback_id = payload.get("employeeID")
        payload["employeeName"] = None
        payload["employeeInitials"] = None
        payload["employeeDisplay"] = f"Employee #{fallback_id}" if fallback_id is not None else "Unknown employee"

    approver = payload.get("approvedBy")
    if approver is None:
        payload["approvedByDisplay"] = None
    else:
        approver_entry = directory.get(str(approver))
        payload["approvedByDisplay"] = (
            approver_entry.get("displayName")
            if approver_entry
            else f"Employee #{approver}"
        )
    return payload


def _normalize_state(raw: str | None) -> str:
    state = (raw or "Reserved").strip()
    return STATE_ALIASES.get(state, state)


def _apply_runtime_state(rental: Rental) -> str:
    current = _normalize_state(rental.Status)
    if current == "Active" and rental.EndDate and rental.EndDate < date.today():
        rental.Status = "Overdue"
        rental.UpdatedDate = datetime.now()
        return "Overdue"
    known_states = set(STATE_ALIASES.values()) | RESERVATION_STATES | TERMINAL_STATES
    if current in known_states:
        rental.Status = current
    return rental.Status


def _transition_state(rental: Rental, target_state: str) -> None:
    current = _normalize_state(rental.Status)
    target = _normalize_state(target_state)
    if target == current:
        return
    if current not in STATE_TRANSITIONS or target not in STATE_TRANSITIONS[current]:
        raise HTTPException(status_code=400, detail=f"Invalid state transition: {current} -> {target}")
    rental.Status = target
    rental.UpdatedDate = datetime.now()


def _has_instance_overlap(
    db: Session,
    tool_instance_id: int,
    start_date: date,
    end_date: date,
    exclude_rental_id: int | None = None,
) -> bool:
    stmt = (
        select(RentalItem.ToolInstanceID, Rental.Status)
        .join(Rental, Rental.RentalID == RentalItem.RentalID)
        .where(RentalItem.ToolInstanceID == tool_instance_id)
        .where(Rental.StartDate <= end_date)
        .where(Rental.EndDate >= start_date)
    )
    if exclude_rental_id:
        stmt = stmt.where(Rental.RentalID != exclude_rental_id)

    rows = db.execute(stmt).all()
    for _, raw_status in rows:
        if _normalize_state(raw_status) in BLOCKING_STATES:
            return True
    return False


def _get_available_instances(
    db: Session,
    tool_id: int,
    start_date: date,
    end_date: date,
    exclude_instance_ids: list[int] | None = None,
) -> list[ToolInstance]:
    exclude_ids = set(exclude_instance_ids or [])

    overlap_stmt = (
        select(RentalItem.ToolInstanceID, Rental.Status)
        .join(Rental, Rental.RentalID == RentalItem.RentalID)
        .where(RentalItem.ToolID == tool_id)
        .where(RentalItem.ToolInstanceID.is_not(None))
        .where(Rental.StartDate <= end_date)
        .where(Rental.EndDate >= start_date)
    )
    busy_ids: set[int] = set()
    for row in db.execute(overlap_stmt).all():
        instance_id, raw_status = row
        if instance_id is None:
            continue
        if _normalize_state(raw_status) in BLOCKING_STATES:
            busy_ids.add(instance_id)

    instances = db.execute(
        select(ToolInstance)
        .where(ToolInstance.ToolID == tool_id)
        .where(ToolInstance.Status == "Available")
        .order_by(ToolInstance.SerialNumber)
    ).scalars().all()

    available: list[ToolInstance] = []
    for instance in instances:
        if instance.ToolInstanceID in busy_ids or instance.ToolInstanceID in exclude_ids:
            continue
        if instance.RequiresCertification:
            if not instance.NextCalibration or instance.NextCalibration < end_date:
                continue
        available.append(instance)
    return available


def _validate_manual_instance(
    db: Session,
    tool_id: int,
    tool_instance_id: int,
    start_date: date,
    end_date: date,
) -> ToolInstance:
    instance = db.get(ToolInstance, tool_instance_id)
    if not instance or instance.ToolID != tool_id:
        raise HTTPException(status_code=400, detail="Invalid tool instance selected.")
    if instance.Status != "Available":
        raise HTTPException(status_code=400, detail="Selected tool instance is not available.")
    if instance.RequiresCertification:
        if not instance.NextCalibration or instance.NextCalibration < end_date:
            raise HTTPException(status_code=400, detail="Selected tool instance expires before rental end.")
    if _has_instance_overlap(db, tool_instance_id, start_date, end_date):
        raise HTTPException(status_code=400, detail="Selected tool instance overlaps existing reservation.")
    return instance


def _release_reserved_instances(db: Session, rental: Rental) -> None:
    for item in rental.RentalItems:
        if not item.ToolInstanceID:
            continue
        instance = db.get(ToolInstance, item.ToolInstanceID)
        if not instance:
            continue
        if instance.Status in {"Reserved", "Rented"}:
            instance.Status = "Available"
            instance.UpdatedDate = datetime.now()


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
