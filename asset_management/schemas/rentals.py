from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CreateRentalItemDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    toolID: int
    toolInstanceID: Optional[int] = None
    quantity: int = 1
    dailyCost: Optional[float] = None


class CreateRentalDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    employeeID: int
    purpose: str
    projectCode: Optional[str] = None
    startDate: date
    endDate: date
    notes: Optional[str] = None
    status: Optional[str] = None
    rentalItems: List[CreateRentalItemDto] = []


class ExtensionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    newEndDate: date


class ReturnRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    condition: str
    notes: Optional[str] = None
