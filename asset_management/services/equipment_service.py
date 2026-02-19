from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.asset_models import Tool, ToolInstance


def _parse_seq(serial_number: str) -> Optional[int]:
    parts = serial_number.split("-")
    if len(parts) != 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def generate_next_registration_number(db: Session) -> str:
    year = date.today().year
    prefix = f"SP{year}-"

    stmt_tools = select(Tool.SerialNumber).where(Tool.SerialNumber.startswith(prefix))
    stmt_instances = select(ToolInstance.SerialNumber).where(ToolInstance.SerialNumber.startswith(prefix))
    existing = db.execute(stmt_tools).scalars().all()
    existing_instances = db.execute(stmt_instances).scalars().all()

    max_seq = 0
    for serial in existing + existing_instances:
        if not serial:
            continue
        seq = _parse_seq(serial)
        if seq and seq > max_seq:
            max_seq = seq

    next_seq = max_seq + 1
    return f"{prefix}{next_seq:04d}"


def apply_certification_schedule(tool: Tool) -> None:
    if not tool.RequiresCertification:
        tool.CalibrationInterval = None
        tool.LastCalibration = None
        tool.NextCalibration = None
        return

    if not tool.LastCalibration:
        tool.LastCalibration = date.today()

    if tool.CalibrationInterval and tool.CalibrationInterval > 0:
        months = tool.CalibrationInterval
        year = tool.LastCalibration.year + (tool.LastCalibration.month - 1 + months) // 12
        month = (tool.LastCalibration.month - 1 + months) % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(tool.LastCalibration.day, last_day)
        tool.NextCalibration = date(year, month, day)
    else:
        tool.NextCalibration = None


def apply_instance_certification_schedule(instance: ToolInstance) -> None:
    if not instance.RequiresCertification:
        instance.CalibrationInterval = None
        instance.LastCalibration = None
        instance.NextCalibration = None
        return

    if not instance.LastCalibration:
        instance.LastCalibration = date.today()

    if instance.CalibrationInterval and instance.CalibrationInterval > 0:
        months = instance.CalibrationInterval
        year = instance.LastCalibration.year + (instance.LastCalibration.month - 1 + months) // 12
        month = (instance.LastCalibration.month - 1 + months) % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(instance.LastCalibration.day, last_day)
        instance.NextCalibration = date(year, month, day)
    else:
        instance.NextCalibration = None


def generate_next_instance_number(db: Session, tool_id: int) -> int:
    stmt = select(ToolInstance.InstanceNumber).where(ToolInstance.ToolID == tool_id)
    existing = db.execute(stmt).scalars().all()
    max_seq = 0
    for number in existing:
        if number and number > max_seq:
            max_seq = number
    return max_seq + 1


def build_instance_serial(tool_serial: str | None, instance_number: int) -> str:
    base = tool_serial or "SP"
    return f"{base}-{instance_number:04d}"


def serialize_tool(tool: Tool, instance_count: int | None = None) -> dict:
    payload = {
        "toolID": tool.ToolID,
        "toolName": tool.ToolName,
        "serialNumber": tool.SerialNumber,
        "modelNumber": tool.ModelNumber,
        "manufacturer": tool.Manufacturer,
        "categoryID": tool.CategoryID,
        "description": tool.Description,
        "purchaseDate": tool.PurchaseDate,
        "purchaseCost": tool.PurchaseCost,
        "currentValue": tool.CurrentValue,
        "calibrationInterval": tool.CalibrationInterval,
        "lastCalibration": tool.LastCalibration,
        "nextCalibration": tool.NextCalibration,
        "status": tool.Status,
        "condition": tool.Condition,
        "dailyRentalCost": tool.DailyRentalCost,
        "requiresCertification": bool(tool.RequiresCertification),
        "warehouseID": tool.WarehouseID,
        "locationCode": tool.LocationCode,
        "imagePath": tool.ImagePath,
        "createdDate": tool.CreatedDate,
        "updatedDate": tool.UpdatedDate,
    }
    if instance_count is not None:
        payload["instanceCount"] = instance_count
    return payload


def serialize_instance(instance: ToolInstance) -> dict:
    return {
        "toolInstanceID": instance.ToolInstanceID,
        "toolID": instance.ToolID,
        "serialNumber": instance.SerialNumber,
        "instanceNumber": instance.InstanceNumber,
        "status": instance.Status,
        "condition": instance.Condition,
        "warehouseID": instance.WarehouseID,
        "locationCode": instance.LocationCode,
        "requiresCertification": bool(instance.RequiresCertification),
        "calibrationInterval": instance.CalibrationInterval,
        "lastCalibration": instance.LastCalibration,
        "nextCalibration": instance.NextCalibration,
        "imagePath": instance.ImagePath,
        "createdDate": instance.CreatedDate,
        "updatedDate": instance.UpdatedDate,
    }
