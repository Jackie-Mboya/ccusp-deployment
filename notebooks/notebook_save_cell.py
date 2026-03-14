"""
PASTE THIS AS THE FINAL CELL IN CCUSP_V4_tuned.ipynb
Saves the 3 files the deployment app needs.
"""
import joblib, os

save_dir = '/content/drive/My Drive/Thesis Project/my_visuals'
os.makedirs(save_dir, exist_ok=True)

joblib.dump(tuned_lasso_models,
            os.path.join(save_dir, 'tuned_ensemble_lasso_models.pkl'))
joblib.dump(scaler,
            os.path.join(save_dir, 'scaler.pkl'))
joblib.dump(best_thresh_t,
            os.path.join(save_dir, 'tuned_optimal_threshold.pkl'))

print("Saved:")
for f in ['tuned_ensemble_lasso_models.pkl', 'scaler.pkl', 'tuned_optimal_threshold.pkl']:
    path = os.path.join(save_dir, f)
    print(f"  {f}  ({os.path.getsize(path):,} bytes)")
print("\nCopy these 3 files into:  ccusp_deployment/models/")
print("Then run:  streamlit run app.py")
