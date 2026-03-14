import streamlit as st
from utils.model_loader import load_models
from practitioner import render_assessment

st.set_page_config(page_title="Self Assessment", page_icon="🩺")

if 'current_user' in st.session_state:
    models = load_models("models")
    render_assessment(models, st.session_state.current_user)
else:
    st.switch_page("app.py")