import streamlit as st
import streamlit.components.v1 as components
import time
from services.cricket_api import get_match_commentary

def process_commentary_text(comment):
    """
    Process commentary text to replace format markers with their values
    
    Args:
        comment (dict): The commentary item
        
    Returns:
        str: Processed commentary text
    """
    comm_text = comment.get("commText", "")
    
    # Process formatting (bold text)
    if "commentaryFormats" in comment and "bold" in comment["commentaryFormats"]:
        bold_format = comment["commentaryFormats"]["bold"]
        format_ids = bold_format.get("formatId", [])
        format_values = bold_format.get("formatValue", [])
        
        # Replace format IDs with their values
        for i in range(len(format_ids)):
            if i < len(format_values):
                comm_text = comm_text.replace(format_ids[i], format_values[i])
    
    # Clean up the text
    comm_text = comm_text.strip()
    
    return comm_text

def display_commentary(match_id):
    """
    Displays cricket match commentary in Streamlit
    
    Args:
        match_id (str): The ID of the match
    """
    # Add custom CSS for commentary styling
    st.markdown("""
    <style>
        .commentary-container {
            margin-bottom: 15px;
        }
        .wicket-commentary {
            background-color: #3c1518;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
            border-left: 4px solid #ff4b4b;
        }
        .four-commentary {
            background-color: #1e2a38;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
            border-left: 4px solid #4cc9f0;
        }
        .six-commentary {
            background-color: #1e2a38;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
            border-left: 4px solid #8338ec;
        }
        .regular-commentary {
            background-color: #1e1e1e;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 10px;
        }
        .event-label {
            color: #ff4b4b;
            font-weight: bold;
        }
        .four-label {
            color: #4cc9f0;
            font-weight: bold;
        }
        .six-label {
            color: #8338ec;
            font-weight: bold;
        }
        .over-label {
            font-size: 14px;
        }
        .commentary-text {
            font-size: 16px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Fetch commentary
    with st.spinner("Loading commentary..."):
        commentary_data = get_match_commentary(match_id)
    
    if not commentary_data or "commentaryList" not in commentary_data:
        st.info("No commentary available for this match.")
        return
    
    commentary_list = commentary_data.get("commentaryList", [])
    
    # Add auto-refresh option
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Live Commentary")
    with col2:
        auto_refresh = st.checkbox("Auto-refresh", value=True, key=f"auto_refresh_comm_{match_id}")
    
    # Display commentary
    for comment in commentary_list[:20]:  # Show last 20 comments
        event = comment.get("event", "NONE")
        over_number = comment.get("overNumber", "")
        
        # Process the commentary text
        comm_text = process_commentary_text(comment)
        
        # Determine if this is a special event
        is_wicket = event == "WICKET" or "THATS OUT!!" in comm_text or "out" in comm_text
        is_four = event == "FOUR" or "FOUR" in comm_text
        is_six = event == "SIX" or "SIX" in comm_text
        
        # Create HTML for the commentary based on event type
        if is_wicket:
            html = f"""
            <div class="wicket-commentary">
                <span class="event-label">WICKET!</span><br>
                <span class="over-label">Over {over_number}</span><br>
                <span class="commentary-text">{comm_text}</span>
            </div>
            """
        elif is_four:
            html = f"""
            <div class="four-commentary">
                <span class="four-label">FOUR!</span><br>
                <span class="over-label">Over {over_number}</span><br>
                <span class="commentary-text">{comm_text}</span>
            </div>
            """
        elif is_six:
            html = f"""
            <div class="six-commentary">
                <span class="six-label">SIX!</span><br>
                <span class="over-label">Over {over_number}</span><br>
                <span class="commentary-text">{comm_text}</span>
            </div>
            """
        else:
            html = f"""
            <div class="regular-commentary">
                <span class="over-label">Over {over_number}</span><br>
                <span class="commentary-text">{comm_text}</span>
            </div>
            """
        
        # Render the HTML
        st.markdown(html, unsafe_allow_html=True)
    
    # Non-blocking auto-refresh logic
    if auto_refresh:
        placeholder = st.empty()
        
        # Initialize counter in session state if not exists
        if f"comm_refresh_counter_{match_id}" not in st.session_state:
            st.session_state[f"comm_refresh_counter_{match_id}"] = 30
        
        # Display current countdown
        placeholder.text(f"Next refresh in {st.session_state[f'comm_refresh_counter_{match_id}']} seconds")
        
        # Schedule the next refresh
        if st.session_state[f"comm_refresh_counter_{match_id}"] <= 0:
            st.session_state[f"comm_refresh_counter_{match_id}"] = 30
            st.rerun()
        else:
            # Decrement counter for next run
            st.session_state[f"comm_refresh_counter_{match_id}"] -= 1
