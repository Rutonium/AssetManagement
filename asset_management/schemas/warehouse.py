from pydantic import BaseModel, ConfigDict


class ToolLocationAssignmentDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    toolID: int
    warehouseID: int
    locationCode: str
