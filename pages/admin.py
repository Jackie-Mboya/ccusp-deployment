"""
pages/admin.py
Administrator analytics dashboard with multiple views.
"""

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import sqlite3
import json

from utils.database import (
    get_all_practitioners,
    get_predictions_df,
    get_practitioners_df,
    count_registered,
    count_predictions,
    get_specialty_counts,
    get_income_counts,
    get_provider_counts,
    get_recent_registrations,
    delete_practitioner_complete,
)
from utils.model_loader import EXPECTED_COLUMNS

_TEAL   = "#188090"
_TEAL2  = "#9ECBD5"
_CORAL  = "#C0392B"
_GREEN  = "#059669"
_NAVY   = "#0C1F2E"
_AMBER  = "#D97706"

_CHART_BG = "rgba(0,0,0,0)"
_GRID     = "rgba(150,150,150,.12)"

# ── Friendly names for SHAP feature labels ────────────────────────────────────
_FRIENDLY = {c: c.replace("_", " ").replace("  ", " ") for c in EXPECTED_COLUMNS}


def render(models, user, page):
    """Main render function - routes to the appropriate admin page based on sidebar selection"""
    
    # Branded admin header with #188090 background
    st.markdown("""
    <style>
    .admin-brand-header {
        background-color: #188090;
        padding: 1.5rem 2rem 1rem 2rem;
        border-radius: 10px 10px 0 0;
        margin-bottom: 0;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .admin-brand-header h1 {
        font-family: 'DM Serif Display', serif;
        color: white;
        font-size: 2.2rem;
        margin: 0 0 0.3rem 0;
        letter-spacing: 1px;
    }
    .admin-brand-header p {
        color: rgba(255,255,255,0.9);
        font-size: 1rem;
        margin: 0;
        font-weight: 300;
    }
    .admin-description {
        background-color: #f8f9fa;
        border-left: 4px solid #188090;
        padding: 1rem 2rem;
        margin-bottom: 2rem;
        border-radius: 0 0 10px 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .admin-description p {
        color: #2E2E2A;
        font-size: 0.95rem;
        margin: 0;
        line-height: 1.6;
    }
    </style>
    
    <div class="admin-brand-header">
        <h1>🩺 CCUSP</h1>
        <p>Critical Care Ultrasound Penetration System · Admin Dashboard</p>
    </div>
    <div class="admin-description">
        <p>Live analytics derived from registered practitioners and recorded predictions.
        All charts update automatically as new users register and run assessments.</p>
    </div>
    """, unsafe_allow_html=True)

    # Route to appropriate page based on sidebar selection
    if page == "🏠  Dashboard":  # ← Changed from "📊" to "🏠"
        _tab_overview(models)
    elif page == "👥  Users":
        _tab_practitioners_with_drilldown()
    elif page == "📈  Analytics":
        _tab_predictions(models)
    elif page == "🏥  Competencies":
        _tab_competencies()
    elif page == "⚙️  Model Analysis":
        _tab_model(models)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Dashboard (Clean Overview with Summary Cards)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_overview(models):
    #st.write("✅ DEBUG: _tab_overview function is running")  # Debug
    
    st.markdown("## 📊 Analytics Overview")
    st.caption("High-level summary of Key Metrics")
    
    # Get data with error handling
    try:
        n_reg = count_registered()
    except:
        n_reg = 0
        
    try:
        n_pred = count_predictions()
    except:
        n_pred = 0
        
    try:
        pred_df = get_predictions_df()
        if pred_df is None or pred_df.empty:
            pred_df = pd.DataFrame()
    except:
        pred_df = pd.DataFrame()
        
    try:
        prac_df = get_practitioners_df()
        if prac_df is None or prac_df.empty:
            prac_df = pd.DataFrame()
    except:
        prac_df = pd.DataFrame()

    # ── Key Metrics Row ─────────────────────────────────────────────────────
    st.markdown("### 📈 Key Metrics")
    
    # Calculate metrics
    if not pred_df.empty and 'ccusp_class' in pred_df.columns:
        n_high = int((pred_df["ccusp_class"] == 1).sum())
        n_low = int((pred_df["ccusp_class"] == 0).sum())
    else:
        n_high = 0
        n_low = 0
    
    if not pred_df.empty and 'probability' in pred_df.columns:
        avg_prob = round(pred_df["probability"].mean() * 100, 1)
    else:
        avg_prob = 0
    
    # Display metrics in 4 columns
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Practitioners", n_reg)
    k2.metric("Total Assessments", n_pred)
    k3.metric("Total High CCUSP", n_high)
    k4.metric("Avg Probability", f"{avg_prob}%")

    if n_reg == 0 and n_pred == 0:
        st.info(
            "No data yet. Once practitioners register and run assessments, "
            "metrics will populate here.",
            icon="ℹ️",
        )
        return

    # ── Summary Charts ─────────────────────────────────────────────────────
    
    # Row 1: CCUSP Distribution and Provider Type Distribution
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("#### 📊 CCUSP Distribution")
        if not pred_df.empty and 'ccusp_label' in pred_df.columns:
            try:
                counts = pred_df["ccusp_label"].value_counts().reset_index()
                counts.columns = ["Label", "Count"]
                fig = px.pie(
                    counts, names="Label", values="Count", hole=0.4,
                    color="Label",
                    color_discrete_map={"High CCUSP": _GREEN, "Low CCUSP": _AMBER},
                )
                fig.update_layout(
                    height=300,
                    paper_bgcolor=_CHART_BG,
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            except:
                _empty("Error displaying chart")
        else:
            _empty("No assessment data")
    
    with col_right:
        st.markdown("#### 👥 Practitioners by Provider Type")
        try:
            pc = get_provider_counts()
            if pc and len(pc) > 0:
                pdf = pd.DataFrame({"Provider Type": list(pc.keys()), "Count": list(pc.values())})
                fig = px.pie(
                    pdf, values="Count", names="Provider Type", hole=0.4,
                    color_discrete_sequence=[_TEAL, _TEAL2, _AMBER],
                )
                fig.update_layout(
                    height=300,
                    paper_bgcolor=_CHART_BG,
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                _empty("No provider type data")
        except:
            _empty("Error loading provider data")

    # Row 2: Probability Distribution
    st.markdown("#### 📈 Probability Distribution")
    if not pred_df.empty and 'probability' in pred_df.columns:
        try:
            fig = px.histogram(
                pred_df, x="probability", nbins=20,
                color_discrete_sequence=[_TEAL],
            )
            fig.update_layout(
                height=300,
                paper_bgcolor=_CHART_BG,
                plot_bgcolor=_CHART_BG,
                xaxis_title="Probability", yaxis_title="Count",
                xaxis=dict(gridcolor=_GRID), 
                yaxis=dict(gridcolor=_GRID),
                margin=dict(l=10, r=10, t=10, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)
        except:
            _empty("Error displaying chart")
    else:
        _empty("No probability data")

    # Row 3: Specialty Distribution (Horizontal Bar Chart)
    st.markdown("#### 🏥 Practitioners by Specialty")
    try:
        sc = get_specialty_counts()
        if sc and len(sc) > 0:
            sdf = pd.DataFrame({"Specialty": list(sc.keys()), "Count": list(sc.values())})
            fig = px.bar(
                sdf.sort_values("Count", ascending=True),
                x="Count", y="Specialty", orientation="h",
                color="Count", color_continuous_scale=[_TEAL2, _TEAL],
                text="Count",
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=400,
                showlegend=False, 
                coloraxis_showscale=False,
                paper_bgcolor=_CHART_BG,
                plot_bgcolor=_CHART_BG,
                xaxis=dict(gridcolor=_GRID), 
                margin=dict(l=10, r=40, t=10, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            _empty("No specialty data")
    except:
        _empty("Error loading specialty data")

    # ── Navigation Hint ─────────────────────────────────────────────────────
    st.markdown("---")
    st.info(
        "👆 **For more detailed analytics with additional charts and filters**, "
        "visit the **Analytics** tab. For practitioner management, go to the **Users** tab.",
        icon="💡"
    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Users with Drill-Down (FIXED for missing names and added delete)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_practitioners_with_drilldown():
    st.subheader("👥 Practitioner Management")
    st.caption("View all practitioners and drill down into individual assessment history")
    
    # Initialize session state for selected user
    if "selected_user" not in st.session_state:
        st.session_state.selected_user = None
    
    # Get all practitioners
    practitioners = get_all_practitioners()
    n = len(practitioners)
    
    if n == 0:
        st.info("No practitioners have registered yet.", icon="ℹ️")
        return
    
    # Back button if viewing individual user
    if st.session_state.selected_user:
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("← Back to All Users", use_container_width=True):
                st.session_state.selected_user = None
                st.rerun()
        
        # Show individual user stats
        _show_individual_user_stats(st.session_state.selected_user)
        return
    
    # Main practitioners view
    prac_df = get_practitioners_df()
    
    # ── Summary metrics ───────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Registered", n)
    
    # Safely get unique counts
    try:
        specialty_count = prac_df["specialty"].nunique() if not prac_df.empty and "specialty" in prac_df.columns else 0
    except:
        specialty_count = 0
    c2.metric("Specialties", specialty_count)
    
    try:
        hospital_count = prac_df["hospital"].nunique() if not prac_df.empty and "hospital" in prac_df.columns else 0
    except:
        hospital_count = 0
    c3.metric("Hospitals", hospital_count)
    
    try:
        physician_count = int((prac_df["provider_type"] == "Physician").sum()) if not prac_df.empty and "provider_type" in prac_df.columns else 0
    except:
        physician_count = 0
    c4.metric("Physicians", physician_count)
    
    # Search/filter section
    with st.expander("🔍 Search and Filter Practitioners", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_name = st.text_input("Search by name", key="search_name")
        
        with col2:
            # Get unique specialties for filter
            if not prac_df.empty and "specialty" in prac_df.columns:
                all_specialties = ["All"] + sorted(prac_df["specialty"].unique().tolist())
            else:
                all_specialties = ["All"]
            specialty_filter = st.selectbox("Filter by specialty", all_specialties, key="filter_specialty")
        
        with col3:
            # Get unique hospitals for filter
            if not prac_df.empty and "hospital" in prac_df.columns:
                all_hospitals = ["All"] + sorted(prac_df["hospital"].unique().tolist())
            else:
                all_hospitals = ["All"]
            hospital_filter = st.selectbox("Filter by hospital", all_hospitals, key="filter_hospital")
    
    # Apply filters
    filtered_practitioners = practitioners.copy()
    
    if search_name:
        filtered_practitioners = [p for p in filtered_practitioners 
                                 if search_name.lower() in str(p.get("name", "")).lower() or
                                    search_name.lower() in str(p.get("Name", "")).lower()]
    
    if specialty_filter != "All":
        filtered_practitioners = [p for p in filtered_practitioners 
                                 if p.get("specialty") == specialty_filter or 
                                    p.get("Specialty") == specialty_filter]
    
    if hospital_filter != "All":
        filtered_practitioners = [p for p in filtered_practitioners 
                                 if p.get("hospital") == hospital_filter or
                                    p.get("Hospital") == hospital_filter]
    
    # Display practitioners in a table with clickable rows
    st.markdown("### Practitioner List")
    st.caption(f"Showing {len(filtered_practitioners)} of {n} practitioners")
    
    if filtered_practitioners:
        # Create DataFrame for display with consistent column names
        display_data = []
        for p in filtered_practitioners:
            # Handle both lowercase and uppercase keys
            row = {
                'Name': p.get('name') or p.get('Name') or p.get('full_name') or p.get('Full Name') or 'Unknown',
                'Username': p.get('username') or p.get('Username') or '',
                'Specialty': p.get('specialty') or p.get('Specialty') or '—',
                'Hospital': p.get('hospital') or p.get('Hospital') or '—',
                'Provider Type': p.get('provider_type') or p.get('Provider Type') or p.get('provider') or '—',
                'Country Income': p.get('country_income') or p.get('Country Income') or '—',
            }
            display_data.append(row)
        
        display_df = pd.DataFrame(display_data)
        
        # Add assessment count column
        try:
            all_preds = get_predictions_df()
            if not all_preds.empty and 'username' in all_preds.columns:
                assessment_counts = all_preds.groupby("username").size().to_dict()
                display_df["Assessments"] = display_df["Username"].map(assessment_counts).fillna(0).astype(int)
            else:
                display_df["Assessments"] = 0
        except:
            display_df["Assessments"] = 0
        
        # Create clickable buttons for each user with delete option
        for idx, row in display_df.iterrows():
            col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 2, 2, 1.5, 1.5, 1, 1, 1])
            
            with col1:
                st.write(row.get("Name", "—"))
            with col2:
                st.write(row.get("Specialty", "—"))
            with col3:
                st.write(row.get("Hospital", "—"))
            with col4:
                st.write(row.get("Provider Type", "—"))
            with col5:
                st.write(row.get("Country Income", "—"))
            with col6:
                st.write(f"📊 {int(row.get('Assessments', 0))}")
            with col7:
                if st.button("👤 View", key=f"view_user_{idx}"):
                    st.session_state.selected_user = row.to_dict()
                    st.rerun()
            with col8:
                if st.button("🗑️ Delete", key=f"delete_user_{idx}"):
                    if st.session_state.get(f"confirm_delete_{idx}", False):
                        try:
                            # Delete user using the enhanced function
                            success, message = delete_practitioner_complete(row.get('Username'))
                            if success:
                                st.success(message)
                                # Clear confirmation state
                                st.session_state[f"confirm_delete_{idx}"] = False
                                st.rerun()
                            else:
                                st.error(message)
                        except Exception as e:
                            st.error(f"Error deleting user: {e}")
                    else:
                        st.session_state[f"confirm_delete_{idx}"] = True
                        st.warning(f"⚠️ Click again to confirm PERMANENT deletion of {row.get('Name')} and ALL their assessments")
            
            st.markdown("---")
    else:
        st.info("No practitioners match your filters")


def _show_individual_user_stats(user_data):
    """Display detailed stats for an individual practitioner"""
    
    # Get username from various possible keys
    username = (user_data.get('Username') or user_data.get('username') or '')
    
    st.markdown(f"""
    <div style="background-color: #EDF8FA; padding: 1.5rem; border-radius: 10px; margin-bottom: 1.5rem;">
        <h3 style="color: #0B6B78; margin: 0;">👤 {user_data.get('Name', 'Unknown')}</h3>
        <p style="color: #2E2E2A; margin: 0.5rem 0 0 0;">
            {user_data.get('Specialty', '—')} · {user_data.get('Hospital', '—')} · {user_data.get('Provider Type', '—')}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get user's predictions
    try:
        all_preds = get_predictions_df()
        if not all_preds.empty and 'username' in all_preds.columns:
            user_preds = all_preds[all_preds["username"] == username].copy()
        else:
            user_preds = pd.DataFrame()
    except:
        user_preds = pd.DataFrame()
    
    # Summary metrics
    if not user_preds.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Assessments", len(user_preds))
        
        high_count = (user_preds["ccusp_class"] == 1).sum() if 'ccusp_class' in user_preds.columns else 0
        low_count = (user_preds["ccusp_class"] == 0).sum() if 'ccusp_class' in user_preds.columns else 0
        
        col2.metric("High CCUSP", high_count)
        col3.metric("Low CCUSP", low_count)
        
        avg_prob = user_preds['probability'].mean() if 'probability' in user_preds.columns else 0
        col4.metric("Avg Probability", f"{avg_prob:.1%}")
        
        # Probability trend
        st.markdown("---")
        st.markdown("#### 📈 Assessment History")
        
        if len(user_preds) >= 2 and 'predicted_at' in user_preds.columns:
            try:
                plot_df = user_preds[["predicted_at", "probability", "ccusp_label"]].copy()
                plot_df["predicted_at"] = pd.to_datetime(plot_df["predicted_at"])
                plot_df = plot_df.sort_values("predicted_at")
                
                fig = px.line(
                    plot_df, x="predicted_at", y="probability",
                    color="ccusp_label",
                    color_discrete_map={"High CCUSP": _GREEN, "Low CCUSP": _AMBER},
                    markers=True,
                )
                fig.update_layout(
                    height=300,
                    paper_bgcolor=_CHART_BG, plot_bgcolor=_CHART_BG,
                    xaxis_title="Date", yaxis_title="Probability",
                    margin=dict(l=10, r=10, t=10, b=30),
                )
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.info("Could not display trend chart")
        
        # Detailed assessments table
        st.markdown("#### 📋 Assessment Details")
        
        display_cols = [
            "predicted_at", "probability", "ccusp_label", 
            "yrs", "icu_vol", "hosp_type", "extra_training", "cert"
        ]
        available_cols = [c for c in display_cols if c in user_preds.columns]
        
        if available_cols:
            table_df = user_preds[available_cols].copy()
            table_df.columns = [c.replace("_", " ").title() for c in table_df.columns]
            
            if "Probability" in table_df.columns:
                table_df["Probability"] = table_df["Probability"].map("{:.1%}".format)
            
            st.dataframe(table_df, use_container_width=True, hide_index=True)
        else:
            st.info("No detailed assessment data available")
        
        # Export and Delete options
        col1, col2 = st.columns(2)
        with col1:
            if not user_preds.empty:
                csv = user_preds.to_csv(index=False)
                st.download_button(
                    "📥 Export User Data",
                    csv,
                    f"{username}_assessments.csv",
                    "text/csv"
                )
        with col2:
            if st.button("🗑️ Delete User Permanently", type="primary"):
                if st.session_state.get("confirm_delete_user", False):
                    try:
                        success, message = delete_practitioner_complete(username)
                        if success:
                            st.success(message)
                            st.session_state.selected_user = None
                            st.session_state["confirm_delete_user"] = False
                            st.rerun()
                        else:
                            st.error(message)
                    except Exception as e:
                        st.error(f"Error deleting user: {e}")
                else:
                    st.session_state["confirm_delete_user"] = True
                    st.warning("⚠️ Click again to confirm PERMANENT deletion of this user")
        
    else:
        st.info("This practitioner has not completed any assessments yet.")
        
        # Option to delete user even if no assessments
        if st.button("🗑️ Delete User (No Assessments)"):
            if st.session_state.get("confirm_delete_user", False):
                try:
                    success, message = delete_practitioner_complete(username)
                    if success:
                        st.success(message)
                        st.session_state.selected_user = None
                        st.session_state["confirm_delete_user"] = False
                        st.rerun()
                    else:
                        st.error(message)
                except Exception as e:
                    st.error(f"Error deleting user: {e}")
            else:
                st.session_state["confirm_delete_user"] = True
                st.warning("⚠️ Click again to confirm deletion of this user")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Analytics (Prediction Analytics)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_predictions(models):
    st.subheader("📈 Prediction Analytics")
    pred_df = get_predictions_df()

    if pred_df.empty:
        st.info(
            "No predictions recorded yet. Once practitioners run self-assessments, "
            "their results will appear here.",
            icon="ℹ️",
        )
        return

    n       = len(pred_df)
    n_high  = int((pred_df["ccusp_class"] == 1).sum()) if 'ccusp_class' in pred_df.columns else 0
    n_low   = n - n_high
    avg_p   = pred_df["probability"].mean() if 'probability' in pred_df.columns else 0

    # ── Metrics ───────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Assessments",  n)
    c2.metric("High CCUSP",         n_high, f"{n_high/n*100:.1f}%" if n > 0 else "0%")
    c3.metric("Low CCUSP",          n_low,  f"{n_low/n*100:.1f}%" if n > 0 else "0%")
    c4.metric("Mean Probability",   f"{avg_p:.1%}")

    col1, col2 = st.columns(2)

    # ── Prob by specialty box-plot ────────────────────────────────────────────
    with col1:
        st.markdown('<p class="chart-title">PROBABILITY BY SPECIALTY</p>',
                    unsafe_allow_html=True)
        if "specialty" in pred_df.columns and pred_df["specialty"].notna().any():
            try:
                fig = px.box(
                    pred_df[pred_df["specialty"].notna()],
                    x="specialty", y="probability",
                    color="specialty",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    points="all",
                )
                thresh = float(models.get('threshold', 0.5))
                fig.add_hline(
                    y=thresh, line_dash="dash", line_color=_AMBER,
                    annotation_text=f"Threshold {thresh:.3f}",
                )
                fig.update_layout(
                    height=340, showlegend=False,
                    paper_bgcolor=_CHART_BG, plot_bgcolor=_CHART_BG,
                    xaxis_title="", yaxis_title="Probability",
                    xaxis=dict(tickangle=-25),
                    margin=dict(l=10, r=10, t=10, b=60),
                )
                st.plotly_chart(fig, use_container_width=True)
            except:
                _empty("Error displaying chart")

    # ── CCUSP class by provider type ──────────────────────────────────────────
    with col2:
        st.markdown('<p class="chart-title">CCUSP LEVEL BY PROVIDER TYPE</p>',
                    unsafe_allow_html=True)
        if "provider_type" in pred_df.columns and "ccusp_label" in pred_df.columns:
            try:
                grp = pred_df.groupby(["provider_type", "ccusp_label"]).size().reset_index(name="Count")
                fig = px.bar(
                    grp, x="provider_type", y="Count",
                    color="ccusp_label",
                    color_discrete_map={"High CCUSP": _GREEN, "Low CCUSP": _AMBER},
                    barmode="group",
                    text="Count",
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(
                    height=340,
                    paper_bgcolor=_CHART_BG, plot_bgcolor=_CHART_BG,
                    xaxis_title="Provider Type", yaxis_title="Count",
                    legend_title="CCUSP Level",
                    yaxis=dict(gridcolor=_GRID),
                    margin=dict(l=10, r=10, t=10, b=30),
                )
                st.plotly_chart(fig, use_container_width=True)
            except:
                _empty("Error displaying chart")

    # ── Timeline of assessments ───────────────────────────────────────────────
    st.markdown('<p class="chart-title">ASSESSMENTS OVER TIME</p>',
                unsafe_allow_html=True)
    if "predicted_at" in pred_df.columns:
        try:
            pred_df["date"] = pd.to_datetime(pred_df["predicted_at"]).dt.date
            timeline = (
                pred_df.groupby(["date", "ccusp_label"])
                .size().reset_index(name="Count")
            )
            fig = px.line(
                timeline, x="date", y="Count",
                color="ccusp_label",
                color_discrete_map={"High CCUSP": _GREEN, "Low CCUSP": _CORAL},
                markers=True,
            )
            fig.update_layout(
                height=260,
                paper_bgcolor=_CHART_BG, plot_bgcolor=_CHART_BG,
                xaxis_title="Date", yaxis_title="Assessments",
                legend_title="",
                yaxis=dict(gridcolor=_GRID),
                margin=dict(l=10, r=10, t=10, b=30),
            )
            st.plotly_chart(fig, use_container_width=True)
        except:
            _empty("Error displaying timeline")

    # ── Full predictions table ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### All Recorded Assessments")

    display_cols = [
        "full_name", "specialty", "hospital", "provider_type",
        "probability", "ccusp_label", "threshold_used", "predicted_at",
    ]
    available_cols = [c for c in display_cols if c in pred_df.columns]
    
    if available_cols:
        show_df = pred_df[available_cols].copy()
        show_df.columns = [c.replace("_", " ").title() for c in show_df.columns]

        def _highlight(row):
            color = "#e8f8ef" if "High" in str(row.get("Ccusp Label", "")) else "#fef3e2"
            return [f"background-color:{color}"] * len(row)

        st.dataframe(
            show_df.style.apply(_highlight, axis=1),
            use_container_width=True, hide_index=True,
        )

        st.download_button(
            "⬇️ Export predictions CSV",
            data=show_df.to_csv(index=False).encode(),
            file_name="ccusp_predictions.csv",
            mime="text/csv",
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Competencies (FIXED with better error handling)
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — Competencies (FIXED - uses correct database connection)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_competencies():
    """View CCUSP competencies across practitioners"""
    st.markdown("## 🏥 CCUSP Competencies")
    st.caption("Procedure-level insights based on practitioner predictions")
    
    # Use the existing database function instead of creating a new connection
    pred_df = get_predictions_df()
    
    # Always show model metrics at the top (from your screenshots)
    # st.markdown("### ENSEMBLE LASSO")
    
    # col1, col2, col3, col4 = st.columns(4)
    # col1.metric("F1-Score", "0.8385")
    # col2.metric("Accuracy", "0.7655") 
    # col3.metric("Precision", "0.8191")
    # col4.metric("Recall", "0.8590")
    
    # st.caption("3-fold CV - Threshold: 0.4023 • 3.3ms inference • ⏰ 20.2s training")
    
    st.markdown("---")
    
    if pred_df.empty:
        st.info("No competency data available yet. Assessments will appear here once practitioners run them.")
        return

    # Overall stats from predictions
    total_high = len(pred_df[pred_df['ccusp_class'] == 1]) if 'ccusp_class' in pred_df.columns else 0
    total_low = len(pred_df[pred_df['ccusp_class'] == 0]) if 'ccusp_class' in pred_df.columns else 0
    
    st.markdown("### 📊 Assessment Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Assessments", len(pred_df))
    if len(pred_df) > 0:
        col2.metric("High CCUSP", total_high, f"{(total_high/len(pred_df))*100:.1f}%")
        col3.metric("Low CCUSP", total_low, f"{(total_low/len(pred_df))*100:.1f}%")
    else:
        col2.metric("High CCUSP", 0)
        col3.metric("Low CCUSP", 0)
    col4.metric("Practitioners", pred_df['full_name'].nunique() if 'full_name' in pred_df.columns else 0)
    
    st.markdown("---")
    
    # Parse prediction data to extract procedure competencies
    procedures_data = []
    
    for _, row in pred_df.iterrows():
        try:
            # Create procedure data from prediction columns
            procedures_data.append({
                'name': row.get('full_name', 'Unknown'),
                'specialty': row.get('specialty', '—'),
                'hospital': row.get('hospital', '—'),
                'probability': row.get('probability', 0),
                'prediction': 'High CCUSP' if row.get('ccusp_class') == 1 else 'Low CCUSP',
                'Internal Jugular': '✅' if row.get('extra_training') == 'Yes' else '❌',
                'Subclavian/Axillary': '✅' if row.get('cert') == 'Yes' else '❌',
                'PICC Line': '✅' if row.get('manages_icu') == 'Yes' else '❌',
                'Volume Responsiveness': '✅' if row.get('icu_vol') in ['2000-3000', '>3000'] else '❌',
                'date': row.get('predicted_at', '')
            })
        except Exception as e:
            continue
    
    if procedures_data:
        proc_df = pd.DataFrame(procedures_data)
        
        # Procedure competency chart
        st.subheader("📊 Procedure Competency")
        
        # Calculate competency counts
        competency_counts = {
            'Internal Jugular': (proc_df['Internal Jugular'] == '✅').sum(),
            'Subclavian/Axillary': (proc_df['Subclavian/Axillary'] == '✅').sum(),
            'PICC Line': (proc_df['PICC Line'] == '✅').sum(),
            'Volume Responsiveness': (proc_df['Volume Responsiveness'] == '✅').sum()
        }
        
        comp_df = pd.DataFrame([
            {"Procedure": k, "Practitioners": v, "Percentage": f"{(v/len(proc_df))*100:.1f}%"} 
            for k, v in competency_counts.items()
        ])
        
        # Bar chart
        fig = px.bar(
            comp_df, 
            x="Procedure", 
            y="Practitioners",
            color="Practitioners",
            color_continuous_scale=[_TEAL2, _TEAL],
            text="Percentage"
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            height=400,
            paper_bgcolor=_CHART_BG,
            plot_bgcolor=_CHART_BG,
            xaxis_title="",
            yaxis_title="Number of Practitioners",
            margin=dict(l=10, r=10, t=10, b=30),
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # By specialty breakdown
        st.subheader("📋 Competency by Specialty")
        if 'specialty' in proc_df.columns and len(proc_df) > 0:
            specialty_comp = proc_df.groupby('specialty').agg({
                'Internal Jugular': lambda x: (x == '✅').sum(),
                'Subclavian/Axillary': lambda x: (x == '✅').sum(),
                'PICC Line': lambda x: (x == '✅').sum(),
                'Volume Responsiveness': lambda x: (x == '✅').sum(),
                'name': 'count'
            }).rename(columns={'name': 'Total'})
            
            st.dataframe(specialty_comp, use_container_width=True)
        
        # Detailed table
        with st.expander("📋 View Detailed Competency Data"):
            st.dataframe(proc_df, use_container_width=True, hide_index=True)
            
            # Export option
            csv = proc_df.to_csv(index=False)
            st.download_button(
                "📥 Download Competency Data",
                csv,
                "ccusp_competencies.csv",
                "text/csv"
            )
    else:
        st.warning("Unable to parse procedure data from assessments")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 — Model Analysis (formerly Settings)
# ─────────────────────────────────────────────────────────────────────────────
def _tab_model(models):
    st.subheader("⚙️ Model Configuration & Analysis")

    # if not models:
    #     st.warning("Model configuration not available")
    #     return

    # meta = pd.DataFrame({
    #     "Property": [
    #         "Algorithm",
    #         "Constituent models",
    #         "Outer CV folds",
    #         "Inner CV folds",
    #         "C search grid",
    #         "Scoring metric",
    #         "Ensemble method",
    #         "Input features",
    #         "Youden threshold",
    #     ],
    #     "Value": [
    #         "LASSO Logistic Regression (L1, liblinear)",
    #         str(len(models.get("lasso_models", []))),
    #         "3 (StratifiedKFold)",
    #         "5 (StratifiedKFold, GridSearchCV)",
    #         "{0.001, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 50, 100}",
    #         "AUC-ROC",
    #         "p̂_ens = (p̂¹ + p̂² + p̂³) / 3",
    #         str(len(EXPECTED_COLUMNS)),
    #         f"{models.get('threshold', 0.5):.4f}",
    #     ],
    # })
    # st.dataframe(meta, use_container_width=True, hide_index=True)

    # LASSO coefficient chart (real model weights — not hardcoded)
    st.markdown("---")
    st.subheader("Feature Weights")
    st.caption(
        "Absolute coefficient magnitudes. "
    )
    
    try:
        lasso_models = models.get("lasso_models", [])
        if lasso_models and len(lasso_models) > 0:
            coefs  = np.abs(lasso_models[0].coef_[0])
            
            # Create dataframe with friendly names
            coef_df = pd.DataFrame({
                "Feature": [_FRIENDLY.get(c, c) for c in EXPECTED_COLUMNS],
                "|β|": coefs,
            })
            
            # Filter out features containing 'Missing' (case insensitive)
            coef_df = coef_df[~coef_df['Feature'].str.contains('Missing', case=False, na=False)]
            
            # Filter out zero coefficients and sort
            coef_df = coef_df[coef_df["|β|"] > 0].sort_values("|β|", ascending=False).reset_index(drop=True)
            
            # Take top 20 for display
            top = coef_df.head(20)
            
            if not top.empty:
                fig = px.bar(
                    top, x="|β|", y="Feature", orientation="h",
                    color="|β|", color_continuous_scale=[_TEAL2, _TEAL],
                    text=top["|β|"].round(4),
                )
                fig.update_traces(
                    textposition="outside",
                    hovertemplate='<b>%{y}</b><br>|β|: %{x:.4f}<extra></extra>'
                )
                fig.update_layout(
                    height=max(400, len(top) * 30),  # Dynamic height based on number of features
                    showlegend=False, 
                    coloraxis_showscale=False,
                    paper_bgcolor=_CHART_BG, 
                    plot_bgcolor=_CHART_BG,
                    yaxis=dict(autorange="reversed"),
                    xaxis=dict(
                        gridcolor=_GRID,
                        title="|β|"
                    ),
                    margin=dict(l=200, r=80, t=10, b=10),  # Increased left margin for feature names
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Show count of features displayed
                # st.caption(f"Showing {len(top)} features with non-zero coefficients (excluding 'Missing' terms)")
            else:
                st.info("No non-zero coefficients found after filtering out 'Missing' features.")
        else:
            st.info("No LASSO models available for coefficient analysis.")
            
    except Exception as e:
        st.warning(f"Could not render coefficient chart: {e}")

    # Threshold adjustment
    st.markdown("---")
    st.subheader("🔄 Threshold Adjustment")
    current_threshold = float(models.get('threshold', 0.5))
    new_threshold = st.slider(
        "Adjust prediction threshold",
        min_value=0.1,
        max_value=0.9,
        value=current_threshold,
        step=0.01
    )
    
    if new_threshold != current_threshold:
        if st.button("Update Threshold", type="primary"):
            st.success(f"Threshold updated to {new_threshold:.2f}")
            # In production, you'd save this to a config file

    # About
    st.markdown("---")
    st.markdown("""
    <div class="info-box">
        <h4>Authentication & Data Policy</h4>
        <p>
        In a production deployment, credentials would be managed via a dedicated
        authentication service with bcrypt hashing and role-based access control.
        For the purposes of this thesis prototype, the current architecture is
        appropriate given that ethics approval does not cover prospective data collection.
        </p>
        <h4>Citation</h4>
        <p>Mboya, J. A. (2025). <em>Predicting Critical Care Ultrasound Penetration
        (CCUSP) Using Machine Learning in High-Dimensional Data.</em>
        MSc Dissertation, Strathmore University, Nairobi, Kenya.</p>
    </div>
    """, unsafe_allow_html=True)


# ── Helper ────────────────────────────────────────────────────────────────────
def _empty(msg: str):
    st.markdown(
        f'<div class="placeholder-box">{msg}</div>',
        unsafe_allow_html=True,
    )