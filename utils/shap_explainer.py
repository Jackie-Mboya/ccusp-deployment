"""SHAP waterfall chart using Plotly."""

import numpy as np
import plotly.graph_objects as go

def get_shap_explanation(model, X_sc, feature_names=None):
    """
    Get SHAP explanation for a single prediction.
    
    Args:
        model: The trained model
        X_sc: Scaled features
        feature_names: List of feature names (optional)
    
    Returns:
        sv: SHAP values
        expected_value: Expected value (baseline)
    """
    try:
        import shap
        
        # If X_sc is numpy array and we have feature_names, convert to DataFrame
        if isinstance(X_sc, np.ndarray) and feature_names is not None:
            if X_sc.ndim == 1:
                X_sc = X_sc.reshape(1, -1)
            X_sc = pd.DataFrame(X_sc, columns=feature_names)
        
        # Create explainer
        exp = shap.LinearExplainer(model, X_sc)
        sv = exp.shap_values(X_sc)
        
        return sv, exp.expected_value
        
    except Exception as e:
        # Return dummy values if SHAP fails
        if hasattr(X_sc, 'shape'):
            n_features = X_sc.shape[1] if X_sc.ndim > 1 else len(X_sc)
        else:
            n_features = len(feature_names) if feature_names else 10
        return np.zeros((1, n_features)), 0.0

def plot_shap_waterfall(shap_values, expected_value, feature_names, max_f=12):
    vals = shap_values[0] if shap_values.ndim == 2 else shap_values
    n    = min(len(vals), len(feature_names))
    idx  = np.argsort(np.abs(vals[:n]))[::-1][:max_f]
    names  = [feature_names[i] for i in idx]
    fvals  = vals[idx]
    colors = ["#059669" if v > 0 else "#DC2626" for v in fvals]

    fig = go.Figure(go.Bar(
        x=fvals[::-1], y=names[::-1], orientation='h',
        marker_color=colors[::-1],
        text=[f"{v:+.3f}" for v in fvals[::-1]],
        textposition='outside',
    ))
    fig.update_layout(
        height=300,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=60, t=8, b=8),
        font=dict(family='DM Sans', size=11),
        xaxis=dict(title="SHAP impact", gridcolor='rgba(150,150,150,.15)',
                   zeroline=True, zerolinecolor='rgba(150,150,150,.4)'),
        yaxis=dict(gridcolor='rgba(0,0,0,0)'),
    )
    return fig
