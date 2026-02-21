from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from db.base import Base


class Tool(Base):
    __tablename__ = "Tools"
    __table_args__ = {"schema": "dbo"}

    ToolID = Column(Integer, primary_key=True)
    ToolName = Column(String(255))
    SerialNumber = Column(String(255))
    ModelNumber = Column(String(255))
    Manufacturer = Column(String(255))
    CategoryID = Column(Integer, ForeignKey("dbo.Categories.CategoryID"))
    Description = Column(String)
    PurchaseDate = Column(Date)
    PurchaseCost = Column(Numeric(18, 2))
    CurrentValue = Column(Numeric(18, 2))
    CalibrationInterval = Column(Integer)
    LastCalibration = Column(Date)
    NextCalibration = Column(Date)
    Status = Column(String(50))
    Condition = Column(String(100))
    DailyRentalCost = Column(Numeric(18, 2))
    RequiresCertification = Column(Boolean, default=False)
    WarehouseID = Column(Integer, ForeignKey("dbo.Warehouses.WarehouseID"))
    LocationCode = Column(String(50))
    ImagePath = Column(String(500))
    CreatedDate = Column(DateTime, server_default=func.now())
    UpdatedDate = Column(DateTime, server_default=func.now())

    Category = relationship("Category", back_populates="Tools")
    Warehouse = relationship("Warehouse", back_populates="Tools")
    RentalItems = relationship("RentalItem", back_populates="Tool")
    Certificates = relationship("Certificate", back_populates="Tool")
    ToolLocations = relationship("ToolLocation", back_populates="Tool")
    ServiceRecords = relationship("ServiceRecord", back_populates="Tool")
    ToolInstances = relationship("ToolInstance", back_populates="Tool")


class Category(Base):
    __tablename__ = "Categories"
    __table_args__ = {"schema": "dbo"}

    CategoryID = Column(Integer, primary_key=True)
    CategoryName = Column(String(100), nullable=False)
    Description = Column(String(500))
    ParentCategoryID = Column(Integer, ForeignKey("dbo.Categories.CategoryID"))
    CreatedDate = Column(DateTime, server_default=func.now())

    ParentCategory = relationship("Category", remote_side=[CategoryID])
    Tools = relationship("Tool", back_populates="Category")


class Warehouse(Base):
    __tablename__ = "Warehouses"
    __table_args__ = {"schema": "dbo"}

    WarehouseID = Column(Integer, primary_key=True)
    WarehouseName = Column(String(255))
    Description = Column(String(255))
    Address = Column(String(255))
    GridColumns = Column(Integer)
    GridRows = Column(Integer)
    ManagerID = Column(Integer)
    ContactPhone = Column(String(50))
    CreatedDate = Column(DateTime, server_default=func.now())
    IsActive = Column(Boolean, default=True)

    Tools = relationship("Tool", back_populates="Warehouse")
    WarehouseLocations = relationship("WarehouseLocation", back_populates="Warehouse")


class WarehouseLocation(Base):
    __tablename__ = "WarehouseLocations"
    __table_args__ = {"schema": "dbo"}

    LocationID = Column(Integer, primary_key=True)
    WarehouseID = Column(Integer, ForeignKey("dbo.Warehouses.WarehouseID"))
    GridColumn = Column(String(2), nullable=False)
    GridRow = Column(Integer)
    ShelfNumber = Column(String(20))
    Zone = Column(String(50))
    CapacityDescription = Column(String(200))
    IsActive = Column(Boolean, default=True)
    CreatedDate = Column(DateTime, server_default=func.now())

    Warehouse = relationship("Warehouse", back_populates="WarehouseLocations")
    ToolLocations = relationship("ToolLocation", back_populates="Location")


class Rental(Base):
    __tablename__ = "Rental"
    __table_args__ = {"schema": "dbo", "implicit_returning": False}

    RentalID = Column(Integer, primary_key=True)
    RentalNumber = Column(String(50), nullable=False)
    EmployeeID = Column(Integer, nullable=False)
    Purpose = Column(String(1000), nullable=False)
    ProjectCode = Column(String(50))
    Status = Column(String(20), default="Pending")
    StartDate = Column(Date, nullable=False)
    EndDate = Column(Date, nullable=False)
    ActualStart = Column(Date)
    ActualEnd = Column(Date)
    TotalCost = Column(Numeric(10, 2))
    ApprovedBy = Column(Integer)
    ApprovalDate = Column(Date)
    CheckoutCondition = Column(String(500))
    ReturnCondition = Column(String(500))
    Notes = Column(String(1000))
    LossAmount = Column(Numeric(10, 2))
    LossCalculatedAt = Column(DateTime)
    LossReason = Column(String(200))
    CreatedDate = Column(DateTime, server_default=func.now())
    UpdatedDate = Column(DateTime, server_default=func.now())

    RentalItems = relationship("RentalItem", back_populates="Rental", cascade="all, delete-orphan")


class RentalItem(Base):
    __tablename__ = "RentalItems"
    __table_args__ = {"schema": "dbo"}

    RentalItemID = Column(Integer, primary_key=True)
    RentalID = Column(Integer, ForeignKey("dbo.Rental.RentalID"))
    ToolID = Column(Integer, ForeignKey("dbo.Tools.ToolID"))
    ToolInstanceID = Column(Integer, ForeignKey("dbo.ToolInstances.ToolInstanceID"))
    Quantity = Column(Integer, default=1)
    DailyCost = Column(Numeric(8, 2))
    TotalCost = Column(Numeric(10, 2))
    CheckoutNotes = Column(String(500))
    ReturnNotes = Column(String(500))

    Rental = relationship("Rental", back_populates="RentalItems")
    Tool = relationship("Tool", back_populates="RentalItems")
    ToolInstance = relationship("ToolInstance", back_populates="RentalItems")


class ServiceRecord(Base):
    __tablename__ = "Service"
    __table_args__ = {"schema": "dbo"}

    ServiceID = Column(Integer, primary_key=True)
    ToolID = Column(Integer, ForeignKey("dbo.Tools.ToolID"))
    ServiceType = Column(String(50), nullable=False)
    ServiceDate = Column(Date, nullable=False)
    Description = Column(String(1000), nullable=False)
    Cost = Column(Numeric(10, 2))
    PerformedBy = Column(String(200))
    NextServiceDue = Column(Date)
    Notes = Column(String(1000))
    CreatedDate = Column(DateTime, server_default=func.now())

    Tool = relationship("Tool", back_populates="ServiceRecords")


class Certificate(Base):
    __tablename__ = "Certificates"
    __table_args__ = {"schema": "dbo"}

    CertificateID = Column(Integer, primary_key=True)
    ToolID = Column(Integer, ForeignKey("dbo.Tools.ToolID"))
    CertificateNumber = Column(String(100), nullable=False)
    CertificateType = Column(String(50), nullable=False)
    IssueDate = Column(Date, nullable=False)
    ExpiryDate = Column(Date)
    IssuingAuthority = Column(String(200))
    CertificatePath = Column(String(500))
    Cost = Column(Numeric(8, 2))
    Notes = Column(String(500))
    CreatedDate = Column(DateTime, server_default=func.now())

    Tool = relationship("Tool", back_populates="Certificates")


class ToolLocation(Base):
    __tablename__ = "ToolLocations"
    __table_args__ = {"schema": "dbo"}

    AssignmentID = Column(Integer, primary_key=True)
    ToolID = Column(Integer, ForeignKey("dbo.Tools.ToolID"))
    LocationID = Column(Integer, ForeignKey("dbo.WarehouseLocations.LocationID"))
    AssignedDate = Column(DateTime, server_default=func.now())
    AssignedBy = Column(Integer)
    Notes = Column(String(500))
    IsCurrent = Column(Boolean, default=True)

    Tool = relationship("Tool", back_populates="ToolLocations")
    Location = relationship("WarehouseLocation", back_populates="ToolLocations")


class ToolInstance(Base):
    __tablename__ = "ToolInstances"
    __table_args__ = {"schema": "dbo"}

    ToolInstanceID = Column(Integer, primary_key=True)
    ToolID = Column(Integer, ForeignKey("dbo.Tools.ToolID"))
    SerialNumber = Column(String(200), nullable=False)
    InstanceNumber = Column(Integer, nullable=False)
    Status = Column(String(40))
    Condition = Column(String(40))
    WarehouseID = Column(Integer, ForeignKey("dbo.Warehouses.WarehouseID"))
    LocationCode = Column(String(40))
    RequiresCertification = Column(Boolean, default=False)
    CalibrationInterval = Column(Integer)
    LastCalibration = Column(Date)
    NextCalibration = Column(Date)
    ImagePath = Column(String(1000))
    CreatedDate = Column(DateTime, server_default=func.now())
    UpdatedDate = Column(DateTime, server_default=func.now())

    Tool = relationship("Tool", back_populates="ToolInstances")
    RentalItems = relationship("RentalItem", back_populates="ToolInstance")


class AuditLog(Base):
    __tablename__ = "AuditLogs"
    __table_args__ = {"schema": "dbo"}

    AuditID = Column(Integer, primary_key=True)
    EntityType = Column(String(50), nullable=False)
    EntityID = Column(Integer, nullable=False)
    Action = Column(String(100), nullable=False)
    Details = Column(String(2000))
    UserID = Column(Integer)
    CreatedAt = Column(DateTime, server_default=func.now())


class NotificationQueue(Base):
    __tablename__ = "NotificationQueue"
    __table_args__ = {"schema": "dbo"}

    NotificationID = Column(Integer, primary_key=True)
    RentalID = Column(Integer)
    NotificationType = Column(String(50), nullable=False)
    Payload = Column(String(2000))
    CreatedAt = Column(DateTime, server_default=func.now())
    SentAt = Column(DateTime)


class AtlasUser(Base):
    __tablename__ = "AtlasUsers"
    __table_args__ = {"schema": "dbo"}

    EmployeeID = Column(Integer, primary_key=True)
    AssetManagementRole = Column(String(50), nullable=False)
    AssetManagementRights = Column(String)
    TimeAppRights = Column(String)
    PeoplePlannerRights = Column(String)
    PasswordHash = Column(String(256))
    PasswordSalt = Column(String(64))
    PasswordUpdatedAt = Column(Integer)
    IsActive = Column(Boolean, default=True)
    CreatedAt = Column(DateTime, server_default=func.now())
    UpdatedAt = Column(DateTime, server_default=func.now())
