# Atlas Login Spec

This document defines the shared login method for Atlas apps:

- AssetManagement
- TimeApp
- PeoplePlanner

## Purpose

Use one identity model (employee-based) with one user library table (`dbo.AtlasUsers`) that stores app roles/rights per employee.

## Identity Model

Primary identity:

- `EmployeeID` (from employee directory source)

Local break-glass identity:

- `admin` username (local admin)
- Password from env (`LOCAL_ADMIN_PASSWORD`)

## Data Source

SQL table:

- `dbo.AtlasUsers`

Key columns:

- `EmployeeID` (PK)
- `AssetManagementRole`
- `AssetManagementRights` (JSON object)
- `TimeAppRights` (JSON object)
- `PeoplePlannerRights` (JSON object)
- password fields (`PasswordHash`, `PasswordSalt`, `PasswordUpdatedAt`)
- lifecycle fields (`IsActive`, `CreatedAt`, `UpdatedAt`)

## Login UX (Look & Feel)

Current pattern in AssetManagement:

1. Modal sign-in.
2. Name field is a searchable dropdown-combobox.
3. No pre-selected user.
4. Typing filters names in dropdown.
5. Arrow button opens full list for scrolling.
6. User enters code (PIN/password).
7. Generic auth errors shown to user.

Behavior requirements:

- No public credential hints in UI.
- No exposed full list unless dropdown opened or user is typing.
- Fast employee lookup from cached employee list endpoint.

## API Contracts

Auth endpoints:

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

Admin user-library endpoints:

- `GET /api/admin/users`
- `POST /api/admin/users` (explicit create/provision)
- `PUT /api/admin/users/{employee_id}` (role/rights/code updates)

## Security Baseline

- Login payload validation with strict schema.
- Generic error responses for invalid credentials.
- Rate limit and lockout on repeated failures.
- Audit events for auth success/failure/throttle.
- Local admin password in env, never hardcoded.

## Admin Workflow

1. Open Admin page.
2. See all directory employees, with provision status.
3. For unprovisioned employees, click `Create`.
4. Set:
   - Asset role
   - Asset rights
   - TimeApp rights JSON
   - PeoplePlanner rights JSON
5. Save updates and optional code reset/change.

## Rollout to Other Atlas Apps

When implementing in TimeApp/PeoplePlanner:

1. Reuse same `AtlasUsers` table.
2. Reuse same auth endpoints and session pattern where possible.
3. Keep same combobox login interaction pattern.
4. Apply app-specific rights from `TimeAppRights` or `PeoplePlannerRights`.
