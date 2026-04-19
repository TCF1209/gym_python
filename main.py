"""
main.py -- Entry point for the FitZone Gym Management System.

Responsibilities:
  1. Force UTF-8 on Windows so box-drawing and bar characters render.
  2. On first run (or empty data/), call seed_data.seed_all() before login.
  3. Show the login screen. Accept up to 3 total attempts across all
     usernames; the user can type 'q' at the username prompt to exit.
  4. After a successful login, run the auto-maintenance tasks in order:
       - auto_mark_no_shows (flips stale Confirmed -> No-Show, creates
         Pending penalty payments, logs AUTO_NO_SHOW audit entries)
       - auto_suspend_expired_members (flips past-grace Active ->
         Suspended, logs AUTO_SUSPEND)
     Print a combined summary: '✓ System ready.' if nothing changed,
     otherwise a '⚠️ ...' line with non-zero counts only.
  5. Route to the matching role menu (Administrator / BookingOfficer /
     Accountant). Menu handlers in admin.py / booking.py / accountant.py
     are stubs at this point; main.py displays the menus and shows a
     placeholder for non-logout choices.
  6. On logout, loop back to the login screen. Quitting from login
     ends the program.

Audit entries written here (in addition to the System-role AUTO_*
entries from utils):
  - {Role} | LOGIN  | {username}
  - {Role} | LOGOUT | {username}
"""

import utils
import seed_data


# ============================================================
# CONSTANTS
# ============================================================

# Max login tries across the whole session (not per username).
LOGIN_ATTEMPTS_MAX = 3

# Menu box width. Chosen so the widest header fits with padding:
#   " BOOKING OFFICER DASHBOARD — Logged in as accountant"  == 52 chars
MENU_WIDTH = 56

# Placeholder for menu choices that aren't implemented yet (role modules
# will take over after their respective files are written).
PLACEHOLDER_LINE = "[Menu action coming next -- to be implemented in the role module.]"


# ============================================================
# BOXED OUTPUT HELPERS
# ============================================================

def _box_top():
    print(f"╔{'═' * MENU_WIDTH}╗")


def _box_middle_divider():
    print(f"╠{'═' * MENU_WIDTH}╣")


def _box_bottom():
    print(f"╚{'═' * MENU_WIDTH}╝")


def _box_line(content):
    """Print one boxed line, padding content to the fixed MENU_WIDTH."""
    # Always leave one space after ║ for readability.
    inner = f" {content}"
    pad = MENU_WIDTH - len(inner)
    if pad < 0:
        # Fall back: truncate rather than break the box.
        inner = inner[:MENU_WIDTH]
        pad = 0
    print(f"║{inner}{' ' * pad}║")


# ============================================================
# LOGIN
# ============================================================

def _display_login_banner():
    """Show the login screen banner and quit hint."""
    print()
    _box_top()
    _box_line("FitZone Gym Management System")
    _box_line("Staff Login")
    _box_bottom()
    print("  Type 'q' at the username prompt to exit.\n")


def login():
    """
    Prompt for credentials up to LOGIN_ATTEMPTS_MAX total tries.
    Returns (role, username) on success, or (None, None) if the user
    types 'q' or exhausts all attempts.
    """
    _display_login_banner()

    attempts_left = LOGIN_ATTEMPTS_MAX
    while attempts_left > 0:
        username = input(
            f"  Username (attempts left: {attempts_left}) or 'q' to quit: "
        ).strip()
        if username.lower() == "q":
            return None, None

        password = input("  Password: ").strip()
        role = utils.authenticate(username, password)
        if role is not None:
            print(f"\n✓ Welcome, {username}! Signed in as {role}.")
            return role, username

        attempts_left -= 1
        if attempts_left > 0:
            print(f"✗ Invalid credentials. {attempts_left} attempt(s) remaining.\n")
        else:
            print("✗ Too many failed login attempts. Exiting.")
    return None, None


# ============================================================
# POST-LOGIN AUTO-MAINTENANCE
# ============================================================

def run_post_login_tasks():
    """
    Run auto_mark_no_shows, then auto_suspend_expired_members.
    Print the combined summary per product decision:
      - ✓ System ready.   (when both counts are zero)
      - ⚠️  ...            (otherwise, only non-zero parts shown)
    """
    affected_no_show = utils.auto_mark_no_shows("System")
    affected_suspend = utils.auto_suspend_expired_members("System")

    n_no_show = len(affected_no_show)
    n_suspend = len(affected_suspend)

    if n_no_show == 0 and n_suspend == 0:
        print("\n✓ System ready.")
        return

    parts = []
    if n_no_show > 0:
        noun = "no-show" if n_no_show == 1 else "no-shows"
        parts.append(f"Auto-processed {n_no_show} {noun}.")
    if n_suspend > 0:
        noun = "member" if n_suspend == 1 else "members"
        parts.append(f"{n_suspend} {noun} suspended.")

    print(f"\n⚠️  {' '.join(parts)}")


# ============================================================
# ROLE MENUS
# ============================================================
# Each menu has a single responsibility: display options, read a valid
# choice, return it. The "session" functions own the loop and routing.

def _display_role_menu(title, username, options):
    """
    Draw the boxed menu for a role.

    Args:
        title:    e.g. "ADMINISTRATOR DASHBOARD"
        username: login username shown on the header
        options:  list of (number_str, label) tuples in display order,
                  including the final 'Logout' entry
    """
    header = f"{title} — Logged in as {username}"
    print()
    _box_top()
    _box_line(header)
    _box_middle_divider()
    for number, label in options:
        _box_line(f"{number}. {label}")
    _box_bottom()


def _ask_menu_choice(options):
    """
    Prompt the user to enter one of the menu numbers.
    'options' is the same list of (number_str, label) tuples.
    Returns the chosen number string.
    """
    valid_numbers = []
    for number, _ in options:
        valid_numbers.append(number)
    prompt = f"  Enter choice [{valid_numbers[0]}-{valid_numbers[-1]}]: "
    return utils.get_valid_menu_choice(prompt, valid_numbers)


# --- Administrator -----------------------------------------------

ADMIN_OPTIONS = [
    ("1", "Manage Classes"),
    ("2", "Manage Trainers"),
    ("3", "View All Members"),
    ("4", "View All Bookings"),
    ("5", "View All Payments"),
    ("6", "System Report"),
    ("7", "Peak Hours Analytics [F6]"),
    ("8", "Analytics Dashboard [F9]"),
    ("9", "Logout"),
]


def run_admin_session(username):
    """Administrator menu loop. Full logic moves to admin.py later."""
    while True:
        _display_role_menu("ADMINISTRATOR DASHBOARD", username, ADMIN_OPTIONS)
        choice = _ask_menu_choice(ADMIN_OPTIONS)
        if choice == "9":
            utils.log_audit("Administrator", "LOGOUT", username)
            print("\n✓ Logged out.")
            return
        print(f"\n{PLACEHOLDER_LINE}")
        utils.pause()


# --- Booking Officer ---------------------------------------------

BOOKING_OPTIONS = [
    ("1", "Register New Member"),
    ("2", "Create New Booking"),
    ("3", "Cancel Booking"),
    ("4", "Reschedule Booking"),
    ("5", "View Member Booking History"),
    ("6", "View All Bookings"),
    ("7", "Logout"),
]


def run_booking_session(username):
    """Booking Officer menu loop. Full logic moves to booking.py later."""
    while True:
        _display_role_menu("BOOKING OFFICER DASHBOARD", username, BOOKING_OPTIONS)
        choice = _ask_menu_choice(BOOKING_OPTIONS)
        if choice == "7":
            utils.log_audit("BookingOfficer", "LOGOUT", username)
            print("\n✓ Logged out.")
            return
        print(f"\n{PLACEHOLDER_LINE}")
        utils.pause()


# --- Accountant --------------------------------------------------

ACCOUNTANT_OPTIONS = [
    ("1", "Record Membership Payment"),
    ("2", "Record Penalty Payment"),
    ("3", "Generate Receipt [F2]"),
    ("4", "View Payment Records"),
    ("5", "Income Report"),
    ("6", "Track Unpaid Memberships"),
    ("7", "Logout"),
]


def run_accountant_session(username):
    """Accountant menu loop. Full logic moves to accountant.py later."""
    while True:
        _display_role_menu("ACCOUNTANT DASHBOARD", username, ACCOUNTANT_OPTIONS)
        choice = _ask_menu_choice(ACCOUNTANT_OPTIONS)
        if choice == "7":
            utils.log_audit("Accountant", "LOGOUT", username)
            print("\n✓ Logged out.")
            return
        print(f"\n{PLACEHOLDER_LINE}")
        utils.pause()


# ============================================================
# ROUTING
# ============================================================

def route(role, username):
    """Dispatch to the menu loop for the authenticated role."""
    if role == "Administrator":
        run_admin_session(username)
    elif role == "BookingOfficer":
        run_booking_session(username)
    elif role == "Accountant":
        run_accountant_session(username)
    else:
        # Defensive: credentials.txt is the only source of roles, so this
        # branch should never fire -- but we refuse to loop blindly.
        print(f"✗ Unknown role '{role}' in credentials. Aborting session.")


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    """Top-level program loop: seed-if-needed -> login -> role menu -> repeat."""
    utils.enable_utf8_on_windows()

    if seed_data.needs_seeding():
        print("🌱 First run detected -- seeding demo data...")
        seed_data.seed_all()
        print("✓ Seed complete.\n")

    while True:
        role, username = login()
        if role is None:
            print("\nGoodbye!")
            return
        utils.log_audit(role, "LOGIN", username)
        run_post_login_tasks()
        utils.pause()
        route(role, username)
        # route() returns on logout; loop restarts at the login screen.


if __name__ == "__main__":
    main()
