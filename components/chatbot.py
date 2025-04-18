import streamlit as st
import sys
import traceback

def display_chatbot():
    """Display the chatbot interface"""
    st.title("🏆 Sports Chatbot ⚽")
    st.caption("Powered by Google Gemini with Web Search & FAISS Semantic Cache")
    st.markdown("---")
    
    # Initialize chat history if needed
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display past chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # User input and chat logic
    if prompt := st.chat_input("Ask me about sports scores, stats, rules, or commentary..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response_content = ""
            error_occurred = False
            
            try:
                print(f"\n👤 User Query: {prompt}")
                print("🤖 Assistant Thinking...")
                
                with st.spinner("Thinking... (May perform web search)"):
                    # Import here to avoid circular imports
                    from services.gemini_service import get_chat_session
                    
                    # Get chat session and send message
                    chat = get_chat_session()
                    response = chat.send_message(prompt)
                    
                    if response.text:
                        full_response_content = response.text
                        print(f"✅ Received response text: {full_response_content[:200]}...")
                    elif response.candidates:
                        candidate = response.candidates[0]
                        finish_reason = "UNKNOWN"
                        if candidate.finish_reason and hasattr(candidate.finish_reason, 'name'):
                            finish_reason = candidate.finish_reason.name
                        print(f"⚠️ Received candidate with finish_reason: {finish_reason} but no direct text.")
                        
                        if finish_reason == "STOP" and not candidate.content.parts:
                            full_response_content = "(Model finished but no text response.)"
                        elif finish_reason == "TOOL_CALLS":
                            full_response_content = "(Tool processing issue.)"
                            print(f"DEBUG: Final state TOOL_CALLS")
                        elif finish_reason == "SAFETY":
                            full_response_content = "⚠️ Response blocked (safety)."
                            st.warning(full_response_content)
                        elif finish_reason == "MAX_TOKENS":
                            full_response_content = "⚠️ Response truncated (length)."
                            st.warning(full_response_content)
                        else:
                            full_response_content = f"(Finished: {finish_reason}, no text.)"
                    else:
                        full_response_content = "(Received empty/unexpected response.)"
                        print("⚠️ Received empty/unexpected response object.")
            
            except Exception as e:
                error_occurred = True
                st.error(f"❌ Unexpected error: {type(e).__name__}")
                full_response_content = f"Sorry, technical issue. Try again.\n\n*Error logged.*"
                print(f"❌ Chat Error: {type(e).__name__} - {e}", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
            
            message_placeholder.markdown(full_response_content)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response_content})
