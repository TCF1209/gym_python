"""
accountant.py -- Accountant role handlers.

Exposes handle_choice(choice, username). This module owns:

  1. Record Membership Payment  (auto-computes tier fee; extends
                                 expiry_date; reactivates Expired /
                                 Suspended members; auto-generates
                                 the F2 receipt)
  2. Record Penalty Payment     (pick from Pending Penalty list;
                                 flip Pending -> Paid; auto-generates
                                 receipt)
  3. Generate Receipt [F2]      (explicit re-print by payment_id;
                                 reads existing receipt file if one
                                 is already on disk, otherwise creates
                                 a fresh one)
  4. View Payment Records
  5. Income Report              (last 6 months Paid Membership +
                                 Paid Penalty, with totals row)
  6. Track Unpaid Memberships   (3 sections: Expired/Suspended,
                                 Near-expiry without recent payment,
                                 Pending Membership payments)

Business rules specific to this module:
  * Record Membership Payment rule:
        new_expiry = max(today, current_expiry) + 30 days
    If the member was Expired or Suspended, flip to Active.
  * Receipt filename: receipts/receipt_{RCP_ID}_{payment_id}.txt
    The RCP_ID is the human-facing receipt number (RCP{YYYYMMDD}{###});
    encoding the payment_id in the filename lets the F2 re-print find
    the existing file without needing to extend the payment schema.
  * Receipts only generate for status=Paid payments.
"""

import os.path
from datetime import datetime, timedelta

import utils


# ============================================================
# ENTRY POINT
# ============================================================

def handle_choice(choice, username):
    """Dispatch one Accountant menu choice. Caller handles Logout."""
    if choice == "1":
        record_membership_payment(username)
    elif choice == "2":
        record_penalty_payment(username)
    elif choice == "3":
        generate_receipt_menu(username)
    elif choice == "4":
        view_payment_records()
    elif choice == "5":
        income_report()
    elif choice == "6":
        track_unpaid_memberships()


# ============================================================
# RECEIPT RENDERING / I/O
# ============================================================

_RECEIPT_WIDTH = 58            # number of ═ between ╔ and ╗ on the banner rows
_RECEIPT_DESC_COL = 44         # description column width in the line-item row
_RECEIPT_AMOUNT_COL = 12       # amount column width; DESC + AMOUNT = 56 = WIDTH - 2


def _describe_payment(payment, member):
    """
    Pick the human-facing receipt description line. Branches on type, and
    for penalties on amount so the RM10 / RM20 cases render the right label.
    """
    if payment["payment_type"] == "Membership":
        return f"Monthly Fee - {member['tier']} Tier"
    if payment["amount"] == utils.NO_SHOW_PENALTY_RM:
        return f"No-Show Penalty - {payment['reference_id']}"
    # Every other Penalty amount treats as a late-cancel (RM10 in the default
    # configuration). reference_id still points at the originating booking.
    return f"Late Cancellation Penalty - {payment['reference_id']}"


def _build_receipt_body(payment, member, rcp_id):
    """Build the full receipt string (trailing newline included)."""
    description = _describe_payment(payment, member)
    timestamp = datetime.now().strftime(utils.DATETIME_FORMAT)
    amount_str = utils.format_amount(payment["amount"])

    # Centre the title inside the banner.
    title = "FitZone Gym Receipt"
    pad = _RECEIPT_WIDTH - len(title)
    left = pad // 2
    right = pad - left

    lines = []
    lines.append(f"╔{'═' * _RECEIPT_WIDTH}╗")
    lines.append(f"║{' ' * left}{title}{' ' * right}║")
    lines.append(f"╠{'═' * _RECEIPT_WIDTH}╣")
    lines.append(f"  Receipt No: {rcp_id}")
    lines.append(f"  Date:       {timestamp}")
    lines.append(f"  Member:     {member['id']} - {member['name']}")
    lines.append(f"  Tier:       {member['tier']}")
    lines.append(f"  {'─' * (_RECEIPT_WIDTH - 2)}")
    lines.append(
        f"  {'Description':<{_RECEIPT_DESC_COL}}"
        f"{'Amount (RM)':>{_RECEIPT_AMOUNT_COL}}"
    )
    lines.append(
        f"  {description:<{_RECEIPT_DESC_COL}}"
        f"{amount_str:>{_RECEIPT_AMOUNT_COL}}"
    )
    lines.append(f"  {'─' * (_RECEIPT_WIDTH - 2)}")
    total_str = f"RM {amount_str}"
    lines.append(
        f"  {'TOTAL':<{_RECEIPT_DESC_COL}}"
        f"{total_str:>{_RECEIPT_AMOUNT_COL}}"
    )
    method_display = payment["method"] if payment["method"] else "—"
    lines.append(f"  Payment Method: {method_display}")
    lines.append(f"  Status:         {payment['status']}")
    lines.append(f"╚{'═' * _RECEIPT_WIDTH}╝")
    # Simple centred thank-you tag (not inside the box).
    thankyou = "Thank you for choosing FitZone!"
    ty_pad = (_RECEIPT_WIDTH + 2 - len(thankyou)) // 2
    lines.append(f"{' ' * ty_pad}{thankyou}")

    return "\n".join(lines) + "\n"


def _find_existing_receipt_for_payment(payment_id):
    """
    Return the full path to an existing receipt file for this payment, or
    None if nothing on disk matches. Relies on the filename ending with
    '_{payment_id}.txt'.
    """
    if not os.path.exists(utils.RECEIPTS_DIR):
        return None
    suffix = f"_{payment_id}.txt"
    try:
        for filename in os.listdir(utils.RECEIPTS_DIR):
            if filename.startswith("receipt_") and filename.endswith(suffix):
                return os.path.join(utils.RECEIPTS_DIR, filename)
    except Exception as e:
        print(f"⚠️  Error scanning receipts directory: {e}")
    return None


def _write_receipt_file(payment, member):
    """
    Create a fresh receipt file in receipts/. Returns (path, rcp_id) on
    success, or (None, None) on write failure.

    Every successful write logs GENERATE_RECEIPT so the audit trail covers
    both the auto-generated path (from Record Membership/Penalty Payment)
    and the explicit F2 re-print path.
    """
    utils.ensure_receipts_dir()
    existing_ids = utils.list_existing_receipt_ids()
    rcp_id = utils.generate_receipt_id(existing_ids)
    body = _build_receipt_body(payment, member, rcp_id)
    filename = f"receipt_{rcp_id}_{payment['id']}.txt"
    path = os.path.join(utils.RECEIPTS_DIR, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
    except Exception as e:
        print(f"⚠️  Error writing receipt: {e}")
        return None, None
    utils.log_audit(
        "Accountant", "GENERATE_RECEIPT",
        f"{rcp_id} for {payment['id']}",
    )
    return path, rcp_id


def _display_file(path):
    """Read a text file and print its contents verbatim."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            print(f.read())
    except Exception as e:
        print(f"⚠️  Error reading {path}: {e}")


def _auto_generate_receipt(payment, member):
    """
    Called immediately after a payment is flipped / added as Paid.
    Writes the receipt file, displays it inline, and prints its path.
    """
    path, rcp_id = _write_receipt_file(payment, member)
    if path is None:
        print("⚠️  Receipt file could not be written.")
        return
    _display_file(path)
    print(f"📄 Receipt saved: {path}")


# ============================================================
# 1. RECORD MEMBERSHIP PAYMENT
# ============================================================

def record_membership_payment(username):
    """
    Record a monthly membership fee. Auto-computes the tier fee, extends
    the member's expiry_date, reactivates a suspended/expired member, and
    auto-generates an F2 receipt.
    """
    print("\n── Record Membership Payment ──")
    member_id = utils.get_non_empty_string("  Member ID: ")

    members = utils.read_members()
    member = utils.find_member_by_id(members, member_id)
    if member is None:
        print(f"✗ Member {member_id} not found.")
        utils.pause()
        return

    fee = utils.get_tier_fee(member["tier"])
    method = utils.get_valid_menu_choice(
        "  Payment method [Cash/Card]: ", utils.VALID_PAYMENT_METHODS,
    )

    today = datetime.now().date()
    today_str = today.strftime(utils.DATE_FORMAT)

    # -- Extend expiry: new_expiry = max(today, current_expiry) + 30 days --
    try:
        current_expiry = datetime.strptime(member["expiry_date"], utils.DATE_FORMAT).date()
    except ValueError:
        # Defensive: if the stored date is malformed, treat as "today".
        current_expiry = today
    base = today
    if current_expiry > base:
        base = current_expiry
    new_expiry = base + timedelta(days=30)
    new_expiry_str = new_expiry.strftime(utils.DATE_FORMAT)

    old_expiry_str = member["expiry_date"]
    old_status = member["status"]
    member["expiry_date"] = new_expiry_str
    if member["status"] in ("Expired", "Suspended"):
        member["status"] = "Active"
    utils.write_members(members)

    # -- Persist the payment --
    payments = utils.read_payments()
    new_payment = {
        "id": utils.generate_payment_id(payments),
        "member_id": member_id,
        "amount": fee,
        "payment_type": "Membership",
        "method": method,
        "payment_date": today_str,
        "status": "Paid",
        "reference_id": "",
    }
    payments.append(new_payment)
    utils.write_payments(payments)

    utils.log_audit(
        "Accountant", "RECORD_PAYMENT",
        f"{new_payment['id']} {member_id} {utils.format_currency(fee)} Membership {method}",
    )
    utils.log_audit(
        "Accountant", "RENEW_MEMBERSHIP",
        f"{member_id} expiry {old_expiry_str} -> {new_expiry_str}",
    )
    if old_status != member["status"]:
        utils.log_audit(
            "Accountant", "REACTIVATE_MEMBER",
            f"{member_id} status {old_status} -> Active",
        )

    print(f"\n✓ Recorded payment {new_payment['id']} for {member_id} {member['name']}.")
    print(f"  Fee:         {utils.format_currency(fee)} ({member['tier']})")
    print(f"  Method:      {method}")
    print(f"  Expiry:      {old_expiry_str} → {new_expiry_str}")
    if old_status != member["status"]:
        print(f"  Status:      {old_status} → {member['status']}")
    print()

    _auto_generate_receipt(new_payment, member)
    utils.pause()


# ============================================================
# 2. RECORD PENALTY PAYMENT
# ============================================================

def _penalty_type_label(payment):
    """Short label for the penalty list: 'No-Show' vs 'Late cancel'."""
    if payment["amount"] == utils.NO_SHOW_PENALTY_RM:
        return "No-Show"
    return "Late cancel"


def record_penalty_payment(username):
    """Show Pending Penalty list; let the Accountant pick one to settle."""
    print("\n── Record Penalty Payment ──")

    payments = utils.read_payments()
    members = utils.read_members()

    # Filter Pending Penalty rows.
    pending = []
    for p in payments:
        if p["payment_type"] == "Penalty" and p["status"] == "Pending":
            pending.append(p)

    if not pending:
        print("\nℹ️  No Pending penalty payments on file.")
        utils.pause()
        return

    # Display as a numbered list.
    utils.print_section_header("💳", f"PENDING PENALTY PAYMENTS ({len(pending)})")
    headers = ["#",  "Payment",  "Member",  "Amount",  "Type",         "Booking"]
    widths =  [3,   7,          7,         10,         12,             14]
    rows = []
    for i in range(len(pending)):
        p = pending[i]
        member = utils.find_member_by_id(members, p["member_id"])
        member_name = member["name"] if member is not None else "?"
        rows.append([
            f"{i + 1}",
            p["id"],
            f"{p['member_id']}",
            utils.format_currency(p["amount"]),
            _penalty_type_label(p),
            p["reference_id"] if p["reference_id"] else "—",
        ])
    utils.print_table(headers, widths, rows)
    # Also show member names (too long to fit in the table neatly).
    print()
    for i in range(len(pending)):
        p = pending[i]
        member = utils.find_member_by_id(members, p["member_id"])
        member_name = member["name"] if member is not None else "?"
        print(f"    {i + 1}. {p['id']}  {p['member_id']} {member_name}")

    # Ask which one to settle.
    pick = utils.get_valid_int(
        f"\n  Enter # to record (1-{len(pending)}, or 0 to cancel): ",
        0, len(pending),
    )
    if pick == 0:
        print("✗ Aborted.")
        utils.pause()
        return

    target = pending[pick - 1]
    member = utils.find_member_by_id(members, target["member_id"])
    if member is None:
        print(f"✗ Member {target['member_id']} not found -- cannot record.")
        utils.pause()
        return

    method = utils.get_valid_menu_choice(
        "  Payment method [Cash/Card]: ", utils.VALID_PAYMENT_METHODS,
    )

    # Flip to Paid on the live payments list (target is a reference into it).
    old_method = target["method"]
    target["method"] = method
    target["status"] = "Paid"
    # Payment_date left as whatever was set when the Pending row was created.
    # (It reflects when the penalty was accrued, not when it was settled.)
    utils.write_payments(payments)

    utils.log_audit(
        "Accountant", "RECORD_PAYMENT",
        f"{target['id']} {target['member_id']} "
        f"{utils.format_currency(target['amount'])} Penalty {method} "
        f"(ref {target['reference_id']})",
    )

    print(f"\n✓ {target['id']} marked Paid.")
    print(f"  Member: {target['member_id']} {member['name']}")
    print(f"  Amount: {utils.format_currency(target['amount'])}  ({_penalty_type_label(target)})")
    print(f"  Ref:    {target['reference_id']}")
    print()

    _auto_generate_receipt(target, member)
    utils.pause()


# ============================================================
# 3. GENERATE RECEIPT [F2] -- explicit re-print
# ============================================================

def generate_receipt_menu(username):
    """
    Accountant picks a payment by ID. If an existing receipt file is on
    disk, display it. Otherwise generate a fresh receipt.
    """
    print("\n── Generate Receipt ──")
    payment_id = utils.get_non_empty_string("  Payment ID: ")

    payments = utils.read_payments()
    payment = None
    for p in payments:
        if p["id"] == payment_id:
            payment = p
            break
    if payment is None:
        print(f"✗ Payment {payment_id} not found.")
        utils.pause()
        return

    if payment["status"] != "Paid":
        print(f"✗ {payment_id} is {payment['status']}; receipts only issue for Paid payments.")
        print("  Record the payment first (Menu 1 or 2).")
        utils.pause()
        return

    members = utils.read_members()
    member = utils.find_member_by_id(members, payment["member_id"])
    if member is None:
        print(f"✗ Member {payment['member_id']} not found -- cannot build receipt header.")
        utils.pause()
        return

    existing_path = _find_existing_receipt_for_payment(payment_id)
    if existing_path is not None:
        print(f"\nℹ️  Existing receipt found: {existing_path}")
        print()
        _display_file(existing_path)
    else:
        # No file on disk (e.g., seeded Paid payment predates receipts/) --
        # generate a fresh one. _write_receipt_file handles the audit entry.
        path, _rcp_id = _write_receipt_file(payment, member)
        if path is None:
            utils.pause()
            return
        print()
        _display_file(path)
        print(f"📄 Receipt saved: {path}")
    utils.pause()


# ============================================================
# 4. VIEW PAYMENT RECORDS
# ============================================================

def view_payment_records():
    """Full payments table -- same shape as admin's view for consistency."""
    payments = utils.read_payments()
    if not payments:
        print("\nℹ️  No payments on file.")
        utils.pause()
        return
    utils.print_section_header("💰", f"ALL PAYMENTS ({len(payments)})")
    headers = ["ID",    "Member", "Amount",     "Type",       "Method", "Date",       "Status",  "Reference"]
    widths =  [6,       7,        10,           12,           7,        12,           8,         16]
    rows = []
    for p in payments:
        method = p["method"] if p["method"] else "—"
        ref = p["reference_id"] if p["reference_id"] else "—"
        rows.append([
            p["id"], p["member_id"], utils.format_currency(p["amount"]),
            p["payment_type"], method,
            p["payment_date"], p["status"], ref,
        ])
    utils.print_table(headers, widths, rows)
    utils.pause()


# ============================================================
# 5. INCOME REPORT
# ============================================================

def _last_six_months_ending(today):
    """
    Return the last 6 calendar months (inclusive of today's month) as a
    list of (year, month) tuples in chronological order.
    """
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
    return months


def income_report():
    """Monthly Paid-payments breakdown (Membership / Penalty / Total) + totals row."""
    payments = utils.read_payments()
    today = datetime.now().date()
    months = _last_six_months_ending(today)

    # Aggregation bucket per month.
    buckets = {}
    for (y, m) in months:
        buckets[(y, m)] = {"membership": 0.0, "penalty": 0.0}

    for p in payments:
        if p["status"] != "Paid":
            continue
        try:
            pdate = datetime.strptime(p["payment_date"], utils.DATE_FORMAT).date()
        except ValueError:
            continue
        key = (pdate.year, pdate.month)
        if key not in buckets:
            continue
        if p["payment_type"] == "Membership":
            buckets[key]["membership"] += p["amount"]
        elif p["payment_type"] == "Penalty":
            buckets[key]["penalty"] += p["amount"]

    utils.print_section_header("💰", "INCOME REPORT (Last 6 Months, Paid only)")
    headers = ["Month",   "Membership",   "Penalty",      "Total"]
    widths =  [9,         14,             14,             14]

    total_mem = 0.0
    total_pen = 0.0
    rows = []
    for (y, m) in months:
        mem = buckets[(y, m)]["membership"]
        pen = buckets[(y, m)]["penalty"]
        total_mem += mem
        total_pen += pen
        rows.append([
            f"{y:04d}-{m:02d}",
            utils.format_currency(mem),
            utils.format_currency(pen),
            utils.format_currency(mem + pen),
        ])

    # Print monthly rows, then a visual separator, then the totals row.
    utils.print_table(headers, widths, rows)
    separator = []
    for w in widths:
        separator.append("=" * w)
    print(utils.format_table_row(widths, separator))
    total_row = [
        "TOTAL",
        utils.format_currency(total_mem),
        utils.format_currency(total_pen),
        utils.format_currency(total_mem + total_pen),
    ]
    print(utils.format_table_row(widths, total_row))

    utils.pause()


# ============================================================
# 6. TRACK UNPAID MEMBERSHIPS
# ============================================================

def _has_recent_paid_membership(payments, member_id, today, days=30):
    """True if the member has a Paid Membership payment in the last 'days' days."""
    for p in payments:
        if p["member_id"] != member_id:
            continue
        if p["payment_type"] != "Membership":
            continue
        if p["status"] != "Paid":
            continue
        try:
            pdate = datetime.strptime(p["payment_date"], utils.DATE_FORMAT).date()
        except ValueError:
            continue
        if (today - pdate).days <= days:
            return True
    return False


def track_unpaid_memberships():
    """Three-section view surfacing members who need collections attention."""
    members = utils.read_members()
    payments = utils.read_payments()
    today = datetime.now().date()

    # --- Section 1: Expired / Suspended members ---
    expired_suspended = []
    for m in members:
        if m["status"] in ("Expired", "Suspended"):
            expired_suspended.append(m)

    utils.print_section_header(
        "⛔", f"EXPIRED / SUSPENDED ({len(expired_suspended)})",
    )
    if expired_suspended:
        headers = ["ID",    "Name",   "Tier",   "Status",    "Expiry",     "Phone"]
        widths =  [6,       18,       8,        10,          12,           12]
        rows = []
        for m in expired_suspended:
            rows.append([
                m["id"], m["name"], m["tier"], m["status"],
                m["expiry_date"], m["phone"],
            ])
        utils.print_table(headers, widths, rows)
    else:
        print("  (none)")

    # --- Section 2: Near-expiry Active members without a recent Paid payment ---
    near_expiry_at_risk = []
    for m in members:
        if m["status"] != "Active":
            continue
        try:
            exp = datetime.strptime(m["expiry_date"], utils.DATE_FORMAT).date()
        except ValueError:
            continue
        days_left = (exp - today).days
        if days_left < 0 or days_left > utils.NEAR_EXPIRY_WARN_DAYS:
            continue
        if _has_recent_paid_membership(payments, m["id"], today):
            continue
        near_expiry_at_risk.append((m, days_left))

    utils.print_section_header(
        "⚠️", f"NEAR-EXPIRY WITHOUT RECENT PAYMENT ({len(near_expiry_at_risk)})",
    )
    if near_expiry_at_risk:
        headers = ["ID",    "Name",   "Tier",   "Expiry",     "Days Left", "Phone"]
        widths =  [6,       18,       8,        12,           10,          12]
        rows = []
        for (m, days_left) in near_expiry_at_risk:
            rows.append([
                m["id"], m["name"], m["tier"],
                m["expiry_date"], days_left, m["phone"],
            ])
        utils.print_table(headers, widths, rows)
    else:
        print("  (none)")

    # --- Section 3: Pending Membership payments ---
    pending_membership = []
    for p in payments:
        if p["payment_type"] == "Membership" and p["status"] == "Pending":
            pending_membership.append(p)

    utils.print_section_header(
        "📋", f"PENDING MEMBERSHIP PAYMENTS ({len(pending_membership)})",
    )
    if pending_membership:
        headers = ["Payment", "Member", "Amount",     "Date",       "Method"]
        widths =  [8,        7,        12,           12,           7]
        rows = []
        for p in pending_membership:
            method = p["method"] if p["method"] else "—"
            rows.append([
                p["id"], p["member_id"], utils.format_currency(p["amount"]),
                p["payment_date"], method,
            ])
        utils.print_table(headers, widths, rows)
    else:
        print("  (none)")

    utils.pause()
