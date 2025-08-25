import streamlit as st

def admin_login():
    """Basic admin login system"""
    st.sidebar.subheader("🔑 Admin Login")

    username = st.sidebar.text_input("Username", key="admin_user")
    password = st.sidebar.text_input("Password", type="password", key="admin_pass")

    if st.sidebar.button("Login"):
        if (
            username == st.secrets["admin"]["username"]
            and password == st.secrets["admin"]["password"]
        ):
            st.session_state["admin_authenticated"] = True
            st.success("✅ Logged in successfully!")
        else:
            st.error("❌ Invalid username or password")

    return st.session_state.get("admin_authenticated", False)


def admin_logout_button():
    """Logout button in sidebar"""
    if st.session_state.get("admin_authenticated", False):
        if st.sidebar.button("Logout"):
            st.session_state["admin_authenticated"] = False
            st.success("🔒 Logged out successfully")
            st.experimental_rerun()
