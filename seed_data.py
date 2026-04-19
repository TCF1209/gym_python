"""
seed_data.py -- generates demo data on first run.

The seed creates a realistic FitZone Gym dataset spanning the last six months
of operations plus the next 30 days of upcoming classes/bookings, anchored to
the current date at run time (so demo data never goes stale).

Call seed_all() when needs_seeding() is True. Running this module directly
(python seed_data.py) also works.

All randomness uses random.seed(42) so every team member gets identical data.

The seed data deliberately includes these demo edge cases:
  - 3 'Active' members whose expiry_date has passed the 7-day grace window
    (auto_suspend_expired_members will flip them to 'Suspended' on first login).
  - 2 'Suspended' members already flagged historically.
  - ~15% of historical bookings marked 'No-Show' -- these trigger
    auto_mark_no_shows on first login and generate Pending Penalty payments.
  - ~15% of historical bookings 'Cancelled' with half carrying a RM10 late
    cancel penalty -- generates matching Penalty payment rows.
"""

import os
import os.path
import random
from datetime import datetime, timedelta

import utils


# ============================================================
# DATE WINDOW (anchored to today so data stays relevant)
# ============================================================

TODAY = datetime.now().date()
HISTORY_DAYS = 183          # ~6 months of operating history
FUTURE_DAYS = 30            # 30 days of upcoming classes
START_DATE = TODAY - timedelta(days=HISTORY_DAYS)
END_DATE = TODAY + timedelta(days=FUTURE_DAYS)


# ============================================================
# PUBLIC ENTRY POINTS
# ============================================================

def needs_seeding():
    """
    Per product decision #9:
      - If data/ is missing     -> seed.
      - Else if members.txt is missing or empty -> seed.
      - Otherwise -> existing data, don't overwrite.
    """
    if not os.path.exists(utils.DATA_DIR):
        return True
    if not os.path.exists(utils.MEMBERS_FILE):
        return True
    try:
        if os.path.getsize(utils.MEMBERS_FILE) == 0:
            return True
    except OSError:
        # If we can't stat the file for any reason, treat as missing.
        return True
    return False


def seed_all():
    """Populate every data file. Only call when needs_seeding() is True."""
    random.seed(42)
    utils.ensure_data_dir()

    _seed_credentials()
    trainers = _seed_trainers()
    members = _seed_members()
    classes = _seed_classes()
    bookings = _seed_bookings(members, classes)
    _seed_payments(members, bookings)

    # Keep classes.current_booked in sync with what we just generated.
    # Done once in memory to avoid 40 read/write round trips.
    _sync_current_booked(classes, bookings)


# ============================================================
# CREDENTIALS
# ============================================================

def _seed_credentials():
    """Write the 3 demo login accounts."""
    creds = [
        {"username": "admin",      "password": "admin123", "role": "Administrator"},
        {"username": "booking",    "password": "book123",  "role": "BookingOfficer"},
        {"username": "accountant", "password": "acc123",   "role": "Accountant"},
    ]
    utils.write_credentials(creds)


# ============================================================
# TRAINERS (fixed per product decision)
# ============================================================

def _seed_trainers():
    """Write the 5 demo trainers. One per class type (Malaysian multi-ethnic mix)."""
    # Each tuple: (id, name, specialization, phone, email)
    trainer_facts = [
        ("T001", "Aisyah Rahman", "Yoga",     "0123401001", "aisyah@fitzone.my"),
        ("T002", "Kumar Selvam",  "HIIT",     "0133401002", "kumar@fitzone.my"),
        ("T003", "Ahmad Faizal",  "Boxing",   "0163401003", "ahmad@fitzone.my"),
        ("T004", "Mei Ling Tan",  "Zumba",    "0193401004", "meiling@fitzone.my"),
        ("T005", "Ryan Lim",      "Spinning", "0143401005", "ryan@fitzone.my"),
    ]
    trainers = []
    for tid, name, specialization, phone, email in trainer_facts:
        trainer = {
            "id": tid,
            "name": name,
            "specialization": specialization,
            "phone": phone,
            "email": email,
            "experience_years": random.randint(3, 8),
            "status": "Active",
        }
        trainers.append(trainer)
    utils.write_trainers(trainers)
    return trainers


# ============================================================
# MEMBERS
# ============================================================

# Names pool: deliberately ordered Basic -> Premium -> VIP.
# Malaysian mix (Malay / Chinese / Indian).
_MEMBER_NAMES = [
    # Basic (8)
    "Ahmad Fikri",
    "Tan Wei Ming",
    "Siti Nurhaliza",
    "Raj Kumar",
    "Lim Jun Hao",
    "Nur Aisyah",
    "Hafiz Rahman",
    "Chen Li Hua",
    # Premium (7)
    "Priya Devi",
    "Muhammad Izzat",
    "Ng Yi Ling",
    "Farah Aziz",
    "Arun Prakash",
    "Wong Kok Wei",
    "Zarah Ismail",
    # VIP (5)
    "Daniel Ong",
    "Aminah Osman",
    "Jaya Nair",
    "Harris Zainal",
    "Chong Hui Min",
]

_MEMBER_TIERS_BY_INDEX = (["Basic"] * 8) + (["Premium"] * 7) + (["VIP"] * 5)

# Indices with special demo states. Spread across tiers on purpose.
_AUTO_SUSPEND_INDICES = {3, 11, 17}   # Active + expiry 8-14d past -> auto_suspend flips on login
_ALREADY_SUSPENDED_INDICES = {6, 14}  # Already flagged Suspended historically

_PHONE_PREFIXES = ["012", "013", "014", "016", "017", "019"]


def _seed_members():
    """Write 20 members across tiers, including the demo edge cases."""
    members = []
    for idx, name in enumerate(_MEMBER_NAMES):
        tier = _MEMBER_TIERS_BY_INDEX[idx]

        # Ages skew 22-35 with a long tail 18-55 (triangular mode = 28).
        age = int(random.triangular(18, 55, 28))
        gender = random.choice(["M", "F"])

        # Phone: Malaysian 01X + 7 digits, stored as digits-only (see utils).
        suffix = str(random.randint(1000000, 9999999))
        phone = random.choice(_PHONE_PREFIXES) + suffix

        email_local = name.lower().replace(" ", ".")
        email = f"{email_local}@email.com"

        # Join date: random within the last 8 months.
        join_date = TODAY - timedelta(days=random.randint(30, 240))

        # Default 'normal' member: yearly membership, still Active.
        expiry_date = join_date + timedelta(days=365)
        status = "Active"

        # --- Edge-case overrides ---
        if idx in _AUTO_SUSPEND_INDICES:
            # Past the 7-day grace window so auto_suspend will fire on first login.
            expiry_date = TODAY - timedelta(days=random.randint(8, 14))
            status = "Active"
        elif idx in _ALREADY_SUSPENDED_INDICES:
            # Already historically suspended (older expiry).
            expiry_date = TODAY - timedelta(days=random.randint(30, 60))
            status = "Suspended"

        member = {
            "id": f"M{idx + 1:03d}",
            "name": name,
            "age": age,
            "gender": gender,
            "phone": phone,
            "email": email,
            "tier": tier,
            "join_date": join_date.strftime(utils.DATE_FORMAT),
            "expiry_date": expiry_date.strftime(utils.DATE_FORMAT),
            "status": status,
        }
        members.append(member)
    utils.write_members(members)
    return members


# ============================================================
# CLASSES
# ============================================================

_CLASS_NAME_TO_TRAINER = {
    "Yoga":     "T001",
    "HIIT":     "T002",
    "Boxing":   "T003",
    "Zumba":    "T004",
    "Spinning": "T005",
}

_PEAK_TIMES = ["18:00", "19:00", "20:00"]
_MORNING_TIMES = ["07:00", "08:00", "09:00", "10:00"]
_OTHER_TIMES = ["06:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00", "21:00"]


def _pick_class_time():
    """Weighted time picker: 30% peak, 25% morning, 45% other."""
    r = random.random()
    if r < 0.30:
        return random.choice(_PEAK_TIMES)
    if r < 0.55:
        return random.choice(_MORNING_TIMES)
    return random.choice(_OTHER_TIMES)


def _seed_classes():
    """Write ~40 class slots spread across the 6-month window."""
    total_classes = 40
    total_days = (END_DATE - START_DATE).days

    classes = []
    for i in range(total_classes):
        class_name = random.choice(utils.VALID_CLASS_NAMES)
        day_offset = random.randint(0, total_days)
        schedule_date = START_DATE + timedelta(days=day_offset)
        start_time = _pick_class_time()

        # Past classes are Completed; future classes are Scheduled.
        # (Cancelled status is reserved for admin-driven cancellations.)
        if schedule_date < TODAY:
            status = "Completed"
        else:
            status = "Scheduled"

        cls = {
            "id": f"C{i + 1:03d}",
            "name": class_name,
            "trainer_id": _CLASS_NAME_TO_TRAINER[class_name],
            "schedule_date": schedule_date.strftime(utils.DATE_FORMAT),
            "start_time": start_time,
            "duration_min": 60,
            "capacity": utils.CLASS_CAPACITY[class_name],
            "current_booked": 0,    # real value computed after bookings generated
            "status": status,
        }
        classes.append(cls)
    utils.write_classes(classes)
    return classes


# ============================================================
# BOOKINGS
# ============================================================

def _seed_bookings(members, classes):
    """
    Write 80-100 bookings: ~60 historical (past classes) + ~30 upcoming.

    Historical status mix: ~70% Completed, ~15% No-Show, ~15% Cancelled.
    Upcoming bookings are all Confirmed and use non-Suspended members.
    """
    # Split classes into past vs future using a plain loop (beginner-friendly).
    past_classes = []
    future_classes = []
    for c in classes:
        schedule_dt = datetime.strptime(c["schedule_date"], utils.DATE_FORMAT).date()
        if schedule_dt < TODAY:
            past_classes.append(c)
        else:
            future_classes.append(c)

    # Track (member_id, class_id) pairs so one member never double-books a class.
    used_pairs = set()
    # Per-date counters for F1-format booking IDs: key = YYYYMMDD, value = last-used counter.
    date_counters = {}
    bookings = []

    # ---- Historical bookings ----
    target_historical = 60
    max_attempts = target_historical * 5
    attempts = 0
    historical_created = 0
    while historical_created < target_historical and attempts < max_attempts:
        attempts += 1
        if not past_classes:
            break
        c = random.choice(past_classes)
        m = random.choice(members)
        pair = (m["id"], c["id"])
        if pair in used_pairs:
            continue

        # Booking was recorded 1-14 days before the class ran.
        class_dt = datetime.strptime(c["schedule_date"], utils.DATE_FORMAT).date()
        days_before = random.randint(1, 14)
        booking_date = class_dt - timedelta(days=days_before)

        # Status mix for historical data.
        r = random.random()
        if r < 0.70:
            status = "Completed"
            penalty_rm = 0.00
        elif r < 0.85:
            status = "No-Show"
            penalty_rm = utils.NO_SHOW_PENALTY_RM
        else:
            status = "Cancelled"
            # Half of cancellations are within-24h (incur late-cancel penalty).
            if random.random() < 0.5:
                penalty_rm = utils.LATE_CANCEL_PENALTY_RM
            else:
                penalty_rm = 0.00

        booking = {
            "id": _next_booking_id(booking_date, date_counters),
            "member_id": m["id"],
            "class_id": c["id"],
            "booking_date": booking_date.strftime(utils.DATE_FORMAT),
            "class_date": c["schedule_date"],
            "status": status,
            "penalty_rm": penalty_rm,
        }
        bookings.append(booking)
        used_pairs.add(pair)
        historical_created += 1

    # ---- Upcoming Confirmed bookings ----
    target_upcoming = 30
    attempts = 0
    max_attempts = target_upcoming * 5
    upcoming_created = 0
    while upcoming_created < target_upcoming and attempts < max_attempts:
        attempts += 1
        if not future_classes:
            break
        c = random.choice(future_classes)
        m = random.choice(members)

        # Suspended members can't book upcoming classes (realistic).
        if m["status"] == "Suspended":
            continue
        pair = (m["id"], c["id"])
        if pair in used_pairs:
            continue

        # Booking recorded 0 to min(14, days_until_class) days before.
        class_dt = datetime.strptime(c["schedule_date"], utils.DATE_FORMAT).date()
        days_ahead = (class_dt - TODAY).days
        upper = min(14, max(1, days_ahead))
        days_before = random.randint(0, upper)
        booking_date = class_dt - timedelta(days=days_before)
        # Guarantee booking_date doesn't land in the future.
        if booking_date > TODAY:
            booking_date = TODAY

        booking = {
            "id": _next_booking_id(booking_date, date_counters),
            "member_id": m["id"],
            "class_id": c["id"],
            "booking_date": booking_date.strftime(utils.DATE_FORMAT),
            "class_date": c["schedule_date"],
            "status": "Confirmed",
            "penalty_rm": 0.00,
        }
        bookings.append(booking)
        used_pairs.add(pair)
        upcoming_created += 1

    # ---- Demo-only 'stale Confirmed' bookings ----
    # Inject 2 bookings where status == Confirmed but class_date has already
    # passed. Nothing in real operation would leave these lying around, but
    # they let auto_mark_no_shows do visible work on the very first login
    # (one of the demo touchpoints).
    stale_target = 2
    stale_created = 0
    attempts = 0
    while stale_created < stale_target and attempts < stale_target * 10 and past_classes:
        attempts += 1
        c = random.choice(past_classes)
        m = random.choice(members)
        if m["status"] == "Suspended":
            continue
        pair = (m["id"], c["id"])
        if pair in used_pairs:
            continue

        class_dt = datetime.strptime(c["schedule_date"], utils.DATE_FORMAT).date()
        booking_date = class_dt - timedelta(days=random.randint(1, 7))
        booking = {
            "id": _next_booking_id(booking_date, date_counters),
            "member_id": m["id"],
            "class_id": c["id"],
            "booking_date": booking_date.strftime(utils.DATE_FORMAT),
            "class_date": c["schedule_date"],
            "status": "Confirmed",       # will flip to No-Show on first login
            "penalty_rm": 0.00,
        }
        bookings.append(booking)
        used_pairs.add(pair)
        stale_created += 1

    utils.write_bookings(bookings)
    return bookings


def _next_booking_id(booking_date, date_counters):
    """
    Return the next BK{YYYYMMDD}{###} ID for a given booking date and
    bump the shared counter so IDs stay unique within a day.
    """
    date_key = booking_date.strftime("%Y%m%d")
    if date_key in date_counters:
        date_counters[date_key] += 1
    else:
        date_counters[date_key] = 1
    return f"BK{date_key}{date_counters[date_key]:03d}"


# ============================================================
# PAYMENTS
# ============================================================

def _seed_payments(members, bookings):
    """
    Write ~50-70 payments:
      - Membership fees: one per billable month per member (capped at 6).
        90% Paid, 10% Pending to seed a realistic mix for the dashboard.
      - Penalty payments: one per historical booking with penalty_rm > 0.
        ~40% Paid (late-cancel/no-show that got settled), rest Pending.
    """
    payments = []
    payment_counter = 0

    # ---- Membership payments ----
    for m in members:
        join_date = datetime.strptime(m["join_date"], utils.DATE_FORMAT).date()
        expiry_date = datetime.strptime(m["expiry_date"], utils.DATE_FORMAT).date()

        # Bill from max(join_date, START_DATE) up to min(expiry_date, TODAY).
        period_start = join_date
        if period_start < START_DATE:
            period_start = START_DATE
        period_end = TODAY
        if expiry_date < period_end:
            period_end = expiry_date
        if period_end < period_start:
            # Nothing to bill -- membership expired before the window.
            continue

        # Per-member cap picked randomly 2-4 so members look realistically
        # varied in billing history. Combined with ~11 penalty rows this
        # keeps the total payment count inside the 50-70 target band.
        max_months = random.randint(2, 4)
        pay_date = period_start
        months_billed = 0
        while pay_date <= period_end and months_billed < max_months:
            if random.random() < 0.90:
                status = "Paid"
                method = random.choice(["Cash", "Card"])
            else:
                status = "Pending"
                method = ""
            payment_counter += 1
            payment = {
                "id": f"P{payment_counter:03d}",
                "member_id": m["id"],
                "amount": utils.get_tier_fee(m["tier"]),
                "payment_type": "Membership",
                "method": method,
                "payment_date": pay_date.strftime(utils.DATE_FORMAT),
                "status": status,
                "reference_id": "",
            }
            payments.append(payment)
            # Step by ~30 days so each period roughly corresponds to a month.
            pay_date = pay_date + timedelta(days=30)
            months_billed += 1

    # ---- Penalty payments (one per past-booking-with-penalty) ----
    for b in bookings:
        if b["penalty_rm"] <= 0:
            continue
        if random.random() < 0.40:
            status = "Paid"
            method = random.choice(["Cash", "Card"])
        else:
            status = "Pending"
            method = ""

        # Penalty recorded 0-3 days after the class -- but never in the future.
        class_dt = datetime.strptime(b["class_date"], utils.DATE_FORMAT).date()
        pay_date = class_dt + timedelta(days=random.randint(0, 3))
        if pay_date > TODAY:
            pay_date = TODAY

        payment_counter += 1
        payment = {
            "id": f"P{payment_counter:03d}",
            "member_id": b["member_id"],
            "amount": b["penalty_rm"],
            "payment_type": "Penalty",
            "method": method,
            "payment_date": pay_date.strftime(utils.DATE_FORMAT),
            "status": status,
            "reference_id": b["id"],
        }
        payments.append(payment)

    utils.write_payments(payments)
    return payments


# ============================================================
# CURRENT_BOOKED SYNC
# ============================================================

def _sync_current_booked(classes, bookings):
    """
    For each class, count its non-Cancelled bookings and persist the result.
    Matches utils.recount_class_bookings but done in-memory in one write.
    """
    for c in classes:
        count = 0
        for b in bookings:
            if b["class_id"] == c["id"] and b["status"] != "Cancelled":
                count += 1
        c["current_booked"] = count
    utils.write_classes(classes)


# ============================================================
# CLI ENTRY POINT
# ============================================================

if __name__ == "__main__":
    utils.enable_utf8_on_windows()
    if not needs_seeding():
        print("ℹ️  Existing data detected in data/. Skipping seed.")
        print("    (Delete data/members.txt to force a re-seed.)")
    else:
        print("🌱 Seeding FitZone demo data...")
        seed_all()
        # Quick summary so the team can sanity-check the run.
        members = utils.read_members()
        classes = utils.read_classes()
        trainers = utils.read_trainers()
        bookings = utils.read_bookings()
        payments = utils.read_payments()
        creds = utils.read_credentials()
        print("✓ Seed complete.")
        print(f"   credentials : {len(creds)}")
        print(f"   trainers    : {len(trainers)}")
        print(f"   members     : {len(members)}")
        print(f"   classes     : {len(classes)}")
        print(f"   bookings    : {len(bookings)}")
        print(f"   payments    : {len(payments)}")
