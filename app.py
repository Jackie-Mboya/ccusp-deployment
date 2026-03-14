"""
app.py — CCUSP Clinical Decision Support System
Run:  streamlit run app.py
"""

import streamlit as st
from utils.database import init_db, authenticate, register_user, SPECIALTIES, HOSPITALS, PROVIDER_TYPES, INCOME_LEVELS, verify_predictions_table
from utils.model_loader import load_models
from pages import practitioner, admin

# ── Must be first Streamlit call ──────────────────────────────────────────────
st.set_page_config(
    page_title="CCUSP · Clinical Decision Support",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===== ADD THIS CODE RIGHT HERE =====
# Initialize session state for login
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None

# Hide sidebar for non-logged-in users
if not st.session_state.get("logged_in"):
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            [data-testid="collapsedControl"] {display: none;}
        </style>
    """, unsafe_allow_html=True)
# ====================================

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
""", unsafe_allow_html=True)

# ── Initialise DB on every startup ────────────────────────────────────────────
init_db()
verify_predictions_table()
# After init_db(), add:
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 Database Status")

try:
    from utils.database import count_registered, count_predictions, _get_raw_conn
    
    # Test connection
    conn, db_type = _get_raw_conn()
    conn.close()
    
    st.sidebar.success(f"✅ Connected to {db_type}")
    st.sidebar.info(f"👥 Users: {count_registered()}")
    st.sidebar.info(f"📊 Predictions: {count_predictions()}")
    
    # Show which database is being used
    if db_type == "postgres":
        st.sidebar.markdown("🟢 **Using Supabase PostgreSQL**")
    else:
        st.sidebar.markdown("🟡 **Using SQLite (local)**")
        
except Exception as e:
    st.sidebar.error(f"❌ DB Error: {str(e)[:100]}")

# ─────────────────────────────────────────────────────────────────────────────
#  GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Serif+Display:ital@0;1&display=swap" rel="stylesheet">

<style>
:root {
    --teal:        #0B6B78;
    --teal-mid:    #188090;
    --teal-light:  #D0EEF2;
    --teal-xlt:    #EDF8FA;
    --navy:        #0C1F2E;
    --navy-mid:    #143347;
    --coral:       #B83228;
    --coral-lt:    #FBECEA;
    --green:       #196640;
    --green-lt:    #E4F5EC;
    --amber:       #D97706;
    --amber-lt:    #FEF3E2;
    --warm:        #FAFAF8;
    --grey-100:    #F1F1EE;
    --grey-200:    #E2E2DE;
    --grey-500:    #717168;
    --grey-800:    #2E2E2A;
    --font-head:   'DM Serif Display', Georgia, serif;
    --font-body:   'DM Sans', system-ui, sans-serif;
    --radius:      10px;
    --shadow:      0 2px 12px rgba(12,31,46,.10);
    --shadow-lg:   0 6px 28px rgba(12,31,46,.16);
}
html, body, [class*="css"] {
    font-family: var(--font-body);
    background: var(--warm);
    color: var(--grey-800);
}
h1,h2,h3,h4 { font-family: var(--font-head); }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stDecoration"] { display: none; }

/* ── Sidebar ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(175deg, var(--navy) 0%, #0E2A40 55%, var(--teal) 100%);
}
[data-testid="stSidebar"] * { color: #C5D8E0 !important; }
[data-testid="stSidebar"] hr { border-color: rgba(197,216,224,.2) !important; }
[data-testid="stSidebar"] .stRadio label {
    font-size: .93rem; padding: .4rem 0; transition: color .15s; cursor: pointer;
}
[data-testid="stSidebar"] .stRadio label:hover { color: #FFFFFF !important; }

/* ── App header ──────────────────────────────────────────────── */
.app-header {
    background: linear-gradient(100deg, var(--navy) 0%, var(--teal-mid) 100%);
    padding: 1.3rem 2rem 1.1rem;
    border-radius: 0 0 var(--radius) var(--radius);
    margin-bottom: 1.6rem;
    box-shadow: var(--shadow-lg);
}
.app-header h1 {
    font-family: var(--font-head);
    color: #FFF !important; font-size: 1.65rem;
    margin: 0 0 .2rem; letter-spacing: .01em;
}
.app-header p { color: #8BBEC9; font-size: .85rem; margin: 0; }

/* ── Welcome bar ─────────────────────────────────────────────── */
.welcome-bar {
    background: var(--teal-xlt);
    border: 1px solid var(--teal-light);
    border-radius: var(--radius);
    padding: .7rem 1.2rem;
    margin-bottom: 1.2rem;
    font-size: .9rem;
}
.welcome-name { font-weight: 600; color: var(--navy); }
.welcome-sub  { color: var(--grey-500); }

/* ── Page header ─────────────────────────────────────────────── */
.page-header {
    border-left: 4px solid var(--teal-mid);
    padding: .45rem 0 .45rem 1rem;
    margin-bottom: 1.4rem;
}
.page-header h2 { color: var(--navy); font-size: 1.3rem; margin: 0 0 .2rem; }
.page-header p  { color: var(--grey-500); font-size: .87rem; margin: 0; }

/* ── Group label inside form ─────────────────────────────────── */
.group-label {
    font-size: .72rem; font-weight: 700; letter-spacing: .07em;
    text-transform: uppercase; color: var(--teal-mid);
    margin: 0 0 .5rem;
    padding-bottom: .25rem;
    border-bottom: 2px solid var(--teal-light);
}

/* ── Chart titles (admin dash) ───────────────────────────────── */
.chart-title {
    font-size: .7rem; font-weight: 700; letter-spacing: .09em;
    text-transform: uppercase; color: var(--grey-500);
    margin: .5rem 0 .2rem;
}

/* ── Form ────────────────────────────────────────────────────── */
[data-testid="stForm"] {
    background: var(--warm);
    border: 1px solid var(--grey-200);
    border-radius: var(--radius);
    padding: 1.4rem;
}
[data-baseweb="select"] > div {
    border-color: var(--teal-light) !important;
    border-radius: 6px !important;
}
[data-baseweb="select"] > div:focus-within {
    border-color: var(--teal-mid) !important;
    box-shadow: 0 0 0 2px rgba(24,128,144,.15) !important;
}
[data-testid="stTextInput"] input {
    border-radius: 6px !important;
    font-family: var(--font-body) !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: var(--teal-mid) !important;
    box-shadow: 0 0 0 2px rgba(24,128,144,.15) !important;
}

/* ── Buttons ─────────────────────────────────────────────────── */
.stButton > button, .stDownloadButton > button {
    font-family: var(--font-body); font-weight: 500;
    border-radius: 8px !important; letter-spacing: .01em;
    transition: all .18s ease;
}
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: var(--teal-mid) !important;
    border-color: var(--teal-mid) !important;
    color: #FFF !important;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover {
    background: var(--teal) !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(11,107,120,.28);
}

/* ── Metric cards ────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #FFF;
    border: 1px solid var(--teal-light);
    border-radius: var(--radius);
    padding: .85rem 1rem;
    box-shadow: var(--shadow);
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: .7rem; font-weight: 700; letter-spacing: .05em;
    text-transform: uppercase; color: var(--teal-mid) !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: var(--font-head); font-size: 1.4rem; color: var(--navy) !important;
}

/* ── Result cards ────────────────────────────────────────────── */
.result-card {
    display: flex; gap: 1rem; align-items: flex-start;
    padding: 1.1rem 1.4rem; border-radius: var(--radius);
    margin-bottom: .8rem; border-left: 6px solid;
}
.result-high { background: var(--green-lt);  border-color: var(--green); }
.result-low  { background: var(--amber-lt);  border-color: var(--amber); }
.result-icon { font-size: 2rem; line-height: 1; }
.result-label { font-family: var(--font-head); font-size: 1.2rem;
                font-weight: 700; color: var(--navy); margin-bottom: .2rem; }
.result-body  { font-size: .9rem; line-height: 1.55; }

/* ── Info / instruction box ──────────────────────────────────── */
.info-box {
    background: var(--teal-xlt);
    border: 1px solid var(--teal-light);
    border-radius: var(--radius);
    padding: 1.1rem 1.3rem;
    margin-top: .8rem;
}
.info-box h4 { color: var(--teal); margin-top: .5rem; font-size: .97rem; }
.info-box h4:first-child { margin-top: 0; }
.info-box li, .info-box p { font-size: .9rem; }

/* ── Login / register card ───────────────────────────────────── */
.auth-card {
    background: #FFF;
    border: 1px solid var(--teal-light);
    border-radius: 14px;
    padding: 2.2rem 2.5rem 1.8rem;
    box-shadow: var(--shadow-lg);
}
.auth-card h2 {
    font-family: var(--font-head);
    color: var(--navy); font-size: 1.5rem;
    margin: 0 0 .1rem;
}
.auth-sub { color: var(--grey-500); font-size: .87rem; margin-bottom: 1.4rem; }

/* ── Cred box ────────────────────────────────────────────────── */
.cred-box {
    background: var(--teal-xlt);
    border: 1px solid var(--teal-light);
    border-radius: var(--radius);
    padding: .8rem 1rem;
    margin-bottom: 1.2rem;
    font-size: .83rem;
    line-height: 1.85;
}
.cred-table { width:100%; border-collapse:collapse; font-size:.82rem; }
.cred-table th { text-align:left; padding:.3rem .5rem;
    color:var(--teal-mid); font-weight:600;
    border-bottom:1px solid var(--teal-light); }
.cred-table td { padding:.28rem .5rem; font-family:monospace; }

/* ── Placeholder ─────────────────────────────────────────────── */
.placeholder-box {
    background: var(--grey-100);
    border: 2px dashed var(--grey-200);
    border-radius: var(--radius);
    padding: 2.2rem 1rem;
    text-align: center;
    color: var(--grey-500);
    font-size: .9rem;
}

/* ── Tabs ────────────────────────────────────────────────────── */
[data-baseweb="tab-list"] { border-bottom: 2px solid var(--teal-light); gap: .15rem; }
[data-baseweb="tab"] {
    font-family: var(--font-body); font-weight: 600; font-size: .86rem;
    padding: .48rem .9rem; border-radius: 6px 6px 0 0;
    color: var(--grey-500) !important;
}
[aria-selected="true"][data-baseweb="tab"] {
    color: var(--teal-mid) !important;
    border-bottom: 3px solid var(--teal-mid);
    background: var(--teal-xlt);
}

/* ── Alerts ──────────────────────────────────────────────────── */
[data-testid="stAlert"] { border-radius: var(--radius); font-size: .9rem; }

/* ── Expander ────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--teal-light) !important;
    border-radius: var(--radius) !important;
}

/* ── Slider ──────────────────────────────────────────────────── */
[data-baseweb="slider"] [role="slider"] {
    background: var(--teal-mid) !important;
    border-color: var(--teal-mid) !important;
}

/* ── Scrollbar ───────────────────────────────────────────────── */
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-thumb { background: var(--teal-light); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background: var(--teal-mid); }

/* Force signout button to be visible */
button[key="sidebar_signout"] {
    display: block !important;
    background-color: #c0392b !important;
    color: white !important;
    border: 2px solid white !important;
    font-weight: bold !important;
    opacity: 1 !important;
    z-index: 9999 !important;
    margin: 10px 0 !important;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  LANDING PAGE (when not logged in)
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.get("logged_in"):
    
    # ── Custom CSS for teal colors ─────────────────────────────────────────
    st.markdown("""
    <style>
    .teal-text {
        color: #188090 !important;
    }
    
    .teal-heading {
        color: #188090 !important;
        font-family: 'DM Serif Display', serif;
    }
    
    /* Style all buttons on landing page */
    div[data-testid="column"] .stButton > button {
        background-color: #188090 !important;
        color: white !important;
        border: none !important;
        transition: all 0.3s ease;
    }
    
    div[data-testid="column"] .stButton > button:hover {
        background-color: #0f5c68 !important;
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(24,128,144,0.3);
    }
    </style>
    """, unsafe_allow_html=True)
    
    # ── Hero Section (CENTERED) ─────────────────────────────────────────────
    left_col, center_col, right_col = st.columns([1, 2, 1])
    
    with center_col:
        # Centered content with teal color
        st.markdown("""
        <div style="text-align: center; padding: 2rem 1rem;">
            <h1 style="font-family: 'DM Serif Display', serif; font-size: 3rem; color: #188090; margin-bottom: 1rem;">
                CCUSP<br>Clinical Decision Support
            </h1>
            <p style="font-size: 1.2rem; color: #2E2E2A; margin-bottom: 2rem; line-height: 1.6;">
                Critical Care Ultrasound Penetration Prediction System.<br>
                Assess your CCUSP level and get personalized insights with SHAP explanations.
            </p>
        """, unsafe_allow_html=True)
        
        # Center the buttons
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("👨‍⚕️ Practitioner", use_container_width=True):
                st.session_state.login_role = "practitioner"
                st.switch_page("pages/login.py")
        
        with col2:
            if st.button("👩‍💼 Admin", use_container_width=True):
                st.session_state.login_role = "admin"
                st.switch_page("pages/login.py")
        
        with col3:
            if st.button("📝 Register", use_container_width=True):
                st.switch_page("pages/register.py")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Medical illustration
        try:
            st.image("assets/images/undraw_doctors_djoj.png", use_column_width=True)
        except:
            st.image("https://illustrations.popsy.co/white/doctor-with-a-stethoscope.svg", use_column_width=True)
    
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
#  LOAD MODELS (cached) - Only for logged-in users
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="⏳ Loading model artefacts…")
def _load():
    return load_models("models")

try:
    models = _load()
except FileNotFoundError as e:
    st.error("### ⚠️ Model files not found")
    st.markdown(f"""**Steps to fix:**
1. Run `CCUSP_V4_tuned.ipynb` in Google Colab.
2. Run `notebooks/notebook_save_cell.py` as the final cell.
3. Copy these 3 files into `models/`:
   - `tuned_ensemble_lasso_models.pkl`
   - `scaler.pkl`
   - `tuned_optimal_threshold.pkl`
4. Restart: `streamlit run app.py`
""")
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR (logged-in) - Role-based navigation
# ─────────────────────────────────────────────────────────────────────────────
user = st.session_state["current_user"]

with st.sidebar:
    # Simple "Menu" header instead of "Navigation"
    st.markdown("""
    <div style="padding:.3rem 0 .7rem; border-bottom:1px solid rgba(197,216,224,.2);
                margin-bottom:.7rem; font-family:'DM Serif Display',serif;
                font-size:1rem; font-weight:700; color:#FFF;">
        Menu
    </div>
    """, unsafe_allow_html=True)

    # ── Role-based navigation ─────────────────────────────────────────────
    if user["role"] == "admin":
        # Admin navigation - management focused
        # In app.py - Update the admin navigation section (around line 280-290)

        # Admin navigation - management focused
        page = st.radio(
            "Admin Menu",
            ["🏠  Dashboard", "👥  Users", "📈  Analytics", "🏥  Competencies", "⚙️  Model Analysis"], 
            label_visibility="collapsed",
            key="admin_nav"
        )
    # In app.py - around line 280-290, replace the practitioner navigation section:

    else:
        # Practitioner navigation - clinical focused
        # Get current practitioner navigation from session state
        if "prac_nav" not in st.session_state:
            st.session_state["prac_nav"] = "🏠  Dashboard"
        
        # Map the display names to match _NAV_KEYS in practitioner.py
        prac_options = ["🏠  Dashboard", "🩺  Self-Assessment", "📊  My History", "📈  Benchmarks"]
        
        # Find the index of current selection
        current_index = prac_options.index(st.session_state["prac_nav"]) if st.session_state["prac_nav"] in prac_options else 0
        
        page = st.radio(
            "Practitioner Menu",
            prac_options,
            index=current_index,
            label_visibility="collapsed",
            key="practitioner_nav"
        )
        
        # Update session state when radio changes
        if page != st.session_state["prac_nav"]:
            st.session_state["prac_nav"] = page
            st.rerun()
        
        # Quick stats for practitioners
        # st.markdown("---")
        # st.markdown("""
        # <div style="font-size:.73rem; opacity:.8;">
        #     <div style="font-weight:600; margin-bottom:.3rem;">Quick Stats</div>
        # """, unsafe_allow_html=True)

        # # Get assessment count with ERROR HANDLING
        # import sqlite3
        # try:
        #     conn = sqlite3.connect('predictions.db')
        #     cursor = conn.cursor()
            
        #     # Check if predictions table exists
        #     cursor.execute("""
        #         SELECT name FROM sqlite_master 
        #         WHERE type='table' AND name='predictions'
        #     """)
        #     table_exists = cursor.fetchone() is not None
            
        #     if table_exists:
        #         cursor.execute("SELECT COUNT(*) FROM predictions WHERE user_id = ?", (user.get('id', ''),))
        #         assessment_count = cursor.fetchone()[0]
        #     else:
        #         assessment_count = 0
        #     conn.close()
        # except Exception as e:
        #     assessment_count = 0

        # st.markdown(f"""
        #     <div style="display:flex; justify-content:space-between;">
        #         <span>Assessments:</span> <span style="font-weight:600;">{assessment_count}</span>
        #     </div>
        # """, unsafe_allow_html=True)

    st.markdown("---")
    
    # User info (same for both)
    st.markdown(f"""
    <div style="font-size:.78rem; line-height:1.9; opacity:.85;">
        <div style="font-weight:700; font-size:.7rem; letter-spacing:.06em;
                    text-transform:uppercase; opacity:.7; margin-bottom:.3rem;">
            Signed in as
        </div>
        <div style="color:#FFF; font-size:.9rem;">{user['name']}</div>
        <div style="font-style:italic;">{user.get('role','').title()}</div>
        <div style="font-size:.75rem; opacity:.7;">{user.get('dept','')}</div>
    </div>
    """, unsafe_allow_html=True)

    # Model metrics (same for both)
    # st.markdown("---")
    # if 'metrics' in models:
    #     m = models['metrics']
    #     st.markdown(f"""
    #     <div style="font-size:.73rem; line-height:1.85; opacity:.7;">
    #         <div style="font-weight:700; font-size:.69rem; letter-spacing:.06em;
    #                     text-transform:uppercase; margin-bottom:.2rem;">🎯 {m['model_name']}</div>
    #         <table style="width:100%; font-size:.73rem; margin-top:.3rem;">
    #             <tr><td>F1-Score:</td><td style="text-align:right; font-weight:600;">{m['f1_score']:.4f}</td></tr>
    #             <tr><td>Accuracy:</td><td style="text-align:right; font-weight:600;">{m['accuracy']:.4f}</td></tr>
    #             <tr><td>Precision:</td><td style="text-align:right; font-weight:600;">{m['precision']:.4f}</td></tr>
    #             <tr><td>Recall:</td><td style="text-align:right; font-weight:600;">{m['recall']:.4f}</td></tr>
    #         </table>
    #         <div style="margin-top:.5rem; border-top:1px solid rgba(197,216,224,.2); padding-top:.4rem;">
    #             <span style="font-weight:500;">{m['cv_folds']}‑fold CV</span> · Threshold: <strong>{models['threshold']:.4f}</strong>
    #         </div>
    #         <div style="font-size:.65rem; margin-top:.3rem; opacity:.6;">
    #             ⚡ {m['inference_ms']:.1f}ms inference · 🕒 {m['train_time_s']:.1f}s training
    #         </div>
    #     </div>
    #     """, unsafe_allow_html=True)
    # else:
    #     # Fallback if metrics not loaded
    #     st.markdown(f"""
    #     <div style="font-size:.73rem; line-height:1.85; opacity:.7;">
    #         <div style="font-weight:700; font-size:.69rem; letter-spacing:.06em;
    #                     text-transform:uppercase; margin-bottom:.2rem;">Ensemble LASSO</div>
    #         <div>Models: {len(models['lasso_models'])}</div>
    #         <div>Threshold: {models['threshold']:.4f}</div>
    #     </div>
    #     """, unsafe_allow_html=True)

    # ── SIGN OUT BUTTON ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("###")  # Add some spacing

    # Use a more prominent button with a unique key
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚪 SIGN OUT", key="sidebar_signout", use_container_width=True, type="primary"):
            # Clear session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # Add a visible marker to confirm the button should be here
    st.caption("End of menu")  # This will show if the section is rendering


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTE - Pass the selected page to the appropriate render function
# ─────────────────────────────────────────────────────────────────────────────
if user["role"] == "admin":
    # Pass the selected admin page to admin.render()
    admin.render(models, user, page)
else:
    # Pass the selected practitioner page to practitioner.render()
    practitioner.render(models, user, page)