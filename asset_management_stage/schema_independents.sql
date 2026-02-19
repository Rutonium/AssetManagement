-- Independent features schema updates

-- 1) Rental loss columns
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

-- 2) AuditLogs table
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
    CREATE INDEX IX_AuditLogs_Entity ON dbo.AuditLogs(EntityType, EntityID);
END
GO

-- 3) NotificationQueue table
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
    CREATE INDEX IX_NotificationQueue_Sent ON dbo.NotificationQueue(SentAt);
END
GO
