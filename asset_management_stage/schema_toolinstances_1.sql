-- ToolInstances + RentalItems.ToolInstanceID migration

-- 1) ToolInstances table
IF OBJECT_ID('dbo.ToolInstances', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ToolInstances (
        ToolInstanceID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ToolID INT NOT NULL,
        SerialNumber NVARCHAR(200) NOT NULL,
        Status NVARCHAR(40) NULL,
        Condition NVARCHAR(40) NULL,
        WarehouseID INT NULL,
        LocationCode NVARCHAR(40) NULL,
        RequiresCertification BIT NULL,
        CalibrationInterval INT NULL,
        LastCalibration DATE NULL,
        NextCalibration DATE NULL,
        ImagePath NVARCHAR(1000) NULL,
        CreatedDate DATETIME2 NULL,
        UpdatedDate DATETIME2 NULL,
        CONSTRAINT FK_ToolInstances_Tools FOREIGN KEY (ToolID) REFERENCES dbo.Tools(ToolID),
        CONSTRAINT FK_ToolInstances_Warehouses FOREIGN KEY (WarehouseID) REFERENCES dbo.Warehouses(WarehouseID)
    );

    CREATE UNIQUE INDEX IX_ToolInstances_SerialNumber ON dbo.ToolInstances(SerialNumber);
    CREATE INDEX IX_ToolInstances_ToolID ON dbo.ToolInstances(ToolID);
END
GO

-- 2) Add ToolInstanceID to RentalItems
IF COL_LENGTH('dbo.RentalItems', 'ToolInstanceID') IS NULL
BEGIN
    ALTER TABLE dbo.RentalItems ADD ToolInstanceID INT NULL;
    ALTER TABLE dbo.RentalItems
        ADD CONSTRAINT FK_RentalItems_ToolInstances
        FOREIGN KEY (ToolInstanceID) REFERENCES dbo.ToolInstances(ToolInstanceID);
END
GO

-- 3) Backfill ToolInstances from existing Tools (if not already present)
INSERT INTO dbo.ToolInstances (
    ToolID,
    SerialNumber,
    Status,
    Condition,
    WarehouseID,
    LocationCode,
    RequiresCertification,
    CalibrationInterval,
    LastCalibration,
    NextCalibration,
    ImagePath,
    CreatedDate,
    UpdatedDate
)
SELECT
    t.ToolID,
    t.SerialNumber,
    t.Status,
    t.Condition,
    t.WarehouseID,
    t.LocationCode,
    t.RequiresCertification,
    t.CalibrationInterval,
    t.LastCalibration,
    t.NextCalibration,
    t.ImagePath,
    t.CreatedDate,
    t.UpdatedDate
FROM dbo.Tools t
WHERE t.SerialNumber IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM dbo.ToolInstances ti
      WHERE ti.ToolID = t.ToolID
        AND ti.SerialNumber = t.SerialNumber
  );
GO
