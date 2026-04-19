# FitZone Gym — Membership & Class Booking System

Group assignment for **CT108-3-1-PYP Python Programming** (Case Study 1).

A procedural-Python (no OOP) command-line system that manages gym memberships,
class bookings, trainers, and payments for a Malaysian fitness center. All
persistence is pipe-delimited text files; the only library dependency is the
Python standard library.

The signature feature is an **ASCII-chart analytics dashboard** (Admin menu
option 8) that visualises revenue trend, class popularity, membership
distribution, and payment status directly in the terminal.

---

## How to run

Requires Python 3.8+ (for f-string support). No `pip install` needed.

```bash
python main.py
```

On **first run** the program auto-seeds realistic demo data into `data/`
(20 members, 5 trainers, ~40 classes, ~90 bookings, ~60 payments) using
`random.seed(42)` for reproducibility. The date window is anchored to
today, so the seed is always relevant to "now".

On **every subsequent run** login-time housekeeping auto-maintains the data:

1. `auto_complete_past_classes` flips Scheduled classes whose end time has
   passed to Completed.
2. `auto_mark_no_shows` flips stale Confirmed bookings on past classes to
   No-Show and creates Pending RM20 penalty payments.
3. `auto_suspend_expired_members` flips Active members past the 7-day
   grace window to Suspended.

Every action above is captured in `data/audit.log` under role `System`.

---

## Demo login credentials

| Username     | Password    | Role            |
|:-------------|:------------|:----------------|
| `admin`      | `admin123`  | Administrator   |
| `booking`    | `book123`   | Booking Officer |
| `accountant` | `acc123`    | Accountant      |

Three failed attempts in a single session exit the program. Type `q` at
the username prompt to quit cleanly.

---

## Role capabilities

- **Administrator** — manage classes and trainers (add / update / remove
  / view); view all members, bookings, and payments; run the System Report
  (5-section text summary); run **F6 Peak Hours Analytics** (ASCII bar
  chart), **F9 Analytics Dashboard** (signature multi-section chart), and
  **F7 View Audit Log** (newest-first with role / action filters).
- **Booking Officer** — register new members; create bookings (auto
  **F1** booking IDs, quota + double-book + capacity + future-date
  checks); cancel bookings (24h late-cancel penalty creates a Pending
  payment referencing the booking); reschedule bookings (same booking
  ID, no penalty); view a member's booking history; view all bookings.
- **Accountant** — record membership payments (auto tier fee; extends
  expiry by 30 days; reactivates Expired/Suspended members; auto-generates
  an **F2** receipt); record penalty payments (pick from Pending list;
  receipt auto-generated); re-print a receipt on demand; view all
  payments; run Income Report (6-month Paid breakdown with totals); track
  unpaid memberships (expired/suspended + near-expiry + pending).

---

## Project layout

```
fitzone_gym/
├── main.py              # entry point: login, router, post-login auto-tasks
├── admin.py             # Administrator role handlers
├── booking.py           # Booking Officer role handlers
├── accountant.py        # Accountant role handlers
├── utils.py             # constants, file I/O, validators, ID generators,
│                        # ASCII bar, audit log, business helpers
├── seed_data.py         # auto-seeds demo data on first run (seed=42)
│
├── CLAUDE.md                       # project rules (internal)
├── CLAUDE_CODE_INSTRUCTIONS.md     # style + build order (internal)
├── PROJECT_BRIEF (1).md            # full specification (internal)
│
├── data/                # pipe-delimited text storage (auto-created)
│   ├── members.txt      # 10 fields per row
│   ├── classes.txt      # 9 fields per row
│   ├── trainers.txt     # 7 fields per row
│   ├── bookings.txt     # 7 fields per row
│   ├── payments.txt     # 8 fields per row (incl. reference_id for
│   │                    #   Penalty -> booking linkage)
│   ├── credentials.txt  # plaintext — documented limitation
│   └── audit.log        # TIMESTAMP|ROLE|ACTION|DETAIL
│
├── receipts/            # receipts/receipt_{RCP_ID}_{payment_id}.txt
└── backup/              # reserved for future use
```

`data/`, `receipts/`, and `backup/` are git-ignored — `seed_data.py`
re-creates `data/` deterministically, and `receipts/` is populated as
payments are recorded.

---

## Signature features (Distinction-tier)

| Code | Feature                         | Where                                   |
|:-----|:--------------------------------|:----------------------------------------|
| F1   | Auto Booking ID generator       | `utils.generate_booking_id` (used by booking.py) |
| F2   | Auto receipt generation         | `accountant.py` → `receipts/*.txt`      |
| F6   | Peak Hours Analytics            | Administrator menu option 7             |
| F7   | Audit Log (+ role/action filters) | Administrator menu option 9           |
| F9   | Analytics Dashboard             | Administrator menu option 8             |

---

## Design constraints (honoured throughout)

- **No OOP** — no `class`, no inheritance, no `self`, no dataclasses.
  Entities are plain dicts passed between functions.
- **No external libraries** — only `os`, `os.path`, `sys`, `datetime`, `random`.
- **No databases** — all state lives in pipe-delimited text files.
- **Cross-platform paths** — every file path goes through `os.path.join`.
- **UTF-8 rendering on Windows** — `utils.enable_utf8_on_windows()` runs
  `chcp 65001` before any box-drawing or emoji output.
- **Beginner-readable** — no decorators, generators, walrus operator,
  complex comprehensions, type hints, or `*args` / `**kwargs`. Every
  module has a docstring; every public function has a docstring.
- **Input validation everywhere** — every `input()` call routes through
  a `utils.get_valid_*` helper.
- **Error-handled I/O** — every file read/write is wrapped in `try/except`
  with a user-friendly message rather than a raw traceback.
- **Audit log for every mutation** — ADD / UPDATE / REMOVE / CREATE /
  CANCEL / RESCHEDULE / RECORD_PAYMENT / GENERATE_RECEIPT / RENEW /
  REACTIVATE / LOGIN / LOGOUT plus the three System-role AUTO_* entries.
