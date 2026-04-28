"""
utils/shap_explainer.py
Enhanced SHAP implementation for CCUSP model interpretability.
Excludes Missing variables for cleaner visualization.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st


def _should_exclude_feature(feature_name):
    """Check if a feature should be excluded from SHAP visualization"""
    exclude_patterns = [
        '_Missing',      # Missing value indicators
        'Missing_',      # Alternative pattern
        '_Missing_',     # Another pattern
        'Missing',       # Any feature with 'Missing' in name
    ]
    
    feature_lower = feature_name.lower()
    for pattern in exclude_patterns:
        if pattern.lower() in feature_lower:
            return True
    return False


def get_shap_explanation(model, X_sc, feature_names=None):
    """
    Get SHAP explanation for a single prediction.
    """
    try:
        import shap
        
        # Convert to DataFrame if needed
        if isinstance(X_sc, np.ndarray):
            if X_sc.ndim == 1:
                X_sc = X_sc.reshape(1, -1)
            if feature_names is not None and len(feature_names) == X_sc.shape[1]:
                X_sc = pd.DataFrame(X_sc, columns=feature_names)
        
        # Define prediction function
        def predict_fn(x):
            if isinstance(x, np.ndarray):
                if feature_names is not None:
                    x = pd.DataFrame(x, columns=feature_names)
                else:
                    x = pd.DataFrame(x)
            # Ensure columns match
            if feature_names is not None and hasattr(x, 'columns'):
                for col in feature_names:
                    if col not in x.columns:
                        x[col] = 0
                x = x[feature_names]
            return model.predict_proba(x)[:, 1]
        
        # Create explainer
        explainer = shap.KernelExplainer(predict_fn, X_sc)
        shap_values = explainer.shap_values(X_sc, nsamples=100)
        
        # For binary classification
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        
        expected_value = explainer.expected_value
        if isinstance(expected_value, list):
            expected_value = expected_value[1]
        
        return shap_values, expected_value
        
    except Exception as e:
        print(f"SHAP error: {e}")
        # Fallback: Use coefficient-based importance
        try:
            coefficients = model.coef_[0] if hasattr(model, 'coef_') else np.ones(X_sc.shape[1])
            if isinstance(X_sc, pd.DataFrame):
                X_arr = X_sc.values
            else:
                X_arr = X_sc
            
            contributions = coefficients * X_arr[0]
            expected_value = 0.5
            shap_values = contributions.reshape(1, -1)
            
            return shap_values, expected_value
            
        except Exception as e2:
            print(f"Fallback failed: {e2}")
            n_features = X_sc.shape[1] if hasattr(X_sc, 'shape') else len(feature_names or 10)
            return np.zeros((1, n_features)), 0.5


def plot_shap_waterfall(shap_values, expected_value, feature_names, max_features=8, probability=None):
    """
    Enhanced waterfall plot excluding Missing variables.
    """
    # Extract values
    vals = shap_values[0] if shap_values.ndim == 2 else shap_values
    
    # Create pairs of (feature_name, shap_value, index)
    pairs = []
    for i, name in enumerate(feature_names):
        if i < len(vals):
            # Skip Missing variables
            if _should_exclude_feature(name):
                continue
            # Skip zero or near-zero contributions (noise)
            if abs(vals[i]) < 0.001:
                continue
            pairs.append((name, vals[i], i))
    
    if not pairs:
        # If all were filtered, create a message figure
        fig = go.Figure()
        fig.add_annotation(
            text="No significant feature contributions detected.<br>All influencers are near zero.",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="#666")
        )
        fig.update_layout(
            height=200,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig, pd.DataFrame()
    
    # Sort by absolute impact and take top max_features
    pairs.sort(key=lambda x: abs(x[1]), reverse=True)
    pairs = pairs[:max_features]
    
    names = [p[0] for p in pairs]
    fvals = [p[1] for p in pairs]
    
    # Convert to friendly names
    friendly_names = [_make_friendly_name(n) for n in names]
    
    # Colors: green for positive, red for negative
    colors = ["#059669" if v > 0 else "#DC2626" for v in fvals]
    
    # Create bar chart (horizontal)
    fig = go.Figure(go.Bar(
        x=fvals[::-1],
        y=friendly_names[::-1],
        orientation='h',
        marker_color=colors[::-1],
        text=[f"{v:+.4f}" for v in fvals[::-1]],
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Impact: %{x:+.4f}<br><extra></extra>'
    ))
    
    # Add vertical line at zero
    fig.add_vline(x=0, line_dash="dash", line_color="rgba(0,0,0,0.3)")
    
    fig.update_layout(
        title={
            'text': "Feature Impact Analysis",
            'font': {'size': 14, 'family': 'DM Sans, sans-serif'}
        },
        height=min(400, 40 * len(friendly_names)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=80, t=40, b=20),
        font=dict(family='DM Sans', size=12),
        xaxis=dict(
            title="SHAP Value (Impact on Prediction)",
            gridcolor='rgba(150,150,150,.15)',
            zeroline=True,
            zerolinecolor='rgba(150,150,150,.4)'
        ),
        yaxis=dict(
            tickfont=dict(size=11),
            gridcolor='rgba(0,0,0,0)'
        )
    )
    
    # Create contributions DataFrame
    contributions_df = pd.DataFrame({
        'Feature': names,
        'Display Name': friendly_names,
        'SHAP Value': fvals,
        'Direction': ['Positive' if v > 0 else 'Negative' for v in fvals],
        'Absolute': np.abs(fvals)
    }).sort_values('Absolute', ascending=False)
    
    return fig, contributions_df


def _make_friendly_name(feature_name):
    """Convert technical feature names to readable clinical terms."""
    # Full mapping for common features
    mappings = {
        'Advanced_POCUS_Certification': '✓ Advanced POCUS Certification',
        'Physician_vs_APN': 'Provider: Physician',
        'Additional_training_Yes': '✓ Additional Training',
        'Additional_training_No': '✗ No Additional Training',
        'Manage_critically_ill_patients_Yes': '✓ Manages ICU Patients',
        'Manage_critically_ill_patients_No': '✗ Does Not Manage ICU',
        'Hospital_Setting_Yes': '✓ Academic Hospital',
        'Hospital_Setting_No': '✗ Community Hospital',
        'High_Income_Country_Yes': '✓ High-Income Country',
        'High_Income_Country_No': '✗ LMIC Country',
        'Adult_vs_Pediatric_Practitioner_Yes': '✓ Adult Practice',
        'Adult_vs_Pediatric_Practitioner_No': '✗ Pediatric Practice',
        'More_than_10_years_of_practice_Yes': '✓ >10 Years Experience',
        'More_than_10_years_of_practice_No': '✗ <10 Years Experience',
        'Large_Practice_hrs_Yes': '✓ Large Practice Volume',
        'Large_Practice_hrs_No': '✗ Small Practice Volume',
        'ICU_Patient_Count_>3000': '✓ High ICU Volume (>3000)',
        'ICU_Patient_Count_2000-3000': '✓ High ICU Volume (2000-3000)',
        'ICU_Patient_Count_1000-2000': '◯ Medium ICU Volume (1000-2000)',
        'ICU_Patient_Count_500-1000': '◯ Medium ICU Volume (500-1000)',
        'ICU_Patient_Count_<500': '✗ Low ICU Volume (<500)',
        'Years_Practiced_in_Specialty_>20 years': '✓ >20 Years Experience',
        'Years_Practiced_in_Specialty_11-20 years': '✓ 11-20 Years Experience',
        'Years_Practiced_in_Specialty_5-10 years': '◯ 5-10 Years Experience',
        'Years_Practiced_in_Specialty_<5 years': '✗ <5 Years Experience',
        'Specialty_Medical ICU': 'Specialty: Medical ICU',
        'Specialty_Cardiac Critical Care': 'Specialty: Cardiac Critical Care',
        'Specialty_Anesthesia': 'Specialty: Anesthesia',
        'Specialty_Neurology/Neuro Critical Care': 'Specialty: Neurology',
        'Specialty_Emergency Medicine': 'Specialty: Emergency Medicine',
        'Specialty_Surgical ICU': 'Specialty: Surgical ICU',
        'Specialty_Other': 'Specialty: Other',
    }
    
    # Try exact match
    if feature_name in mappings:
        return mappings[feature_name]
    
    # Clean up feature name
    cleaned = feature_name.replace('_', ' ')
    
    # Remove common patterns
    cleaned = cleaned.replace('Yes', '✓')
    cleaned = cleaned.replace('No', '✗')
    
    # Remove any 'Missing' references
    if 'Missing' in cleaned:
        return None  # Will be filtered out
    
    # Truncate if too long
    if len(cleaned) > 45:
        cleaned = cleaned[:42] + '...'
    
    return cleaned if cleaned else feature_name


def display_shap_insights(fig, contributions_df, prediction_label, probability):
    """
    Display SHAP insights with actionable recommendations.
    Fixed layout to prevent overlap and improved readability.
    """
    st.markdown("### 🔬 Understanding Your Prediction")
    st.markdown("The chart below shows which factors influenced your CCUSP prediction.")
    
    # Full width chart first (no sidebar)
    st.plotly_chart(fig, use_container_width=True)
    
    # Then show drivers in columns below the chart
    st.markdown("#### 📊 Key Drivers")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Positive contributors
        pos_contrib = contributions_df[contributions_df['SHAP Value'] > 0].head(5)
        if not pos_contrib.empty:
            st.markdown("**✅ Increases CCUSP probability:**")
            for _, row in pos_contrib.iterrows():
                display_name = row['Display Name']
                if display_name:
                    st.markdown(f"- {display_name}: **+{row['SHAP Value']:.4f}**")
    
    with col2:
        # Negative contributors
        neg_contrib = contributions_df[contributions_df['SHAP Value'] < 0].head(5)
        if not neg_contrib.empty:
            st.markdown("**⚠️ Decreases CCUSP probability:**")
            for _, row in neg_contrib.iterrows():
                display_name = row['Display Name']
                if display_name:
                    st.markdown(f"- {display_name}: **{row['SHAP Value']:.4f}**")
    
    if pos_contrib.empty and neg_contrib.empty:
        st.info("No significant feature contributions detected.")
    
    # Actionable recommendations
    st.markdown("---")
    st.markdown("#### 💡 Recommendations")
    
    if prediction_label == "High CCUSP":
        st.success("""
        ✅ **You demonstrate CCUSP competency.**
        
        **To maintain and enhance:**
        - Continue regular POCUS practice
        - Mentor junior colleagues
        - Explore advanced POCUS applications
        """)
    else:
        # Identify top negative factor for specific recommendation
        top_negative = contributions_df[contributions_df['SHAP Value'] < 0].head(1)
        if not top_negative.empty:
            factor = top_negative.iloc[0]['Display Name']
            # Clean up factor name for display
            if factor and '✗' in factor:
                factor = factor.replace('✗', '').strip()
            if factor:
                st.warning(f"""
                ⚠️ **Primary improvement area: {factor}**
                
                **Recommended actions:**
                - Pursue additional structured POCUS training
                - Seek mentorship from experienced colleagues
                - Increase ICU patient exposure
                """)
            else:
                st.warning("""
                ⚠️ **Recommendations to improve CCUSP competency:**
                - Pursue additional POCUS training or workshops
                - Consider Advanced POCUS Certification
                - Increase exposure to ICU patients
                """)
        else:
            st.warning("""
            ⚠️ **Recommendations to improve CCUSP competency:**
            - Pursue additional POCUS training or workshops
            - Consider Advanced POCUS Certification
            - Increase exposure to ICU patients
            """)
    
    # Educational note
    with st.expander("ℹ️ How to interpret this chart"):
        st.markdown("""
        **SHAP (SHapley Additive exPlanations)** shows how each factor contributed:
        
        - **Green bars** → Push prediction **toward** High CCUSP
        - **Red bars** → Push prediction **toward** Low CCUSP  
        - Bar length = magnitude of impact
        
        Focus on red bars to identify improvement areas.
        """)