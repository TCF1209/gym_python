"""
utils.py -- Shared utilities for the FitZone Gym Management System.

This module is the single source of truth for:
  - Constants (pricing, quotas, penalties, file paths, UI settings, validation sets)
  - File I/O for every data entity (pipe-delimited text files)
  - Audit logging (Feature F7)
  - Input validators (every user prompt should use one)
  - ID generators (member, class, trainer, booking, payment, receipt)
  - Terminal UI helpers (ASCII bar chart for F6 and F9, menu headers, pauses)
  - Business helpers (cancellation penalty, tier quota, membership suspension,
    class-booking recount for keeping CURRENT_BOOKED in sync)
  - Simple authentication against credentials.txt

Design rules (do not break):
  - Pure procedural Python. No classes, no inheritance, no self.
  - Only the Python standard library. No pip-installed modules.
  - All persistence goes through text files using the pipe "|" delimiter.
  - Every entity is represented as a plain dictionary.
"""

import os
import os.path
import sys
from datetime import datetime, timedelta


# ============================================================
# CONSTANTS
# ============================================================

# --- Pricing (Ringgit Malaysia, monthly) ---
BASIC_MONTHLY_FEE = 80.00
PREMIUM_MONTHLY_FEE = 150.00
VIP_MONTHLY_FEE = 250.00

# --- Class quotas per membership tier (per calendar month) ---
BASIC_QUOTA = 5
PREMIUM_QUOTA = 15
VIP_QUOTA = 9999  # sentinel for "unlimited" -- UI must display "Unlimited", never the number

# --- Cancellation / no-show penalties ---
LATE_CANCEL_PENALTY_RM = 10.00
NO_SHOW_PENALTY_RM = 20.00
CANCELLATION_WINDOW_HOURS = 24

# --- Membership suspension grace period ---
# A member is auto-suspended when: expiry_date + SUSPENSION_GRACE_DAYS < today AND status == "Active"
SUSPENSION_GRACE_DAYS = 7

# Days-ahead threshold for "near expiry" warnings (System Report, Booking
# Officer alerts). Independent of SUSPENSION_GRACE_DAYS so the two concepts
# can drift apart later if needed.
NEAR_EXPIRY_WARN_DAYS = 7

# --- Class capacities (fixed per class type) ---
CLASS_CAPACITY = {
    "Yoga": 15,
    "HIIT": 12,
    "Boxing": 8,
    "Zumba": 15,
    "Spinning": 12,
}

# --- Valid value sets (used by validators and seed data) ---
VALID_CLASS_NAMES = ["Yoga", "HIIT", "Boxing", "Zumba", "Spinning"]
VALID_TIERS = ["Basic", "Premium", "VIP"]
VALID_MEMBER_STATUSES = ["Active", "Expired", "Suspended"]
VALID_CLASS_STATUSES = ["Scheduled", "Completed", "Cancelled"]
VALID_BOOKING_STATUSES = ["Confirmed", "Cancelled", "Completed", "No-Show"]
VALID_PAYMENT_TYPES = ["Membership", "Penalty"]
VALID_PAYMENT_METHODS = ["Cash", "Card"]
VALID_PAYMENT_STATUSES = ["Paid", "Pending"]
VALID_GENDERS = ["M", "F"]
VALID_ROLES = ["Administrator", "BookingOfficer", "Accountant"]
# Audit log additionally accepts "System" so automated tasks don't masquerade
# as a logged-in user when recording AUTO_SUSPEND / AUTO_NO_SHOW etc.
VALID_AUDIT_ROLES = ["Administrator", "BookingOfficer", "Accountant", "System"]

# --- Directory and file paths (cross-platform via os.path.join) ---
DATA_DIR = "data"
RECEIPTS_DIR = "receipts"
BACKUP_DIR = "backup"

MEMBERS_FILE = os.path.join(DATA_DIR, "members.txt")
CLASSES_FILE = os.path.join(DATA_DIR, "classes.txt")
TRAINERS_FILE = os.path.join(DATA_DIR, "trainers.txt")
BOOKINGS_FILE = os.path.join(DATA_DIR, "bookings.txt")
PAYMENTS_FILE = os.path.join(DATA_DIR, "payments.txt")
CREDENTIALS_FILE = os.path.join(DATA_DIR, "credentials.txt")
AUDIT_LOG_FILE = os.path.join(DATA_DIR, "audit.log")

# --- UI formatting ---
MENU_WIDTH = 44
BAR_CHAR = "█"          # full-block; change to "#" if a console can't render it
BAR_WIDTH_DEFAULT = 30
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


# ============================================================
# PLATFORM / DIRECTORY SETUP
# ============================================================

def enable_utf8_on_windows():
    """
    Force the Windows console to UTF-8 so box-drawing characters and the
    ASCII bar character render correctly. Safe no-op on macOS / Linux / WSL.
    """
    if sys.platform.startswith("win"):
        # chcp 65001 switches cmd.exe's active code page to UTF-8.
        # '> nul' hides the 'Active code page: 65001' banner.
        os.system("chcp 65001 > nul")


def ensure_dir(path):
    """Create a directory (and any parents) if it does not already exist."""
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except Exception as e:
            print(f"⚠️  Error creating directory '{path}': {e}")


def ensure_data_dir():
    """Create the data/ folder if it does not exist."""
    ensure_dir(DATA_DIR)


def ensure_receipts_dir():
    """Create the receipts/ folder if it does not exist."""
    ensure_dir(RECEIPTS_DIR)


# ============================================================
# FILE I/O -- MEMBERS
# ============================================================

def read_members():
    """Read members.txt and return a list of member dicts."""
    members = []
    try:
        with open(MEMBERS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 10:
                    # Skip malformed lines rather than crash on bad data.
                    continue
                member = {
                    "id": parts[0],
                    "name": parts[1],
                    "age": int(parts[2]),
                    "gender": parts[3],
                    "phone": parts[4],
                    "email": parts[5],
                    "tier": parts[6],
                    "join_date": parts[7],
                    "expiry_date": parts[8],
                    "status": parts[9],
                }
                members.append(member)
    except FileNotFoundError:
        # First run: file will be created when the first member is written.
        pass
    except Exception as e:
        print(f"⚠️  Error reading members: {e}")
    return members


def write_members(members):
    """Overwrite members.txt with the given list of member dicts."""
    try:
        ensure_data_dir()
        with open(MEMBERS_FILE, "w", encoding="utf-8") as f:
            for m in members:
                line = "|".join([
                    m["id"], m["name"], str(m["age"]), m["gender"],
                    m["phone"], m["email"], m["tier"],
                    m["join_date"], m["expiry_date"], m["status"],
                ])
                f.write(f"{line}\n")
    except Exception as e:
        print(f"⚠️  Error writing members: {e}")


# ============================================================
# FILE I/O -- CLASSES
# ============================================================

def read_classes():
    """Read classes.txt and return a list of class dicts."""
    classes = []
    try:
        with open(CLASSES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 9:
                    continue
                cls = {
                    "id": parts[0],
                    "name": parts[1],
                    "trainer_id": parts[2],
                    "schedule_date": parts[3],
                    "start_time": parts[4],
                    "duration_min": int(parts[5]),
                    "capacity": int(parts[6]),
                    "current_booked": int(parts[7]),
                    "status": parts[8],
                }
                classes.append(cls)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  Error reading classes: {e}")
    return classes


def write_classes(classes):
    """Overwrite classes.txt with the given list of class dicts."""
    try:
        ensure_data_dir()
        with open(CLASSES_FILE, "w", encoding="utf-8") as f:
            for c in classes:
                line = "|".join([
                    c["id"], c["name"], c["trainer_id"],
                    c["schedule_date"], c["start_time"],
                    str(c["duration_min"]), str(c["capacity"]),
                    str(c["current_booked"]), c["status"],
                ])
                f.write(f"{line}\n")
    except Exception as e:
        print(f"⚠️  Error writing classes: {e}")


# ============================================================
# FILE I/O -- TRAINERS
# ============================================================

def read_trainers():
    """Read trainers.txt and return a list of trainer dicts."""
    trainers = []
    try:
        with open(TRAINERS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 7:
                    continue
                trainer = {
                    "id": parts[0],
                    "name": parts[1],
                    "specialization": parts[2],
                    "phone": parts[3],
                    "email": parts[4],
                    "experience_years": int(parts[5]),
                    "status": parts[6],
                }
                trainers.append(trainer)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  Error reading trainers: {e}")
    return trainers


def write_trainers(trainers):
    """Overwrite trainers.txt with the given list of trainer dicts."""
    try:
        ensure_data_dir()
        with open(TRAINERS_FILE, "w", encoding="utf-8") as f:
            for t in trainers:
                line = "|".join([
                    t["id"], t["name"], t["specialization"],
                    t["phone"], t["email"],
                    str(t["experience_years"]), t["status"],
                ])
                f.write(f"{line}\n")
    except Exception as e:
        print(f"⚠️  Error writing trainers: {e}")


# ============================================================
# FILE I/O -- BOOKINGS
# ============================================================

def read_bookings():
    """Read bookings.txt and return a list of booking dicts."""
    bookings = []
    try:
        with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 7:
                    continue
                booking = {
                    "id": parts[0],
                    "member_id": parts[1],
                    "class_id": parts[2],
                    "booking_date": parts[3],
                    "class_date": parts[4],
                    "status": parts[5],
                    "penalty_rm": float(parts[6]),
                }
                bookings.append(booking)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  Error reading bookings: {e}")
    return bookings


def write_bookings(bookings):
    """Overwrite bookings.txt with the given list of booking dicts."""
    try:
        ensure_data_dir()
        with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
            for b in bookings:
                line = "|".join([
                    b["id"], b["member_id"], b["class_id"],
                    b["booking_date"], b["class_date"],
                    b["status"], format_amount(b["penalty_rm"]),
                ])
                f.write(f"{line}\n")
    except Exception as e:
        print(f"⚠️  Error writing bookings: {e}")


# ============================================================
# FILE I/O -- PAYMENTS
# ============================================================

def read_payments():
    """
    Read payments.txt and return a list of payment dicts.

    Schema (8 fields, pipe-delimited):
      PAYMENT_ID | MEMBER_ID | AMOUNT | PAYMENT_TYPE | METHOD |
      PAYMENT_DATE | STATUS | REFERENCE_ID

    REFERENCE_ID is the booking_id for Penalty payments (so receipts can
    say "Late Cancellation Penalty - BK..."), and an empty string for
    Membership payments. This field is an extension to the brief's
    original 7-field schema, chosen over sentinel conventions so the
    payment -> booking link is explicit.
    """
    payments = []
    try:
        with open(PAYMENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 8:
                    continue
                payment = {
                    "id": parts[0],
                    "member_id": parts[1],
                    "amount": float(parts[2]),
                    "payment_type": parts[3],
                    "method": parts[4],
                    "payment_date": parts[5],
                    "status": parts[6],
                    "reference_id": parts[7],
                }
                payments.append(payment)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  Error reading payments: {e}")
    return payments


def write_payments(payments):
    """Overwrite payments.txt with the given list of payment dicts (8 fields)."""
    try:
        ensure_data_dir()
        with open(PAYMENTS_FILE, "w", encoding="utf-8") as f:
            for p in payments:
                line = "|".join([
                    p["id"], p["member_id"], format_amount(p["amount"]),
                    p["payment_type"], p["method"],
                    p["payment_date"], p["status"], p["reference_id"],
                ])
                f.write(f"{line}\n")
    except Exception as e:
        print(f"⚠️  Error writing payments: {e}")


# ============================================================
# FILE I/O -- CREDENTIALS
# ============================================================
# NOTE: Passwords are stored in plaintext. Documented as a deliberate
# limitation of this student project; hashing is out of scope.

def read_credentials():
    """Read credentials.txt and return a list of credential dicts."""
    creds = []
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 3:
                    continue
                cred = {
                    "username": parts[0],
                    "password": parts[1],
                    "role": parts[2],
                }
                creds.append(cred)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  Error reading credentials: {e}")
    return creds


def write_credentials(creds):
    """Overwrite credentials.txt with the given list of credential dicts."""
    try:
        ensure_data_dir()
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            for c in creds:
                line = "|".join([c["username"], c["password"], c["role"]])
                f.write(f"{line}\n")
    except Exception as e:
        print(f"⚠️  Error writing credentials: {e}")


# ============================================================
# AUDIT LOG (Feature F7)
# ============================================================

def log_audit(role, action, detail):
    """
    Append a single audit entry to data/audit.log.

    Format: TIMESTAMP|ROLE|ACTION|DETAIL

    Args:
        role:   "Administrator" / "BookingOfficer" / "Accountant" / "System"
        action: short uppercase verb (e.g. ADD_CLASS, CANCEL_BOOKING)
        detail: free-text description with the relevant IDs and values
    """
    try:
        ensure_data_dir()
        timestamp = datetime.now().strftime(DATETIME_FORMAT)
        line = "|".join([timestamp, role, action, detail])
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{line}\n")
    except Exception as e:
        # Never let an audit-log failure break the user's action.
        print(f"⚠️  Error writing audit log: {e}")


def read_audit_log():
    """Return audit-log entries as a list of dicts (oldest first)."""
    entries = []
    try:
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) != 4:
                    continue
                entry = {
                    "timestamp": parts[0],
                    "role": parts[1],
                    "action": parts[2],
                    "detail": parts[3],
                }
                entries.append(entry)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"⚠️  Error reading audit log: {e}")
    return entries


# ============================================================
# INPUT VALIDATORS
# ============================================================
# Every user-facing input() should use one of these so we never accept bad data.

def get_non_empty_string(prompt):
    """Prompt until the user enters a non-empty string. Returns the stripped value."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("✗ Input cannot be empty. Please try again.")


def get_valid_int(prompt, min_val, max_val):
    """Prompt until the user enters an integer within [min_val, max_val]."""
    while True:
        raw = input(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            print("✗ Please enter a whole number.")
            continue
        if value < min_val or value > max_val:
            print(f"✗ Value must be between {min_val} and {max_val}.")
            continue
        return value


def get_valid_float(prompt, min_val, max_val):
    """Prompt until the user enters a number (float) within [min_val, max_val]."""
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
        except ValueError:
            print("✗ Please enter a valid number.")
            continue
        if value < min_val or value > max_val:
            print(f"✗ Value must be between {min_val} and {max_val}.")
            continue
        return value


def get_valid_menu_choice(prompt, valid_options):
    """
    Prompt until the user enters one of valid_options (list of strings).
    Input is compared case-insensitively and returned in the exact form
    from valid_options so callers can compare directly.
    """
    while True:
        raw = input(prompt).strip()
        for option in valid_options:
            if raw.lower() == option.lower():
                return option
        joined = ", ".join(valid_options)
        print(f"✗ Invalid choice. Options: {joined}")


def get_valid_date(prompt, allow_past=True):
    """
    Prompt until the user enters a date in YYYY-MM-DD format.
    Returns a datetime (at 00:00). If allow_past is False, rejects dates before today.
    """
    while True:
        raw = input(prompt).strip()
        try:
            value = datetime.strptime(raw, DATE_FORMAT)
        except ValueError:
            print("✗ Invalid date. Use YYYY-MM-DD (e.g. 2026-05-01).")
            continue
        if not allow_past:
            today_start = datetime.combine(datetime.now().date(), datetime.min.time())
            if value < today_start:
                print("✗ Date cannot be in the past.")
                continue
        return value


def get_valid_time(prompt):
    """Prompt until the user enters a time in HH:MM (24-hour) format. Returns the string."""
    while True:
        raw = input(prompt).strip()
        try:
            datetime.strptime(raw, TIME_FORMAT)
        except ValueError:
            print("✗ Invalid time. Use HH:MM in 24-hour format (e.g. 18:30).")
            continue
        return raw


def get_valid_phone(prompt):
    """
    Prompt for a Malaysian mobile number. Accepted inputs:
        0123456789, 012-3456789, 012 3456789, 01X-XXXXXXX (10-11 digits starting with 01).
    The returned value is normalised to digits only (e.g. "0123456789").
    """
    while True:
        raw = input(prompt).strip()
        digits = ""
        for ch in raw:
            if ch.isdigit():
                digits += ch
        if len(digits) < 10 or len(digits) > 11:
            print("✗ Phone must have 10 or 11 digits (e.g. 0123456789).")
            continue
        if not digits.startswith("01"):
            print("✗ Malaysian mobile numbers start with 01.")
            continue
        return digits


def get_valid_email(prompt):
    """
    Prompt for an email address. Basic check only: exactly one '@', at least one
    '.' after the '@', no spaces. Sufficient for a student project per the brief.
    """
    while True:
        raw = input(prompt).strip()
        if " " in raw:
            print("✗ Email cannot contain spaces.")
            continue
        if raw.count("@") != 1:
            print("✗ Email must contain exactly one '@'.")
            continue
        local, _, domain = raw.partition("@")
        if not local or "." not in domain:
            print("✗ Email domain must contain a '.' (e.g. name@example.com).")
            continue
        return raw


def get_yes_no(prompt):
    """Prompt until the user answers yes or no. Returns True for yes, False for no."""
    while True:
        raw = input(f"{prompt} (y/n): ").strip().lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("✗ Please answer y or n.")


# ============================================================
# ID GENERATORS
# ============================================================
# Each generator looks at existing records, finds the highest counter,
# and returns the next one. For seed data and live use both work the same way.

def _max_numeric_suffix(ids, prefix):
    """
    Internal helper: given a list of ID strings and a prefix (e.g. 'M'),
    return the highest integer suffix found. Returns 0 if none.
    """
    highest = 0
    for record_id in ids:
        if not record_id.startswith(prefix):
            continue
        suffix = record_id[len(prefix):]
        if suffix.isdigit():
            number = int(suffix)
            if number > highest:
                highest = number
    return highest


def generate_member_id(members):
    """Return the next member ID in M### format (M001, M002, ...)."""
    ids = []
    for m in members:
        ids.append(m["id"])
    next_num = _max_numeric_suffix(ids, "M") + 1
    return f"M{next_num:03d}"


def generate_class_id(classes):
    """Return the next class ID in C### format."""
    ids = []
    for c in classes:
        ids.append(c["id"])
    next_num = _max_numeric_suffix(ids, "C") + 1
    return f"C{next_num:03d}"


def generate_trainer_id(trainers):
    """Return the next trainer ID in T### format."""
    ids = []
    for t in trainers:
        ids.append(t["id"])
    next_num = _max_numeric_suffix(ids, "T") + 1
    return f"T{next_num:03d}"


def generate_payment_id(payments):
    """Return the next payment ID in P### format."""
    ids = []
    for p in payments:
        ids.append(p["id"])
    next_num = _max_numeric_suffix(ids, "P") + 1
    return f"P{next_num:03d}"


def generate_booking_id(bookings, today=None):
    """
    Feature F1: generate the next booking ID in BK{YYYYMMDD}{###} format.

    Counter resets on each new calendar day. 'today' can be overridden for
    tests and seed data; in production it defaults to datetime.now().
    """
    if today is None:
        today = datetime.now()
    date_part = today.strftime("%Y%m%d")
    prefix = f"BK{date_part}"
    # Count only bookings whose ID starts with today's prefix.
    highest = 0
    for b in bookings:
        bid = b["id"]
        if bid.startswith(prefix) and len(bid) == len(prefix) + 3:
            suffix = bid[len(prefix):]
            if suffix.isdigit():
                number = int(suffix)
                if number > highest:
                    highest = number
    return f"{prefix}{highest + 1:03d}"


def generate_receipt_id(existing_receipt_ids, today=None):
    """
    Generate the next receipt ID in RCP{YYYYMMDD}{###} format.

    Caller passes the list of previously-issued receipt IDs (usually obtained
    by listing the receipts/ folder). Counter resets each calendar day.
    """
    if today is None:
        today = datetime.now()
    date_part = today.strftime("%Y%m%d")
    prefix = f"RCP{date_part}"
    highest = 0
    for rid in existing_receipt_ids:
        if rid.startswith(prefix) and len(rid) == len(prefix) + 3:
            suffix = rid[len(prefix):]
            if suffix.isdigit():
                number = int(suffix)
                if number > highest:
                    highest = number
    return f"{prefix}{highest + 1:03d}"


def list_existing_receipt_ids():
    """Scan receipts/ and return the list of receipt IDs already on disk."""
    ids = []
    if not os.path.exists(RECEIPTS_DIR):
        return ids
    try:
        for filename in os.listdir(RECEIPTS_DIR):
            # Expected form: receipt_RCP20260420001.txt
            if filename.startswith("receipt_") and filename.endswith(".txt"):
                rid = filename[len("receipt_"):-len(".txt")]
                ids.append(rid)
    except Exception as e:
        print(f"⚠️  Error scanning receipts directory: {e}")
    return ids


# ============================================================
# LOOKUP HELPERS
# ============================================================

def find_member_by_id(members, member_id):
    """Return the member dict with this id, or None if not found."""
    for m in members:
        if m["id"] == member_id:
            return m
    return None


def find_class_by_id(classes, class_id):
    """Return the class dict with this id, or None if not found."""
    for c in classes:
        if c["id"] == class_id:
            return c
    return None


def find_trainer_by_id(trainers, trainer_id):
    """Return the trainer dict with this id, or None if not found."""
    for t in trainers:
        if t["id"] == trainer_id:
            return t
    return None


def find_booking_by_id(bookings, booking_id):
    """Return the booking dict with this id, or None if not found."""
    for b in bookings:
        if b["id"] == booking_id:
            return b
    return None


# ============================================================
# UI HELPERS
# ============================================================

def format_amount(amount):
    """Format a money value to a two-decimal string (e.g. 150.00)."""
    return f"{float(amount):.2f}"


def format_currency(amount):
    """Format a money value as 'RM 150.00' for human-facing output."""
    return f"RM {format_amount(amount)}"


def pause():
    """Pause the CLI until the user presses Enter. Used after every action."""
    input("\nℹ️  Press Enter to continue...")


def print_divider(char="-", width=MENU_WIDTH):
    """Print a simple horizontal divider."""
    print(char * width)


def print_header(title, width=MENU_WIDTH):
    """Print a boxed header like the menus in the brief."""
    print()
    print(f"╔{'═' * width}╗")
    # Pad title to fill the box width (leaving one space each side).
    inner = f" {title}"
    padding = width - len(inner)
    if padding < 0:
        padding = 0
    print(f"║{inner}{' ' * padding}║")
    print(f"╚{'═' * width}╝")


def print_section_header(emoji, title, width=60):
    """Emoji-tagged section header with a horizontal underline. Used in role views and reports."""
    print()
    print(f"{emoji} {title}")
    print("─" * width)


def format_table_row(widths, values):
    """
    Format one table row so each value sits in a fixed-width column.
    Values longer than the column width are truncated with a Unicode
    ellipsis (…) so the overall layout never shifts.
    """
    parts = []
    for i in range(len(widths)):
        w = widths[i]
        s = str(values[i])
        if len(s) > w:
            s = s[:w - 1] + "…"
        parts.append(s.ljust(w))
    return "  ".join(parts)


def print_table(headers, widths, rows):
    """Print a simple header / underline / rows table with consistent column widths."""
    print(format_table_row(widths, headers))
    underline = []
    for w in widths:
        underline.append("-" * w)
    print(format_table_row(widths, underline))
    for row in rows:
        print(format_table_row(widths, row))


def render_ascii_bar(label, value, max_value, bar_width=BAR_WIDTH_DEFAULT, char=BAR_CHAR):
    """
    Render one row of an ASCII bar chart.

    Returns a string such as:   "Yoga         ██████████████ 45"

    Args:
        label:      left-hand label (max 12 chars rendered)
        value:      the numeric value (int or float)
        max_value:  the largest value across the dataset, used to scale bars
        bar_width:  maximum number of characters used for the bar itself
        char:       the bar-fill character (BAR_CHAR by default)
    """
    if max_value is None or max_value <= 0:
        filled = 0
    else:
        # Scale proportionally. int() truncates toward zero, which we want.
        filled = int((float(value) / float(max_value)) * bar_width)
        if filled < 0:
            filled = 0
        if filled > bar_width:
            filled = bar_width
    bar = char * filled
    # {:<12} left-aligns the label in a 12-character column.
    return f"{label:<12} {bar} {value}"


# ============================================================
# BUSINESS HELPERS
# ============================================================

def get_tier_fee(tier):
    """Return the monthly fee (RM) for a membership tier."""
    if tier == "Basic":
        return BASIC_MONTHLY_FEE
    if tier == "Premium":
        return PREMIUM_MONTHLY_FEE
    if tier == "VIP":
        return VIP_MONTHLY_FEE
    # Unknown tier -- default to 0 so reports don't crash on bad data.
    return 0.00


def get_tier_quota(tier):
    """Return the monthly class quota for a tier (VIP_QUOTA is the 'unlimited' sentinel)."""
    if tier == "Basic":
        return BASIC_QUOTA
    if tier == "Premium":
        return PREMIUM_QUOTA
    if tier == "VIP":
        return VIP_QUOTA
    return 0


def format_quota_display(tier):
    """Return a human-friendly quota label; VIP shows 'Unlimited' instead of the sentinel."""
    if tier == "VIP":
        return "Unlimited"
    return str(get_tier_quota(tier))


def calculate_cancellation_penalty(class_date_str, class_start_time_str, now=None):
    """
    Return the penalty (in RM) for cancelling a booking right now.

    Rule:
      - >= 24 hours before class start: RM 0
      - < 24 hours before class start : RM LATE_CANCEL_PENALTY_RM
      - class already started / passed: RM LATE_CANCEL_PENALTY_RM as a
        defensive fallback (booking.py should prevent cancelling past bookings
        in the first place; no-show handling is separate).

    Args:
        class_date_str:       "YYYY-MM-DD"
        class_start_time_str: "HH:MM" (24-hour)
        now:                  datetime for testing; defaults to datetime.now()
    """
    if now is None:
        now = datetime.now()
    try:
        class_dt = datetime.strptime(
            f"{class_date_str} {class_start_time_str}", "%Y-%m-%d %H:%M"
        )
    except ValueError:
        # Bad date/time in the stored booking -- treat conservatively as penalty.
        return LATE_CANCEL_PENALTY_RM

    diff_seconds = (class_dt - now).total_seconds()
    hours_until_class = diff_seconds / 3600.0

    if hours_until_class < CANCELLATION_WINDOW_HOURS:
        return LATE_CANCEL_PENALTY_RM
    return 0.00


def get_quota_used_this_month(bookings, member_id, reference_date=None):
    """
    Count how many quota-consuming bookings a member has for the month of
    reference_date. Per product decision, these statuses consume quota:
        Confirmed, Completed, No-Show
    Cancelled bookings do NOT consume quota.

    Args:
        bookings:        list of all booking dicts
        member_id:       e.g. "M001"
        reference_date:  a date or datetime; defaults to today's date
    """
    if reference_date is None:
        reference_date = datetime.now()
    ref_year = reference_date.year
    ref_month = reference_date.month

    used = 0
    for b in bookings:
        if b["member_id"] != member_id:
            continue
        if b["status"] == "Cancelled":
            continue
        try:
            class_dt = datetime.strptime(b["class_date"], DATE_FORMAT)
        except ValueError:
            continue
        if class_dt.year == ref_year and class_dt.month == ref_month:
            used += 1
    return used


def is_over_quota(member, bookings, reference_date=None):
    """Return True if booking one more class would exceed the member's monthly quota."""
    quota = get_tier_quota(member["tier"])
    used = get_quota_used_this_month(bookings, member["id"], reference_date)
    return used >= quota


def is_double_booked(bookings, member_id, class_id):
    """
    Per product decision #8: a member cannot book the same class slot twice
    (same class_id) while still Confirmed. Returns True if such a booking
    already exists.
    """
    for b in bookings:
        if b["member_id"] == member_id and b["class_id"] == class_id:
            if b["status"] == "Confirmed":
                return True
    return False


def recount_class_bookings(class_id):
    """
    Recompute and persist CURRENT_BOOKED for a single class.

    Defined as: number of bookings for this class whose status is NOT 'Cancelled'.
    This covers both the pre-class period (Confirmed) and the post-class state
    (Completed and No-Show still represent a used seat).

    Called by booking.py after every create / cancel / reschedule so the
    cached counter in classes.txt never drifts from bookings.txt.
    """
    bookings = read_bookings()
    classes = read_classes()

    count = 0
    for b in bookings:
        if b["class_id"] == class_id and b["status"] != "Cancelled":
            count += 1

    updated = False
    for c in classes:
        if c["id"] == class_id:
            c["current_booked"] = count
            updated = True
            break

    if updated:
        write_classes(classes)


def auto_suspend_expired_members(acting_role="System"):
    """
    Called at successful login (per product decision #4).

    Rule: if expiry_date + SUSPENSION_GRACE_DAYS < today AND status == 'Active',
    flip the member's status to 'Suspended' and record an audit-log entry.

    Args:
        acting_role: role string to record in the audit log. Defaults to
                     'System' because this runs automatically; callers may
                     pass the logged-in role if they prefer to attribute it.

    Returns the list of suspended member IDs (useful for UI feedback).
    """
    members = read_members()
    today = datetime.now().date()
    suspended_ids = []
    changed = False

    for m in members:
        if m["status"] != "Active":
            continue
        try:
            expiry = datetime.strptime(m["expiry_date"], DATE_FORMAT).date()
        except ValueError:
            # Bad date stored -- skip this member to avoid clobbering data.
            continue
        grace_deadline = expiry + timedelta(days=SUSPENSION_GRACE_DAYS)
        if grace_deadline < today:
            m["status"] = "Suspended"
            suspended_ids.append(m["id"])
            changed = True
            log_audit(
                acting_role,
                "AUTO_SUSPEND",
                f"{m['id']} suspended (expired {m['expiry_date']})",
            )

    if changed:
        write_members(members)
    return suspended_ids


def auto_complete_past_classes(acting_role="System"):
    """
    Called at login, BEFORE auto_mark_no_shows.

    Flip every Scheduled class whose end datetime (schedule_date + start_time
    + duration_min) has already passed to status 'Completed'. Log an audit
    entry per class.

    Runs first in the login pipeline so that auto_mark_no_shows sees a fresh
    class-status picture when it looks for stale Confirmed bookings.

    Returns the list of class IDs that flipped.
    """
    classes = read_classes()
    now = datetime.now()
    affected = []
    changed = False

    for c in classes:
        if c["status"] != "Scheduled":
            continue
        try:
            start = datetime.strptime(
                f"{c['schedule_date']} {c['start_time']}",
                "%Y-%m-%d %H:%M",
            )
        except ValueError:
            # Bad stored date/time; skip without mutating.
            continue
        end = start + timedelta(minutes=c["duration_min"])
        if end < now:
            c["status"] = "Completed"
            affected.append(c["id"])
            changed = True
            log_audit(
                acting_role,
                "AUTO_COMPLETE_CLASS",
                f"{c['id']} marked Completed (ended {end.strftime(DATETIME_FORMAT)})",
            )

    if changed:
        write_classes(classes)
    return affected


def auto_mark_no_shows(acting_role="System"):
    """
    Called at successful login (same slot as auto_suspend_expired_members).

    For every Confirmed booking whose class datetime has already passed:
      - Flip booking status to 'No-Show' and set its penalty_rm to
        NO_SHOW_PENALTY_RM.
      - Create a Pending Penalty payment referencing the booking_id.
        The payment's 'method' is left empty until the Accountant
        records how it is paid.
      - Append an audit-log entry as role='System' (default).

    Returns the list of affected booking IDs (for login-time UI feedback).
    """
    bookings = read_bookings()
    classes = read_classes()
    payments = read_payments()
    now = datetime.now()
    affected = []

    bookings_changed = False
    payments_changed = False

    for b in bookings:
        if b["status"] != "Confirmed":
            continue
        cls = find_class_by_id(classes, b["class_id"])
        if cls is None:
            # Orphaned booking (class was deleted); skip safely.
            continue
        try:
            class_dt = datetime.strptime(
                f"{cls['schedule_date']} {cls['start_time']}",
                "%Y-%m-%d %H:%M",
            )
        except ValueError:
            # Bad stored date/time; skip without mutating.
            continue
        if class_dt >= now:
            continue

        # Flip Confirmed -> No-Show and record the penalty on the booking.
        b["status"] = "No-Show"
        b["penalty_rm"] = NO_SHOW_PENALTY_RM
        bookings_changed = True

        # Create the Pending Penalty payment that ties to this booking.
        new_payment_id = generate_payment_id(payments)
        new_payment = {
            "id": new_payment_id,
            "member_id": b["member_id"],
            "amount": NO_SHOW_PENALTY_RM,
            "payment_type": "Penalty",
            "method": "",                              # set when Accountant records payment
            "payment_date": now.strftime(DATE_FORMAT),
            "status": "Pending",
            "reference_id": b["id"],
        }
        payments.append(new_payment)
        payments_changed = True

        penalty_str = format_amount(NO_SHOW_PENALTY_RM)
        log_audit(
            acting_role,
            "AUTO_NO_SHOW",
            f"{b['id']} -> No-Show, penalty {new_payment_id} RM{penalty_str}",
        )
        affected.append(b["id"])

    if bookings_changed:
        write_bookings(bookings)
    if payments_changed:
        write_payments(payments)
    return affected


# ============================================================
# AUTHENTICATION
# ============================================================

def authenticate(username, password):
    """
    Check username/password against credentials.txt.
    Returns the role string on success, or None on failure.
    """
    creds = read_credentials()
    for c in creds:
        if c["username"] == username and c["password"] == password:
            return c["role"]
    return None
