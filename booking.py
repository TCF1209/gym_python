"""
booking.py -- Booking Officer role handlers.

Stub. To be implemented in the next pass:
  - Register New Member (generates M### ID, validates phone/email)
  - Create New Booking  (F1 BK{YYYYMMDD}{###} ID, quota & double-book checks)
  - Cancel Booking      (calculate_cancellation_penalty, create Pending
                         Penalty payment if penalty_rm > 0)
  - Reschedule Booking  (in-place CLASS_ID update; reject if new slot full;
                         no penalty applied)
  - View Member Booking History
  - View All Bookings

All create/cancel/reschedule actions must call utils.recount_class_bookings
so classes.txt's CURRENT_BOOKED counter stays in sync with bookings.txt.
"""
