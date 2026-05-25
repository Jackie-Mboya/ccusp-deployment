# CCUSP Prediction System

> MSc Data Science & Analytics · Strathmore University

## Overview

The **CCUSP (Critical Care Ultrasound Practitioner) Prediction System** is a machine learning-powered web application that predicts a practitioner's likelihood of achieving CCUSP certification based on their professional background, training, and practice patterns. The system provides real-time predictions with SHAP-based explainability to help practitioners understand key factors influencing their certification potential.

## Features

- **User Authentication** — Secure registration and login system
- **Self-Assessment Tool** — Interactive form for practitioners to evaluate their CCUSP readiness
- **Real-Time Predictions** — Powered by tuned ensemble Lasso models
- **Model Explainability** — SHAP value visualizations showing feature importance
- **Admin Dashboard** — Dynamic analytics with real-time charts from live database
- **Prediction History** — Tracks and stores all predictions for analysis

## Technology Stack

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: SQLite
- **Machine Learning**: Scikit-learn, SHAP, XGBoost
- **Visualization**: Matplotlib, Plotly

## Installation

### Prerequisites

- Python 3.8 or higher
- Git Bash (Windows) or terminal (Mac/Linux)

### Setup Instructions

```bash
# 1. Clone the repository
git clone <repository-url>
cd ccusp_deployment

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/Scripts/activate        # Windows (Git Bash)
# OR
source .venv/bin/activate            # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download model files from Google Drive and place in models/ folder
#    - tuned_ensemble_lasso_models.pkl
#    - scaler.pkl
#    - tuned_optimal_threshold.pkl

# 5. Run the application
streamlit run app.py
