-- Bootstrap one admin account directly in AtlasUsers.
-- After running, login with EmployeeID = 999999 and code = 1234 (default).
-- Change EmployeeID if you prefer a real employee number.

MERGE dbo.AtlasUsers AS target
USING (
    SELECT
        CAST(999999 AS INT) AS EmployeeID,
        CAST('Admin' AS NVARCHAR(50)) AS AssetManagementRole,
        CAST('{"manageUsers":true,"manageRentals":true,"manageWarehouse":true,"manageEquipment":true,"checkout":true}' AS NVARCHAR(MAX)) AS AssetManagementRights,
        CAST('{}' AS NVARCHAR(MAX)) AS TimeAppRights,
        CAST('{}' AS NVARCHAR(MAX)) AS PeoplePlannerRights
) AS source
ON target.EmployeeID = source.EmployeeID
WHEN MATCHED THEN
    UPDATE SET
        AssetManagementRole = source.AssetManagementRole,
        AssetManagementRights = source.AssetManagementRights,
        TimeAppRights = source.TimeAppRights,
        PeoplePlannerRights = source.PeoplePlannerRights,
        UpdatedAt = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT (
        EmployeeID,
        AssetManagementRole,
        AssetManagementRights,
        TimeAppRights,
        PeoplePlannerRights,
        PasswordHash,
        PasswordSalt,
        PasswordUpdatedAt,
        CreatedAt,
        UpdatedAt
    )
    VALUES (
        source.EmployeeID,
        source.AssetManagementRole,
        source.AssetManagementRights,
        source.TimeAppRights,
        source.PeoplePlannerRights,
        NULL,
        NULL,
        NULL,
        SYSUTCDATETIME(),
        SYSUTCDATETIME()
    );

SELECT
    EmployeeID,
    AssetManagementRole,
    AssetManagementRights,
    PasswordHash,
    PasswordSalt,
    UpdatedAt
FROM dbo.AtlasUsers
WHERE EmployeeID = 999999;
