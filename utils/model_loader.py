"""
Model loading and prediction for CCUSP deployment.
"""

import os
import joblib
import numpy as np
import pandas as pd
import json

# ── Exact columns the scaler was fitted on ────────────────────────────────────
EXPECTED_COLUMNS = [
    'Physician_vs_APN',
    'Advanced_POCUS_Certification',
    'High_Income_Country_Missing',
    'High_Income_Country_No',
    'High_Income_Country_Yes',
    'Adult_vs_Pediatric_Practitioner_Missing',
    'Adult_vs_Pediatric_Practitioner_No',
    'Adult_vs_Pediatric_Practitioner_Yes',
    'More_than_10_years_of_practice_Missing',
    'More_than_10_years_of_practice_No',
    'More_than_10_years_of_practice_Yes',
    'Large_Practice_hrs_Missing',
    'Large_Practice_hrs_No',
    'Large_Practice_hrs_Yes',
    'Additional_training_Missing',
    'Additional_training_No',
    'Additional_training_Yes',
    'Manage_critically_ill_patients_Missing',
    'Manage_critically_ill_patients_No',
    'Manage_critically_ill_patients_Yes',
    'Hospital_Setting_Missing',
    'Hospital_Setting_No',
    'Hospital_Setting_Yes',
    'Specialty_Anesthesia',
    'Specialty_Cardiac Critical Care',
    'Specialty_Medical ICU',
    'Specialty_Missing',
    'Specialty_Neurology/Neuro Critical Care',
    'Years_Practiced_in_Specialty_11-20 years',
    'Years_Practiced_in_Specialty_5-10 years',
    'Years_Practiced_in_Specialty_<5 years',
    'Years_Practiced_in_Specialty_>20 years',
    # Years_Practiced_in_Specialty_Missing excluded — not present in fitted scaler
    'ICU_Patient_Count_1000-2000',
    'ICU_Patient_Count_2000-3000',
    'ICU_Patient_Count_500-1000',
    'ICU_Patient_Count_<500',
    'ICU_Patient_Count_>3000',
    # ICU_Patient_Count_Missing excluded — not present in fitted scaler
]

_CATEGORICAL = [
    'High_Income_Country', 'Adult_vs_Pediatric_Practitioner',
    'More_than_10_years_of_practice', 'Large_Practice_hrs',
    'Additional_training', 'Manage_critically_ill_patients',
    'Hospital_Setting', 'Specialty',
    'Years_Practiced_in_Specialty', 'ICU_Patient_Count',
]


def load_ensemble_metrics(model_path='models'):
    """Load only Ensemble LASSO metrics from JSON file."""
    metrics_path = os.path.join(model_path, 'ensemble_metrics.json')
    if os.path.exists(metrics_path):
        with open(metrics_path, 'r') as f:
            return json.load(f)
    return {
        'model_name': 'Ensemble LASSO',
        'f1_score': 0.8385,
        'accuracy': 0.7655,
        'precision': 0.8191,
        'recall': 0.8590,
        'auc_roc': 0.7244,
        'auprc': 0.8487,
        'threshold': 0.4023,
        'cv_folds': 3,
        'inference_ms': 3.316,
        'train_time_s': 20.168
    }


def load_models(model_path='models'):
    """Load only Ensemble LASSO models and metrics."""
    files = {
        'scaler':       'scaler.pkl',
        'lasso_models': 'tuned_ensemble_lasso_models.pkl',
        'threshold':    'tuned_optimal_threshold.pkl',
    }
    missing = [f for f in files.values()
               if not os.path.exists(os.path.join(model_path, f))]
    if missing:
        raise FileNotFoundError(
            f"Missing model files in '{model_path}': {missing}. "
            "Copy pkl files from Google Drive/my_visuals/ into models/.")
    try:
        models = {k: joblib.load(os.path.join(model_path, f)) for k, f in files.items()}
        models['metrics'] = load_ensemble_metrics(model_path)
        return models
    except Exception as e:
        raise RuntimeError(f"Failed to load model artifacts: {e}") from e


def map_ui_to_training_values(ui_dict):
    """Convert UI input values to the categorical values used during training."""
    mapped = {}
    mapped['High_Income_Country'] = 'Yes' if ui_dict['income'] == 'High Income' else 'No'
    mapped['Adult_vs_Pediatric_Practitioner'] = 'Yes' if ui_dict['pop'] == 'Adult' else 'No'
    mapped['More_than_10_years_of_practice'] = 'Yes' if ui_dict['yrs'] in ['11-20 years', '>20 years'] else 'No'
    mapped['Large_Practice_hrs'] = 'Yes' if ui_dict['icu_vol'] in ['2000-3000', '>3000'] else 'No'
    mapped['Additional_training'] = ui_dict['extra']
    mapped['Manage_critically_ill_patients'] = ui_dict['manages']
    mapped['Hospital_Setting'] = 'Yes' if ui_dict['hosp_type'] == 'Academic' else 'No'
    specialty_map = {
        'Anesthesiology': 'Anesthesia',
        'Cardiac Critical Care': 'Cardiac Critical Care',
        'Medical ICU': 'Medical ICU',
        'Neurology/Neuro Critical Care': 'Neurology/Neuro Critical Care',
        'Surgical ICU': 'Surgical ICU',
    }
    mapped['Specialty'] = specialty_map.get(ui_dict['specialty'], ui_dict['specialty'])
    mapped['Years_Practiced_in_Specialty'] = ui_dict['yrs']
    mapped['ICU_Patient_Count'] = ui_dict['icu_vol']
    mapped['Physician_vs_APN'] = 1 if ui_dict['provider_type'] == 'Physician' else 0
    mapped['Advanced_POCUS_Certification'] = 1 if ui_dict['cert'] == 'Yes' else 0
    return mapped


def preprocess_input(ui_dict):
    """Transform UI inputs into the format expected by the model."""
    mapped_values = map_ui_to_training_values(ui_dict)
    df = pd.DataFrame([mapped_values])
    df_encoded = pd.get_dummies(df, columns=_CATEGORICAL, drop_first=False)
    df_encoded = df_encoded.reindex(columns=EXPECTED_COLUMNS, fill_value=0)
    return df_encoded.astype(float)


def predict_from_ui(models, ui_dict: dict, use_youden: bool = True):
    """
    Main prediction function. Takes clean UI dict and returns prob, pred, X_sc.
    """
    X_input  = preprocess_input(ui_dict)
    X_scaled = models['scaler'].transform(X_input)

    # ── Keep column names so sklearn doesn't warn about feature name mismatch ─
    X_scaled = pd.DataFrame(X_scaled, columns=EXPECTED_COLUMNS)

    prob_list = []
    for model in models['lasso_models']:
        prob = model.predict_proba(X_scaled)[:, 1]
        prob_list.append(prob)

    prob      = float(np.mean(prob_list))
    threshold = models['threshold'] if use_youden else 0.5
    pred      = int(prob >= threshold)

    return prob, pred, X_scaled