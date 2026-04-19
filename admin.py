"""
admin.py -- System Administrator role handlers.

Exposes one entry point -- handle_choice(choice, username) -- which main.py
calls for every Administrator menu selection except Logout. This module
owns:

  1. Manage Classes       (Add / Update / Remove / View, via sub-menu)
  2. Manage Trainers      (Add / Update / Remove / View, via sub-menu)
  3. View All Members
  4. View All Bookings
  5. View All Payments
  6. System Report        (multi-section text summary)

F6 Peak Hours Analytics, F9 Analytics Dashboard, and F7 View Audit Log
are placeholders here -- they're the last step of the build order and
will be filled in after booking.py and accountant.py.

Business rules enforced in this module:
  * Removing a class that still has Confirmed bookings cascades those
    bookings to Cancelled (penalty=0, not the member's fault) and soft-
    deletes the class by flipping its status to Cancelled (the row is
    kept for historical reporting). Logs ADMIN_CANCEL_CLASS.
  * Removing a trainer is REJECTED if the trainer has any active class
    assignments (status != Cancelled AND schedule_date >= today). The
    admin is shown the blocking classes and told to reassign first.
    Otherwise the trainer is soft-deleted by flipping status to Inactive.
"""

import os.path
from datetime import datetime

import utils


# ============================================================
# ENTRY POINT (called from main.py)
# ============================================================

def handle_choice(choice, username):
    """Dispatch a single admin menu choice. Caller handles Logout."""
    if choice == "1":
        manage_classes(username)
    elif choice == "2":
        manage_trainers(username)
    elif choice == "3":
        view_all_members()
    elif choice == "4":
        view_all_bookings()
    elif choice == "5":
        view_all_payments()
    elif choice == "6":
        system_report()
    elif choice == "7":
        peak_hours_analytics()
    elif choice == "8":
        analytics_dashboard()
    elif choice == "9":
        view_audit_log()


def _placeholder(feature_name):
    """Stand-in until the feature is implemented in the next pass."""
    print(f"\nℹ️  {feature_name} -- to be implemented in the next pass.")
    utils.pause()


# ============================================================
# SHARED UI HELPERS
# ============================================================

# Section-header width must be wide enough for the System Report banner
# without wrapping on a standard 80-column terminal. Shared with every
# utils.print_section_header call in this module.
SECTION_WIDTH = 60


def _print_sub_menu(title, options):
    """Compact sub-menu (used inside Manage Classes / Manage Trainers)."""
    print()
    print(f"── {title} ──")
    for num, label in options:
        print(f"  {num}. {label}")


def _ask_option(options):
    """Prompt for one of the option numbers and return the chosen string."""
    valid_nums = []
    for num, _ in options:
        valid_nums.append(num)
    prompt = f"  Enter choice [{valid_nums[0]}-{valid_nums[-1]}]: "
    return utils.get_valid_menu_choice(prompt, valid_nums)


# ============================================================
# MANAGE CLASSES
# ============================================================

_CLASS_SUBMENU = [
    ("1", "Add Class"),
    ("2", "Update Class"),
    ("3", "Remove Class"),
    ("4", "View All Classes"),
    ("5", "Back"),
]


def manage_classes(username):
    """Manage Classes sub-menu loop."""
    while True:
        _print_sub_menu("MANAGE CLASSES", _CLASS_SUBMENU)
        choice = _ask_option(_CLASS_SUBMENU)
        if choice == "5":
            return
        if choice == "1":
            _add_class(username)
        elif choice == "2":
            _update_class(username)
        elif choice == "3":
            _remove_class(username)
        elif choice == "4":
            _view_all_classes()


def _find_first_active_trainer_for(class_name):
    """Return the first Active trainer whose specialization matches, else None."""
    trainers = utils.read_trainers()
    for t in trainers:
        if t["specialization"] == class_name and t["status"] == "Active":
            return t
    return None


def _add_class(username):
    """Add a new class with auto-generated ID and trainer."""
    print("\n── Add Class ──")
    options_str = "/".join(utils.VALID_CLASS_NAMES)
    class_name = utils.get_valid_menu_choice(
        f"  Class name [{options_str}]: ", utils.VALID_CLASS_NAMES,
    )

    matching_trainer = _find_first_active_trainer_for(class_name)
    if matching_trainer is None:
        print(f"✗ No Active trainer available for {class_name}.")
        print("  Add or reactivate a trainer in 'Manage Trainers' first.")
        utils.pause()
        return

    schedule_dt = utils.get_valid_date(
        "  Schedule date (YYYY-MM-DD, today or later): ", allow_past=False,
    )
    start_time = utils.get_valid_time("  Start time (HH:MM, 24-hour): ")

    classes = utils.read_classes()
    new_class = {
        "id": utils.generate_class_id(classes),
        "name": class_name,
        "trainer_id": matching_trainer["id"],
        "schedule_date": schedule_dt.strftime(utils.DATE_FORMAT),
        "start_time": start_time,
        "duration_min": 60,
        "capacity": utils.CLASS_CAPACITY[class_name],
        "current_booked": 0,
        "status": "Scheduled",
    }
    classes.append(new_class)
    utils.write_classes(classes)
    utils.log_audit(
        "Administrator", "ADD_CLASS",
        f"{new_class['id']} {class_name} on {new_class['schedule_date']} {start_time}",
    )
    print(f"\n✓ Added class {new_class['id']} ({class_name}).")
    print(f"  Date:     {new_class['schedule_date']} {start_time}")
    print(f"  Trainer:  {matching_trainer['id']} {matching_trainer['name']}")
    print(f"  Capacity: {new_class['capacity']}")
    utils.pause()


_CLASS_UPDATE_FIELDS = [
    ("1", "Schedule Date"),
    ("2", "Start Time"),
    ("3", "Trainer"),
    ("4", "Cancel update"),
]


def _update_class(username):
    """Update date, time, or trainer for an existing class. Status changes use Remove."""
    print("\n── Update Class ──")
    class_id = utils.get_non_empty_string(
        "  Class ID (blank to cancel): ",
    ).strip()
    # get_non_empty_string guarantees non-empty, but keep the blank-cancel
    # idiom clear at the call site. If we ever want an opt-out prompt we
    # can swap this for a custom helper.

    classes = utils.read_classes()
    cls = utils.find_class_by_id(classes, class_id)
    if cls is None:
        print(f"✗ Class {class_id} not found.")
        utils.pause()
        return

    print(f"\n  Current values for {class_id}:")
    print(f"    Name:          {cls['name']}")
    print(f"    Schedule Date: {cls['schedule_date']}")
    print(f"    Start Time:    {cls['start_time']}")
    print(f"    Trainer:       {cls['trainer_id']}")
    print(f"    Status:        {cls['status']}  (change via Remove Class)")
    print(f"    Capacity:      {cls['capacity']}  (fixed by class type)")

    _print_sub_menu("UPDATE WHICH FIELD", _CLASS_UPDATE_FIELDS)
    choice = _ask_option(_CLASS_UPDATE_FIELDS)
    if choice == "4":
        return

    old_value = None
    new_value = None
    field_label = None

    if choice == "1":
        new_dt = utils.get_valid_date(
            "  New schedule date: ", allow_past=False,
        )
        old_value = cls["schedule_date"]
        cls["schedule_date"] = new_dt.strftime(utils.DATE_FORMAT)
        new_value = cls["schedule_date"]
        field_label = "schedule_date"
        # Keep the denormalised class_date on bookings in sync.
        _sync_booking_class_dates(class_id, new_value)
    elif choice == "2":
        new_time = utils.get_valid_time("  New start time: ")
        old_value = cls["start_time"]
        cls["start_time"] = new_time
        new_value = new_time
        field_label = "start_time"
    elif choice == "3":
        # Only list Active trainers whose specialization matches this class type.
        trainers = utils.read_trainers()
        matching = []
        for t in trainers:
            if t["specialization"] == cls["name"] and t["status"] == "Active":
                matching.append(t)
        if not matching:
            print(f"✗ No Active trainer available for {cls['name']}.")
            utils.pause()
            return
        print("\n  Available trainers:")
        for t in matching:
            print(f"    {t['id']}  {t['name']}")
        valid_tids = []
        for t in matching:
            valid_tids.append(t["id"])
        new_tid = utils.get_valid_menu_choice("  New trainer ID: ", valid_tids)
        old_value = cls["trainer_id"]
        cls["trainer_id"] = new_tid
        new_value = new_tid
        field_label = "trainer_id"

    utils.write_classes(classes)
    utils.log_audit(
        "Administrator", "UPDATE_CLASS",
        f"{class_id} {field_label}: {old_value} -> {new_value}",
    )
    print(f"\n✓ Updated {class_id} {field_label}: {old_value} → {new_value}.")
    utils.pause()


def _sync_booking_class_dates(class_id, new_class_date):
    """Rewrite booking.class_date for every booking referencing this class."""
    bookings = utils.read_bookings()
    changed = False
    for b in bookings:
        if b["class_id"] == class_id and b["class_date"] != new_class_date:
            b["class_date"] = new_class_date
            changed = True
    if changed:
        utils.write_bookings(bookings)


def _remove_class(username):
    """Soft-delete a class. If it has Confirmed bookings, prompt and cascade."""
    print("\n── Remove Class ──")
    class_id = utils.get_non_empty_string("  Class ID (blank to cancel): ").strip()

    classes = utils.read_classes()
    cls = utils.find_class_by_id(classes, class_id)
    if cls is None:
        print(f"✗ Class {class_id} not found.")
        utils.pause()
        return
    if cls["status"] == "Cancelled":
        print(f"ℹ️  {class_id} is already Cancelled.")
        utils.pause()
        return

    bookings = utils.read_bookings()
    affected = []
    for b in bookings:
        if b["class_id"] == class_id and b["status"] == "Confirmed":
            affected.append(b)

    if affected:
        print(f"\n⚠️  {class_id} has {len(affected)} Confirmed booking(s):")
        for b in affected:
            print(f"    {b['id']}  member={b['member_id']}  class_date={b['class_date']}")
        print("\n  Cancelling the class will cascade-cancel those bookings")
        print("  (penalty = RM 0.00 -- not the member's fault).")
        if not utils.get_yes_no("  Proceed with cancellation?"):
            print("✗ Aborted.")
            utils.pause()
            return
        for b in affected:
            b["status"] = "Cancelled"
            b["penalty_rm"] = 0.00
        utils.write_bookings(bookings)

    cls["status"] = "Cancelled"
    utils.write_classes(classes)
    # Recompute current_booked now that Confirmed rows are gone.
    utils.recount_class_bookings(class_id)

    utils.log_audit(
        "Administrator", "ADMIN_CANCEL_CLASS",
        f"{class_id} cancelled; {len(affected)} booking(s) cascade-cancelled",
    )
    print(f"\n✓ Class {class_id} marked Cancelled. "
          f"{len(affected)} booking(s) cascade-cancelled.")
    utils.pause()


def _view_all_classes():
    """Print the full class list as a table."""
    classes = utils.read_classes()
    if not classes:
        print("\nℹ️  No classes on file.")
        utils.pause()
        return
    utils.print_section_header("🏋️", f"ALL CLASSES ({len(classes)})", SECTION_WIDTH)
    headers = ["ID",    "Name",   "Trainer", "Date",       "Time",  "Booked", "Cap", "Status"]
    widths =  [6,       10,       7,         12,           6,       6,        4,     10]
    rows = []
    for c in classes:
        rows.append([
            c["id"], c["name"], c["trainer_id"],
            c["schedule_date"], c["start_time"],
            c["current_booked"], c["capacity"], c["status"],
        ])
    utils.print_table(headers, widths, rows)
    utils.pause()


# ============================================================
# MANAGE TRAINERS
# ============================================================

_TRAINER_SUBMENU = [
    ("1", "Add Trainer"),
    ("2", "Update Trainer"),
    ("3", "Remove Trainer"),
    ("4", "View All Trainers"),
    ("5", "Back"),
]


def manage_trainers(username):
    """Manage Trainers sub-menu loop."""
    while True:
        _print_sub_menu("MANAGE TRAINERS", _TRAINER_SUBMENU)
        choice = _ask_option(_TRAINER_SUBMENU)
        if choice == "5":
            return
        if choice == "1":
            _add_trainer(username)
        elif choice == "2":
            _update_trainer(username)
        elif choice == "3":
            _remove_trainer(username)
        elif choice == "4":
            _view_all_trainers()


def _add_trainer(username):
    """Add a new Active trainer."""
    print("\n── Add Trainer ──")
    name = utils.get_non_empty_string("  Full name: ")
    options_str = "/".join(utils.VALID_CLASS_NAMES)
    specialization = utils.get_valid_menu_choice(
        f"  Specialization [{options_str}]: ", utils.VALID_CLASS_NAMES,
    )
    phone = utils.get_valid_phone("  Phone (Malaysian mobile): ")
    email = utils.get_valid_email("  Email: ")
    experience_years = utils.get_valid_int(
        "  Experience years (0-50): ", 0, 50,
    )

    trainers = utils.read_trainers()
    new_trainer = {
        "id": utils.generate_trainer_id(trainers),
        "name": name,
        "specialization": specialization,
        "phone": phone,
        "email": email,
        "experience_years": experience_years,
        "status": "Active",
    }
    trainers.append(new_trainer)
    utils.write_trainers(trainers)
    utils.log_audit(
        "Administrator", "ADD_TRAINER",
        f"{new_trainer['id']} {name} ({specialization})",
    )
    print(f"\n✓ Added trainer {new_trainer['id']} {name}.")
    utils.pause()


_TRAINER_UPDATE_FIELDS = [
    ("1", "Name"),
    ("2", "Phone"),
    ("3", "Email"),
    ("4", "Experience Years"),
    ("5", "Status"),
    ("6", "Cancel update"),
]

_TRAINER_STATUSES = ["Active", "Inactive"]


def _update_trainer(username):
    """Update an existing trainer's personal fields or status."""
    print("\n── Update Trainer ──")
    trainer_id = utils.get_non_empty_string("  Trainer ID (blank to cancel): ").strip()

    trainers = utils.read_trainers()
    t = utils.find_trainer_by_id(trainers, trainer_id)
    if t is None:
        print(f"✗ Trainer {trainer_id} not found.")
        utils.pause()
        return

    print(f"\n  Current values for {trainer_id}:")
    print(f"    Name:              {t['name']}")
    print(f"    Specialization:    {t['specialization']}  (cannot change)")
    print(f"    Phone:             {t['phone']}")
    print(f"    Email:             {t['email']}")
    print(f"    Experience Years:  {t['experience_years']}")
    print(f"    Status:            {t['status']}")

    _print_sub_menu("UPDATE WHICH FIELD", _TRAINER_UPDATE_FIELDS)
    choice = _ask_option(_TRAINER_UPDATE_FIELDS)
    if choice == "6":
        return

    old_value = None
    new_value = None
    field_label = None

    if choice == "1":
        new_name = utils.get_non_empty_string("  New name: ")
        old_value = t["name"]
        t["name"] = new_name
        new_value = new_name
        field_label = "name"
    elif choice == "2":
        new_phone = utils.get_valid_phone("  New phone: ")
        old_value = t["phone"]
        t["phone"] = new_phone
        new_value = new_phone
        field_label = "phone"
    elif choice == "3":
        new_email = utils.get_valid_email("  New email: ")
        old_value = t["email"]
        t["email"] = new_email
        new_value = new_email
        field_label = "email"
    elif choice == "4":
        new_years = utils.get_valid_int("  New experience years (0-50): ", 0, 50)
        old_value = t["experience_years"]
        t["experience_years"] = new_years
        new_value = new_years
        field_label = "experience_years"
    elif choice == "5":
        new_status = utils.get_valid_menu_choice(
            "  New status [Active/Inactive]: ", _TRAINER_STATUSES,
        )
        old_value = t["status"]
        t["status"] = new_status
        new_value = new_status
        field_label = "status"

    utils.write_trainers(trainers)
    utils.log_audit(
        "Administrator", "UPDATE_TRAINER",
        f"{trainer_id} {field_label}: {old_value} -> {new_value}",
    )
    print(f"\n✓ Updated {trainer_id} {field_label}: {old_value} → {new_value}.")
    utils.pause()


def _remove_trainer(username):
    """Soft-delete a trainer. Rejected if they still have active class assignments."""
    print("\n── Remove Trainer ──")
    trainer_id = utils.get_non_empty_string("  Trainer ID (blank to cancel): ").strip()

    trainers = utils.read_trainers()
    t = utils.find_trainer_by_id(trainers, trainer_id)
    if t is None:
        print(f"✗ Trainer {trainer_id} not found.")
        utils.pause()
        return
    if t["status"] == "Inactive":
        print(f"ℹ️  {trainer_id} is already Inactive.")
        utils.pause()
        return

    # Active class assignment = not Cancelled AND scheduled today or later.
    today = datetime.now().date()
    classes = utils.read_classes()
    blocking = []
    for c in classes:
        if c["trainer_id"] != trainer_id:
            continue
        if c["status"] == "Cancelled":
            continue
        try:
            sched = datetime.strptime(c["schedule_date"], utils.DATE_FORMAT).date()
        except ValueError:
            continue
        if sched >= today:
            blocking.append(c)

    if blocking:
        print(f"\n✗ Cannot remove {trainer_id}: {len(blocking)} active class assignment(s):")
        for c in blocking:
            print(f"    {c['id']}  {c['name']:<10} {c['schedule_date']} {c['start_time']}  ({c['status']})")
        print("\n  Reassign these classes to another trainer, then try again.")
        utils.pause()
        return

    t["status"] = "Inactive"
    utils.write_trainers(trainers)
    utils.log_audit(
        "Administrator", "REMOVE_TRAINER",
        f"{trainer_id} marked Inactive",
    )
    print(f"\n✓ Trainer {trainer_id} marked Inactive.")
    utils.pause()


def _view_all_trainers():
    trainers = utils.read_trainers()
    if not trainers:
        print("\nℹ️  No trainers on file.")
        utils.pause()
        return
    utils.print_section_header("🧑‍🏫", f"ALL TRAINERS ({len(trainers)})", SECTION_WIDTH)
    headers = ["ID",    "Name",   "Specialization", "Phone",     "Email",              "Exp", "Status"]
    widths =  [6,       18,       14,               12,          24,                   4,     10]
    rows = []
    for t in trainers:
        rows.append([
            t["id"], t["name"], t["specialization"],
            t["phone"], t["email"],
            t["experience_years"], t["status"],
        ])
    utils.print_table(headers, widths, rows)
    utils.pause()


# ============================================================
# VIEW ALL (read-only bulk listings)
# ============================================================

def view_all_members():
    members = utils.read_members()
    if not members:
        print("\nℹ️  No members on file.")
        utils.pause()
        return
    utils.print_section_header("👥", f"ALL MEMBERS ({len(members)})", SECTION_WIDTH)
    headers = ["ID",    "Name",   "Age", "G", "Tier",   "Phone",      "Expiry",     "Status"]
    widths =  [6,       18,       4,     3,   8,        12,           12,           10]
    rows = []
    for m in members:
        rows.append([
            m["id"], m["name"], m["age"], m["gender"],
            m["tier"], m["phone"],
            m["expiry_date"], m["status"],
        ])
    utils.print_table(headers, widths, rows)
    utils.pause()


def view_all_bookings():
    bookings = utils.read_bookings()
    if not bookings:
        print("\nℹ️  No bookings on file.")
        utils.pause()
        return
    utils.print_section_header("📋", f"ALL BOOKINGS ({len(bookings)})", SECTION_WIDTH)
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


def view_all_payments():
    payments = utils.read_payments()
    if not payments:
        print("\nℹ️  No payments on file.")
        utils.pause()
        return
    utils.print_section_header("💰", f"ALL PAYMENTS ({len(payments)})", SECTION_WIDTH)
    headers = ["ID",    "Member", "Amount",     "Type",       "Method", "Date",       "Status",  "Reference"]
    widths =  [6,       7,        10,           12,           7,        12,           8,         16]
    rows = []
    for p in payments:
        # Dashes read better than empty cells in a fixed-width table.
        method_display = p["method"] if p["method"] else "—"
        ref_display = p["reference_id"] if p["reference_id"] else "—"
        rows.append([
            p["id"], p["member_id"], utils.format_currency(p["amount"]),
            p["payment_type"], method_display,
            p["payment_date"], p["status"], ref_display,
        ])
    utils.print_table(headers, widths, rows)
    utils.pause()


# ============================================================
# SYSTEM REPORT (expanded multi-section summary)
# ============================================================

def system_report():
    """Print a five-section text report of the gym's current state."""
    members = utils.read_members()
    classes = utils.read_classes()
    bookings = utils.read_bookings()
    payments = utils.read_payments()
    audit_entries = utils.read_audit_log()

    _print_report_banner()

    _report_membership(members)
    _report_classes(classes)
    _report_bookings(bookings)
    _report_revenue(payments)
    _report_system_health(members, payments, audit_entries)

    print()
    utils.pause()


def _print_report_banner():
    """Boxed banner shown at the top of the System Report."""
    timestamp = datetime.now().strftime(utils.DATETIME_FORMAT)
    line1 = " SYSTEM REPORT"
    line2 = f" Generated: {timestamp}"
    print()
    print(f"╔{'═' * SECTION_WIDTH}╗")
    print(f"║{line1.ljust(SECTION_WIDTH)}║")
    print(f"║{line2.ljust(SECTION_WIDTH)}║")
    print(f"╚{'═' * SECTION_WIDTH}╝")


def _report_membership(members):
    """Membership totals by tier and by status."""
    utils.print_section_header("👥", "MEMBERSHIP OVERVIEW", SECTION_WIDTH)
    tier_counts = {"Basic": 0, "Premium": 0, "VIP": 0}
    status_counts = {"Active": 0, "Expired": 0, "Suspended": 0}
    for m in members:
        if m["tier"] in tier_counts:
            tier_counts[m["tier"]] += 1
        if m["status"] in status_counts:
            status_counts[m["status"]] += 1
    print(f"  Total members:   {len(members)}")
    print(f"  By tier:         Basic={tier_counts['Basic']}   "
          f"Premium={tier_counts['Premium']}   VIP={tier_counts['VIP']}")
    print(f"  By status:       Active={status_counts['Active']}   "
          f"Expired={status_counts['Expired']}   Suspended={status_counts['Suspended']}")


def _report_classes(classes):
    """Class totals by type, by status, plus overall capacity utilisation."""
    utils.print_section_header("🏋️", "CLASS OVERVIEW", SECTION_WIDTH)
    type_counts = {}
    status_counts = {"Scheduled": 0, "Completed": 0, "Cancelled": 0}
    total_capacity = 0
    total_booked = 0
    for c in classes:
        type_counts[c["name"]] = type_counts.get(c["name"], 0) + 1
        if c["status"] in status_counts:
            status_counts[c["status"]] += 1
        total_capacity += c["capacity"]
        total_booked += c["current_booked"]

    # Build the "by type" line without a generator expression.
    type_parts = []
    for name in utils.VALID_CLASS_NAMES:
        count = type_counts.get(name, 0)
        type_parts.append(f"{name}={count}")
    print(f"  Total classes:   {len(classes)}")
    print(f"  By type:         {'   '.join(type_parts)}")
    print(f"  By status:       Scheduled={status_counts['Scheduled']}   "
          f"Completed={status_counts['Completed']}   "
          f"Cancelled={status_counts['Cancelled']}")
    if total_capacity > 0:
        util_pct = (total_booked * 100.0) / total_capacity
    else:
        util_pct = 0.0
    print(f"  Capacity used:   {total_booked}/{total_capacity} seats ({util_pct:.1f}%)")


def _report_bookings(bookings):
    """Booking totals by status."""
    utils.print_section_header("📋", "BOOKING OVERVIEW", SECTION_WIDTH)
    status_counts = {"Confirmed": 0, "Completed": 0, "Cancelled": 0, "No-Show": 0}
    for b in bookings:
        if b["status"] in status_counts:
            status_counts[b["status"]] += 1
    print(f"  Total bookings:  {len(bookings)}")
    print(f"  By status:       Confirmed={status_counts['Confirmed']}   "
          f"Completed={status_counts['Completed']}   "
          f"Cancelled={status_counts['Cancelled']}   "
          f"No-Show={status_counts['No-Show']}")


def _report_revenue(payments):
    """Revenue split by payment type and status."""
    utils.print_section_header("💰", "REVENUE OVERVIEW", SECTION_WIDTH)
    paid_mem = 0.0
    pending_mem = 0.0
    paid_pen = 0.0
    pending_pen = 0.0
    for p in payments:
        amt = p["amount"]
        if p["payment_type"] == "Membership":
            if p["status"] == "Paid":
                paid_mem += amt
            else:
                pending_mem += amt
        elif p["payment_type"] == "Penalty":
            if p["status"] == "Paid":
                paid_pen += amt
            else:
                pending_pen += amt

    total_paid = paid_mem + paid_pen
    total_pending = pending_mem + pending_pen
    print(f"  Membership (Paid):    {utils.format_currency(paid_mem)}")
    print(f"  Membership (Pending): {utils.format_currency(pending_mem)}")
    print(f"  Penalty    (Paid):    {utils.format_currency(paid_pen)}")
    print(f"  Penalty    (Pending): {utils.format_currency(pending_pen)}")
    print(f"  {'-' * 40}")
    print(f"  TOTAL PAID:           {utils.format_currency(total_paid)}")
    print(f"  TOTAL PENDING:        {utils.format_currency(total_pending)}")


def _report_system_health(members, payments, audit_entries):
    """Operational signals: audit volume, pending payments, near-expiry, data files present."""
    utils.print_section_header("🩺", "SYSTEM HEALTH", SECTION_WIDTH)
    print(f"  Audit log entries:   {len(audit_entries)}")
    pending_count = 0
    for p in payments:
        if p["status"] == "Pending":
            pending_count += 1
    print(f"  Pending payments:    {pending_count}")

    today = datetime.now().date()
    near_expiry = 0
    for m in members:
        if m["status"] != "Active":
            continue
        try:
            exp = datetime.strptime(m["expiry_date"], utils.DATE_FORMAT).date()
        except ValueError:
            continue
        days_left = (exp - today).days
        if 0 <= days_left <= utils.NEAR_EXPIRY_WARN_DAYS:
            near_expiry += 1
    print(f"  Near-expiry alerts:  {near_expiry}  "
          f"(Active members expiring within {utils.NEAR_EXPIRY_WARN_DAYS} days)")

    data_files = [
        utils.MEMBERS_FILE, utils.CLASSES_FILE, utils.TRAINERS_FILE,
        utils.BOOKINGS_FILE, utils.PAYMENTS_FILE, utils.CREDENTIALS_FILE,
    ]
    present = 0
    for fp in data_files:
        if os.path.exists(fp):
            present += 1
    print(f"  Data files on disk:  {present}/{len(data_files)}")


# ============================================================
# F6 -- PEAK HOURS ANALYTICS
# ============================================================

def peak_hours_analytics():
    """
    Hour-bucket bar chart of non-Cancelled bookings (per product decision:
    peak hours reflect actual usage, not abandoned reservations). Each bar
    uses utils.render_ascii_bar; the busiest hour is flagged with a star
    plus a short recommendation line.
    """
    bookings = utils.read_bookings()
    classes = utils.read_classes()

    # class_id -> start_time mapping so we don't O(n*m) linear-scan per booking.
    class_start = {}
    for c in classes:
        class_start[c["id"]] = c["start_time"]

    # Count by integer start-hour.
    hour_counts = {}
    total = 0
    for b in bookings:
        if b["status"] == "Cancelled":
            continue
        if b["class_id"] not in class_start:
            continue
        start_time = class_start[b["class_id"]]
        try:
            hour = int(start_time.split(":")[0])
        except ValueError:
            continue
        if hour in hour_counts:
            hour_counts[hour] += 1
        else:
            hour_counts[hour] = 1
        total += 1

    if total == 0:
        print("\nℹ️  No non-Cancelled bookings to analyse yet.")
        utils.pause()
        return

    # Find the peak hour and the max count (for scaling the bars).
    peak_hour = 0
    peak_count = 0
    for h in hour_counts:
        if hour_counts[h] > peak_count:
            peak_count = hour_counts[h]
            peak_hour = h

    utils.print_section_header(
        "📊", f"PEAK HOUR ANALYSIS (Based on {total} bookings)", SECTION_WIDTH,
    )

    # Ascending hour order so the chart reads left-to-right like a clock.
    sorted_hours = sorted(hour_counts.keys())
    for h in sorted_hours:
        count = hour_counts[h]
        label = f"{h:02d}:00"
        bar = utils.render_ascii_bar(label, count, peak_count)
        if h == peak_hour:
            bar = f"{bar}  ⭐ PEAK"
        print(f"  {bar}")

    print(f"  {'─' * (SECTION_WIDTH - 2)}")
    peak_pct = (peak_count * 100.0) / total
    print(f"  Busiest hour:   {peak_hour:02d}:00  ({peak_pct:.1f}% of all bookings)")
    print(f"  Recommendation: schedule more classes at {peak_hour:02d}:00")
    utils.pause()


# ============================================================
# F7 -- VIEW AUDIT LOG (with filters)
# ============================================================

_AUDIT_FILTER_OPTIONS = [
    ("1", "All entries"),
    ("2", "Filter by role"),
    ("3", "Filter by action"),
    ("4", "Back"),
]

_AUDIT_LIMIT = 50                       # newest-N cap per product decision


def _unique_sorted(values):
    """Return a stable-sorted list of unique values (beginner-friendly dedup)."""
    seen = []
    for v in values:
        if v not in seen:
            seen.append(v)
    seen.sort()
    return seen


def view_audit_log():
    """Feature F7: newest-first audit log with optional role / action filter."""
    entries = utils.read_audit_log()
    if not entries:
        print("\nℹ️  No audit entries on file.")
        utils.pause()
        return

    # Newest first.
    entries_desc = list(reversed(entries))

    print("\n── View Audit Log ──")
    for num, label in _AUDIT_FILTER_OPTIONS:
        print(f"  {num}. {label}")
    choice = utils.get_valid_menu_choice(
        "  Enter choice [1-4]: ", ["1", "2", "3", "4"],
    )
    if choice == "4":
        return

    filter_label = "All entries"
    filtered = entries_desc

    if choice == "2":
        roles_in_log = []
        for e in entries:
            roles_in_log.append(e["role"])
        roles = _unique_sorted(roles_in_log)
        print("\n  Roles in log:")
        for r in roles:
            print(f"    - {r}")
        role_pick = utils.get_valid_menu_choice("  Role: ", roles)
        filter_label = f"role = {role_pick}"
        filtered = []
        for e in entries_desc:
            if e["role"] == role_pick:
                filtered.append(e)

    elif choice == "3":
        actions_in_log = []
        for e in entries:
            actions_in_log.append(e["action"])
        actions = _unique_sorted(actions_in_log)
        print("\n  Actions in log:")
        for a in actions:
            print(f"    - {a}")
        action_pick = utils.get_valid_menu_choice("  Action: ", actions)
        filter_label = f"action = {action_pick}"
        filtered = []
        for e in entries_desc:
            if e["action"] == action_pick:
                filtered.append(e)

    if not filtered:
        print(f"\nℹ️  No audit entries match filter: {filter_label}")
        utils.pause()
        return

    total_match = len(filtered)
    if total_match > _AUDIT_LIMIT:
        print(f"\nℹ️  Showing newest {_AUDIT_LIMIT} of {total_match} "
              f"matching entries  (filter: {filter_label}).")
        filtered = filtered[:_AUDIT_LIMIT]
    else:
        print(f"\nℹ️  {total_match} matching entries, newest first  "
              f"(filter: {filter_label}).")

    utils.print_section_header("📜", "AUDIT LOG", SECTION_WIDTH)
    # Line format avoids the 80-col wrap problems of a fixed-width table --
    # the variable-length 'detail' field is the last column and can wrap
    # naturally without disturbing the earlier alignment.
    for e in filtered:
        print(f"  {e['timestamp']} | {e['role']:<14} | "
              f"{e['action']:<22} | {e['detail']}")
    utils.pause()


# ============================================================
# F9 -- ANALYTICS DASHBOARD
# ============================================================
#
# Multi-section ASCII dashboard. Each section uses the same bar style as
# F6 (utils.render_ascii_bar for counts; a local _render_money_bar for
# currency values). Bars scale per-section so small sections (payment
# status with 2 bars) and large ones (6-month revenue trend) all render
# at the same width on screen.

_DASH_COUNT_BAR_WIDTH = 26         # for class popularity / tier / peak-hour bars
_DASH_MONEY_BAR_WIDTH = 22         # leaves room for "RM 1234.56" + % change tag


def _render_money_bar(label, amount, max_amount, bar_width=_DASH_MONEY_BAR_WIDTH):
    """Count-based render_ascii_bar, but the tail shows a formatted RM value."""
    if max_amount is None or max_amount <= 0:
        filled = 0
    else:
        filled = int((float(amount) / float(max_amount)) * bar_width)
        if filled < 0:
            filled = 0
        if filled > bar_width:
            filled = bar_width
    bar = utils.BAR_CHAR * filled
    return f"{label:<12} {bar} {utils.format_currency(amount)}"


def _count_pair_sort_key(pair):
    """Sort helper: sort a (name, count) tuple by count. Used with reverse=True."""
    return pair[1]


def analytics_dashboard():
    """Feature F9. Five sections (Revenue / Class popularity / Members /
    Payment / Summary) rendered with consistent ASCII bars."""
    members = utils.read_members()
    classes = utils.read_classes()
    bookings = utils.read_bookings()
    payments = utils.read_payments()
    today = datetime.now().date()

    _dashboard_banner()
    _dashboard_revenue_trend(payments, today)
    _dashboard_class_popularity(bookings, classes)
    _dashboard_membership_distribution(members)
    _dashboard_payment_status(payments)
    _dashboard_summary(members, bookings, payments)

    utils.pause()


def _dashboard_banner():
    """Boxed top banner with generation timestamp."""
    timestamp = datetime.now().strftime(utils.DATETIME_FORMAT)
    title = " FITZONE ANALYTICS DASHBOARD"
    subtitle = f" Generated: {timestamp}"
    print()
    print(f"╔{'═' * SECTION_WIDTH}╗")
    print(f"║{title.ljust(SECTION_WIDTH)}║")
    print(f"║{subtitle.ljust(SECTION_WIDTH)}║")
    print(f"╚{'═' * SECTION_WIDTH}╝")


def _dashboard_revenue_trend(payments, today):
    """
    Section 1: 6-month Paid Membership revenue, oldest first, with a
    month-over-month % change tag on months 2..6. Penalty payments are
    excluded per product decision (their amounts skew the chart).
    """
    # Build the (year, month) list, oldest first.
    months = []
    y = today.year
    m = today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    months.reverse()

    # Bucket Paid Membership by month.
    buckets = {}
    for key in months:
        buckets[key] = 0.0
    for p in payments:
        if p["status"] != "Paid":
            continue
        if p["payment_type"] != "Membership":
            continue
        try:
            pdate = datetime.strptime(p["payment_date"], utils.DATE_FORMAT).date()
        except ValueError:
            continue
        key = (pdate.year, pdate.month)
        if key in buckets:
            buckets[key] += p["amount"]

    max_amount = 0.0
    for key in buckets:
        if buckets[key] > max_amount:
            max_amount = buckets[key]

    utils.print_section_header(
        "📊", "REVENUE TREND (Last 6 Months, Paid Membership)", SECTION_WIDTH,
    )

    prev = None
    for key in months:
        (yr, mo) = key
        amount = buckets[key]
        label = datetime(yr, mo, 1).strftime("%b %Y")
        line = _render_money_bar(label, amount, max_amount)

        # Month-over-month % change tag for months 2..6.
        if prev is not None and prev > 0:
            pct = ((amount - prev) / prev) * 100.0
            # Tiny changes (<0.5%) show no tag so the line stays tidy.
            if pct >= 0.5:
                line = f"{line}  📈 +{pct:.1f}%"
            elif pct <= -0.5:
                line = f"{line}  📉 {pct:.1f}%"
        elif prev is not None and prev == 0 and amount > 0:
            # No previous baseline to compute a % against but not empty now.
            line = f"{line}  📈 new"

        print(f"  {line}")
        prev = amount


def _dashboard_class_popularity(bookings, classes):
    """Section 2: non-Cancelled bookings grouped by class type, sorted desc."""
    # class_id -> class_name lookup.
    name_of_class = {}
    for c in classes:
        name_of_class[c["id"]] = c["name"]

    counts_by_name = {}
    total = 0
    for b in bookings:
        if b["status"] == "Cancelled":
            continue
        if b["class_id"] not in name_of_class:
            continue
        name = name_of_class[b["class_id"]]
        if name in counts_by_name:
            counts_by_name[name] += 1
        else:
            counts_by_name[name] = 1
        total += 1

    utils.print_section_header(
        "🏆", f"CLASS POPULARITY ({total} non-Cancelled bookings)", SECTION_WIDTH,
    )

    if total == 0:
        print("  (no bookings to rank)")
        return

    pairs = []
    for name, count in counts_by_name.items():
        pairs.append((name, count))
    pairs.sort(key=_count_pair_sort_key, reverse=True)

    max_count = pairs[0][1]
    for name, count in pairs:
        pct = (count * 100.0) / total
        bar_line = utils.render_ascii_bar(name, count, max_count, bar_width=_DASH_COUNT_BAR_WIDTH)
        print(f"  {bar_line} ({pct:.1f}%)")


def _dashboard_membership_distribution(members):
    """Section 3: tier split across ALL members regardless of status."""
    tier_counts = {"Basic": 0, "Premium": 0, "VIP": 0}
    for m in members:
        if m["tier"] in tier_counts:
            tier_counts[m["tier"]] += 1
    total = len(members)

    utils.print_section_header(
        "👥", f"MEMBERSHIP DISTRIBUTION ({total} members)", SECTION_WIDTH,
    )
    if total == 0:
        print("  (no members on file)")
        return

    max_count = 0
    for tier in tier_counts:
        if tier_counts[tier] > max_count:
            max_count = tier_counts[tier]

    # Render in tier hierarchy order (Basic -> Premium -> VIP), not by count.
    for tier in utils.VALID_TIERS:
        count = tier_counts[tier]
        pct = (count * 100.0) / total
        bar_line = utils.render_ascii_bar(tier, count, max_count, bar_width=_DASH_COUNT_BAR_WIDTH)
        print(f"  {bar_line} ({pct:.1f}%)")


def _dashboard_payment_status(payments):
    """Section 4: Paid vs Pending totals (across all payment types) with %."""
    paid_total = 0.0
    pending_total = 0.0
    for p in payments:
        if p["status"] == "Paid":
            paid_total += p["amount"]
        elif p["status"] == "Pending":
            pending_total += p["amount"]
    grand = paid_total + pending_total

    utils.print_section_header("💰", "PAYMENT STATUS", SECTION_WIDTH)

    if grand <= 0:
        print("  (no payments on file)")
        return

    paid_pct = (paid_total * 100.0) / grand
    pending_pct = (pending_total * 100.0) / grand

    max_amt = paid_total
    if pending_total > max_amt:
        max_amt = pending_total

    paid_line = _render_money_bar("Paid", paid_total, max_amt)
    pending_line = _render_money_bar("Pending", pending_total, max_amt)
    print(f"  {paid_line}  ({paid_pct:.1f}%)")
    print(f"  {pending_line}  ({pending_pct:.1f}%)")


def _dashboard_summary(members, bookings, payments):
    """Bottom summary footer: Total Revenue (Paid) / Active Members / Total Bookings."""
    paid_total = 0.0
    for p in payments:
        if p["status"] == "Paid":
            paid_total += p["amount"]
    active_count = 0
    for m in members:
        if m["status"] == "Active":
            active_count += 1

    print()
    print(f"  {'─' * (SECTION_WIDTH - 2)}")
    print(f"  Total Revenue:  {utils.format_currency(paid_total)}  (Paid only)")
    print(f"  Active Members: {active_count}")
    print(f"  Total Bookings: {len(bookings)}")
