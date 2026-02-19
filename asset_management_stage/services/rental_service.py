from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.asset_models import Rental, RentalItem, Tool, ToolInstance


def generate_rental_number(db: Session) -> str:
    last = db.execute(select(Rental).order_by(Rental.RentalID.desc())).scalars().first()
    next_number = 1
    if last and last.RentalNumber:
        raw = last.RentalNumber.replace("RNT-", "")
        try:
            next_number = int(raw) + 1
        except ValueError:
            next_number = 1
    return f"RNT-{next_number:03d}"


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
        total += daily * rental_days * item.Quantity
    rental.TotalCost = total


def serialize_rental(rental: Rental) -> dict:
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
        "rentalItems": [
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
            for item in rental.RentalItems
        ],
    }


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
