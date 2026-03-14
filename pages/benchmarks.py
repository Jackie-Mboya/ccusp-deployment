import streamlit as st
from practitioner import render_benchmarks

st.set_page_config(page_title="Benchmarks", page_icon="📈")

if 'current_user' in st.session_state:
    render_benchmarks(st.session_state.current_user)
else:
    st.switch_page("app.py")