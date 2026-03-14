import streamlit as st
from practitioner import render_history

st.set_page_config(page_title="My History", page_icon="📊")

if 'current_user' in st.session_state:
    render_history(st.session_state.current_user)
else:
    st.switch_page("app.py")