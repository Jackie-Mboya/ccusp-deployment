import streamlit as st
from utils.database import register_user, SPECIALTIES, HOSPITALS, PROVIDER_TYPES, INCOME_LEVELS

st.set_page_config(page_title="Register", page_icon="📝")

st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: none !important;}
        [data-testid="collapsedControl"] {display: none !important;}
        [data-testid="stSidebarNav"] {display: none !important;}
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; margin-bottom: 2rem;">
    <h1 style="font-family: 'DM Serif Display', serif; color: #0C1F2E;">📝 Practitioner Registration</h1>
    <p style="color: #717168;">Create your account to access the CCUSP self-assessment tool</p>
</div>
""", unsafe_allow_html=True)

# Registration form
with st.form("register_form"):
    full_name = st.text_input("Full name *")
    email = st.text_input("Email address *")
    
    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Choose username *")
    with col2:
        password = st.text_input("Password *", type="password")
    
    col3, col4 = st.columns(2)
    with col3:
        specialty = st.selectbox("Specialty *", SPECIALTIES)
    with col4:
        hospital = st.selectbox("Hospital *", HOSPITALS)
    
    col5, col6 = st.columns(2)
    with col5:
        provider_type = st.selectbox("Provider type *", PROVIDER_TYPES)
    with col6:
        country_income = st.selectbox("Country income *", INCOME_LEVELS)
    
    st.caption("* Required fields")
    
    # This is the form submit button - it's allowed inside the form
    submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")
    
    if submitted:
        if not all([full_name, email, username, password]):
            st.error("❌ Please fill in all required fields")
        else:
            ok, msg = register_user(
                full_name, email, username, password,
                specialty, hospital, country_income, provider_type,
            )
            if ok:
                st.success("✅ Account created successfully!")
                # Store success state in session
                st.session_state.registration_success = True
                st.session_state.registered_username = username
            else:
                st.error(f"❌ {msg}")

# Handle post-registration actions (outside the form)
if st.session_state.get("registration_success", False):
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔐 Go to Login", use_container_width=True):
            # Clear success state and go to login
            st.session_state.registration_success = False
            st.switch_page("pages/login.py")
    with col2:
        if st.button("📝 Register Another", use_container_width=True):
            # Just clear the success state to show form again
            st.session_state.registration_success = False
            st.rerun()

# Back to home button (always available, outside form)
if not st.session_state.get("registration_success", False):
    if st.button("← Back to Home", use_container_width=True):
        st.switch_page("app.py")