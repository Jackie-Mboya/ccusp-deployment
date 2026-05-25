# CCUSP Prediction System

> MSc Data Science & Analytics · Strathmore University  
> Mboya Jackline Achieng — Reg. 193670

---

## Credentials

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| Practitioner | *(register first)* | *(you choose)* | Stored in SQLite |

---

## Setup

```bash
# 1. Copy 3 pkl files from Google Drive into models/
#    tuned_ensemble_lasso_models.pkl
#    scaler.pkl
#    tuned_optimal_threshold.pkl

# 2. Install and run (Git Bash)
source .venv/Scripts/activate       # if using venv
pip install -r requirements.txt
streamlit run app.py
```

---

## How It Works

**Register** → create an account with name, email, specialty, hospital  
**Sign in** → access your self-assessment form  
**Run prediction** → live model output 
**Admin dashboard** → all charts generated dynamically from real DB data  

## File Structure

```
ccusp_deployment/
├── app.py                    ← Entry point
├── requirements.txt
├── pages/
│   ├── practitioner.py       ← Self-assessment (real model prediction)
│   └── admin.py              ← Dynamic analytics dashboard
├── utils/
│   ├── database.py           ← SQLite registry + prediction log
│   ├── model_loader.py       ← Load models + predict_from_ui()
│   └── shap_explainer.py     ← SHAP chart
├── models/                   ← Place pkl files here
└── data/                     ← ccusp_users.db auto-created here
```


Link ccusp-deployment-knkc2rbqhx4qirx4wbvgj5.streamlit.app
