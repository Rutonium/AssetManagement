import os
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from db.deps import get_asset_db
from models.asset_models import AuditLog, NotificationQueue, Rental, RentalItem, Tool, ToolInstance, Warehouse, WarehouseLocation
from schemas.equipment import EquipmentUpsert, ToolInstanceUpsert
from schemas.rentals import CreateRentalDto, ExtensionRequest, ReturnRequest
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
from services.rental_service import (
    apply_return_updates,
    generate_rental_number,
    recalc_total_cost,
    serialize_rental,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads" / "tools"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

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
    return [serialize_rental(rental) for rental in rentals]


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
    return serialize_rental(rental)


@app.post("/api/rentals")
def create_rental(payload: CreateRentalDto, db: Session = Depends(get_asset_db)):
    rental = Rental(
        EmployeeID=payload.employeeID,
        Purpose=payload.purpose,
        ProjectCode=payload.projectCode,
        StartDate=payload.startDate,
        EndDate=payload.endDate,
        Notes=payload.notes,
        Status="Pending",
        RentalNumber="TEMP",
        CreatedDate=datetime.now(),
        UpdatedDate=datetime.now(),
    )

    rental.RentalNumber = generate_rental_number(db)

    for item in payload.rentalItems:
        instance_id = item.toolInstanceID
        if instance_id:
            instance = db.get(ToolInstance, instance_id)
            if not instance or instance.ToolID != item.toolID:
                raise HTTPException(status_code=400, detail="Invalid tool instance selected.")
            if instance.Status != "Available":
                raise HTTPException(status_code=400, detail="Selected tool instance is not available.")
            if instance.RequiresCertification:
                if not instance.NextCalibration or instance.NextCalibration < payload.endDate:
                    raise HTTPException(status_code=400, detail="Selected tool instance expires before rental end.")
        else:
            instance_id = _auto_pick_instance(
                db,
                item.toolID,
                payload.startDate,
                payload.endDate,
            )
            if not instance_id:
                raise HTTPException(status_code=400, detail="No available instances for rental period.")

        rental_item = RentalItem(
            ToolID=item.toolID,
            ToolInstanceID=instance_id,
            Quantity=item.quantity,
            DailyCost=item.dailyCost,
        )
        rental.RentalItems.append(rental_item)

    recalc_total_cost(rental)
    db.add(rental)
    db.commit()
    db.refresh(rental)

    return serialize_rental(rental)


@app.post("/api/rentals/{rental_id}/approve")
def approve_rental(rental_id: int, db: Session = Depends(get_asset_db)):
    rental = db.get(Rental, rental_id)
    if not rental or rental.Status != "Pending":
        raise HTTPException(status_code=400, detail="Could not approve rental.")

    rental.Status = "Approved"
    rental.ApprovedBy = 1
    rental.ApprovalDate = date.today()
    rental.UpdatedDate = datetime.now()

    db.commit()
    log_audit(db, "Rental", rental_id, "Approve", f"Approved by {rental.ApprovedBy}")
    db.commit()
    return {"message": "Rental Approved"}


@app.post("/api/rentals/{rental_id}/extend")
def extend_rental(rental_id: int, payload: ExtensionRequest, db: Session = Depends(get_asset_db)):
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental or rental.Status != "Active":
        raise HTTPException(status_code=400, detail="Could not extend rental.")

    for item in rental.RentalItems:
        if item.ToolInstance and item.ToolInstance.RequiresCertification:
            if not item.ToolInstance.NextCalibration or item.ToolInstance.NextCalibration < payload.newEndDate:
                raise HTTPException(status_code=400, detail="One or more items expire before the new end date.")

    rental.EndDate = payload.newEndDate
    rental.UpdatedDate = datetime.now()
    recalc_total_cost(rental)

    db.commit()
    log_audit(db, "Rental", rental_id, "Extend", f"Extended to {payload.newEndDate}")
    db.commit()
    return {"message": "Rental Extended"}


@app.post("/api/rentals/{rental_id}/cancel")
def cancel_rental(rental_id: int, db: Session = Depends(get_asset_db)):
    rental = db.get(Rental, rental_id)
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    rental.Status = "Cancelled"
    rental.UpdatedDate = datetime.now()
    db.commit()
    log_audit(db, "Rental", rental_id, "Cancel", "Rental cancelled")
    db.commit()
    return {"message": "Rental Cancelled"}


@app.post("/api/rentals/{rental_id}/return")
def return_rental(rental_id: int, payload: ReturnRequest, db: Session = Depends(get_asset_db)):
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental or rental.Status != "Active":
        raise HTTPException(status_code=400, detail="Could not process return. Check if rental is active.")

    apply_return_updates(db, rental, payload.condition, payload.notes)
    db.commit()
    log_audit(db, "Rental", rental_id, "Return", "Rental returned")
    db.commit()
    return {"message": "Return processed successfully"}


@app.post("/api/rentals/{rental_id}/force-extend")
def force_extend_rental(rental_id: int, payload: ExtensionRequest, db: Session = Depends(get_asset_db)):
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    rental.EndDate = payload.newEndDate
    rental.UpdatedDate = datetime.now()
    recalc_total_cost(rental)
    db.commit()
    log_audit(db, "Rental", rental_id, "ForceExtend", f"Force-extended to {payload.newEndDate}")
    db.commit()
    return {"message": "Rental Force Extended"}


@app.post("/api/rentals/{rental_id}/force-return")
def force_return_rental(rental_id: int, payload: ReturnRequest, db: Session = Depends(get_asset_db)):
    stmt = (
        select(Rental)
        .options(selectinload(Rental.RentalItems))
        .options(selectinload(Rental.RentalItems).selectinload(RentalItem.ToolInstance))
        .where(Rental.RentalID == rental_id)
    )
    rental = db.execute(stmt).scalars().first()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    apply_return_updates(db, rental, payload.condition or "Forced Return", payload.notes)
    db.commit()
    log_audit(db, "Rental", rental_id, "ForceReturn", "Rental force returned")
    db.commit()
    return {"message": "Rental Force Returned"}


@app.post("/api/rentals/{rental_id}/mark-lost")
def mark_rental_lost(rental_id: int, db: Session = Depends(get_asset_db)):
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
    log_audit(db, "Rental", rental_id, "MarkLost", f"Loss {total_loss:.2f}")
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
        .where(ToolInstance.WarehouseID == warehouse_id)
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
        if rental.Status not in ("Active", "Approved"):
            continue
        if rental.EndDate and rental.EndDate <= due_soon:
            db.add(
                NotificationQueue(
                    RentalID=rental.RentalID,
                    NotificationType="DueSoon",
                    Payload=f"Rental {rental.RentalNumber} due {rental.EndDate}",
                    CreatedAt=datetime.now(),
                )
            )
            created += 1
        if rental.EndDate and rental.EndDate < today:
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


def _auto_pick_instance(db: Session, tool_id: int, start_date: date, end_date: date) -> int | None:
    busy_stmt = (
        select(RentalItem.ToolInstanceID)
        .join(Rental, Rental.RentalID == RentalItem.RentalID)
        .where(RentalItem.ToolInstanceID.is_not(None))
        .where(RentalItem.ToolID == tool_id)
        .where(Rental.Status.in_(["Pending", "Approved", "Active"]))
        .where(Rental.StartDate <= end_date)
        .where(Rental.EndDate >= start_date)
    )
    busy_ids = {row[0] for row in db.execute(busy_stmt).all()}

    stmt = (
        select(ToolInstance)
        .where(ToolInstance.ToolID == tool_id)
        .where(ToolInstance.Status == "Available")
    )

    instances = db.execute(stmt).scalars().all()
    for instance in instances:
        if instance.ToolInstanceID in busy_ids:
            continue
        if instance.RequiresCertification:
            if not instance.NextCalibration:
                continue
            if instance.NextCalibration < end_date:
                continue
        return instance.ToolInstanceID

    return None


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
