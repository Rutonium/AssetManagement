# TODO

## Independent

1. Audit trail: record who changed status/extended/forced returns with timestamps.
2. Notifications: simple email/SMS reminders for upcoming due date and overdue items.

## Dependent

1. Reservation states: use a clear state machine (Offer ? Reserved ? Active ? Returned ? Overdue ? Closed) so edge cases are predictable.
   - Predecessor: None (foundation for rental-related features)
2. Availability engine: compute instance availability by date range, block overlaps, respect certification expiry and status.
   - Predecessor: Reservation states
3. Auto-assign vs manual: allow auto-pick by default with a manual override to choose specific instances.
   - Predecessor: Availability engine
4. Exceptions: allow over-allocation but mark it as a "deficit" instead of blocking the reservation.
   - Predecessor: Availability engine
5. Pricing integrity: snapshot pricing at reservation time so later price changes don’t alter existing rentals/offers.
   - Predecessor: Reservation states
6. Create webshop "save rental case cart as offer" where the user can pick all tools neccessary and then print out a pdf stating the prices (per day, and total for period) as a sort of rental offer, without actually reserving anything. The Rental offer should create a uniue number that when inserted in the empty cart it should fetch the data and start a new cart with the dates, tools etc that was in the offer. When pressing Checkout a reservation of the tools are made to the projektnumber until the tools are returned.
   - Predecessor: Reservation states, Pricing integrity
7. The webshop should have an "kiosk mode" for internal renting. It will run off a android tablet. In this users shall be able to selct their own id and a tool the need. They then type in their pin-code and press "confirm". when they press confirm the camera of the tablet takes a picture and stores with the reciept for who has lent the equipment. Users make a cart with dates and everything and then press "lend". Once confirmed they are presented with a screen with the specific tool instances that they can pick up. maybe later we can add a camera barcode scanner to verify.
   - Predecessor: Reservation states, Availability engine, Auto-assign vs manual
