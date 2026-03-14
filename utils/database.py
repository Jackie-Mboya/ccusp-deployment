"""
database.py — PostgreSQL (Supabase) backend for CCUSP deployment.

Connection string is read from Streamlit secrets:
    [database]
    url = "postgresql://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres"

Falls back to SQLite for local development if no secret is configured.
"""

import os
import hashlib
import re
from datetime import datetime

import pandas as pd
import streamlit as st

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

PROVIDER_TYPES = ["Physician", "APN"]
INCOME_LEVELS  = ["High Income", "LMIC"]


# ── Password hashing ───────────────────────────────────────────────────────────
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


# ── Connection factory ─────────────────────────────────────────────────────────
def _get_conn():
    """
    Returns a pg8000 connection if Streamlit secrets contain [database].url,
    otherwise falls back to SQLite for local development.
    pg8000 is a pure-Python PostgreSQL driver — no binary dependencies,
    works reliably on Streamlit Cloud.
    """
    try:
        db_url = st.secrets["database"]["url"]
        import pg8000.dbapi
        from urllib.parse import urlparse, unquote
        p = urlparse(db_url)
        return pg8000.dbapi.connect(
            host=p.hostname,
            port=p.port or 5432,
            database=p.path.lstrip("/"),
            user=unquote(p.username),
            password=unquote(p.password),
            ssl_context=True,
        ), "postgres"
    except (KeyError, FileNotFoundError):
        # Local dev fallback — SQLite
        import sqlite3
        db_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
        db_path = os.path.join(db_dir, 'ccusp_users.db')
        os.makedirs(db_dir, exist_ok=True)
        return sqlite3.connect(db_path, check_same_thread=False), "sqlite"


def _placeholder(db_type: str, n: int = 1) -> str:
    """Return the correct placeholder for the DB type (%s for PG, ? for SQLite)."""
    ph = "%s" if db_type == "postgres" else "?"
    return ", ".join([ph] * n)


# ── Schema initialisation ──────────────────────────────────────────────────────
def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    conn, db_type = _get_conn()
    try:
        cur = conn.cursor()
        if db_type == "postgres":
            cur.execute("""
                CREATE TABLE IF NOT EXISTS practitioners (
                    id            SERIAL PRIMARY KEY,
                    username      TEXT UNIQUE NOT NULL,
                    email         TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name     TEXT NOT NULL,
                    specialty     TEXT NOT NULL,
                    hospital      TEXT NOT NULL,
                    country_income TEXT NOT NULL DEFAULT 'High Income',
                    provider_type  TEXT NOT NULL DEFAULT 'Physician',
                    registered_at  TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id             SERIAL PRIMARY KEY,
                    username       TEXT NOT NULL,
                    full_name      TEXT NOT NULL,
                    specialty      TEXT NOT NULL,
                    hospital       TEXT NOT NULL,
                    provider_type  TEXT NOT NULL,
                    country_income TEXT NOT NULL,
                    pop            TEXT,
                    yrs            TEXT,
                    icu_vol        TEXT,
                    hosp_type      TEXT,
                    extra_training TEXT,
                    cert           TEXT,
                    manages_icu    TEXT,
                    probability    REAL NOT NULL,
                    ccusp_class    INTEGER NOT NULL,
                    ccusp_label    TEXT NOT NULL,
                    threshold_used REAL NOT NULL,
                    predicted_at   TIMESTAMP DEFAULT NOW()
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS practitioners (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    username       TEXT UNIQUE NOT NULL,
                    email          TEXT UNIQUE NOT NULL,
                    password_hash  TEXT NOT NULL,
                    full_name      TEXT NOT NULL,
                    specialty      TEXT NOT NULL,
                    hospital       TEXT NOT NULL,
                    country_income TEXT NOT NULL DEFAULT 'High Income',
                    provider_type  TEXT NOT NULL DEFAULT 'Physician',
                    registered_at  TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    username       TEXT NOT NULL,
                    full_name      TEXT NOT NULL,
                    specialty      TEXT NOT NULL,
                    hospital       TEXT NOT NULL,
                    provider_type  TEXT NOT NULL,
                    country_income TEXT NOT NULL,
                    pop            TEXT,
                    yrs            TEXT,
                    icu_vol        TEXT,
                    hosp_type      TEXT,
                    extra_training TEXT,
                    cert           TEXT,
                    manages_icu    TEXT,
                    probability    REAL NOT NULL,
                    ccusp_class    INTEGER NOT NULL,
                    ccusp_label    TEXT NOT NULL,
                    threshold_used REAL NOT NULL,
                    predicted_at   TEXT NOT NULL
                )
            """)
        conn.commit()
    finally:
        conn.close()

def verify_predictions_table():
    """Check if predictions table has the expected columns"""
    conn, db_type = _get_conn()
    try:
        cur = conn.cursor()
        if db_type == "postgres":
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'predictions'
                ORDER BY ordinal_position
            """)
            columns = [col[0] for col in cur.fetchall()]
            print(f"✅ Predictions table columns: {columns}")
            
            # Check if confidence column exists
            if 'confidence' in columns:
                print("✅ confidence column exists")
            else:
                print("❌ confidence column MISSING - run ALTER TABLE")
                # Add it if missing
                cur.execute("ALTER TABLE predictions ADD COLUMN confidence TEXT")
                conn.commit()
                print("✅ Added confidence column")
        else:
            cur.execute("PRAGMA table_info(predictions)")
            columns = [col[1] for col in cur.fetchall()]
            print(f"✅ Predictions table columns: {columns}")
    except Exception as e:
        print(f"❌ Error verifying table: {e}")
    finally:
        conn.close()

# Call this after init_db() in app.py to ensure the new column is added in deployed environments.

# ── Registration ───────────────────────────────────────────────────────────────
def register_user(full_name, email, username, password,
                  specialty, hospital,
                  country_income="High Income",
                  provider_type="Physician"):
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

    conn, db_type = _get_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(f"""
            INSERT INTO practitioners
                (username, email, password_hash, full_name, specialty,
                 hospital, country_income, provider_type, registered_at)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
        """, (username, email, _h(password), full_name.strip(),
              specialty, hospital, country_income, provider_type, now))
        conn.commit()
        return True, ""
    except Exception as e:
        err = str(e).lower()
        if "username" in err or "unique" in err and "username" in err:
            return False, "Username already taken. Please choose another."
        if "email" in err:
            return False, "An account with that email already exists."
        return False, f"Registration failed: {e}"
    finally:
        conn.close()


# ── Authentication ─────────────────────────────────────────────────────────────
def authenticate(username, password):
    u = username.strip().lower()

    if u in _ADMINS:
        adm = _ADMINS[u]
        if adm["password_hash"] == _h(password):
            return {"username": u, **{k: v for k, v in adm.items() if k != "password_hash"}}
        return None

    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        ph  = "%s" if _ == "postgres" else "?"
        cur.execute(
            f"SELECT id,username,email,password_hash,full_name,specialty,"
            f"hospital,country_income,provider_type,registered_at "
            f"FROM practitioners WHERE username={ph}", (u,)
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return None
    cols = ["id","username","email","password_hash","full_name","specialty",
            "hospital","country_income","provider_type","registered_at"]
    rec = dict(zip(cols, row))
    if rec["password_hash"] != _h(password):
        return None
    return {
        "username":       rec["username"],
        "name":           rec["full_name"],
        "email":          rec["email"],
        "role":           "practitioner",
        "dept":           rec["specialty"],
        "hospital":       rec["hospital"],
        "specialty":      rec["specialty"],
        "country_income": rec["country_income"],
        "provider_type":  rec["provider_type"],
        "registered_at":  str(rec["registered_at"]),
    }


# ── Save prediction ────────────────────────────────────────────────────────────
# ── Save prediction ────────────────────────────────────────────────────────────
# ── Save prediction ────────────────────────────────────────────────────────────
def save_prediction(user: dict, inputs: dict, result: dict):
    conn, db_type = _get_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get confidence from result or calculate it
        confidence = result.get("confidence", "Moderate")
        
        cur.execute(f"""
            INSERT INTO predictions
                (username, full_name, specialty, hospital,
                 provider_type, country_income,
                 pop, yrs, icu_vol, hosp_type,
                 extra_training, cert, manages_icu,
                 probability, ccusp_class, ccusp_label,
                 threshold_used, confidence, predicted_at)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
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
            confidence,  # Add confidence here
            now,
        ))
        conn.commit()
    except Exception as e:
        import traceback
        print(f"[save_prediction ERROR] {e}")
        print(traceback.format_exc())
    finally:
        conn.close()

# ── Admin queries ──────────────────────────────────────────────────────────────
def get_predictions_df() -> pd.DataFrame:
    conn, db_type = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM predictions ORDER BY predicted_at DESC")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        if not df.empty and "predicted_at" in df.columns:
            df["predicted_at"] = pd.to_datetime(df["predicted_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        if not df.empty and "probability" in df.columns:
            df["probability"] = df["probability"].astype(float)
        return df
    except Exception as e:
        import traceback
        print(f"[get_predictions_df ERROR] {e}")
        print(traceback.format_exc())
        return pd.DataFrame()
    finally:
        conn.close()


def get_practitioners_df() -> pd.DataFrame:
    conn, db_type = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT full_name,specialty,hospital,country_income,"
            "provider_type,registered_at FROM practitioners ORDER BY registered_at DESC"
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        if not df.empty and "registered_at" in df.columns:
            df["registered_at"] = pd.to_datetime(df["registered_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        return df
    except Exception as e:
        import traceback
        print(f"[get_practitioners_df ERROR] {e}")
        print(traceback.format_exc())
        return pd.DataFrame()
    finally:
        conn.close()

def debug_check_tables():
    """Debug function to check if tables exist and have correct schema"""
    conn, db_type = _get_conn()
    try:
        cur = conn.cursor()
        if db_type == "postgres":
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = cur.fetchall()
            print(f"Tables in PostgreSQL: {tables}")
            
            # Check predictions table columns
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'predictions'
            """)
            columns = cur.fetchall()
            print(f"Predictions table columns: {columns}")
        else:
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cur.fetchall()
            print(f"Tables in SQLite: {tables}")
            
            cur.execute("PRAGMA table_info(predictions)")
            columns = cur.fetchall()
            print(f"Predictions table columns: {columns}")
    except Exception as e:
        print(f"Error checking tables: {e}")
    finally:
        conn.close()
        

def get_all_practitioners():
    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id,username,email,full_name,specialty,hospital,"
            "country_income,provider_type,registered_at "
            "FROM practitioners ORDER BY registered_at DESC"
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    cols = ["ID","Username","Email","Full Name","Specialty","Hospital",
            "Country Income","Provider Type","Registered At"]
    return [dict(zip(cols, r)) for r in rows]


def count_registered():
    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM practitioners")
        return cur.fetchone()[0]
    finally:
        conn.close()


def count_predictions():
    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM predictions")
        return cur.fetchone()[0]
    finally:
        conn.close()


def get_recent_registrations(n=5):
    conn, _ = _get_conn()
    ph = "%s" if _ == "postgres" else "?"
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT full_name,specialty,hospital,registered_at "
            f"FROM practitioners ORDER BY registered_at DESC LIMIT {ph}", (n,)
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [{"name": r[0], "specialty": r[1], "hospital": r[2], "registered_at": str(r[3])}
            for r in rows]


def delete_practitioner(username):
    conn, db_type = _get_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM practitioners WHERE username={ph}", (username,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_specialty_counts():
    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT specialty, COUNT(*) FROM practitioners GROUP BY specialty")
        return {r[0]: r[1] for r in cur.fetchall()}
    finally:
        conn.close()


def get_income_counts():
    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT country_income, COUNT(*) FROM practitioners GROUP BY country_income")
        return {r[0]: r[1] for r in cur.fetchall()}
    finally:
        conn.close()


def get_provider_counts():
    conn, _ = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT provider_type, COUNT(*) FROM practitioners GROUP BY provider_type")
        return {r[0]: r[1] for r in cur.fetchall()}
    finally:
        conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────
def role_color(role):
    return {"practitioner": "#1B6CA8", "admin": "#7C3AED"}.get(role, "#64748B")


def delete_practitioner_complete(username):
    """
    Delete a practitioner and all their predictions.
    Returns (success: bool, message: str).
    """
    conn, db_type = _get_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT full_name FROM practitioners WHERE username={ph}", (username,))
        user = cur.fetchone()
        if not user:
            return False, f"User '{username}' not found."
        full_name = user[0]
        cur.execute(f"DELETE FROM predictions WHERE username={ph}", (username,))
        predictions_deleted = cur.rowcount
        cur.execute(f"DELETE FROM practitioners WHERE username={ph}", (username,))
        user_deleted = cur.rowcount > 0
        conn.commit()
        if user_deleted:
            return True, (f"✅ Deleted {full_name} and "
                          f"{predictions_deleted} assessment"
                          f"{'s' if predictions_deleted != 1 else ''}.")
        return False, "Failed to delete user."
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


def get_user_predictions(username):
    conn, db_type = _get_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM predictions WHERE username={ph} ORDER BY predicted_at DESC",
            (username,))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        print(f"[get_user_predictions ERROR] {e}")
        return pd.DataFrame()
    finally:
        conn.close()