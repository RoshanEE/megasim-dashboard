import streamlit as st
from pathlib import Path
import time
from utils.auth import admin_login, admin_logout_button

st.title("🔐 Admin Panel")

# Resolve project root even when this file is inside /pages
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
TARGET = DATA_DIR / "latest.xlsx"

st.caption(f"Data directory: `{DATA_DIR}`")

if admin_login():
    st.success("Authenticated as Admin.")
    admin_logout_button()

    uploaded = st.file_uploader("Upload Excel (.xlsx) to replace current data", type=["xlsx"])
    if uploaded is not None:
        # Save to absolute path
        TARGET.write_bytes(uploaded.getbuffer())

        # Bump a version to bust caches across pages
        st.session_state["data_version"] = time.time()

        # Clear all cached @st.cache_data functions globally
        st.cache_data.clear()

        st.success(f"✅ Saved to: `{TARGET}`")
        st.info("All pages will now read this file. Switch to Player Stats and hit 'Reload data' if needed.")

    if TARGET.exists():
        st.caption(f"Current data file present ✔ — `{TARGET}` (last modified: {time.ctime(TARGET.stat().st_mtime)})")
    else:
        st.warning(f"No data file found yet at: `{TARGET}`")

    if st.button("Clear current data (delete file)"):
        try:
            if TARGET.exists():
                TARGET.unlink()
            st.cache_data.clear()
            st.success("Data file removed. Caches cleared.")
        except Exception as e:
            st.error(f"Failed to remove file: {e}")
