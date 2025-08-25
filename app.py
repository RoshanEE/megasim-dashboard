import streamlit as st
import os

st.set_page_config(page_title="MEGASIM Dashboard", layout="wide")

st.title("⚽ MEGASIM Dashboard")

st.markdown("""
Welcome!  
Use the sidebar to navigate between:
- **Admin Panel**
- **Player Stats**
- **Team Stats**
- **Leaderboards**
- **Fixtures & Results**
""")

if not os.path.exists("data"):
    os.makedirs("data")
