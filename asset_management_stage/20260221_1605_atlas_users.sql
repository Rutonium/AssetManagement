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
