"""
Sidebar UI components for layer selection and configuration.
"""
import streamlit as st

def render_sidebar():
    """Renders the entire sidebar interface."""
    st.sidebar.title("City of Westminster Green Cover", text_alignment="center")
    
    # --- Configuration Expander ---
    with st.sidebar.expander("⚙️ Connection Settings"):
        api_url = st.text_input("API Base URL", value=st.session_state["api_url"])
        s3_prefix = st.text_input("S3 Target Folder", value=st.session_state["s3_prefix"])
        if st.button("Update Connection"):
            st.session_state["api_url"] = api_url.rstrip("/")
            st.session_state["s3_prefix"] = s3_prefix.strip("/")
            st.rerun()

    st.sidebar.divider()

    # --- Active Layers Management ---
    st.sidebar.subheader("Active Layers")
    st.session_state["global_opacity"] = st.sidebar.slider("Global Layer Opacity", 0.0, 1.0, 1.0, 0.05)
    
    if st.sidebar.button("Clear All Layers", use_container_width=True):
        st.session_state["layers"] = []
        st.rerun()