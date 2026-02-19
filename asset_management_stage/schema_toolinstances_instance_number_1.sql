-- ToolInstances instance numbering migration

-- 1) Add InstanceNumber column if missing
IF COL_LENGTH('dbo.ToolInstances', 'InstanceNumber') IS NULL
BEGIN
    ALTER TABLE dbo.ToolInstances ADD InstanceNumber INT NULL;
END
GO

-- 2) Backfill InstanceNumber per ToolID (ordered by ToolInstanceID)
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

-- 3) Ensure SerialNumber uses Tool.SerialNumber + InstanceNumber
UPDATE ti
SET SerialNumber = t.SerialNumber + '-' + RIGHT('0000' + CAST(ti.InstanceNumber AS VARCHAR(4)), 4)
FROM dbo.ToolInstances ti
JOIN dbo.Tools t ON t.ToolID = ti.ToolID
WHERE ti.InstanceNumber IS NOT NULL
  AND (ti.SerialNumber IS NULL OR ti.SerialNumber NOT LIKE t.SerialNumber + '-%');
GO

-- 4) Enforce NOT NULL on InstanceNumber
ALTER TABLE dbo.ToolInstances ALTER COLUMN InstanceNumber INT NOT NULL;
GO

-- 5) Unique per tool + instance
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UX_ToolInstances_ToolID_InstanceNumber'
      AND object_id = OBJECT_ID('dbo.ToolInstances')
)
BEGIN
    CREATE UNIQUE INDEX UX_ToolInstances_ToolID_InstanceNumber ON dbo.ToolInstances(ToolID, InstanceNumber);
END
GO
