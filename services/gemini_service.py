import streamlit as st
import sys
import traceback
from config import MODEL_NAME, SYSTEM_INSTRUCTION

# Import Gemini libraries
try:
    import google.genai as genai
    from google.genai import types as genai_types
    from google.generativeai.types import StopCandidateException
    print(f"Using google-genai SDK version: {genai.__version__}")
except ImportError as e:
    StopCandidateException = Exception
    if "google.generativeai" in str(e):
        st.error("WARNING: Specific StopCandidateException not found.")
    elif "google.genai" in str(e):
        st.error("ERROR: 'google-generativeai' package required.")
        st.stop()
    else:
        st.error(f"ERROR: Import error: {e}")
        st.stop()
except Exception as e:
     st.error(f"ERROR: Failed to import google.genai: {e}")
     st.stop()

# Global client variable
client = None

@st.cache_resource
def initialize_gemini_client():
    """Initialize the Gemini client and store it in the global variable"""
    global client
    
    try:
        # Get API key from Streamlit secrets
        api_key = st.secrets.get("GOOGLE_API_KEY")
        if not api_key:
            st.error("❌ Google API Key not found in Streamlit secrets!")
            print("❌ ERROR: API Key missing", file=sys.stderr)
            st.stop()
        
        # Initialize client
        client = genai.Client(api_key=api_key)
        print("✅ Gemini Client initialized.")
        return client
    except Exception as e:
        st.error(f"Fatal Error during client initialization: {e}")
        print(f"❌ FATAL ERROR during client initialization: {type(e).__name__} - {e}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        st.stop()

def get_client():
    """Get the initialized Gemini client"""
    global client
    if client is None:
        initialize_gemini_client()
    return client

def get_tools():
    """Returns the list of tools available to the Gemini model."""
    # Import here to avoid circular imports
    from utils.web_search import get_search_results_with_cache
    
    print("Defining Tool List (Web Search with Cache)...")
    tools = [get_search_results_with_cache]
    print(f"✅ Tools defined: {[func.__name__ for func in tools]}")
    return tools

def get_chat_session():
    """Get or create a chat session"""
    if "chat" not in st.session_state:
        try:
            print(f"\nCreating NEW Gemini Chat Session with model '{MODEL_NAME}'...")
            
            # Ensure client is initialized
            client = get_client()
            if client is None:
                raise ValueError("Gemini client is not initialized before creating chat.")
            
            # Get tools
            tools = get_tools()
            
            # Create chat session
            st.session_state.chat = client.chats.create(
                model=MODEL_NAME,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=tools,
                )
            )
            print("✅ New Gemini chat session created and stored.")
        except Exception as e:
            st.error(f"❌ ERROR: Failed to initialize Gemini chat session: {type(e).__name__} - {e}")
            print(f"❌ ERROR: Failed to initialize chat session: {type(e).__name__} - {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            st.stop()
    
    return st.session_state.chat
