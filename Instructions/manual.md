# Asset Management Manual

## Dashboard

The Dashboard gives a high-level overview of equipment and rental activity.

- Track total equipment and active rentals.
- Review status distribution of equipment.
- Check quick system indicators before operational work.

## Warehouse

The Warehouse view is used to manage where physical tool instances are stored.

- Open a warehouse and select a location cell.
- Use location assignment actions to place or remove tool instances.
- Verify location occupancy and item statuses.

## Equipment

The Equipment section is used to browse tools, manage tool data, and work with cart/offer flows.

- View tool details, pricing, condition, and availability.
- Manage tool instances (serial-linked units).
- Add available tools to cart for reservation/offer workflows.

### Find Who Has a Specific Item

If an item is missing, use this process:

1. Open **Rentals** and focus on rentals with status **Active** or **Overdue**.
2. Open the relevant rental and find the matching item by tool/serial number.
3. Identify the renter from the rental’s **Employee ID**.
4. For kiosk checkouts, review **Checkout Condition** and **Notes** for stored photo reference/path.
5. If needed, verify with API data from `GET /api/rentals` and match:
   - `rentalItems[].instance.serialNumber`
   - `employeeID`
   - `checkoutCondition` / `notes`

## Rental

The Rental section handles reservation lifecycle actions.

- Create reservations from selected tools and rental dates.
- Approve, extend, return, or force-handle overdue rentals.
- Review rental items, period, and total cost per case.

## API

Use API endpoints for integrations, kiosks, and operational checklists.

- Base path: `/api`
- Health checks:
  - `/healthz`
  - `/api/healthz`

### Core Rental Endpoints

- `GET /api/rentals`
- `GET /api/rentals/{rental_id}`
- `POST /api/rentals`
- `POST /api/rentals/{rental_id}/approve`
- `POST /api/rentals/{rental_id}/extend`
- `POST /api/rentals/{rental_id}/return`
- `GET /api/rentals/availability/by-tool?toolID=1&startDate=2026-02-20&endDate=2026-02-25&quantity=2`

### Offer Endpoints

- `GET /api/offers/{offer_number}`
- `POST /api/offers/{offer_number}/checkout`

Example checkout payload:

```json
{
  "employeeID": 12,
  "projectCode": "PRJ-2026-021",
  "purpose": "Site work week 8",
  "startDate": "2026-02-20",
  "endDate": "2026-02-24",
  "notes": "Converted from offer in webshop"
}
```

### Kiosk Endpoint

- `POST /api/kiosk/lend`

Example kiosk lend payload:

```json
{
  "employeeID": 12,
  "pinCode": "1234",
  "projectCode": "PRJ-2026-021",
  "purpose": "Internal pickup",
  "startDate": "2026-02-20",
  "endDate": "2026-02-24",
  "photoDataUrl": "data:image/jpeg;base64,...",
  "rentalItems": [
    {
      "toolID": 4,
      "quantity": 1,
      "assignmentMode": "auto",
      "allowDeficit": true
    }
  ]
}
```

### Line-Level Operations (Phase 1 API)

- `POST /api/rentals/{rental_id}/mark-items-for-rental`
- `POST /api/rentals/{rental_id}/receive-marked-items`

Example mark-items-for-rental payload:

```json
{
  "operatorUserID": 1,
  "items": [
    {
      "rentalItemID": 101,
      "pickedQuantity": 1,
      "toolInstanceIDs": [5021],
      "serialInput": "SP2026-0101-0001",
      "notes": "Picked from shelf B-12"
    }
  ]
}
```

Example receive-marked-items payload:

```json
{
  "operatorUserID": 1,
  "items": [
    {
      "rentalItemID": 101,
      "returnedQuantity": 1,
      "notReturnedQuantity": 0,
      "condition": "Good",
      "notes": "Returned complete"
    }
  ]
}
```

### Notes

- Offer numbers are numeric `YYNNNN` (example: `260001`).
- Normal rental numbers use the `RNT-###` format.
- Kiosk photo files are stored under `/uploads/rentals/` and linked from rental notes/checkout fields.
