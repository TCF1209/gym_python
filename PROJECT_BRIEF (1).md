# FitZone Gym Membership & Class Booking System

**Module**: CT108-3-1-PYP Python Programming
**Assignment Type**: Group Assignment (3 members)
**Case Study**: Case 1 — Fitness Center Membership & Class Booking System
**Target Grade**: Distinction (80%+)
**Signature**: Data Visualization & Analytics Dashboard (ASCII Charts)

---

## 1. Project Identity

FitZone Gym is a fitness center management system built in pure Python (procedural, no OOP) that manages gym memberships, class bookings, trainers, and payments through text-file storage. The system simulates real-world Malaysian fitness center operations with role-based access for three staff positions.

The signature feature of this system is its **ASCII-chart-based analytics dashboard** that visualizes business insights (peak hours, class popularity, revenue trends) directly in the terminal — a differentiator from typical text-only Python student projects.

---

## 2. Core Constraints (Non-Negotiable)

These constraints come directly from the assignment brief and must be respected without exception.

### 2.1 Language & Paradigm
- **Python only** — no other programming languages
- **No Object-Oriented Programming** — no `class`, no inheritance, no objects, no `self`
- **Procedural + modular functions only** — organize code through functions and modules
- Use lists, tuples, dictionaries, loops, conditionals for logic

### 2.2 Libraries
- **No external libraries** — nothing that requires `pip install`
- **Python built-in standard library is allowed**, specifically:
  - `datetime` — for date/time operations (booking timestamps, penalty calculation)
  - `os` — for file/folder existence checks and cross-platform paths
  - `os.path` — always use `os.path.join()` for file paths (cross-platform)
  - `random` — for pre-seeded data generation
  - `csv` — optional, if using CSV reader for structured text files
  - `json` — NOT used (we use pipe-delimited text format instead)

### 2.3 Data Storage
- **Text files only** — no databases
- **Pipe `|` delimiter** as the consistent format across all files
- All reads/writes go through file handling functions in `utils.py`

### 2.4 Interface
- **Command-line menu only** — no GUI, no web interface
- Every screen is text-based with clear menu numbering
- Input validation on every prompt

### 2.5 Cross-Platform Compatibility
- Code must run on Windows, macOS, Linux, and WSL identically
- Use `os.path.join()` for all file paths
- Avoid hardcoded `/` or `\\` separators
- Test with both relative paths and current working directory

---

## 3. System Architecture

### 3.1 File Structure

```
fitzone_gym/
├── main.py                    # Entry point, login, main menu router
├── admin.py                   # System Administrator module
├── booking.py                 # Booking Officer module
├── accountant.py              # Accountant module
├── utils.py                   # Shared utilities (file I/O, validation, formatting)
├── seed_data.py               # Pre-seeds demo data on first run
│
├── data/                      # All text-file data
│   ├── members.txt
│   ├── classes.txt
│   ├── trainers.txt
│   ├── bookings.txt
│   ├── payments.txt
│   ├── credentials.txt
│   └── audit.log
│
├── receipts/                  # Auto-generated receipts (Feature F2)
│   └── receipt_BK20260420001.txt
│
└── backup/                    # Optional backups
```

### 3.2 Module Responsibilities

**`main.py`** — Entry point
- Checks if data files exist; if not, calls `seed_data.py` to populate demo data
- Handles login (role + password)
- Routes authenticated users to their role-specific menu
- Handles logout and system exit

**`admin.py`** — System Administrator role
- Manage classes (add, update, remove)
- Manage trainers (add, update, remove)
- View all data (members, bookings, payments)
- Generate system report (totals: members, classes, revenue)
- Peak Hours Analytics (F6)
- Analytics Dashboard (F9)

**`booking.py`** — Booking Officer role
- Register new gym members
- Process new bookings (with auto-generated Booking ID — F1)
- Cancel bookings (with penalty calculation)
- Reschedule bookings
- View member booking history
- Check tier quota before booking

**`accountant.py`** — Accountant role
- Record membership fee payments
- Generate Receipts (F2)
- Generate income reports
- Track unpaid/pending memberships
- View all payment records

**`utils.py`** — Shared functions
- `read_file(filename)` → returns list of records
- `write_file(filename, records)` → overwrites with new data
- `append_file(filename, record)` → appends single record
- `log_audit(role, action, detail)` → writes to audit.log (F7)
- `validate_date(input)`, `validate_id(input)`, `validate_menu_choice(input, valid_options)` etc.
- `display_ascii_bar(value, max_value, width=30)` → renders ASCII bar chart
- `generate_booking_id()` → auto-increment BK-format IDs

---

## 4. Data File Schemas (Pipe-Delimited)

### 4.1 `members.txt`
```
MEMBER_ID|NAME|AGE|GENDER|PHONE|EMAIL|TIER|JOIN_DATE|EXPIRY_DATE|STATUS
M001|John Tan|28|M|0123456789|john@email.com|Premium|2026-01-15|2026-12-15|Active
```

**Fields**:
- `MEMBER_ID` — format `M###` (auto-generated)
- `TIER` — `Basic` / `Premium` / `VIP`
- `STATUS` — `Active` / `Expired` / `Suspended`
- Dates in `YYYY-MM-DD` format

### 4.2 `classes.txt`
```
CLASS_ID|CLASS_NAME|TRAINER_ID|SCHEDULE_DATE|START_TIME|DURATION_MIN|CAPACITY|CURRENT_BOOKED|STATUS
C001|Yoga|T001|2026-04-25|09:00|60|15|8|Scheduled
```

**Fields**:
- `CLASS_ID` — format `C###`
- `CLASS_NAME` — `Yoga` / `HIIT` / `Boxing` / `Zumba` / `Spinning`
- `CAPACITY` — fixed per class type (see Business Rules)
- `START_TIME` — 24h format `HH:MM`
- `STATUS` — `Scheduled` / `Completed` / `Cancelled`

### 4.3 `trainers.txt`
```
TRAINER_ID|NAME|SPECIALIZATION|PHONE|EMAIL|EXPERIENCE_YEARS|STATUS
T001|Aisyah Rahman|Yoga|0112345678|aisyah@fitzone.my|5|Active
```

### 4.4 `bookings.txt`
```
BOOKING_ID|MEMBER_ID|CLASS_ID|BOOKING_DATE|CLASS_DATE|STATUS|PENALTY_RM
BK20260420001|M001|C001|2026-04-20|2026-04-25|Confirmed|0
```

**Fields**:
- `BOOKING_ID` — format `BK{YYYYMMDD}{###}` (F1)
- `STATUS` — `Confirmed` / `Cancelled` / `Completed` / `No-Show`
- `PENALTY_RM` — `0` / `10` (late cancel) / `20` (no-show)

### 4.5 `payments.txt`
```
PAYMENT_ID|MEMBER_ID|AMOUNT|PAYMENT_TYPE|METHOD|PAYMENT_DATE|STATUS
P001|M001|150.00|Membership|Card|2026-04-15|Paid
```

**Fields**:
- `PAYMENT_TYPE` — `Membership` / `Penalty`
- `METHOD` — `Cash` / `Card`
- `STATUS` — `Paid` / `Pending`

### 4.6 `credentials.txt`
```
USERNAME|PASSWORD|ROLE
admin|admin123|Administrator
booking|book123|BookingOfficer
accountant|acc123|Accountant
```

### 4.7 `audit.log` (F7)
```
2026-04-19 14:23:15|Administrator|ADD_CLASS|C015 Yoga on 2026-05-01 09:00
2026-04-19 14:24:02|BookingOfficer|CANCEL_BOOKING|BK20260419003 (penalty: RM10)
```

Format: `TIMESTAMP|ROLE|ACTION|DETAIL`

---

## 5. Business Rules

### 5.1 Membership Tiers

| Tier | Monthly Fee (RM) | Class Quota/Month |
|---|---|---|
| Basic | 80 | 5 |
| Premium | 150 | 15 |
| VIP | 250 | Unlimited |

Pricing based on Malaysian local gym market research (Anytime Fitness, Celebrity Fitness, Chi Fitness).

### 5.2 Class Types & Capacity

| Class | Trainer ID | Capacity | Rationale |
|---|---|---|---|
| Yoga | T001 | 15 | Static practice, minimal space per person |
| HIIT | T002 | 12 | Requires spacing for movement |
| Boxing | T003 | 8 | Equipment-based (bags, gloves) |
| Zumba | T004 | 15 | Group dance, large open floor |
| Spinning | T005 | 12 | Limited by bike count |

### 5.3 Booking Rules
- Members can only book within their tier's monthly quota
- VIP has unlimited bookings
- Quota resets on the 1st of each month
- Cannot book past dates
- Cannot book if class is full (show "FULL" status)
- One member cannot double-book the same class slot

### 5.4 Cancellation Penalty
- Cancellation **more than 24h** before class = Free
- Cancellation **less than 24h** before class = **RM10 penalty**
- **No-show** (class has passed, member didn't attend) = **RM20 penalty**
- Penalties recorded as payments with `Pending` status until paid
- Penalty uses `datetime.now()` for comparison with class start time

### 5.5 Payment Rules
- Classes are FREE for members (covered by monthly fee)
- Payment types: `Membership` (monthly fee) or `Penalty` (cancellation/no-show)
- Status `Pending` until marked `Paid` by Accountant
- Member with overdue membership (expired + unpaid) is flagged as `Suspended`

---

## 6. User Roles & Menu Navigation

### 6.1 Login Flow
```
========================================
    FitZone Gym Management System
========================================
Username: _____
Password: _____
```

On success → route to role-specific menu.
On failure (3 attempts) → exit program.

### 6.2 System Administrator Menu
```
╔══════════════════════════════════════╗
║  ADMINISTRATOR DASHBOARD             ║
╠══════════════════════════════════════╣
║  1. Manage Classes                   ║
║  2. Manage Trainers                  ║
║  3. View All Members                 ║
║  4. View All Bookings                ║
║  5. View All Payments                ║
║  6. System Report                    ║
║  7. Peak Hours Analytics [F6]        ║
║  8. Analytics Dashboard [F9]         ║
║  9. Logout                           ║
╚══════════════════════════════════════╝
```

**Manage Classes submenu**: Add / Update / Remove / View
**Manage Trainers submenu**: Add / Update / Remove / View

### 6.3 Booking Officer Menu
```
╔══════════════════════════════════════╗
║  BOOKING OFFICER DASHBOARD           ║
╠══════════════════════════════════════╣
║  1. Register New Member              ║
║  2. Create New Booking               ║
║  3. Cancel Booking                   ║
║  4. Reschedule Booking               ║
║  5. View Member Booking History      ║
║  6. View All Bookings                ║
║  7. Logout                           ║
╚══════════════════════════════════════╝
```

### 6.4 Accountant Menu
```
╔══════════════════════════════════════╗
║  ACCOUNTANT DASHBOARD                ║
╠══════════════════════════════════════╣
║  1. Record Membership Payment        ║
║  2. Record Penalty Payment           ║
║  3. Generate Receipt [F2]            ║
║  4. View Payment Records             ║
║  5. Income Report                    ║
║  6. Track Unpaid Memberships         ║
║  7. Logout                           ║
╚══════════════════════════════════════╝
```

---

## 7. Extra Features (Distinction-Tier)

### 7.1 F1 — Auto Booking ID Generator
**Owner**: Booking Officer

**Format**: `BK{YYYYMMDD}{###}` (e.g., `BK20260420001`)

**Logic**:
- Read last booking from `bookings.txt`
- Extract date portion; if today's date matches, increment counter
- If new day, start counter from `001`
- Guaranteed unique, human-readable

### 7.2 F2 — Receipt Generator
**Owner**: Accountant

On payment recording, auto-generate a `.txt` receipt in `receipts/` folder:

```
╔══════════════════════════════════════╗
║       FitZone Gym Receipt            ║
╠══════════════════════════════════════╣
  Receipt No: RCP20260420001
  Date: 2026-04-20 15:30
  Member: M001 - John Tan
  Tier: Premium
  ──────────────────────────────────
  Description       Amount (RM)
  Monthly Fee       150.00
  ──────────────────────────────────
  TOTAL             RM 150.00
  Payment Method: Card
  Status: Paid
╚══════════════════════════════════════╝
       Thank you for choosing FitZone!
```

### 7.3 F6 — Peak Hours Analytics
**Owner**: System Administrator

Analyzes all bookings and displays ASCII bar chart:

```
PEAK HOUR ANALYSIS (Based on 156 bookings)
═══════════════════════════════════════════
06:00  ██ 8
08:00  ██████ 24
10:00  ████████ 32
12:00  ████ 16
14:00  █████ 20
16:00  ███████ 28
18:00  █████████████ 52  ⭐ PEAK
20:00  ██████████ 40
───────────────────────────────────────────
Busiest hour: 18:00 (33% of all bookings)
Recommendation: Schedule more classes at 18:00
```

### 7.4 F7 — Audit Log
**Owner**: All roles (auto-triggered)

Every mutating action (add/update/delete/book/cancel/pay) calls `log_audit()` which appends to `audit.log`:

```
2026-04-19 14:23:15|Administrator|ADD_CLASS|C015 Yoga
2026-04-19 14:24:02|BookingOfficer|CANCEL_BOOKING|BK20260419003 (penalty: RM10)
2026-04-19 14:25:18|Accountant|RECORD_PAYMENT|P045 M001 RM150 Card
```

Admin can view `audit.log` via a menu option.

### 7.5 F9 — Analytics Dashboard
**Owner**: System Administrator

Full multi-section report:

```
╔══════════════════════════════════════════════════╗
║     FITZONE ANALYTICS DASHBOARD                  ║
║     Generated: 2026-04-19 15:30                  ║
╚══════════════════════════════════════════════════╝

📊 REVENUE TREND (Last 6 Months)
─────────────────────────────────────────────────
Nov 2025  ████████ RM 8,400
Dec 2025  █████████ RM 9,200
Jan 2026  ██████████ RM10,400
Feb 2026  ███████████ RM11,500
Mar 2026  █████████████ RM13,200  📈 +14%
Apr 2026  ██████████████ RM14,800  📈 +12%

🏆 CLASS POPULARITY
─────────────────────────────────────────────────
Yoga      ████████████ 45 bookings (29%)
HIIT      ██████████ 38 bookings (24%)
Zumba     █████████ 32 bookings (21%)
Spinning  ██████ 24 bookings (15%)
Boxing    █████ 17 bookings (11%)

👥 MEMBERSHIP DISTRIBUTION
─────────────────────────────────────────────────
Basic     █████████ 45 members (45%)
Premium   ███████ 35 members (35%)
VIP       ████ 20 members (20%)

💰 PAYMENT STATUS
─────────────────────────────────────────────────
Paid:    RM 14,800 (92%)
Pending: RM  1,280 (8%)
─────────────────────────────────────────────────
Total Revenue:  RM 16,080
Active Members: 100
Total Bookings: 156
```

---

## 8. Research Assumptions (for Documentation)

Based on research into Malaysian local gyms (Anytime Fitness Malaysia, Celebrity Fitness, Chi Fitness), the following logical assumptions are embedded in the system:

1. **Pricing tier structure** — Malaysian mid-tier gyms charge RM80–250/month; we mirror this range.
2. **Class quota system** — Premium tier unlocks more classes, based on ClassPass-style tiered access.
3. **Peak hour pattern** — Malaysian gyms peak at 18:00–20:00 post-work, reflected in pre-seed data.
4. **Class mix** — Yoga, HIIT, Boxing, Zumba, Spinning are the 5 most common in Klang Valley gyms.
5. **24-hour cancellation window** — Industry standard across ClassPass, Mindbody, and local chains.
6. **Penalty amounts** — RM10/RM20 penalties align with typical Malaysian gym cancellation fees.
7. **Multi-ethnic trainer names** — Malaysian context reflects Malay/Chinese/Indian/mixed names.
8. **Payment methods** — Cash still widely used in Malaysian SMEs alongside card; e-wallets excluded to keep scope manageable.
9. **Monthly fee cycle** — Most local gyms use monthly recurring; we assume 30-day cycles.
10. **Membership expiry auto-flag** — Expired members auto-suspend after 7 days grace (industry norm).

---

## 9. Demo Data (Pre-Seeded)

System's first run populates:

| File | Records |
|---|---|
| `credentials.txt` | 3 accounts (admin / booking / accountant) |
| `trainers.txt` | 5 trainers (1 per class type, multi-ethnic names) |
| `classes.txt` | 30-40 class slots (mix of past, present, future — covering 3 months) |
| `members.txt` | 20 members (8 Basic, 7 Premium, 5 VIP) |
| `bookings.txt` | 50-60 bookings (40 historical + 20 upcoming, mixed status) |
| `payments.txt` | 30-40 payments (mixed Paid/Pending for trend visualization) |

**Data generation rules**:
- Historical bookings span last 3 months (for Dashboard trend charts)
- Upcoming bookings span next 30 days (for Booking Officer operations)
- Time distribution follows Malaysian peak pattern (18:00 = 30% of bookings)
- Members distributed across 3 tiers realistically (Basic > Premium > VIP)
- Use `random.seed(42)` for reproducible demo data

---

## 10. Presentation & Demo Strategy (3 Members, 20 Minutes)

Each member demonstrates their assigned role (≈3 minutes per part) plus group Q&A (10 min).

### Member 1 — System Administrator (Chye Fong — leads)
- Login as admin
- Add a new class + new trainer
- View all data
- **Demo signature F6 Peak Hours** + **F9 Dashboard** (Wow moments)
- Show `audit.log` (F7)

### Member 2 — Booking Officer
- Login as booking officer
- Register a new member
- Create a booking (show auto-generated BK ID — F1)
- Cancel a booking within 24h (show RM10 penalty applied)
- View booking history

### Member 3 — Accountant
- Login as accountant
- Record a membership payment (show auto-generated receipt — F2)
- Open the generated receipt file
- Generate income report
- Track unpaid/pending members

---

## 11. Quality Checklist

Before considering the system done, verify:

- [ ] All 3 role menus functional, navigable
- [ ] All CRUD operations work (Add/Update/Delete/View for each entity)
- [ ] Pre-seed data loads on first run
- [ ] Every user input has validation
- [ ] All file I/O wrapped in `try/except`
- [ ] `audit.log` captures every mutation
- [ ] ASCII charts render correctly (aligned, readable)
- [ ] Booking ID auto-generator never produces duplicates
- [ ] Penalty calculation correct for 24h / no-show cases
- [ ] Receipts generated as separate `.txt` files
- [ ] Tier quota enforced in booking
- [ ] Cross-platform paths (`os.path.join`)
- [ ] Comments on every non-trivial function
- [ ] Code readable by teammates (Member 2 & 3 can explain their sections)
- [ ] No `class` keyword anywhere in codebase
- [ ] No `import` of non-standard library modules

---

## 12. Submission Deliverables

1. **ZIP file** containing:
   - All `.py` files
   - `data/` folder with initial text files
   - (receipts/ and backup/ can be auto-created at runtime)
2. **Documentation `.docx`** with:
   - Cover page (APU logo, group info)
   - Table of contents
   - Introduction & Assumptions (use Section 8 of this brief)
   - System design (flowcharts + pseudocode)
   - Programming concepts applied (with code snippets)
   - Additional features explanation
   - Screenshots of execution
   - Conclusion & References (APA)
   - Appendix (workload matrix + file content screenshots)

Documentation will be drafted in a separate pass after code is complete.
