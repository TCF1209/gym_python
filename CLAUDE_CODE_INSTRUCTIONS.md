# Claude Code Instructions — FitZone Gym System

**Purpose**: This file is a tight, instruction-level brief for Claude Code. Read this BEFORE `PROJECT_BRIEF.md`. These rules override any default behavior and must be respected throughout the entire codebase.

---

## 🚨 Hard Constraints (Zero Exceptions)

### ❌ ABSOLUTELY FORBIDDEN

1. **NO Object-Oriented Programming**
   - No `class` keyword anywhere
   - No inheritance, no `@classmethod`, no `@staticmethod`
   - No `self` parameter
   - No dataclasses, no namedtuples with methods
   - Represent "entities" (members, classes, bookings) as **dictionaries** passed between functions
   - Example: `member = {"id": "M001", "name": "John", "tier": "Premium"}`

2. **NO External Libraries**
   - Nothing that requires `pip install`
   - Specifically banned: `pandas`, `numpy`, `matplotlib`, `tabulate`, `colorama`, `rich`, `click`, `pytest`, `requests`, etc.
   - If you think you need one, **use a built-in alternative or write it manually**

3. **NO Databases**
   - No SQLite (even though it's built-in — the assignment explicitly bans DBs)
   - No in-memory DB libraries
   - All persistence goes through plain text files

4. **NO Advanced Python Features That Teammates Can't Explain**
   - Avoid complex list/dict comprehensions (nested ones especially)
   - Avoid lambda functions in non-trivial places
   - Avoid decorators
   - Avoid generators with `yield`
   - Avoid `*args`, `**kwargs` unless absolutely essential
   - Avoid walrus operator `:=`
   - Avoid type hints (keep code beginner-friendly)

   **Rationale**: 2 of 3 team members have limited Python experience. They must be able to read the code and explain it during Q&A. Readability > cleverness.

---

### ✅ ALLOWED (Built-in Standard Library)

These `import`s are acceptable:
```python
import os
import os.path
from datetime import datetime, timedelta
import random
```

**NOT recommended** (but not forbidden):
- `csv` — pipe delimiter is preferred; don't default to csv module
- `json` — don't use; the brief specifies pipe-delimited format

---

## 🎯 Code Style Rules

### Structure
1. **Every module starts with a docstring** explaining its purpose
2. **Every function has a docstring** with 1-line purpose + args/returns
3. **Constants at top of file** in SCREAMING_SNAKE_CASE
4. **Main logic wrapped in** `if __name__ == "__main__":` block

### Naming
- `snake_case` for functions and variables
- `SCREAMING_SNAKE_CASE` for constants
- Descriptive names: `calculate_cancellation_penalty()` not `calc_pen()`
- Boolean functions start with `is_` / `has_` / `can_`: `is_valid_date()`, `can_book_class()`

### Comments
- Comment the **"why"**, not the "what"
- Every non-trivial logic block gets a short comment
- Example:
  ```python
  # Penalty only applies if cancellation is within 24h of class start time
  if hours_until_class < 24:
      penalty = LATE_CANCEL_PENALTY_RM
  ```

### Error Handling
- Every file read/write wrapped in `try/except`
- User-friendly error messages (not raw exception strings)
- Example:
  ```python
  try:
      with open(MEMBERS_FILE, "r") as f:
          lines = f.readlines()
  except FileNotFoundError:
      print("⚠️  Members file not found. Starting with empty member list.")
      lines = []
  except Exception as e:
      print(f"⚠️  Error reading members: {e}")
      lines = []
  ```

### Input Validation
- Wrap every `input()` with a validation loop
- Create reusable validators in `utils.py`:
  - `get_valid_int(prompt, min_val, max_val)`
  - `get_valid_date(prompt)` — returns datetime object
  - `get_valid_choice(prompt, valid_options)`
  - `get_non_empty_string(prompt)`
  - `get_valid_phone(prompt)` — Malaysian format 01X-XXXXXXX
  - `get_valid_email(prompt)` — basic `@` and `.` check

---

## 📂 File Handling Pattern

### Consistent Read/Write Pattern

Every data file follows this pattern in `utils.py`:

```python
DATA_DIR = "data"
MEMBERS_FILE = os.path.join(DATA_DIR, "members.txt")

def read_members():
    """Read all members from file and return as list of dicts."""
    members = []
    try:
        with open(MEMBERS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) == 10:  # expected field count
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
                        "status": parts[9]
                    }
                    members.append(member)
    except FileNotFoundError:
        pass  # file will be created on first write
    except Exception as e:
        print(f"⚠️  Error reading members: {e}")
    return members

def write_members(members):
    """Write all members back to file, overwriting."""
    try:
        with open(MEMBERS_FILE, "w") as f:
            for m in members:
                line = "|".join([
                    m["id"], m["name"], str(m["age"]), m["gender"],
                    m["phone"], m["email"], m["tier"],
                    m["join_date"], m["expiry_date"], m["status"]
                ])
                f.write(line + "\n")
    except Exception as e:
        print(f"⚠️  Error writing members: {e}")
```

**Apply this pattern** for every entity (classes, trainers, bookings, payments).

---

## 🎨 Terminal UI Rules

### Visual Style
- Use box-drawing characters for menus: `═ ║ ╔ ╗ ╚ ╝ ╠ ╣`
- Section dividers: `──────` or `═══════`
- Consistent width (recommend 50 chars for menus)
- Clear line spacing (blank lines between sections)

### Menu Structure
```python
def display_admin_menu():
    print()
    print("╔" + "═" * 44 + "╗")
    print("║  ADMINISTRATOR DASHBOARD" + " " * 19 + "║")
    print("╠" + "═" * 44 + "╣")
    print("║  1. Manage Classes" + " " * 25 + "║")
    # ... etc
    print("╚" + "═" * 44 + "╝")
```

### Feedback Messages
- Success: `✓ Member M001 registered successfully`
- Warning: `⚠️  This booking is within 24h — RM10 penalty applies`
- Error: `✗ Invalid member ID`
- Info: `ℹ️  Press Enter to continue...`

After every action, pause with `input("\nPress Enter to continue...")` before returning to menu.

---

## 📊 ASCII Chart Rendering (Signature Feature)

Create a helper in `utils.py`:

```python
def render_ascii_bar(label, value, max_value, bar_width=30, char="█"):
    """
    Render a single ASCII bar for visualizations.

    Args:
        label: text on the left
        value: the numeric value
        max_value: the maximum value in the dataset (for scaling)
        bar_width: max width of the bar in characters
        char: the character used to fill the bar
    Returns:
        Formatted string like: "Yoga      ████████████ 45"
    """
    if max_value == 0:
        filled = 0
    else:
        filled = int((value / max_value) * bar_width)
    bar = char * filled
    return f"{label:<12} {bar} {value}"
```

Use this consistently in F6 and F9 so all charts look uniform.

---

## 🔑 Constants to Define (in `utils.py`)

```python
# Pricing
BASIC_MONTHLY_FEE = 80.00
PREMIUM_MONTHLY_FEE = 150.00
VIP_MONTHLY_FEE = 250.00

# Tier Quotas
BASIC_QUOTA = 5
PREMIUM_QUOTA = 15
VIP_QUOTA = 9999  # sentinel for "unlimited"

# Penalties
LATE_CANCEL_PENALTY_RM = 10.00
NO_SHOW_PENALTY_RM = 20.00
CANCELLATION_WINDOW_HOURS = 24

# Class Capacities
CLASS_CAPACITY = {
    "Yoga": 15,
    "HIIT": 12,
    "Boxing": 8,
    "Zumba": 15,
    "Spinning": 12
}

# File paths (using os.path.join for cross-platform)
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
```

---

## 🧪 Build Order (Suggested Sequence)

Build in this order to avoid integration hell:

1. **`utils.py` first** — all helpers, constants, file I/O, validators, ASCII bar
2. **`seed_data.py`** — generates initial demo data (test utils.py works)
3. **`main.py`** — login flow + menu router (without role implementations)
4. **`admin.py`** — CRUD for classes & trainers, view operations
5. **`booking.py`** — member registration, booking creation with ID gen, cancellation with penalty
6. **`accountant.py`** — payment recording, receipt generation, income report
7. **Admin F6 Peak Hours** — needs bookings data populated
8. **Admin F9 Dashboard** — needs all data populated
9. **F7 Audit Log** — weave `log_audit()` calls into every mutation
10. **Final polish** — error handling consistency, comment pass, quality checklist

---

## 🎤 Demo-Critical Requirements

The Demo happens live in 20 minutes. These MUST work flawlessly:

1. **First run**: `python main.py` → data auto-populates → login screen appears
2. **Admin login** → F9 Dashboard renders a complete multi-section ASCII report
3. **Booking Officer login** → create booking → **receipt-worthy confirmation** showing auto-generated BK ID
4. **Accountant login** → record payment → `.txt` receipt file generated in `receipts/` folder
5. **Audit log** → viewable by admin, shows all demo actions chronologically

Prioritize these demo paths working over marginal edge cases.

---

## 🗣️ Teammate Explainability Checklist

Before marking code as "done", ask:

- Could a beginner read this function and explain it in 30 seconds?
- Are variable names self-documenting (no single-letter vars outside loops)?
- Is there a comment explaining any business logic decision?
- Would a different team member know which file/function handles this feature?

If any answer is "no" — simplify before moving on.

---

## ⚠️ Common Traps to Avoid

1. **Don't use `dict.get()` with complex fallbacks** — use `if key in dict:` for clarity
2. **Don't chain string operations** — break into multiple steps
3. **Don't nest loops > 2 deep** — extract inner loop into a function
4. **Don't use ternary `x if cond else y`** in complex expressions — use regular if/else
5. **Don't silently catch exceptions** — always print user-friendly message
6. **Don't hardcode paths** — always use `os.path.join` and constants
7. **Don't forget to call `log_audit()`** on mutations — F7 needs comprehensive logging
8. **Don't let menus loop infinitely without exit option** — every menu has a "back/logout" choice

---

## 📋 Deliverables Expected from Claude Code

After one full pass, you should produce:

1. `main.py` — complete, runnable
2. `admin.py` — all admin features including F6 & F9
3. `booking.py` — all booking ops with F1 auto-ID
4. `accountant.py` — payments + F2 receipt generator
5. `utils.py` — all shared helpers, constants, file I/O, F7 audit logger
6. `seed_data.py` — populates realistic demo data
7. `data/` folder created on first run with initial files
8. `receipts/` folder created when first receipt generated

---

## 🏁 Definition of Done

- [ ] `python main.py` runs without error on Windows, macOS, Linux
- [ ] First run auto-populates demo data
- [ ] All 3 roles can log in and access their menus
- [ ] All CRUD operations functional
- [ ] All 5 extra features (F1, F2, F6, F7, F9) implemented and visible
- [ ] Every input validated
- [ ] Every file op has error handling
- [ ] Code is readable by junior Python students
- [ ] No `class`, no external libraries, no databases
- [ ] `audit.log` captures all mutations
