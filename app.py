import streamlit as st
from components.chatbot import display_chatbot
from components.live_matches import display_live_matches
from services.gemini_service import initialize_gemini_client
from config import PAGE_CONFIG
import os

# This MUST be the first Streamlit command
st.set_page_config(**PAGE_CONFIG)

# Add custom CSS for dark theme
st.markdown("""
<style>
    /* Dark theme */
    body {
        background-color: #0e1117;
        color: #ffffff;
    }
    
    .main .block-container {
        padding-top: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 1200px;
    }
    
    /* Ensure chat messages have proper spacing */
    .stChatMessage {
        margin-bottom: 1rem;
    }
    
    /* Style for live match cards */
    .match-card {
        border: 1px solid #333;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
        background-color: #1e1e1e;
    }
    
    /* Live indicator styling */
    .live-indicator {
        background-color: #ff4b4b;
        color: white;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        display: inline-block;
    }
    
    /* Make sidebar wider when showing matches */
    [data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
        width: 350px;
    }
    
    /* Customize tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0px;
        border-bottom: 1px solid #333;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 0px;
        padding-top: 10px;
        padding-bottom: 10px;
        color: white;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: transparent;
        color: #ff4b4b !important;
        font-weight: bold;
        border-bottom: 2px solid #ff4b4b;
    }
    
    /* Status indicator */
    [data-testid="stStatus"] {
        background-color: #1e1e1e;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session states
if "show_scorecard" not in st.session_state:
    st.session_state.show_scorecard = False
if "selected_match_id" not in st.session_state:
    st.session_state.selected_match_id = None
if "selected_match_title" not in st.session_state:
    st.session_state.selected_match_title = None
if "show_live_matches" not in st.session_state:
    st.session_state.show_live_matches = True

# Initialize Gemini client with status indicator
with st.status("Initializing chatbot resources (Client & FAISS Cache)...", expanded=False) as status:
    initialize_gemini_client()
    status.update(label="Resources initialized successfully!", state="complete")

# Sidebar content
with st.sidebar:
    st.header("⚙️ Bot Info & Settings")
    st.markdown("---")
    
    # Model info
    from config import MODEL_NAME, EMBEDDING_MODEL
    st.write(f"**Model:** `{MODEL_NAME}`")
    st.write(f"**Embedding:** `{EMBEDDING_MODEL}`")
    
    # Live matches toggle
    st.markdown("---")
    st.subheader("🏏 Live Matches")
    show_matches = st.toggle("Show Live Cricket Updates", value=st.session_state.show_live_matches)
    
    # Update session state if toggle changed
    if show_matches != st.session_state.show_live_matches:
        st.session_state.show_live_matches = show_matches
        st.rerun()
    
    # Display live matches in sidebar if enabled
    if st.session_state.show_live_matches:
        st.markdown("---")
        display_live_matches()
    
    # Cache info
    st.markdown("---")
    from utils.cache_utils import get_cache_info
    cache_info = get_cache_info()
    st.subheader("Cache Details")
    st.write(f"**Status:** {cache_info['status']}")
    st.write(f"**Items Indexed:** `{cache_info['items']}`")
    st.write(f"**Directory:** `{cache_info['directory']}`")
    st.write(f"**Similarity Threshold:** `{cache_info['threshold']}`")
    
    # Session control
    st.markdown("---")
    st.header("📄 Session Control")
    if st.button("Clear Chat History", key="clear_chat"):
        if "messages" in st.session_state:
            st.session_state.messages = []
        if "chat" in st.session_state:
            del st.session_state["chat"]
        st.rerun()
    st.caption("Reload page to fully reset.")

# Main content area
if st.session_state.show_scorecard and st.session_state.selected_match_id:
    from components.scorecard import display_scorecard
    display_scorecard(st.session_state.selected_match_id, st.session_state.selected_match_title)
else:
    display_chatbot()
