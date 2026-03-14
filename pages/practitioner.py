"""
pages/practitioner.py
Practitioner view with dashboard, self-assessment, history, and benchmarks.
Navigation is handled entirely by the sidebar - no duplicate navigation buttons.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from utils.model_loader import predict_from_ui, EXPECTED_COLUMNS
from utils.shap_explainer import get_shap_explanation, plot_shap_waterfall
from utils.database import save_prediction, get_predictions_df, SPECIALTIES

@st.cache_data(ttl=3)
def _cached_predictions():
    """Re-fetched every 3 seconds so pages stay in sync after a new assessment."""
    return get_predictions_df()

# ── Option lists ──────────────────────────────────────────────────────────────
_YRS     = ["<5 years", "5-10 years", "11-20 years", ">20 years"]
_ICU_VOL = ["<500", "500-1000", "1000-2000", "2000-3000", ">3000"]
_HOSP    = ["Academic", "Community"]
_YN      = ["Yes", "No"]
_POP     = ["Adult", "Pediatric"]

# ── Consistent navigation keys - MUST MATCH app.py EXACTLY ───────────────────
NAV_KEYS = {
    "dashboard": "🏠  Dashboard",
    "assessment": "🩺  Self-Assessment", 
    "history": "📊  My History",
    "benchmarks": "📈  Benchmarks"
}

# List of all navigation options for easy reference
NAV_OPTIONS = list(NAV_KEYS.values())


def render(models, user, page=None):
    # ── Initialise nav in session state if not present ─────────────────────
    if "prac_nav" not in st.session_state:
        st.session_state["prac_nav"] = NAV_KEYS["dashboard"]
    
    # ── Sync with sidebar navigation when page parameter is provided ───────
    # This ensures when you click sidebar, it updates the practitioner view
    if page is not None and page in NAV_OPTIONS:
        if page != st.session_state["prac_nav"]:
            st.session_state["prac_nav"] = page
            st.rerun()
    
    # ── Welcome banner ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="welcome-bar">
        <span class="welcome-name">Welcome, {user['name']}</span>
        <span class="welcome-sub"> · {user.get('specialty','—')} · {user.get('hospital','—')}</span>
    </div>
    """, unsafe_allow_html=True)

    # Get current navigation value from session state
    nav = st.session_state.get("prac_nav", NAV_KEYS["dashboard"])

    # Route to appropriate page
    if nav == NAV_KEYS["dashboard"]:
        _render_dashboard(user, models)
    elif nav == NAV_KEYS["assessment"]:
        _render_assessment(models, user)
    elif nav == NAV_KEYS["history"]:
        _render_history(user)
    elif nav == NAV_KEYS["benchmarks"]:
        _render_benchmarks(user)
    else:
        # Fallback - if invalid nav, reset to dashboard
        st.session_state["prac_nav"] = NAV_KEYS["dashboard"]
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
def _render_dashboard(user, models):
    st.markdown("""
    <div class="page-header">
        <h2>🏠 Critical Care Ultrasound Penetration System: Practitioner Dashboard</h2>
        <p>Your personal CCUSP overview. Run a self-assessment to see your results here.</p>
    </div>
    """, unsafe_allow_html=True)

    # Pull this user's predictions from DB
    all_df = _cached_predictions()
    my_df  = all_df[all_df["username"] == user["username"]] if not all_df.empty else pd.DataFrame()

    # ── KPI metrics ───────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    n = len(my_df)
    k1.metric("Total Assessments", n)

    if n > 0:
        latest     = my_df.iloc[0]
        latest_lbl = latest["ccusp_label"]
        latest_p   = f"{float(latest['probability']):.1%}"
        k2.metric("Latest CCUSP",    latest_lbl)
        k3.metric("Latest Probability", latest_p)
        k4.metric("Assessments — High",
                  int((my_df["ccusp_class"] == 1).sum()),
                  f"of {n} total")
    else:
        k2.metric("Latest CCUSP",        "N/A")
        k3.metric("Latest Probability",  "N/A")
        k4.metric("Assessments — High",  "N/A")

    st.markdown("---")

    # ── Profile card + quick actions ──────────────────────────────────────────
    col_prof, col_act = st.columns([1, 1])

    with col_prof:
        st.markdown("#### 👤 My Profile")
        st.markdown(f"""
        <div class="info-box" style="line-height:2;">
            <strong>Name:</strong> {user['name']}<br>
            <strong>Specialty:</strong> {user.get('specialty','—')}<br>
            <strong>Hospital:</strong> {user.get('hospital','—')}<br>
            <strong>Provider type:</strong> {user.get('provider_type','—')}<br>
            <strong>Country income:</strong> {user.get('country_income','—')}<br>
            <strong>Registered:</strong> {user.get('registered_at','—')}
        </div>
        """, unsafe_allow_html=True)

    with col_act:
        st.markdown("#### 🚀 Quick Actions")
        
        if st.button("🩺  New Self-Assessment", use_container_width=True, type="primary", key="dash_new_assess"):
            st.session_state["prac_nav"] = NAV_KEYS["assessment"]
            st.rerun()
        
        if st.button("📊  View My History", use_container_width=True, key="dash_history"):
            st.session_state["prac_nav"] = NAV_KEYS["history"]
            st.rerun()
        
        if st.button("📈  View Benchmarks", use_container_width=True, key="dash_benchmarks"):
            st.session_state["prac_nav"] = NAV_KEYS["benchmarks"]
            st.rerun()
        
        st.caption("Click any button above to navigate")

    # ── Mini probability trend (only if ≥2 assessments) ──────────────────────
    if n >= 2:
        st.markdown("---")
        st.markdown("#### 📊 My Probability Trend")
        plot_df = my_df[["predicted_at", "probability", "ccusp_label"]].copy()
        plot_df["predicted_at"] = pd.to_datetime(plot_df["predicted_at"])
        plot_df = plot_df.sort_values("predicted_at")
        fig = px.line(
            plot_df, x="predicted_at", y="probability",
            color="ccusp_label",
            color_discrete_map={"High CCUSP": "#059669", "Low CCUSP": "#D97706"},
            markers=True,
        )
        thresh = float(models["threshold"])
        fig.add_hline(y=thresh, line_dash="dash", line_color="#9ECBD5",
                      annotation_text=f"Threshold {thresh:.3f}",
                      annotation_font_color="#9ECBD5")
        fig.update_layout(
            height=240, showlegend=True,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Date", yaxis_title="Probability",
            margin=dict(l=10, r=10, t=10, b=30),
            yaxis=dict(range=[0, 1], gridcolor="rgba(150,150,150,.12)"),
        )
        st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# SELF-ASSESSMENT
# ─────────────────────────────────────────────────────────────────────────────
def _render_assessment(models, user):
    st.markdown("""
    <div class="page-header">
        <h2>🩺 CCUSP Self-Assessment</h2>
        <p>Complete your clinical profile to receive a live model prediction.</p>
    </div>
    """, unsafe_allow_html=True)

    # REMOVED: Navigation buttons at the top
    # REMOVED: Current page indicator

    default_specialty = user.get("specialty", SPECIALTIES[0])
    default_income    = user.get("country_income", "High Income")
    default_ptype     = user.get("provider_type", "Physician")

    with st.form("assess_form", clear_on_submit=False):
        st.markdown("#### Clinical Profile")
        st.caption(
            "Fields pre-filled from your registration profile. "
            "All fields are required for an accurate prediction."
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown('<p class="group-label">Background</p>', unsafe_allow_html=True)
            provider_type = st.selectbox(
                "Provider type", ["Physician", "APN"],
                index=0 if default_ptype == "Physician" else 1, key="sa_pt")
            income = st.selectbox(
                "Country income level", ["High Income", "LMIC"],
                index=0 if default_income == "High Income" else 1, key="sa_inc")
            pop      = st.selectbox("Patient population", _POP, key="sa_pop")
            specialty = st.selectbox(
                "Specialty", SPECIALTIES,
                index=SPECIALTIES.index(default_specialty)
                      if default_specialty in SPECIALTIES else 0,
                key="sa_spec")

        with col2:
            st.markdown('<p class="group-label">Experience</p>', unsafe_allow_html=True)
            yrs     = st.selectbox("Years in specialty",       _YRS,     index=1, key="sa_yrs")
            icu_vol = st.selectbox("Annual ICU patient volume", _ICU_VOL, index=1, key="sa_vol")
            hosp_type = st.selectbox("Hospital type",          _HOSP,            key="sa_ht")
            manages   = st.selectbox("Manages critically ill patients?", _YN,    key="sa_mgr")

        with col3:
            st.markdown('<p class="group-label">Training</p>', unsafe_allow_html=True)
            extra = st.selectbox("Additional ultrasound training?", _YN, key="sa_ex")
            cert  = st.selectbox("Advanced POCUS Certification?",   _YN, key="sa_cert")
            st.markdown("<br>", unsafe_allow_html=True)
            threshold_override = st.checkbox("Use custom threshold", value=False, key="sa_tcb")
            custom_thresh = st.slider(
                "Threshold", min_value=0.10, max_value=0.90,
                value=float(models["threshold"]), step=0.01,
                disabled=not threshold_override, key="sa_tsl",
                help=f"Youden-optimal = {models['threshold']:.4f}")

        st.markdown("---")
        submitted = st.form_submit_button(
            "🔍  Run Prediction", use_container_width=True, type="primary")

    if not submitted:
        _how_to_use(models)
        return

    ui_dict = {
        "provider_type": provider_type,
        "income":        income,
        "pop":           pop,
        "yrs":           yrs,
        "specialty":     specialty,
        "icu_vol":       icu_vol,
        "hosp_type":     hosp_type,
        "extra":         extra,
        "cert":          cert,
        "manages":       manages,
    }
    thresh = custom_thresh if threshold_override else models["threshold"]

    try:
        prob, pred, X_sc = predict_from_ui(models, ui_dict,
                                           use_youden=not threshold_override)
        if threshold_override:
            pred = int(prob >= thresh)
    except Exception as e:
        st.error(f"Prediction error: {e}")
        return

    label   = "High CCUSP" if pred == 1 else "Low CCUSP"
    is_high = pred == 1
    conf = ("High" if prob >= 0.75 or prob <= 0.25 else
            "Moderate" if prob >= 0.62 or prob <= 0.38 else
            "Low (near boundary)")

    result = {
        "probability": round(prob, 4),
        "class":       pred,
        "label":       label,
        "threshold":   round(float(thresh), 4),
        "confidence":  conf,
    }

    # DEBUG: Print before saving
    print("🟢 About to call save_prediction...")
    print(f"🟢 User: {user.get('username')}")
    print(f"🟢 Result: {result}")
    
    # Save to DB so dashboard + history update immediately
    save_prediction(user, ui_dict, result)
    
    print("🟢 save_prediction completed")
    st.cache_data.clear()

    # Verify the save
    all_df = _cached_predictions()
    my_df = all_df[all_df["username"] == user["username"]] if not all_df.empty else pd.DataFrame()
    print(f"📊 After save - User has {len(my_df)} predictions in DataFrame")

    # Show success message with count
    count = len(my_df)
    st.success(f"✅ Assessment saved successfully! You now have {count} total assessment(s).", icon="✅")

    # ── Result card ───────────────────────────────────────────────────────────
    st.markdown("---")
    card_cls = "result-high" if is_high else "result-low"
    icon     = "✅" if is_high else "⚠️"
    ability  = ("likely able to independently perform 2 or more core CCUS procedures"
                if is_high else
                "unlikely to independently perform 2 or more core CCUS procedures")
    st.markdown(f"""
    <div class="result-card {card_cls}">
        <div class="result-icon">{icon}</div>
        <div>
            <div class="result-label">{label}</div>
            <div class="result-body">
                Based on your profile, you are <strong>{ability}</strong>.<br>
                Predicted probability: <strong>{prob:.1%}</strong>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Prediction",  label)
    m2.metric("Probability", f"{prob:.1%}")
    m3.metric("Threshold",   f"{thresh:.4f}")
    m4.metric("Confidence",  conf)

    # Optional: Show a preview of the data
    if count > 0:
        with st.expander("📋 View your saved assessment data"):
            st.dataframe(my_df[['predicted_at', 'probability', 'ccusp_label']].head())

    # REMOVED: Navigation buttons after assessment


# ─────────────────────────────────────────────────────────────────────────────
# MY HISTORY
# ─────────────────────────────────────────────────────────────────────────────
def _render_history(user):
    st.markdown("""
    <div class="page-header">
        <h2>📊 My Assessment History</h2>
        <p>A full record of every self-assessment you have submitted.</p>
    </div>
    """, unsafe_allow_html=True)

    # REMOVED: Navigation options at the top
    # REMOVED: Current page indicator

    all_df = _cached_predictions()
    my_df  = (all_df[all_df["username"] == user["username"]].copy()
              if not all_df.empty else pd.DataFrame())

    if my_df.empty:
        st.info("You have not submitted any assessments yet. "
                "Go to **Self-Assessment** to run your first prediction.", icon="ℹ️")
        
        if st.button("🩺  Go to Self-Assessment", type="primary", key="history_goto_assess"):
            st.session_state["prac_nav"] = NAV_KEYS["assessment"]
            st.rerun()
        return

    # ── Summary metrics ───────────────────────────────────────────────────────
    n      = len(my_df)
    n_high = int((my_df["ccusp_class"] == 1).sum())
    avg_p  = my_df["probability"].astype(float).mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Assessments",  n)
    c2.metric("High CCUSP",         n_high, f"{n_high/n*100:.0f}%")
    c3.metric("Low CCUSP",          n - n_high, f"{(n-n_high)/n*100:.0f}%")
    c4.metric("Avg Probability",    f"{avg_p:.1%}")

    st.markdown("---")

    # ── Competency summary ────────────────────────────────────────────────────
    st.markdown("#### 🎯 Competency Profile Across All Assessments")
    comp_cols = {
        "extra_training":  "Additional Training",
        "cert":            "Adv. POCUS Certification",
        "manages_icu":     "Manages ICU Patients",
    }
    comp_data = []
    for col, label in comp_cols.items():
        if col in my_df.columns:
            yes_count = int((my_df[col] == "Yes").sum())
            comp_data.append({"Competency": label,
                               "Times = Yes": yes_count,
                               "Times = No":  n - yes_count})
    if comp_data:
        cdf = pd.DataFrame(comp_data)
        fig = go.Figure()
        fig.add_bar(name="Yes", x=cdf["Competency"], y=cdf["Times = Yes"],
                    marker_color="#059669")
        fig.add_bar(name="No",  x=cdf["Competency"], y=cdf["Times = No"],
                    marker_color="#D97706")
        fig.update_layout(
            barmode="stack", height=220,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis=dict(gridcolor="rgba(150,150,150,.12)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── Full history table ────────────────────────────────────────────────────
    st.markdown("#### 📄 Full Assessment Log")

    display_cols = {
        "predicted_at":  "Date & Time",
        "ccusp_label":   "CCUSP Level",
        "probability":   "Probability",
        "threshold_used":"Threshold",
        "yrs":           "Years in Specialty",
        "icu_vol":       "ICU Volume",
        "hosp_type":     "Hospital Type",
        "extra_training":"Extra Training",
        "cert":          "POCUS Cert.",
        "manages_icu":   "Manages ICU",
        "pop":           "Patient Pop.",
    }
    # Only keep columns that exist in the DataFrame
    show_cols = {k: v for k, v in display_cols.items() if k in my_df.columns}
    table_df  = my_df[list(show_cols.keys())].rename(columns=show_cols).copy()

    # Format probability as percentage
    if "Probability" in table_df.columns:
        table_df["Probability"] = table_df["Probability"].astype(float).map("{:.1%}".format)

    # Row highlight: green = High, amber = Low
    def _highlight(row):
        color = "#e8f8ef" if "High" in str(row.get("CCUSP Level", "")) else "#fef3e2"
        return [f"background-color:{color}"] * len(row)

    st.dataframe(
        table_df.style.apply(_highlight, axis=1),
        use_container_width=True,
        hide_index=True,
    )

    # Export button only - navigation removed
    st.markdown("---")
    st.download_button(
        "⬇️ Export CSV",
        data=table_df.to_csv(index=False).encode(),
        file_name=f"ccusp_history_{user['username']}.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARKS
# ─────────────────────────────────────────────────────────────────────────────
def _render_benchmarks(user):
    st.markdown("""
    <div class="page-header">
        <h2>📈 Benchmarks</h2>
        <p>See how your CCUSP probability compares to practitioners in the system.</p>
    </div>
    """, unsafe_allow_html=True)

    # REMOVED: Navigation options at the top
    # REMOVED: Current page indicator

    all_df = _cached_predictions()
    if all_df.empty:
        st.info("No benchmark data available yet — assessments from all practitioners "
                "will appear here once submitted.", icon="ℹ️")
        
        if st.button("🩺  Go to Self-Assessment", type="primary", key="bench_goto_assess"):
            st.session_state["prac_nav"] = NAV_KEYS["assessment"]
            st.rerun()
        return

    my_df    = all_df[all_df["username"] == user["username"]]
    my_avg   = my_df["probability"].astype(float).mean() if not my_df.empty else None
    all_avg  = all_df["probability"].astype(float).mean()
    spec     = user.get("specialty", "")
    spec_df  = all_df[all_df["specialty"] == spec] if spec else pd.DataFrame()
    spec_avg = spec_df["probability"].astype(float).mean() if not spec_df.empty else None

    # ── Comparison metrics ────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("My Avg Probability",
              f"{my_avg:.1%}" if my_avg is not None else "N/A")
    c2.metric("All Practitioners Avg", f"{all_avg:.1%}",
              delta=f"{(my_avg - all_avg):+.1%}" if my_avg is not None else None)
    c3.metric(f"{spec or 'My Specialty'} Avg",
              f"{spec_avg:.1%}" if spec_avg is not None else "N/A",
              delta=f"{(my_avg - spec_avg):+.1%}"
                    if my_avg is not None and spec_avg is not None else None)

    st.markdown("---")

    # ── Distribution with my position ────────────────────────────────────────
    st.markdown("#### Probability Distribution — All Practitioners")
    fig = px.histogram(
        all_df, x="probability", nbins=20,
        color_discrete_sequence=["#9ECBD5"],
        labels={"probability": "CCUSP Probability"},
    )
    if my_avg is not None:
        fig.add_vline(x=my_avg, line_dash="solid", line_color="#059669",
                      annotation_text="My average",
                      annotation_font_color="#059669",
                      annotation_position="top left")
    fig.add_vline(x=all_avg, line_dash="dash", line_color="#D97706",
                  annotation_text="System average",
                  annotation_font_color="#D97706")
    fig.update_layout(
        height=280, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=30),
        xaxis=dict(gridcolor="rgba(150,150,150,.12)"),
        yaxis=dict(gridcolor="rgba(150,150,150,.12)"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── CCUSP rate by specialty (anonymised) ──────────────────────────────────
    if "specialty" in all_df.columns and all_df["specialty"].notna().any():
        st.markdown("#### CCUSP High Rate by Specialty")
        grp = all_df.groupby("specialty").apply(
            lambda d: round((d["ccusp_class"] == 1).mean() * 100, 1)
        ).reset_index()
        grp.columns = ["Specialty", "% High CCUSP"]
        grp = grp.sort_values("% High CCUSP")
        colors = ["#059669" if s == spec else "#9ECBD5" for s in grp["Specialty"]]
        fig2 = px.bar(
            grp, x="% High CCUSP", y="Specialty", orientation="h",
            text="% High CCUSP",
            color="Specialty",
            color_discrete_sequence=colors,
        )
        fig2.update_traces(texttemplate="%{text}%", textposition="outside",
                           showlegend=False)
        fig2.update_layout(
            height=max(200, len(grp) * 45),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(range=[0, 115], gridcolor="rgba(150,150,150,.12)"),
            margin=dict(l=10, r=60, t=10, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("🟢 Your specialty is highlighted in green.")
    
    # REMOVED: Navigation buttons at bottom


# ─────────────────────────────────────────────────────────────────────────────
# HOW TO USE
# ─────────────────────────────────────────────────────────────────────────────
def _how_to_use(models):
    st.markdown(f"""
    <div class="info-box">
        <h4>How to use this assessment</h4>
        <ol>
            <li>Review the pre-filled fields — they come from your registration profile.</li>
            <li>Complete the remaining fields accurately.</li>
            <li>Click <strong>Run Prediction</strong> to receive your live model result.</li>
        </ol>
        <p><strong>What is CCUSP?</strong> Critical Care Ultrasound Penetration (High CCUSP)
        means a practitioner can independently perform ≥ 2 of these 4 procedures:
        IJ cannulation · Subclavian/Axillary access · PICC line · Volume Responsiveness.</p>
        <p style="margin-top:.6rem; color:#666; font-size:.85rem;">
        Youden-optimal threshold: <strong>{models['threshold']:.4f}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)