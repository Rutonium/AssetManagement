from __future__ import annotations

from datetime import date, datetime
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.asset_models import Rental, RentalItem, Tool, ToolInstance


def generate_rental_number(db: Session, prefix: str = "RNT") -> str:
    token = (prefix or "RNT").upper()
    last = db.execute(
        select(Rental)
        .where(Rental.RentalNumber.like(f"{token}-%"))
        .order_by(Rental.RentalID.desc())
    ).scalars().first()
    next_number = 1
    if last and last.RentalNumber:
        raw = last.RentalNumber.replace(f"{token}-", "")
        try:
            next_number = int(raw) + 1
        except ValueError:
            next_number = 1
    return f"{token}-{next_number:03d}"


def generate_offer_number(db: Session, created_on: date | None = None) -> str:
    current_date = created_on or date.today()
    yy = f"{current_date.year % 100:02d}"

    rows = db.execute(
        select(Rental.RentalNumber).where(Rental.RentalNumber.like(f"{yy}%"))
    ).all()

    max_suffix = 0
    for row in rows:
        number = (row[0] or "").strip()
        if len(number) != 6 or not number.isdigit():
            continue
        if not number.startswith(yy):
            continue
        suffix = int(number[2:])
        if suffix > max_suffix:
            max_suffix = suffix

    next_suffix = max_suffix + 1
    return f"{yy}{next_suffix:04d}"


def recalc_total_cost(rental: Rental) -> None:
    if not rental.RentalItems:
        rental.TotalCost = 0
        return

    rental_days = (rental.EndDate - rental.StartDate).days
    if rental_days < 1:
        rental_days = 1

    total = 0
    for item in rental.RentalItems:
        daily = float(item.DailyCost or 0)
        quantity = int(item.Quantity or 0)
        line_total = daily * rental_days * quantity
        item.TotalCost = line_total
        total += line_total
    rental.TotalCost = total


def serialize_rental(rental: Rental) -> dict:
    rental_items = []
    deficit_quantity = 0
    invoiceable_quantity = 0
    for item in rental.RentalItems:
        notes = item.CheckoutNotes or ""
        is_deficit = item.ToolInstanceID is None and "DEFICIT" in notes.upper()
        lifecycle = _parse_lifecycle(item.ReturnNotes)
        if is_deficit:
            deficit_quantity += int(item.Quantity or 0)
        state = str(lifecycle.get("state") or "")
        is_invoiceable = state == "Picked Up"
        if is_invoiceable:
            invoiceable_quantity += int(item.Quantity or 0)
        rental_items.append(
            {
                "rentalItemID": item.RentalItemID,
                "rentalID": item.RentalID,
                "toolID": item.ToolID,
                "toolInstanceID": item.ToolInstanceID,
                "quantity": item.Quantity,
                "dailyCost": item.DailyCost,
                "totalCost": item.TotalCost,
                "checkoutNotes": item.CheckoutNotes,
                "returnNotes": item.ReturnNotes,
                "isAllocated": item.ToolInstanceID is not None,
                "isDeficit": is_deficit,
                "isInvoiceable": is_invoiceable,
                "lifecycle": lifecycle,
                "tool": {
                    "toolID": item.Tool.ToolID,
                    "toolName": item.Tool.ToolName,
                    "serialNumber": item.Tool.SerialNumber,
                } if item.Tool else None,
                "instance": {
                    "toolInstanceID": item.ToolInstance.ToolInstanceID,
                    "serialNumber": item.ToolInstance.SerialNumber,
                    "status": item.ToolInstance.Status,
                    "lastCalibration": item.ToolInstance.LastCalibration,
                    "nextCalibration": item.ToolInstance.NextCalibration,
                } if item.ToolInstance else None,
            }
        )

    return {
        "rentalID": rental.RentalID,
        "rentalNumber": rental.RentalNumber,
        "employeeID": rental.EmployeeID,
        "purpose": rental.Purpose,
        "projectCode": rental.ProjectCode,
        "status": rental.Status,
        "startDate": rental.StartDate,
        "endDate": rental.EndDate,
        "actualStart": rental.ActualStart,
        "actualEnd": rental.ActualEnd,
        "totalCost": rental.TotalCost,
        "approvedBy": rental.ApprovedBy,
        "approvalDate": rental.ApprovalDate,
        "checkoutCondition": rental.CheckoutCondition,
        "returnCondition": rental.ReturnCondition,
        "notes": rental.Notes,
        "createdDate": rental.CreatedDate,
        "updatedDate": rental.UpdatedDate,
        "hasDeficit": deficit_quantity > 0,
        "deficitQuantity": deficit_quantity,
        "invoiceableQuantity": invoiceable_quantity,
        "rentalItems": rental_items,
    }


def _parse_lifecycle(raw: str | None) -> dict:
    if not raw:
        return {}
    value = raw.strip()
    if not value.startswith("{"):
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, json.JSONDecodeError):
        return {}


def apply_return_updates(db: Session, rental: Rental, return_condition: str, return_notes: str | None) -> None:
    rental.Status = "Returned"
    rental.ActualEnd = date.today()
    rental.ReturnCondition = return_condition
    rental.UpdatedDate = datetime.now()

    if return_notes:
        rental.Notes = (rental.Notes + "\n" if rental.Notes else "") + return_notes

    for item in rental.RentalItems:
        if item.ToolInstanceID:
            instance = db.get(ToolInstance, item.ToolInstanceID)
            if instance:
                instance.Status = "Available"
                instance.UpdatedDate = datetime.now()
            continue

        tool = db.get(Tool, item.ToolID)
        if tool:
            tool.Status = "Available"
            tool.UpdatedDate = datetime.now()
