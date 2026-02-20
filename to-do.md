# TODO

## Independent

1. Audit trail: record who changed status/extended/forced returns with timestamps.
2. Notifications: simple email/SMS reminders for upcoming due date and overdue items.
3. Warehouse location assignment bug: in Warehouse view, clicking a location and pressing "Edit Location" opens the modal, but unassigned tools cannot be selected and search returns no results when typing and searching.
   - Repro: Warehouse -> click location -> Edit Location -> try selecting unassigned tool / type in search.
   - Expected: unassigned tools list should load, search should filter, and selected tool should be assignable to the location.

## Dependent

### Phase 1 - DB/API First

1. Employee sync from Employee API: import/sync employee list and use employee IDs as the only valid renter/reserver identities.
   - Predecessor: None (required before final notification and identity flows)
   - Status: Deferred until API hash/credentials are available.

### Phase 2 - UI/Operations

1. Simple warehouse Pickup/Return screen integration: operational entry point that uses the checklist flows and photo capture in warehouse context.
   - Predecessor: Incoming and Outgoing tablet checklist flows
2. Reservation receipt/communication UX: after reservation submit, show confirmation details (reservation number) and provide downloadable/printable receipt; after approve/reject, surface outbound notification status/details.
   - Predecessor: Phase 1 reservation decision API (completed), Employee sync from Employee API
3. Checklist photo persistence: store pickup/return checklist photos in backend records (not only local UI preview) and surface them for later lookup/audit.
   - Predecessor: Incoming/Outgoing checklist flows (completed)

### Phase 3 - Accounting

1. Weekly accounting notification job: send accounting a weekly report of invoiceable rental items/cases with rental duration, per-line amount, ledger/case breakdown, and case totals.
   - Predecessor: Phase 1 pricing integrity (completed)
   - Note: report format/details can be refined later; automated weekly collection/delivery is the priority.
2. Weekly accounting integration for partial flows: bill only picked items for active rental duration, stop billing returned lines at receive date, and include replacement charge for not-returned/lost lines.
   - Predecessor: Weekly accounting notification job, Phase 1 rental line lifecycle + transaction APIs (completed)
3. Reservation communication delivery: send employee-facing approval/rejection notifications including reservation/rental number, reason (for reject), and order details (for approve); support email first and optional SMS later.
   - Predecessor: Phase 1 reservation decision API (completed), Reservation approval/rejection UX (completed), Employee sync from Employee API
4. Shortage and partial-dispatch accounting treatment: replacement/procure lines remain non-invoiceable until picked and marked In Rental; weekly statements must exclude pending shortage lines.
   - Predecessor: Weekly accounting integration for partial flows, Phase 1 shortage/partial-dispatch rules (completed)
