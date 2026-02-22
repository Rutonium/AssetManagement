-- AtlasUsers table for shared Atlas identity and cross-app rights
-- Created: 2026-02-21 16:05
-- Safe to run repeatedly (idempotent)

SET NOCOUNT ON;

IF OBJECT_ID('dbo.AtlasUsers', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.AtlasUsers (
        EmployeeID INT NOT NULL PRIMARY KEY,
        AssetManagementRole NVARCHAR(50) NOT NULL CONSTRAINT DF_AtlasUsers_AssetManagementRole DEFAULT ('User'),
        AssetManagementRights NVARCHAR(MAX) NULL,
        TimeAppRights NVARCHAR(MAX) NULL,
        PeoplePlannerRights NVARCHAR(MAX) NULL,
        PasswordHash NVARCHAR(256) NULL,
        PasswordSalt NVARCHAR(64) NULL,
        PasswordUpdatedAt BIGINT NULL,
        IsActive BIT NOT NULL CONSTRAINT DF_AtlasUsers_IsActive DEFAULT (1),
        CreatedAt DATETIME2 NOT NULL CONSTRAINT DF_AtlasUsers_CreatedAt DEFAULT (SYSUTCDATETIME()),
        UpdatedAt DATETIME2 NOT NULL CONSTRAINT DF_AtlasUsers_UpdatedAt DEFAULT (SYSUTCDATETIME())
    );
END
GO

IF COL_LENGTH('dbo.AtlasUsers', 'EmployeeID') IS NULL
BEGIN
    RAISERROR('AtlasUsers exists but schema is unexpected (missing EmployeeID). Manual intervention required.', 16, 1);
END
GO

-- Reconcile missing columns for environments where AtlasUsers exists partially.
IF COL_LENGTH('dbo.AtlasUsers', 'AssetManagementRole') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD AssetManagementRole NVARCHAR(50) NULL;
END
IF COL_LENGTH('dbo.AtlasUsers', 'AssetManagementRights') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD AssetManagementRights NVARCHAR(MAX) NULL;
END
IF COL_LENGTH('dbo.AtlasUsers', 'TimeAppRights') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD TimeAppRights NVARCHAR(MAX) NULL;
END
IF COL_LENGTH('dbo.AtlasUsers', 'PeoplePlannerRights') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD PeoplePlannerRights NVARCHAR(MAX) NULL;
END
IF COL_LENGTH('dbo.AtlasUsers', 'PasswordHash') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD PasswordHash NVARCHAR(256) NULL;
END
IF COL_LENGTH('dbo.AtlasUsers', 'PasswordSalt') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD PasswordSalt NVARCHAR(64) NULL;
END
IF COL_LENGTH('dbo.AtlasUsers', 'PasswordUpdatedAt') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD PasswordUpdatedAt BIGINT NULL;
END
IF COL_LENGTH('dbo.AtlasUsers', 'IsActive') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD IsActive BIT NULL;
END
IF COL_LENGTH('dbo.AtlasUsers', 'CreatedAt') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD CreatedAt DATETIME2 NULL;
END
IF COL_LENGTH('dbo.AtlasUsers', 'UpdatedAt') IS NULL
BEGIN
    ALTER TABLE dbo.AtlasUsers ADD UpdatedAt DATETIME2 NULL;
END
GO

-- Ensure defaults exist.
IF NOT EXISTS (
    SELECT 1 FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.AtlasUsers') AND name = 'DF_AtlasUsers_AssetManagementRole'
)
BEGIN
    ALTER TABLE dbo.AtlasUsers
        ADD CONSTRAINT DF_AtlasUsers_AssetManagementRole DEFAULT ('User') FOR AssetManagementRole;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.AtlasUsers') AND name = 'DF_AtlasUsers_IsActive'
)
BEGIN
    ALTER TABLE dbo.AtlasUsers
        ADD CONSTRAINT DF_AtlasUsers_IsActive DEFAULT (1) FOR IsActive;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.AtlasUsers') AND name = 'DF_AtlasUsers_CreatedAt'
)
BEGIN
    ALTER TABLE dbo.AtlasUsers
        ADD CONSTRAINT DF_AtlasUsers_CreatedAt DEFAULT (SYSUTCDATETIME()) FOR CreatedAt;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.default_constraints
    WHERE parent_object_id = OBJECT_ID('dbo.AtlasUsers') AND name = 'DF_AtlasUsers_UpdatedAt'
)
BEGIN
    ALTER TABLE dbo.AtlasUsers
        ADD CONSTRAINT DF_AtlasUsers_UpdatedAt DEFAULT (SYSUTCDATETIME()) FOR UpdatedAt;
END
GO

-- Backfill nulls and enforce NOT NULL where expected.
UPDATE dbo.AtlasUsers SET AssetManagementRole = COALESCE(NULLIF(LTRIM(RTRIM(AssetManagementRole)), ''), 'User')
WHERE AssetManagementRole IS NULL OR LTRIM(RTRIM(AssetManagementRole)) = '';
UPDATE dbo.AtlasUsers SET IsActive = 1 WHERE IsActive IS NULL;
UPDATE dbo.AtlasUsers SET CreatedAt = SYSUTCDATETIME() WHERE CreatedAt IS NULL;
UPDATE dbo.AtlasUsers SET UpdatedAt = SYSUTCDATETIME() WHERE UpdatedAt IS NULL;
GO

ALTER TABLE dbo.AtlasUsers ALTER COLUMN AssetManagementRole NVARCHAR(50) NOT NULL;
ALTER TABLE dbo.AtlasUsers ALTER COLUMN IsActive BIT NOT NULL;
ALTER TABLE dbo.AtlasUsers ALTER COLUMN CreatedAt DATETIME2 NOT NULL;
ALTER TABLE dbo.AtlasUsers ALTER COLUMN UpdatedAt DATETIME2 NOT NULL;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = 'IX_AtlasUsers_AssetManagementRole'
      AND object_id = OBJECT_ID('dbo.AtlasUsers')
)
BEGIN
    CREATE INDEX IX_AtlasUsers_AssetManagementRole ON dbo.AtlasUsers(AssetManagementRole);
END
GO
