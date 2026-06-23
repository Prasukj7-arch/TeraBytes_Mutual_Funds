"""
AI Chat Assistant module UI for the Mutual Fund Analytics dashboard.
"""

import streamlit as st
from databricks_connector.data_service import DataService
from services.chat_service import ChatService
from config.settings import OpenAIConfig

@st.cache_resource
def get_data_service():
    return DataService()

@st.cache_resource
def get_chat_service():
    ds = get_data_service()
    return ChatService(ds)

def render():
    """Render the AI Chat Assistant page."""
    ds = get_data_service()
    chat_svc = get_chat_service()

    st.markdown('<h1 class="page-title">💬 AI Chat Assistant</h1>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Ask your personal AI Advisor questions about mutual fund comparisons, risk metrics, and allocations.</p>', unsafe_allow_html=True)

    # Status check
    if not OpenAIConfig.is_configured():
        st.info("ℹ️ Running in offline rule-based fallback mode. Configure your OpenAI API key in `.env` to unlock full natural language capabilities.")

    # Two column layout: Chat on left, suggestions on right
    chat_col, sidebar_col = st.columns([7, 3])

    with chat_col:
        # Initialize message history
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                {
                    "role": "assistant",
                    "content": "👋 Hello! I'm your AI Mutual Fund Advisor. Ask me anything about specific schemes, portfolio health, or category comparisons!"
                }
            ]

        # Display history
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

        # Chat Input
        user_input = st.chat_input("Ask a financial question...")

        # Process input
        if user_input:
            # Append user msg
            st.session_state.chat_history.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.write(user_input)

            # Generate reply
            with st.spinner("AI thinking..."):
                response = chat_svc.process_message(user_input)

            st.session_state.chat_history.append({"role": "assistant", "content": response})
            with st.chat_message("assistant"):
                st.write(response)

    with sidebar_col:
        st.markdown('<div class="section-subheader">💡 Suggested Questions</div>', unsafe_allow_html=True)
        suggestions = chat_svc.get_suggested_questions()
        
        # Display suggested questions as clickable elements that append to query
        for q in suggestions:
            if st.button(q, key=f"btn_{q.replace(' ', '_')}", use_container_width=True):
                # When clicked, append and query
                st.session_state.chat_history.append({"role": "user", "content": q})
                with st.spinner("AI thinking..."):
                    response = chat_svc.process_message(q)
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()

        # Clear history button
        st.markdown("<br><hr>", unsafe_allow_html=True)
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.chat_history = [
                {
                    "role": "assistant",
                    "content": "👋 Conversational memory cleared. Ask me any new questions!"
                }
            ]
            st.rerun()
