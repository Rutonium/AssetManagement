from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class CreateRentalItemDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    toolID: int
    toolInstanceID: Optional[int] = None
    quantity: int = 1
    dailyCost: Optional[float] = None
    assignmentMode: Optional[Literal["auto", "manual"]] = "auto"
    allowDeficit: bool = True


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


class OfferCheckoutRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    employeeID: int
    projectCode: Optional[str] = None
    purpose: Optional[str] = None
    startDate: date
    endDate: date
    notes: Optional[str] = None


class KioskLendRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    employeeID: int
    pinCode: str
    projectCode: Optional[str] = None
    purpose: str
    startDate: date
    endDate: date
    rentalItems: List[CreateRentalItemDto] = []
    photoDataUrl: Optional[str] = None


class MarkRentalItemDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    rentalItemID: int
    pickedQuantity: int = 1
    toolInstanceIDs: List[int] = []
    serialInput: Optional[str] = None
    notes: Optional[str] = None


class MarkItemsForRentalRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    operatorUserID: Optional[int] = None
    items: List[MarkRentalItemDto] = []


class ReceiveRentalItemDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    rentalItemID: int
    returnedQuantity: int = 0
    notReturnedQuantity: int = 0
    condition: Optional[str] = None
    notes: Optional[str] = None


class ReceiveMarkedItemsRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    operatorUserID: Optional[int] = None
    items: List[ReceiveRentalItemDto] = []


class ReservationShortageActionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    rentalItemID: int
    action: Literal["replacement", "procure", "exclude"]
    owner: Optional[str] = None
    dueDate: Optional[date] = None
    notes: Optional[str] = None


class ReservationDecisionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    decision: Literal["approve", "reject"]
    reason: Optional[str] = None
    operatorUserID: Optional[int] = None
    shortageActions: List[ReservationShortageActionDto] = []
