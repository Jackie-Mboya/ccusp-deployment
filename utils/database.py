"""
database.py — SQLite user registry for CCUSP demo system.

Stores registered practitioners. Admin accounts are hardcoded (never in DB).
File lives at: data/ccusp_users.db  (auto-created on first run)
"""

import os, sqlite3, hashlib, re
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────
DB_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
DB_PATH = os.path.join(DB_DIR, 'ccusp_users.db')

# ── Option lists ───────────────────────────────────────────────────────────────
SPECIALTIES = [
    "Medical ICU",
    "Cardiac Critical Care",
    "Anesthesia",
    "Neurology/Neuro Critical Care",
    "Emergency Medicine",
    "Pulmonology/Critical Care",
    "Surgical ICU",
    "Other",
]

HOSPITALS = [
    "Kenyatta National Hospital",
    "Nairobi Hospital",
    "Aga Khan University Hospital",
    "MP Shah Hospital",
    "Moi Teaching & Referral Hospital",
    "Coast Provincial General Hospital",
    "Eldoret District Hospital",
    "Kisumu County Hospital",
    "Other",
]

PROVIDER_TYPES  = ["Physician", "APN"]
INCOME_LEVELS   = ["High Income", "LMIC"]


# ── Hashing ────────────────────────────────────────────────────────────────────
def _h(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ── Hardcoded admin accounts (never stored in DB) ─────────────────────────────
_ADMINS = {
    "admin": {
        "password_hash": _h("admin2025"),
        "name":     "System Administrator",
        "dept":     "Administration",
        "hospital": "Central Administration",
        "email":    "admin@ccusp.ac.ke",
        "role":     "admin",
    },
    "dr.policy": {
        "password_hash": _h("admin2025"),
        "name":     "Dr. Policy Maker",
        "dept":     "Health Policy",
        "hospital": "Ministry of Health",
        "email":    "policy@moh.go.ke",
        "role":     "admin",
    },
}


# ── DB helpers ─────────────────────────────────────────────────────────────────
def _conn():
    os.makedirs(DB_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    """Create tables on first run. Safe to call on every startup."""
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS practitioners (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                username       TEXT    UNIQUE NOT NULL,
                email          TEXT    UNIQUE NOT NULL,
                password_hash  TEXT    NOT NULL,
                full_name      TEXT    NOT NULL,
                specialty      TEXT    NOT NULL,
                hospital       TEXT    NOT NULL,
                country_income TEXT    NOT NULL DEFAULT 'High Income',
                provider_type  TEXT    NOT NULL DEFAULT 'Physician',
                registered_at  TEXT    NOT NULL
            )
        """)
        # Prediction log — added for dynamic analytics
        con.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT NOT NULL,
                full_name       TEXT NOT NULL,
                specialty       TEXT NOT NULL,
                hospital        TEXT NOT NULL,
                provider_type   TEXT NOT NULL,
                country_income  TEXT NOT NULL,
                pop             TEXT,
                yrs             TEXT,
                icu_vol         TEXT,
                hosp_type       TEXT,
                extra_training  TEXT,
                cert            TEXT,
                manages_icu     TEXT,
                probability     REAL NOT NULL,
                ccusp_class     INTEGER NOT NULL,
                ccusp_label     TEXT NOT NULL,
                threshold_used  REAL NOT NULL,
                predicted_at    TEXT NOT NULL
            )
        """)
        con.commit()


# ── Registration ───────────────────────────────────────────────────────────────
def register_user(full_name, email, username, password,
                  specialty, hospital,
                  country_income="High Income",
                  provider_type="Physician"):
    """
    Register a new practitioner.
    Returns (True, "") on success or (False, error_message) on failure.
    """
    username = username.strip().lower()
    email    = email.strip().lower()

    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False, "Please enter a valid email address."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if not full_name.strip():
        return False, "Full name is required."
    if username in _ADMINS:
        return False, "That username is reserved. Please choose another."

    try:
        with _conn() as con:
            con.execute("""
                INSERT INTO practitioners
                    (username, email, password_hash, full_name, specialty,
                     hospital, country_income, provider_type, registered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, email, _h(password), full_name.strip(),
                  specialty, hospital, country_income, provider_type,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            con.commit()
        return True, ""
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return False, "Username already taken. Please choose another."
        if "email" in str(e):
            return False, "An account with that email already exists."
        return False, "Registration failed. Please try again."


# ── Authentication ─────────────────────────────────────────────────────────────
def authenticate(username, password):
    """Returns user dict on success, None on failure."""
    u = username.strip().lower()

    # Admins first
    if u in _ADMINS:
        adm = _ADMINS[u]
        if adm["password_hash"] == _h(password):
            return {"username": u, **{k: v for k, v in adm.items() if k != "password_hash"}}
        return None

    # Practitioner DB
    with _conn() as con:
        row = con.execute(
            "SELECT id,username,email,password_hash,full_name,specialty,"
            "hospital,country_income,provider_type,registered_at "
            "FROM practitioners WHERE username=?", (u,)
        ).fetchone()
    if row is None:
        return None
    rec = dict(zip(["id","username","email","password_hash","full_name","specialty",
                    "hospital","country_income","provider_type","registered_at"], row))
    if rec["password_hash"] != _h(password):
        return None
    return {
        "username":      rec["username"],
        "name":          rec["full_name"],
        "email":         rec["email"],
        "role":          "practitioner",
        "dept":          rec["specialty"],
        "hospital":      rec["hospital"],
        "specialty":     rec["specialty"],
        "country_income":rec["country_income"],
        "provider_type": rec["provider_type"],
        "registered_at": rec["registered_at"],
    }


# ── Prediction log ─────────────────────────────────────────────────────────────
def save_prediction(user: dict, inputs: dict, result: dict):
    """Persist one prediction so admin analytics are fully dynamic."""
    try:
        with _conn() as con:
            con.execute("""
                INSERT INTO predictions
                    (username, full_name, specialty, hospital,
                     provider_type, country_income,
                     pop, yrs, icu_vol, hosp_type,
                     extra_training, cert, manages_icu,
                     probability, ccusp_class, ccusp_label,
                     threshold_used, predicted_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                user.get("username", ""),
                user.get("name", ""),
                user.get("specialty", inputs.get("specialty", "")),
                user.get("hospital", ""),
                user.get("provider_type", inputs.get("provider_type", "")),
                user.get("country_income", inputs.get("income", "")),
                inputs.get("pop", ""),
                inputs.get("yrs", ""),
                inputs.get("icu_vol", ""),
                inputs.get("hosp_type", ""),
                inputs.get("extra", ""),
                inputs.get("cert", ""),
                inputs.get("manages", ""),
                result["probability"],
                result["class"],
                result["label"],
                result["threshold"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))
            con.commit()
    except Exception as e:
        print(f"Error saving prediction: {e}")  # Log the error for debugging
        pass  # log failure must never crash the app


# ── Admin queries ──────────────────────────────────────────────────────────────
def get_all_practitioners():
    with _conn() as con:
        rows = con.execute(
            "SELECT id,username,email,full_name,specialty,hospital,"
            "country_income,provider_type,registered_at "
            "FROM practitioners ORDER BY registered_at DESC"
        ).fetchall()
    cols = ["ID","Username","Email","Full Name","Specialty","Hospital",
            "Country Income","Provider Type","Registered At"]
    return [dict(zip(cols, r)) for r in rows]


def count_registered():
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM practitioners").fetchone()[0]


def count_predictions():
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]


def get_specialty_counts():
    with _conn() as con:
        rows = con.execute(
            "SELECT specialty, COUNT(*) FROM practitioners GROUP BY specialty"
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_income_counts():
    with _conn() as con:
        rows = con.execute(
            "SELECT country_income, COUNT(*) FROM practitioners GROUP BY country_income"
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_provider_counts():
    with _conn() as con:
        rows = con.execute(
            "SELECT provider_type, COUNT(*) FROM practitioners GROUP BY provider_type"
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def get_recent_registrations(n=5):
    with _conn() as con:
        rows = con.execute(
            "SELECT full_name,specialty,hospital,registered_at "
            "FROM practitioners ORDER BY registered_at DESC LIMIT ?", (n,)
        ).fetchall()
    return [{"name": r[0], "specialty": r[1], "hospital": r[2], "registered_at": r[3]}
            for r in rows]


def delete_practitioner(username):
    """
    Delete a practitioner and ALL their associated predictions.
    Returns True if user was deleted, False otherwise.
    """
    conn = None
    try:
        conn = _conn()
        cursor = conn.cursor()
        
        # First get the user to confirm it exists
        cursor.execute("SELECT full_name FROM practitioners WHERE username=?", (username,))
        user = cursor.fetchone()
        
        if not user:
            return False
        
        # Delete ALL predictions for this username FIRST
        cursor.execute("DELETE FROM predictions WHERE username=?", (username,))
        predictions_deleted = cursor.rowcount
        print(f"Deleted {predictions_deleted} predictions for user {username}")
        
        # Then delete the practitioner
        cursor.execute("DELETE FROM practitioners WHERE username=?", (username,))
        user_deleted = cursor.rowcount > 0
        
        conn.commit()
        print(f"Successfully deleted user {username} and {predictions_deleted} predictions")
        return user_deleted
        
    except Exception as e:
        print(f"Error in delete_practitioner: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def delete_practitioner_complete(username):
    """
    Enhanced version with better feedback.
    Returns (success, message) tuple.
    """
    conn = None
    try:
        conn = _conn()
        cursor = conn.cursor()
        
        # Get user info first
        cursor.execute("SELECT full_name FROM practitioners WHERE username=?", (username,))
        user = cursor.fetchone()
        
        if not user:
            return False, f"User '{username}' not found"
        
        full_name = user[0]
        
        # Delete all predictions
        cursor.execute("DELETE FROM predictions WHERE username=?", (username,))
        predictions_deleted = cursor.rowcount
        
        # Delete the user
        cursor.execute("DELETE FROM practitioners WHERE username=?", (username,))
        user_deleted = cursor.rowcount > 0
        
        conn.commit()
        
        if user_deleted:
            message = f"✅ Deleted {full_name} and {predictions_deleted} assessment{'s' if predictions_deleted != 1 else ''}"
            return True, message
        else:
            return False, "Failed to delete user"
            
    except Exception as e:
        if conn:
            conn.rollback()
        return False, f"Error: {str(e)}"
    finally:
        if conn:
            conn.close()


def get_predictions_df():
    """Return all predictions as DataFrame for dynamic charting."""
    import pandas as pd
    with _conn() as con:
        df = pd.read_sql_query(
            "SELECT * FROM predictions ORDER BY predicted_at DESC", con
        )
    return df


def get_practitioners_df():
    """Return all practitioners as DataFrame."""
    import pandas as pd
    with _conn() as con:
        df = pd.read_sql_query(
            "SELECT full_name,specialty,hospital,country_income,"
            "provider_type,registered_at FROM practitioners ORDER BY registered_at DESC",
            con
        )
    return df


def get_user_predictions(username):
    """Get all predictions for a specific user."""
    import pandas as pd
    with _conn() as con:
        df = pd.read_sql_query(
            "SELECT * FROM predictions WHERE username=? ORDER BY predicted_at DESC",
            con, params=(username,)
        )
    return df


# ── Helpers ────────────────────────────────────────────────────────────────────
def role_color(role):
    return {"practitioner": "#1B6CA8", "admin": "#7C3AED"}.get(role, "#64748B")