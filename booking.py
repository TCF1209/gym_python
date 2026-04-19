"""
booking.py -- Booking Officer role handlers.

Exposes one entry point -- handle_choice(choice, username) -- which main.py
calls for every Booking Officer menu selection except Logout. This module
owns:

  1. Register New Member       (M### auto-ID; monthly expiry; NO auto-payment)
  2. Create New Booking        (F1 BK{YYYYMMDD}{###} ID; quota + double-book
                                + capacity + status + future-date checks)
  3. Cancel Booking            (calculate_cancellation_penalty; creates a
                                Pending Penalty payment on late cancel)
  4. Reschedule Booking        (in-place class_id update; same booking_id;
                                NO penalty; rejects if new slot full)
  5. View Member Booking History (member summary + booking history table)
  6. View All Bookings

Business rules:
  * Suspended/Expired members cannot create new bookings.
  * Quota consumption is checked against the month of the chosen class date
    (not today). Basic=5, Premium=15, VIP=Unlimited. Confirmed + Completed +
    No-Show count; Cancelled doesn't.
  * One member cannot have two Confirmed bookings for the same class_id.
  * Every create / cancel / reschedule calls utils.recount_class_bookings
    so classes.current_booked stays in sync with bookings.
  * Cancelling within CANCELLATION_WINDOW_HOURS (24h) of class start creates
    a Pending Penalty payment of LATE_CANCEL_PENALTY_RM referencing the
    booking_id. Outside the window, no penalty.
  * Register does NOT auto-create the first monthly payment; the Accountant
    records it separately.
"""

from datetime import datetime, timedelta

import utils


# ============================================================
# ENTRY POINT (called from main.py)
# ============================================================

def handle_choice(choice, username):
    """Dispatch a single Booking Officer menu choice. Caller handles Logout."""
    if choice == "1":
        register_new_member(username)
    elif choice == "2":
        create_new_booking(username)
    elif choice == "3":
        cancel_booking(username)
    elif choice == "4":
        reschedule_booking(username)
    elif choice == "5":
        view_member_booking_history(username)
    elif choice == "6":
        view_all_bookings(username)


# ============================================================
# 1. REGISTER NEW MEMBER
# ============================================================

def register_new_member(username):
    """Collect member details, assign M###, set 30-day expiry, persist."""
    print("\n── Register New Member ──")

    name = utils.get_non_empty_string("  Full name: ")
    age = utils.get_valid_int("  Age (18-100): ", 18, 100)
    gender = utils.get_valid_menu_choice("  Gender (M/F): ", utils.VALID_GENDERS)
    phone = utils.get_valid_phone("  Phone (Malaysian mobile): ")
    email = utils.get_valid_email("  Email: ")
    tiers_str = "/".join(utils.VALID_TIERS)
    tier = utils.get_valid_menu_choice(
        f"  Tier [{tiers_str}]: ", utils.VALID_TIERS,
    )

    members = utils.read_members()
    today = datetime.now().date()
    join_date_str = today.strftime(utils.DATE_FORMAT)
    # Monthly membership cycle: 30-day expiry from today.
    expiry_date_str = (today + timedelta(days=30)).strftime(utils.DATE_FORMAT)

    new_member = {
        "id": utils.generate_member_id(members),
        "name": name,
        "age": age,
        "gender": gender,
        "phone": phone,
        "email": email,
        "tier": tier,
        "join_date": join_date_str,
        "expiry_date": expiry_date_str,
        "status": "Active",
    }
    members.append(new_member)
    utils.write_members(members)
    utils.log_audit(
        "BookingOfficer", "REGISTER_MEMBER",
        f"{new_member['id']} {name} ({tier})",
    )

    print(f"\n✓ Registered {new_member['id']} {name}.")
    print(f"  Tier:    {tier} — {utils.format_currency(utils.get_tier_fee(tier))}/month")
    print(f"  Quota:   {utils.format_quota_display(tier)} classes/month")
    print(f"  Expiry:  {expiry_date_str}  (renew before then)")
    print("  ℹ️  Accountant: please record the first monthly payment separately.")
    utils.pause()


# ============================================================
# 2. CREATE NEW BOOKING
# ============================================================

def create_new_booking(username):
    """Collect member + class, run all checks, then persist booking + audit."""
    print("\n── Create New Booking ──")

    # -- Member --
    member_id = utils.get_non_empty_string("  Member ID: ")
    members = utils.read_members()
    member = utils.find_member_by_id(members, member_id)
    if member is None:
        print(f"✗ Member {member_id} not found.")
        utils.pause()
        return
    if member["status"] == "Suspended":
        print(f"✗ {member_id} ({member['name']}) is Suspended. Resolve membership first.")
        utils.pause()
        return
    if member["status"] == "Expired":
        print(f"✗ {member_id} ({member['name']}) is Expired. Renew membership first.")
        utils.pause()
        return

    # -- Class --
    class_id = utils.get_non_empty_string("  Class ID: ")
    classes = utils.read_classes()
    cls = utils.find_class_by_id(classes, class_id)
    if cls is None:
        print(f"✗ Class {class_id} not found.")
        utils.pause()
        return
    if cls["status"] != "Scheduled":
        print(f"✗ {class_id} is {cls['status']}; only Scheduled classes can be booked.")
        utils.pause()
        return

    try:
        class_date_dt = datetime.strptime(cls["schedule_date"], utils.DATE_FORMAT)
    except ValueError:
        print(f"✗ {class_id} has an invalid schedule_date.")
        utils.pause()
        return

    today = datetime.now().date()
    if class_date_dt.date() < today:
        print(f"✗ {class_id} is on {cls['schedule_date']} — cannot book past classes.")
        utils.pause()
        return

    # -- Capacity --
    if cls["current_booked"] >= cls["capacity"]:
        print(f"✗ {class_id} is FULL ({cls['current_booked']}/{cls['capacity']}).")
        utils.pause()
        return

    # -- Quota (in the class's month) --
    bookings = utils.read_bookings()
    used = utils.get_quota_used_this_month(bookings, member_id, class_date_dt)
    quota_num = utils.get_tier_quota(member["tier"])
    quota_display = utils.format_quota_display(member["tier"])
    if used >= quota_num:
        month_str = class_date_dt.strftime("%Y-%m")
        print(f"✗ {member_id} has used {used}/{quota_display} in {month_str}.")
        utils.pause()
        return

    # -- Double-book --
    if utils.is_double_booked(bookings, member_id, class_id):
        print(f"✗ {member_id} already has a Confirmed booking for {class_id}.")
        utils.pause()
        return

    # -- Create --
    booking_id = utils.generate_booking_id(bookings)
    new_booking = {
        "id": booking_id,
        "member_id": member_id,
        "class_id": class_id,
        "booking_date": today.strftime(utils.DATE_FORMAT),
        "class_date": cls["schedule_date"],
        "status": "Confirmed",
        "penalty_rm": 0.00,
    }
    bookings.append(new_booking)
    utils.write_bookings(bookings)
    utils.recount_class_bookings(class_id)

    utils.log_audit(
        "BookingOfficer", "CREATE_BOOKING",
        f"{booking_id} {member_id} -> {class_id} {cls['name']} "
        f"{cls['schedule_date']} {cls['start_time']}",
    )

    # Receipt-worthy confirmation -- one of the demo touchpoints in the brief.
    used_after = utils.get_quota_used_this_month(bookings, member_id, class_date_dt)
    month_str = class_date_dt.strftime("%Y-%m")
    print()
    print("─" * 50)
    print("           BOOKING CONFIRMED")
    print("─" * 50)
    print(f"  Booking ID:  {booking_id}")
    print(f"  Member:      {member_id} {member['name']}")
    print(f"  Class:       {class_id} {cls['name']}")
    print(f"  Trainer:     {cls['trainer_id']}")
    print(f"  Date:        {cls['schedule_date']} {cls['start_time']}")
    print(f"  Duration:    {cls['duration_min']} min")
    print(f"  Quota used:  {used_after}/{quota_display} for {month_str}")
    print("─" * 50)
    utils.pause()


# ============================================================
# 3. CANCEL BOOKING
# ============================================================

def cancel_booking(username):
    """Cancel a Confirmed booking. Late cancels create a Pending Penalty payment."""
    print("\n── Cancel Booking ──")
    booking_id = utils.get_non_empty_string("  Booking ID: ")

    bookings = utils.read_bookings()
    booking = utils.find_booking_by_id(bookings, booking_id)
    if booking is None:
        print(f"✗ Booking {booking_id} not found.")
        utils.pause()
        return
    if booking["status"] != "Confirmed":
        print(f"✗ {booking_id} is {booking['status']}; "
              f"only Confirmed bookings can be cancelled.")
        utils.pause()
        return

    # Pull the class start time for the 24h penalty calculation.
    classes = utils.read_classes()
    cls = utils.find_class_by_id(classes, booking["class_id"])
    if cls is None:
        # Orphan booking (class was removed after booking) -- cancel with no penalty.
        start_time_for_calc = "00:00"
    else:
        start_time_for_calc = cls["start_time"]

    penalty = utils.calculate_cancellation_penalty(
        booking["class_date"], start_time_for_calc,
    )

    # Show the member what they're about to do.
    print(f"\n  Booking {booking_id}")
    print(f"    Member:     {booking['member_id']}")
    print(f"    Class:      {booking['class_id']}  on {booking['class_date']} {start_time_for_calc}")
    if penalty > 0:
        print(f"  ⚠️  Within {utils.CANCELLATION_WINDOW_HOURS}h of class start "
              f"→ {utils.format_currency(penalty)} late-cancel penalty")
    else:
        print("  ℹ️  Outside cancellation window → no penalty")

    if not utils.get_yes_no("  Proceed with cancellation?"):
        print("✗ Aborted.")
        utils.pause()
        return

    # Apply cancellation on the booking side.
    booking["status"] = "Cancelled"
    booking["penalty_rm"] = penalty
    utils.write_bookings(bookings)
    utils.recount_class_bookings(booking["class_id"])

    if penalty > 0:
        # Mirror the no-show flow: Pending Penalty referencing the booking.
        payments = utils.read_payments()
        new_payment = {
            "id": utils.generate_payment_id(payments),
            "member_id": booking["member_id"],
            "amount": penalty,
            "payment_type": "Penalty",
            "method": "",                                    # set when Accountant records it
            "payment_date": datetime.now().strftime(utils.DATE_FORMAT),
            "status": "Pending",
            "reference_id": booking_id,
        }
        payments.append(new_payment)
        utils.write_payments(payments)
        utils.log_audit(
            "BookingOfficer", "CANCEL_BOOKING",
            f"{booking_id} cancelled; penalty {new_payment['id']} "
            f"{utils.format_currency(penalty)} (late cancel)",
        )
        print(f"\n✓ {booking_id} cancelled.")
        print(f"  Pending penalty payment {new_payment['id']} "
              f"({utils.format_currency(penalty)}) created.")
    else:
        utils.log_audit(
            "BookingOfficer", "CANCEL_BOOKING",
            f"{booking_id} cancelled; no penalty",
        )
        print(f"\n✓ {booking_id} cancelled. No penalty.")

    utils.pause()


# ============================================================
# 4. RESCHEDULE BOOKING
# ============================================================

def reschedule_booking(username):
    """Move a Confirmed booking to a different class. Same ID, no penalty."""
    print("\n── Reschedule Booking ──")
    booking_id = utils.get_non_empty_string("  Booking ID: ")

    bookings = utils.read_bookings()
    booking = utils.find_booking_by_id(bookings, booking_id)
    if booking is None:
        print(f"✗ Booking {booking_id} not found.")
        utils.pause()
        return
    if booking["status"] != "Confirmed":
        print(f"✗ {booking_id} is {booking['status']}; "
              f"only Confirmed bookings can be rescheduled.")
        utils.pause()
        return

    classes = utils.read_classes()
    old_class = utils.find_class_by_id(classes, booking["class_id"])
    print(f"\n  Current: {booking['class_id']} on {booking['class_date']}")
    if old_class is not None:
        print(f"           {old_class['name']}  {old_class['start_time']}")

    new_class_id = utils.get_non_empty_string("  New class ID: ")
    if new_class_id == booking["class_id"]:
        print("✗ New class is the same as current class -- nothing to do.")
        utils.pause()
        return

    new_class = utils.find_class_by_id(classes, new_class_id)
    if new_class is None:
        print(f"✗ Class {new_class_id} not found.")
        utils.pause()
        return
    if new_class["status"] != "Scheduled":
        print(f"✗ {new_class_id} is {new_class['status']}; "
              f"only Scheduled classes can be rescheduled into.")
        utils.pause()
        return

    try:
        new_date = datetime.strptime(new_class["schedule_date"], utils.DATE_FORMAT).date()
    except ValueError:
        print(f"✗ {new_class_id} has an invalid schedule_date.")
        utils.pause()
        return
    if new_date < datetime.now().date():
        print(f"✗ {new_class_id} is on {new_class['schedule_date']} — "
              f"cannot reschedule to a past date.")
        utils.pause()
        return

    if new_class["current_booked"] >= new_class["capacity"]:
        print(f"✗ {new_class_id} is FULL "
              f"({new_class['current_booked']}/{new_class['capacity']}).")
        utils.pause()
        return

    if utils.is_double_booked(bookings, booking["member_id"], new_class_id):
        print(f"✗ {booking['member_id']} already has a Confirmed booking for {new_class_id}.")
        utils.pause()
        return

    # Apply in place. Same booking_id. Penalty unchanged (per spec: no penalty
    # for reschedule).
    old_class_id = booking["class_id"]
    old_class_date = booking["class_date"]
    booking["class_id"] = new_class_id
    booking["class_date"] = new_class["schedule_date"]
    utils.write_bookings(bookings)

    # Both classes need their counters resynced: the old one frees a seat,
    # the new one takes one.
    utils.recount_class_bookings(old_class_id)
    utils.recount_class_bookings(new_class_id)

    utils.log_audit(
        "BookingOfficer", "RESCHEDULE_BOOKING",
        f"{booking_id} {old_class_id} {old_class_date} -> "
        f"{new_class_id} {new_class['schedule_date']}",
    )

    print(f"\n✓ {booking_id} rescheduled.")
    print(f"  Member:  {booking['member_id']}")
    print(f"  From:    {old_class_id} on {old_class_date}")
    print(f"  To:      {new_class_id} on {new_class['schedule_date']} "
          f"{new_class['start_time']}")
    print("  No penalty applied.")
    utils.pause()


# ============================================================
# 5. VIEW MEMBER BOOKING HISTORY
# ============================================================

def view_member_booking_history(username):
    """Summary card for a member + their booking list."""
    print("\n── View Member Booking History ──")
    member_id = utils.get_non_empty_string("  Member ID: ")

    members = utils.read_members()
    member = utils.find_member_by_id(members, member_id)
    if member is None:
        print(f"✗ Member {member_id} not found.")
        utils.pause()
        return

    bookings = utils.read_bookings()
    used = utils.get_quota_used_this_month(bookings, member_id)
    quota_display = utils.format_quota_display(member["tier"])

    # --- Member summary card ---
    print()
    print("─" * 60)
    print(f"  Member:     {member['id']}   {member['name']}")
    print(f"  Tier:       {member['tier']}")
    print(f"  Status:     {member['status']}")
    print(f"  Expiry:     {member['expiry_date']}")
    print(f"  Quota used: {used} / {quota_display} this month")
    print("─" * 60)

    # --- Booking list ---
    member_bookings = []
    for b in bookings:
        if b["member_id"] == member_id:
            member_bookings.append(b)

    if not member_bookings:
        print(f"\n  No booking history for {member_id}.")
        utils.pause()
        return

    utils.print_section_header("📋", f"BOOKINGS ({len(member_bookings)})")
    headers = ["Booking ID",    "Class", "Booked",     "Class Date", "Status",   "Penalty"]
    widths =  [14,              6,       12,           12,           10,         10]
    rows = []
    for b in member_bookings:
        rows.append([
            b["id"], b["class_id"],
            b["booking_date"], b["class_date"],
            b["status"], utils.format_currency(b["penalty_rm"]),
        ])
    utils.print_table(headers, widths, rows)
    utils.pause()


# ============================================================
# 6. VIEW ALL BOOKINGS
# ============================================================

def view_all_bookings(username):
    """Tabular listing of every booking."""
    bookings = utils.read_bookings()
    if not bookings:
        print("\nℹ️  No bookings on file.")
        utils.pause()
        return
    utils.print_section_header("📋", f"ALL BOOKINGS ({len(bookings)})")
    headers = ["Booking ID",    "Member", "Class", "Booked",     "Class Date", "Status",   "Penalty"]
    widths =  [14,              7,        6,       12,           12,           10,         10]
    rows = []
    for b in bookings:
        rows.append([
            b["id"], b["member_id"], b["class_id"],
            b["booking_date"], b["class_date"],
            b["status"], utils.format_currency(b["penalty_rm"]),
        ])
    utils.print_table(headers, widths, rows)
    utils.pause()
