import streamlit as st
from utils.database import authenticate

st.set_page_config(page_title="Login", page_icon="🔐")

st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none !important;}
        [data-testid="collapsedControl"] {display: none !important;}
        [data-testid="stSidebarNav"] {display: none !important;}
    </style>
""", unsafe_allow_html=True)

# Check if coming from landing page
if 'login_role' not in st.session_state:
    st.session_state.login_role = None

st.markdown("""
<div style="text-align: center; margin-bottom: 2rem;">
    <h1 style="font-family: 'DM Serif Display', serif; color: #0C1F2E;">🔐 Login</h1>
</div>
""", unsafe_allow_html=True)

# Role selection if not already selected
if not st.session_state.login_role:
    st.markdown("### Select your role")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("👨‍⚕️ Practitioner", use_container_width=True):
            st.session_state.login_role = "practitioner"
            st.rerun()
    
    with col2:
        if st.button("👩‍💼 Admin", use_container_width=True):
            st.session_state.login_role = "admin"
            st.rerun()
else:
    # Show back button
    if st.button("← Back to role selection"):
        st.session_state.login_role = None
        st.rerun()
    
    # Login form
    role_display = "Practitioner" if st.session_state.login_role == "practitioner" else "Admin"
    st.markdown(f"### {role_display} Login")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login", use_container_width=True, type="primary"):
            user = authenticate(username, password)
            if user and user['role'] == st.session_state.login_role:
                st.session_state["logged_in"] = True
                st.session_state["current_user"] = user
                st.session_state.login_role = None
                st.switch_page("app.py")
            else:
                st.error(f"❌ Invalid credentials for {role_display}")