from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EquipmentUpsert(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    toolID: Optional[int] = None
    toolName: Optional[str] = None
    serialNumber: Optional[str] = None
    modelNumber: Optional[str] = None
    manufacturer: Optional[str] = None
    categoryID: Optional[int] = None
    description: Optional[str] = None
    purchaseDate: Optional[date] = None
    purchaseCost: Optional[float] = None
    currentValue: Optional[float] = None
    calibrationInterval: Optional[int] = None
    lastCalibration: Optional[date] = None
    nextCalibration: Optional[date] = None
    status: Optional[str] = None
    condition: Optional[str] = None
    dailyRentalCost: Optional[float] = None
    requiresCertification: Optional[bool] = None
    warehouseID: Optional[int] = None
    locationCode: Optional[str] = None
    imagePath: Optional[str] = None


class ToolInstanceUpsert(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    toolInstanceID: Optional[int] = None
    toolID: Optional[int] = None
    serialNumber: Optional[str] = None
    instanceNumber: Optional[int] = None
    status: Optional[str] = None
    condition: Optional[str] = None
    warehouseID: Optional[int] = None
    locationCode: Optional[str] = None
    requiresCertification: Optional[bool] = None
    calibrationInterval: Optional[int] = None
    lastCalibration: Optional[date] = None
    nextCalibration: Optional[date] = None
    imagePath: Optional[str] = None
