import streamlit as st
import time
from services.cricket_api import get_live_cricket_matches

def display_live_matches():
    """Display live cricket matches in a Streamlit component"""
    # Add auto-refresh option
    auto_refresh = st.checkbox("Auto-refresh (every 30 seconds)", value=True, key="refresh_toggle")
    
    # Container for match data that will be refreshed
    match_container = st.container()
    
    # Function to load and display matches
    def load_matches():
        with match_container:
            st.empty()  # Clear previous content
            
            with st.spinner("Fetching live matches..."):
                live_matches = get_live_cricket_matches()
            
            if live_matches.get("status") == "success" and live_matches.get("response"):
                for series in live_matches["response"]:
                    st.subheader(series.get("seriesName", "Unknown Series"))
                    
                    for match in series.get("matchList", []):
                        with st.expander(f"{match.get('matchTitle', 'Unknown Match')}", expanded=True):
                            # Live indicator
                            if match.get('currentStatus') == 'live':
                                st.markdown("🔴 **LIVE**")
                            
                            # Match status
                            status = match.get('matchStatus', 'N/A')
                            st.write(f"**Status:** {status}")
                            
                            # Team information with proper formatting
                            team1 = match.get('teamOne', {})
                            team2 = match.get('teamTwo', {})
                            
                            # Get team codes and format them properly
                            team1_code = team1.get('teamShortName', team1.get('name', 'Team 1'))
                            team2_code = team2.get('teamShortName', team2.get('name', 'Team 2'))
                            
                            # Format scores
                            team1_score = team1.get('score', '')
                            team2_score = team2.get('score', '')
                            
                            # Add overs information if available
                            team1_overs = team1.get('overs', '')
                            if team1_score and team1_overs:
                                team1_display = f"{team1_score} ({team1_overs} Ovs)"
                            elif team1_score:
                                team1_display = team1_score
                            else:
                                team1_display = "Yet to bat"
                                
                            team2_overs = team2.get('overs', '')
                            if team2_score and team2_overs:
                                team2_display = f"{team2_score} ({team2_overs} Ovs)"
                            elif team2_score:
                                team2_display = team2_score
                            else:
                                team2_display = "Yet to bat"
                            
                            # Display team scores in a format similar to the image
                            st.write(f"**{team1_code}:** {team1_display}")
                            st.write(f"**{team2_code}:** {team2_display}")
                            
                            # Add a button to view scorecard
                            match_id = match.get('matchId', 'unknown')
                            if st.button(f"View Scorecard", key=f"view_{match_id}"):
                                # Store match ID in session state to display scorecard
                                st.session_state.selected_match_id = match_id
                                st.session_state.selected_match_title = match.get('matchTitle', 'Match Details')
                                st.session_state.show_scorecard = True
                                # Force a rerun to update the UI
                                st.rerun()
            else:
                st.info("No live matches available at the moment.")
            
            # Show last updated time
            st.caption(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initial load
    load_matches()
    
    # Auto-refresh logic with non-blocking approach
    if auto_refresh:
        placeholder = st.empty()
        
        # Use a session state counter instead of a blocking loop
        if "refresh_counter" not in st.session_state:
            st.session_state.refresh_counter = 30
        
        # Display current countdown
        placeholder.text(f"Next refresh in {st.session_state.refresh_counter} seconds")
        
        # Schedule the next refresh
        if st.session_state.refresh_counter <= 0:
            st.session_state.refresh_counter = 30
            load_matches()
            # Only rerun if we're not viewing a scorecard
            if not st.session_state.get("show_scorecard", False):
                st.rerun()
        else:
            # Decrement counter for next run
            st.session_state.refresh_counter -= 1
