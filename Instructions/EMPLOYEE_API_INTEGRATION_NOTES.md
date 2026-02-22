# Employee API Integration Notes (SubCPartner.Common.API)

Source of truth (live):
- `http://common.subcpartner.com/swagger`
- `http://common.subcpartner.com/swagger/v1/swagger.json`

Checked against Swagger JSON on 2026-02-22.

## 1) What this API exposes

OpenAPI summary:
- `openapi: 3.0.4`
- `title: SubCPartner.Common.API`
- `version: 1.0`

Relevant employee endpoints:
- `GET /Employees/all`
- `GET /Employees/{id}`
- `GET /Employees/number/{employeeNumber}`

Employee schema (`EmployeeDto`):
- `id` (int32)
- `number` (string)
- `name` (string)
- `eMail` (string)
- `initials` (string)
- `departmentCode` (string)

## 2) Auth details (critical)

Swagger security:
- Global security requirement: `AuthToken`
- Security scheme type: `apiKey`
- Header name: `Authorization`
- Header location: `in: header`

Implication for this project:
- The token is sent in `Authorization` header.
- This spec does **not** say `Bearer` is required.
- Default integration should therefore send raw token value unless verified otherwise.

Recommended env settings for this repo:
- `EMPLOYEE_API_BASE_URL=http://common.subcpartner.com`
- `EMPLOYEE_API_TOKEN=<real token>`
- `EMPLOYEE_API_AUTH_HEADER=Authorization`
- `EMPLOYEE_API_AUTH_SCHEME=` (empty)

If API later requires bearer format, set:
- `EMPLOYEE_API_AUTH_SCHEME=Bearer`

## 3) First-time setup checklist

1. Confirm server env file used by systemd:
   - `/etc/asset_management/asset_management.env`
2. Set employee API env vars listed above.
3. Restart service:
   - `sudo systemctl restart asset_management`
4. Verify app-level health:
   - `curl -fsS http://127.0.0.1:5001/healthz`
   - `curl -fsS http://127.0.0.1:5001/api/healthz`
5. Verify employee integration status endpoint:
   - `curl -s http://127.0.0.1:5001/api/employees/status`
6. Verify employee list endpoint from app:
   - `curl -s http://127.0.0.1:5001/api/employees | head`

## 4) First-time API smoke test (direct against Common API)

Use these from a trusted machine with network access:

```bash
TOKEN="<real_token>"
BASE="http://common.subcpartner.com"

# All employees
curl -fsS -H "Authorization: ${TOKEN}" "${BASE}/Employees/all" | head

# By numeric ID
curl -fsS -H "Authorization: ${TOKEN}" "${BASE}/Employees/1"

# By employee number
curl -fsS -H "Authorization: ${TOKEN}" "${BASE}/Employees/number/12345"
```

If you get 401/403:
- token invalid/expired or wrong header format
- try `Authorization: Bearer <token>` only if provider confirms Bearer requirement

## 5) Known integration gotchas in this project

1. If `EMPLOYEE_API_BASE_URL` is missing, `/api/employees` returns 503.
2. Login name dropdown depends on `/api/employees`; missing API config breaks lookup.
3. Employee login is now restricted to users provisioned in `dbo.AtlasUsers`.
4. Admin user page requires successful auth first (`/api/admin/users` returns 401 before login).
5. Employee cache exists in app (5-minute TTL by default), so stale data can appear briefly.

## 6) Operational checks after deploy

1. Confirm env on server includes employee vars and token.
2. Confirm `/api/employees/status` shows healthy cache and no `lastError`.
3. Confirm login modal search populates names.
4. Confirm admin page loads all personnel and supports Create/Edit actions.

## 7) If this API changes later

Re-check and update these assumptions:
- auth scheme (`apiKey` raw token vs `Bearer`)
- employee endpoint paths
- `EmployeeDto` field names (`eMail` casing matters)
- non-200 response semantics
