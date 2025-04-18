import streamlit as st
import streamlit.components.v1 as components
from services.cricket_api import get_match_details
from components.commentary import display_commentary

def display_scorecard(match_id, match_title):
    """Display detailed scorecard for a specific match with proper column headers"""
    # Add custom CSS for dark theme, table styling, and tab spacing
    st.markdown("""
    <style>
        /* Dark theme */
        body {
            background-color: #0e1117;
            color: #ffffff;
        }
        
        /* Tab styling with proper spacing */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0px;
            border-bottom: 1px solid #333;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 0px;
            padding: 10px 20px;
            margin-right: 15px;
            color: white;
            font-size: 16px;
        }
        
        .stTabs [aria-selected="true"] {
            background-color: transparent;
            color: #ff4b4b !important;
            font-weight: bold;
            border-bottom: 2px solid #ff4b4b;
        }
        
        /* Table styling */
        .scorecard-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            background-color: #0e1117;
        }
        
        .scorecard-table tr {
            border-bottom: 1px solid #333;
        }
        
        .scorecard-table th, .scorecard-table td {
            padding: 8px;
            text-align: left;
            color: white;
        }
        
        .scorecard-table th {
            background-color: #1e1e1e;
            font-weight: bold;
        }
        
        .dismissal {
            color: #888;
            font-size: 12px;
        }
        
        .extras, .total {
            margin-top: 10px;
            margin-bottom: 10px;
            color: white;
        }
        
        /* Close button styling */
        .close-button {
            background-color: #333;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Title and close button
    st.title(f"🏏 {match_title}")
    if st.button("✕ Return to Chatbot", key="close_scorecard"):
        st.session_state.show_scorecard = False
        st.session_state.selected_match_id = None
        st.session_state.selected_match_title = None
        st.rerun()
    
    # Fetch match details
    with st.spinner("Loading scorecard..."):
        match_data = get_match_details(match_id)
    
    if match_data.get("status") != "success" or not match_data.get("response"):
        st.error("Failed to load match details")
        return
    
    # Extract match data
    match_info = match_data.get("response", {})
    
    # Create tabs for SCORECARD and COMMENTARY with proper spacing
    tab1, tab2 = st.tabs(["SCORECARD", "COMMENTARY"])
    
    with tab1:
        # Display innings data if available
        if "firstInnings" in match_info:
            team_name = match_info.get("teamOne", {}).get("name", "Team 1")
            display_innings_with_components(match_info["firstInnings"], f"{team_name} Innings")
        
        if "secondInnings" in match_info:
            team_name = match_info.get("teamTwo", {}).get("name", "Team 2")
            st.markdown("---")
            display_innings_with_components(match_info["secondInnings"], f"{team_name} Innings")
    
    with tab2:
        # Display commentary using our new component
        display_commentary(match_id)

def display_innings_with_components(innings_data, innings_title):
    """Display batting and bowling data for an innings using streamlit components"""
    # Create HTML content with embedded CSS
    html_content = """
    <style>
        body {
            background-color: #0e1117;
            color: white;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        }
        h2 {
            color: white;
            font-size: 24px;
            margin-top: 20px;
        }
        h3 {
            color: white;
            font-size: 20px;
            margin-top: 15px;
        }
        .scorecard-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
            background-color: #0e1117;
        }
        .scorecard-table tr {
            border-bottom: 1px solid #333;
        }
        .scorecard-table th, .scorecard-table td {
            padding: 8px;
            text-align: left;
            color: white;
        }
        .scorecard-table th {
            background-color: #1e1e1e;
            font-weight: bold;
        }
        .dismissal {
            color: #888;
            font-size: 12px;
        }
        .extras, .total {
            margin-top: 10px;
            margin-bottom: 10px;
            color: white;
        }
    </style>
    """
    
    # Add innings title
    html_content += f"<h2>{innings_title}</h2>"
    
    # Add batting section
    html_content += "<h3>Batting</h3>"
    
    # Create batting table
    batting_data = innings_data.get("batters", [])
    if batting_data:
        html_content += """
        <table class="scorecard-table">
            <tr>
                <th style="width: 40%;">Batter</th>
                <th style="width: 10%;">R</th>
                <th style="width: 10%;">B</th>
                <th style="width: 10%;">4s</th>
                <th style="width: 10%;">6s</th>
                <th style="width: 20%;">SR</th>
            </tr>
        """
        
        # Add rows for each batter
        for batter in batting_data:
            name = batter.get("name", "Unknown")
            dismissal = batter.get("dismissal", "batting")
            runs = batter.get("runs", "0")
            balls = batter.get("balls", "0")
            fours = batter.get("fours", "0")
            sixes = batter.get("sixes", "0")
            strike_rate = batter.get("strikeRate", "0.00")
            
            # Format dismissal text
            dismissal_text = dismissal if dismissal and dismissal.lower() != "batting" else "batting"
            
            # Add row to table
            html_content += f"""
            <tr>
                <td>{name}<br><span class="dismissal">{dismissal_text}</span></td>
                <td>{runs}</td>
                <td>{balls}</td>
                <td>{fours}</td>
                <td>{sixes}</td>
                <td>{strike_rate}</td>
            </tr>
            """
        
        # Close batting table
        html_content += "</table>"
    else:
        html_content += "<p>No batting data available</p>"
    
    # Display extras and total
    if "extras" in innings_data:
        extras = innings_data.get("extras", {})
        if isinstance(extras, dict) and "details" in extras:
            html_content += f'<p class="extras"><b>Extras:</b> {extras["details"]}</p>'
        elif isinstance(extras, str):
            html_content += f'<p class="extras"><b>Extras:</b> {extras}</p>'
    
    if "total" in innings_data:
        total = innings_data.get("total", {})
        if isinstance(total, dict):
            details = total.get("details", "")
            runs = total.get("runs", "0")
            html_content += f'<p class="total"><b>Total:</b> {details if details else runs}</p>'
        elif isinstance(total, str):
            html_content += f'<p class="total"><b>Total:</b> {total}</p>'
    
    # Add bowling section
    html_content += "<h3>Bowling</h3>"
    
    # Create bowling table
    bowling_data = innings_data.get("bowlers", [])
    if bowling_data:
        html_content += """
        <table class="scorecard-table">
            <tr>
                <th style="width: 40%;">Bowler</th>
                <th style="width: 10%;">O</th>
                <th style="width: 10%;">M</th>
                <th style="width: 10%;">R</th>
                <th style="width: 10%;">W</th>
                <th style="width: 20%;">Econ</th>
            </tr>
        """
        
        # Add rows for each bowler
        for bowler in bowling_data:
            name = bowler.get("name", "Unknown")
            overs = bowler.get("overs", "0")
            maidens = bowler.get("maidens", "0")
            runs = bowler.get("runs", "0")
            wickets = bowler.get("wickets", "0")
            economy = bowler.get("economy", "0.00")
            
            # Add row to table
            html_content += f"""
            <tr>
                <td>{name}</td>
                <td>{overs}</td>
                <td>{maidens}</td>
                <td>{runs}</td>
                <td>{wickets}</td>
                <td>{economy}</td>
            </tr>
            """
        
        # Close bowling table
        html_content += "</table>"
    else:
        html_content += "<p>No bowling data available</p>"
    
    # Render HTML using components
    components.html(html_content, height=600, scrolling=True)
