import streamlit as st

def show_under_construction(panel_name: str = "This panel"):
    st.markdown(
        f"""
        <div style='text-align: center; padding: 60px;'>
            <h1 style='font-size: 3em;'>🚧 {panel_name} Under Construction 🚧</h1>
            <p style='font-size: 1.5em; color: gray;'>
                We're working hard to bring this feature to you soon!
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
