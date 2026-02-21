-- AssetManagement schema reconciliation
-- Created: 2026-02-21 14:00
-- Safe to run repeatedly (idempotent)

SET NOCOUNT ON;

-- 1) ToolInstances table
IF OBJECT_ID('dbo.ToolInstances', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.ToolInstances (
        ToolInstanceID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ToolID INT NOT NULL,
        SerialNumber NVARCHAR(200) NOT NULL,
        InstanceNumber INT NULL,
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
END
GO

IF COL_LENGTH('dbo.ToolInstances', 'InstanceNumber') IS NULL
BEGIN
    ALTER TABLE dbo.ToolInstances ADD InstanceNumber INT NULL;
END
GO

-- 2) RentalItems.ToolInstanceID + FK
IF COL_LENGTH('dbo.RentalItems', 'ToolInstanceID') IS NULL
BEGIN
    ALTER TABLE dbo.RentalItems ADD ToolInstanceID INT NULL;
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.foreign_keys
    WHERE name = 'FK_RentalItems_ToolInstances'
      AND parent_object_id = OBJECT_ID('dbo.RentalItems')
)
BEGIN
    ALTER TABLE dbo.RentalItems
        ADD CONSTRAINT FK_RentalItems_ToolInstances
        FOREIGN KEY (ToolInstanceID) REFERENCES dbo.ToolInstances(ToolInstanceID);
END
GO

-- 3) Backfill missing ToolInstances for tools that have none
INSERT INTO dbo.ToolInstances (
    ToolID,
    SerialNumber,
    InstanceNumber,
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
    COALESCE(t.SerialNumber, 'SP') + '-0001',
    1,
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
      SELECT 1
      FROM dbo.ToolInstances ti
      WHERE ti.ToolID = t.ToolID
  );
GO

-- 4) Backfill InstanceNumber when null
;WITH numbered AS (
    SELECT
        ToolInstanceID,
        ToolID,
        ROW_NUMBER() OVER (PARTITION BY ToolID ORDER BY ToolInstanceID) AS NewNumber
    FROM dbo.ToolInstances
)
UPDATE ti
SET InstanceNumber = n.NewNumber
FROM dbo.ToolInstances ti
JOIN numbered n ON ti.ToolInstanceID = n.ToolInstanceID
WHERE ti.InstanceNumber IS NULL;
GO

-- 5) Normalize serial pattern to <Tool.SerialNumber>-<0001..>
UPDATE ti
SET SerialNumber = t.SerialNumber + '-' + RIGHT('0000' + CAST(ti.InstanceNumber AS VARCHAR(4)), 4)
FROM dbo.ToolInstances ti
JOIN dbo.Tools t ON t.ToolID = ti.ToolID
WHERE ti.InstanceNumber IS NOT NULL
  AND t.SerialNumber IS NOT NULL
  AND (ti.SerialNumber IS NULL OR ti.SerialNumber NOT LIKE t.SerialNumber + '-%');
GO

-- 6) Enforce NOT NULL on InstanceNumber
IF EXISTS (SELECT 1 FROM dbo.ToolInstances WHERE InstanceNumber IS NULL)
BEGIN
    RAISERROR('Cannot enforce NOT NULL on ToolInstances.InstanceNumber; null values remain.', 16, 1);
END
ELSE
BEGIN
    ALTER TABLE dbo.ToolInstances ALTER COLUMN InstanceNumber INT NOT NULL;
END
GO

-- 7) Indexes for ToolInstances
IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_ToolInstances_SerialNumber'
      AND object_id = OBJECT_ID('dbo.ToolInstances')
)
BEGIN
    CREATE UNIQUE INDEX IX_ToolInstances_SerialNumber ON dbo.ToolInstances(SerialNumber);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_ToolInstances_ToolID'
      AND object_id = OBJECT_ID('dbo.ToolInstances')
)
BEGIN
    CREATE INDEX IX_ToolInstances_ToolID ON dbo.ToolInstances(ToolID);
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'UX_ToolInstances_ToolID_InstanceNumber'
      AND object_id = OBJECT_ID('dbo.ToolInstances')
)
BEGIN
    CREATE UNIQUE INDEX UX_ToolInstances_ToolID_InstanceNumber ON dbo.ToolInstances(ToolID, InstanceNumber);
END
GO

-- 8) Rental loss columns
IF COL_LENGTH('dbo.Rental', 'LossAmount') IS NULL
BEGIN
    ALTER TABLE dbo.Rental ADD LossAmount DECIMAL(10,2) NULL;
END
IF COL_LENGTH('dbo.Rental', 'LossCalculatedAt') IS NULL
BEGIN
    ALTER TABLE dbo.Rental ADD LossCalculatedAt DATETIME2 NULL;
END
IF COL_LENGTH('dbo.Rental', 'LossReason') IS NULL
BEGIN
    ALTER TABLE dbo.Rental ADD LossReason NVARCHAR(200) NULL;
END
GO

-- 9) AuditLogs
IF OBJECT_ID('dbo.AuditLogs', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AuditLogs (
        AuditID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        EntityType NVARCHAR(50) NOT NULL,
        EntityID INT NOT NULL,
        Action NVARCHAR(100) NOT NULL,
        Details NVARCHAR(2000) NULL,
        UserID INT NULL,
        CreatedAt DATETIME2 NULL
    );
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_AuditLogs_Entity'
      AND object_id = OBJECT_ID('dbo.AuditLogs')
)
BEGIN
    CREATE INDEX IX_AuditLogs_Entity ON dbo.AuditLogs(EntityType, EntityID);
END
GO

-- 10) NotificationQueue
IF OBJECT_ID('dbo.NotificationQueue', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.NotificationQueue (
        NotificationID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        RentalID INT NULL,
        NotificationType NVARCHAR(50) NOT NULL,
        Payload NVARCHAR(2000) NULL,
        CreatedAt DATETIME2 NULL,
        SentAt DATETIME2 NULL
    );
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_NotificationQueue_Sent'
      AND object_id = OBJECT_ID('dbo.NotificationQueue')
)
BEGIN
    CREATE INDEX IX_NotificationQueue_Sent ON dbo.NotificationQueue(SentAt);
END
GO
