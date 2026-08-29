"""
App entry point — sets up the page, theme, and sidebar navigation menu.

Run with:
    streamlit run app/streamlit_app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so "app.theme" imports work

import streamlit as st

from finance_controller.db.session import init_db
from app.theme import inject_theme

st.set_page_config(
    page_title="AI Finance Controller",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()
init_db()

with st.sidebar:
    st.markdown(
        "<div style='padding: 8px 0 20px 0;'>"
        "<div style='font-family:Space Grotesk; font-size:1.3rem; font-weight:600; color:white;'>Finance Controller</div>"
        "<div style='font-size:0.8rem; color:#9CA3AF;'>Multi-source reconciliation</div>"
        "</div>",
        unsafe_allow_html=True,
    )

pages = {
    "": [
        st.Page("views/dashboard.py", title="Dashboard", icon=":material/dashboard:"),
        st.Page("views/ingestion.py", title="Add Your Data", icon=":material/upload_file:"),
        st.Page("views/reconciliation.py", title="Reconciliation", icon=":material/fact_check:"),
        st.Page("views/chat.py", title="Verify Your Record", icon=":material/chat:"),
    ]
}

nav = st.navigation(pages)
nav.run()