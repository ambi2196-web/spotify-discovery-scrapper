"""
Spotify Discovery · Review Analysis Heatmap
Streamlit entry point — serves the pre-built self-contained dashboard.
"""
import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

st.set_page_config(
    page_title="Spotify Discovery · Review Analysis",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Remove default Streamlit chrome so the dashboard fills the page
st.markdown("""
<style>
  #MainMenu, header, footer {visibility: hidden;}
  .block-container {padding: 0 !important; max-width: 100% !important;}
</style>
""", unsafe_allow_html=True)

HTML_PATH = Path(__file__).parent / "reports" / "heatmap_dashboard.html"

if HTML_PATH.exists():
    html_content = HTML_PATH.read_text(encoding="utf-8")
    components.html(html_content, height=1800, scrolling=True)
else:
    st.error("Dashboard not found. Run `python generate_heatmap.py` first.")
    st.code("python generate_heatmap.py", language="bash")
