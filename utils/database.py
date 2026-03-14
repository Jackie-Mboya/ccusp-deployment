"""
database.py — PostgreSQL (Supabase) + SQLite fallback for CCUSP deployment.

On Streamlit Cloud: reads connection string from secrets → uses Supabase PostgreSQL
Locally: falls back to SQLite automatically

Secrets format (in Streamlit Cloud settings):
    [database]
    url = "postgresql://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres"
"""

import os
import hashlib
import re
from datetime import datetime
import pandas as pd

# ── Option lists ───────────────────────────────────────────────────────────────
SPECIALTIES = [
    "Medical ICU", "Cardiac Critical Care", "Anesthesia",
    "Neurology/Neuro Critical Care", "Emergency Medicine",
    "Pulmonology/Critical Care", "Surgical ICU", "Other",
]
HOSPITALS = [
    "Kenyatta National Hospital", "Nairobi Hospital",
    "Aga Khan University Hospital", "MP Shah Hospital",
    "Moi Teaching & Referral Hospital", "Coast Provincial General Hospital",
    "Eldoret District Hospital", "Kisumu County Hospital", "Other",
]
PROVIDER_TYPES = ["Physician", "APN"]
INCOME_LEVELS  = ["High Income", "LMIC"]

# ── Hashing ────────────────────────────────────────────────────────────────────
def _h(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# ── Admins ─────────────────────────────────────────────────────────────────────
_ADMINS = {
    "admin": {
        "password_hash": _h("admin2025"),
        "name": "System Administrator", "dept": "Administration",
        "hospital": "Central Administration", "email": "admin@ccusp.ac.ke",
        "role": "admin",
    },
    "dr.policy": {
        "password_hash": _h("admin2025"),
        "name": "Dr. Policy Maker", "dept": "Health Policy",
        "hospital": "Ministry of Health", "email": "policy@moh.go.ke",
        "role": "admin",
    },
}

# ── Connection factory ─────────────────────────────────────────────────────────
def _get_engine():
    """
    Returns a SQLAlchemy engine.
    Uses Supabase PostgreSQL if secret is available, otherwise SQLite.
    SQLAlchemy works perfectly with pd.read_sql_query — no warnings.
    """
    from sqlalchemy import create_engine
    try:
        import streamlit as st
        db_url = st.secrets["database"]["url"]
        # SQLAlchemy needs postgresql:// not postgres://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url), "postgres"
    except Exception:
        db_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, 'ccusp_users.db')
        return create_engine(f"sqlite:///{db_path}"), "sqlite"


def _get_raw_conn():
    """
    Returns a raw DBAPI connection for INSERT/UPDATE/DELETE operations.
    """
    try:
        import streamlit as st
        db_url = st.secrets["database"]["url"]
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        import psycopg2
        return psycopg2.connect(db_url), "postgres"
    except Exception:
        import sqlite3
        db_dir  = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, 'ccusp_users.db')
        return sqlite3.connect(db_path, check_same_thread=False), "sqlite"


# ── Schema initialisation ──────────────────────────────────────────────────────
def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    conn, db_type = _get_raw_conn()
    try:
        cur = conn.cursor()
        if db_type == "postgres":
            cur.execute("""
                CREATE TABLE IF NOT EXISTS practitioners (
                    id             SERIAL PRIMARY KEY,
                    username       TEXT UNIQUE NOT NULL,
                    email          TEXT UNIQUE NOT NULL,
                    password_hash  TEXT NOT NULL,
                    full_name      TEXT NOT NULL,
                    specialty      TEXT NOT NULL,
                    hospital       TEXT NOT NULL,
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
                    confidence     TEXT,
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
                    confidence     TEXT,
                    predicted_at   TEXT NOT NULL
                )
            """)
        conn.commit()
    except Exception as e:
        print(f"[init_db ERROR] {e}")
    finally:
        conn.close()


# ── Registration ───────────────────────────────────────────────────────────────
def register_user(full_name, email, username, password,
                  specialty, hospital,
                  country_income="High Income", provider_type="Physician"):
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

    conn, db_type = _get_raw_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(f"""
            INSERT INTO practitioners
                (username,email,password_hash,full_name,specialty,
                 hospital,country_income,provider_type,registered_at)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
        """, (username, email, _h(password), full_name.strip(),
              specialty, hospital, country_income, provider_type, now))
        conn.commit()
        return True, ""
    except Exception as e:
        err = str(e).lower()
        if "username" in err or ("unique" in err and "username" in err):
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

    conn, db_type = _get_raw_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id,username,email,password_hash,full_name,specialty,"
            f"hospital,country_income,provider_type,registered_at "
            f"FROM practitioners WHERE username={ph}", (u,)
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    cols = ["id","username","email","password_hash","full_name","specialty",
            "hospital","country_income","provider_type","registered_at"]
    rec = dict(zip(cols, row))
    if rec["password_hash"] != _h(password):
        return None
    return {
        "username": rec["username"], "name": rec["full_name"],
        "email": rec["email"], "role": "practitioner",
        "dept": rec["specialty"], "hospital": rec["hospital"],
        "specialty": rec["specialty"], "country_income": rec["country_income"],
        "provider_type": rec["provider_type"],
        "registered_at": str(rec["registered_at"]),
    }


# ── Save prediction ────────────────────────────────────────────────────────────
def save_prediction(user: dict, inputs: dict, result: dict):
    conn, db_type = _get_raw_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(f"""
            INSERT INTO predictions
                (username,full_name,specialty,hospital,
                 provider_type,country_income,
                 pop,yrs,icu_vol,hosp_type,
                 extra_training,cert,manages_icu,
                 probability,ccusp_class,ccusp_label,
                 threshold_used,confidence,predicted_at)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
        """, (
            user.get("username",""), user.get("name",""),
            user.get("specialty", inputs.get("specialty","")),
            user.get("hospital",""),
            user.get("provider_type", inputs.get("provider_type","")),
            user.get("country_income", inputs.get("income","")),
            inputs.get("pop",""), inputs.get("yrs",""),
            inputs.get("icu_vol",""), inputs.get("hosp_type",""),
            inputs.get("extra",""), inputs.get("cert",""),
            inputs.get("manages",""),
            result["probability"], result["class"],
            result["label"], result["threshold"],
            result.get("confidence","Moderate"),
            now,
        ))
        conn.commit()
    except Exception as e:
        print(f"[save_prediction ERROR] {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        conn.close()


# ── Read queries (use SQLAlchemy engine — works with pd.read_sql_query) ────────
def get_predictions_df() -> pd.DataFrame:
    try:
        engine, _ = _get_engine()
        with engine.connect() as con:
            df = pd.read_sql_query(
                "SELECT * FROM predictions ORDER BY predicted_at DESC", con)
        if not df.empty and "predicted_at" in df.columns:
            df["predicted_at"] = pd.to_datetime(df["predicted_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        if not df.empty and "probability" in df.columns:
            df["probability"] = df["probability"].astype(float)
        return df
    except Exception as e:
        print(f"[get_predictions_df ERROR] {e}")
        return pd.DataFrame()


def get_practitioners_df() -> pd.DataFrame:
    try:
        engine, _ = _get_engine()
        with engine.connect() as con:
            df = pd.read_sql_query(
                "SELECT full_name,specialty,hospital,country_income,"
                "provider_type,registered_at FROM practitioners "
                "ORDER BY registered_at DESC", con)
        if not df.empty and "registered_at" in df.columns:
            df["registered_at"] = pd.to_datetime(df["registered_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        return df
    except Exception as e:
        print(f"[get_practitioners_df ERROR] {e}")
        return pd.DataFrame()


def get_user_predictions(username) -> pd.DataFrame:
    try:
        engine, db_type = _get_engine()
        ph = "%s" if db_type == "postgres" else "?"
        with engine.connect() as con:
            df = pd.read_sql_query(
                f"SELECT * FROM predictions WHERE username={ph} "
                f"ORDER BY predicted_at DESC", con, params=(username,))
        return df
    except Exception as e:
        print(f"[get_user_predictions ERROR] {e}")
        return pd.DataFrame()


# ── Other queries ──────────────────────────────────────────────────────────────
def get_all_practitioners():
    conn, _ = _get_raw_conn()
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
    conn, _ = _get_raw_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM practitioners")
        return cur.fetchone()[0]
    finally:
        conn.close()


def count_predictions():
    conn, _ = _get_raw_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM predictions")
        return cur.fetchone()[0]
    finally:
        conn.close()


def get_specialty_counts():
    conn, _ = _get_raw_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT specialty,COUNT(*) FROM practitioners GROUP BY specialty")
        return {r[0]: r[1] for r in cur.fetchall()}
    finally:
        conn.close()


def get_income_counts():
    conn, _ = _get_raw_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT country_income,COUNT(*) FROM practitioners GROUP BY country_income")
        return {r[0]: r[1] for r in cur.fetchall()}
    finally:
        conn.close()


def get_provider_counts():
    conn, _ = _get_raw_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT provider_type,COUNT(*) FROM practitioners GROUP BY provider_type")
        return {r[0]: r[1] for r in cur.fetchall()}
    finally:
        conn.close()


def get_recent_registrations(n=5):
    conn, db_type = _get_raw_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT full_name,specialty,hospital,registered_at "
            f"FROM practitioners ORDER BY registered_at DESC LIMIT {ph}", (n,)
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return [{"name":r[0],"specialty":r[1],"hospital":r[2],"registered_at":str(r[3])}
            for r in rows]


def delete_practitioner(username):
    conn, db_type = _get_raw_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM practitioners WHERE username={ph}", (username,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_practitioner_complete(username):
    conn, db_type = _get_raw_conn()
    ph = "%s" if db_type == "postgres" else "?"
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT full_name FROM practitioners WHERE username={ph}", (username,))
        user = cur.fetchone()
        if not user:
            return False, f"User '{username}' not found."
        full_name = user[0]
        cur.execute(f"DELETE FROM predictions WHERE username={ph}", (username,))
        n_preds = cur.rowcount
        cur.execute(f"DELETE FROM practitioners WHERE username={ph}", (username,))
        conn.commit()
        return True, (f"✅ Deleted {full_name} and {n_preds} "
                      f"assessment{'s' if n_preds != 1 else ''}.")
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────
def role_color(role):
    return {"practitioner":"#1B6CA8","admin":"#7C3AED"}.get(role,"#64748B")

def debug_check_tables():
    pass  # no-op — kept for import compatibility

def verify_predictions_table():
    pass  # no-op — kept for import compatibility