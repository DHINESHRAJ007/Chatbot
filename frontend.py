import streamlit as st
import httpx
import uuid
from typing import List, Dict

# Configuration
BACKEND_URL = "http://localhost:8001"

# Initialize session state
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

def send_message(message: str) -> str:
    """Send message to backend and return response"""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{BACKEND_URL}/chat",
                json={"message": message, "conversation_id": st.session_state.conversation_id}
            )
            response.raise_for_status()
            return response.json()["response"]
    except Exception as e:
        return f"Error connecting to backend: {str(e)}"

# Streamlit UI
st.set_page_config(
    page_title="EcoTravel Planner",
    page_icon="🌍",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border-radius: 20px;
    }
    .user-message {
        background-color: #e3f2fd;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
        color: black;  /* Add this line */
    }
    .assistant-message {
        background-color: #f1f8e9;
        padding: 10px;
        border-radius: 10px;
        margin: 5px 0;
        color: black; /* Add this line */
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header"><h1>🌍 EcoTravel Planner</h1><p>Plan sustainable adventures with AI</p></div>', unsafe_allow_html=True)

# Sidebar with instructions
with st.sidebar:
    st.header("About EcoTravel Planner")
    st.write("""
    This AI assistant helps you plan eco-friendly trips by:
    - Suggesting sustainable destinations
    - Recommending low-impact transportation
    - Finding eco-certified accommodations
    - Supporting local communities
    - Minimizing plastic waste
    
    **Tip**: Be specific about your sustainability priorities!
    """)
    
    if st.button("New Conversation"):
        st.session_state.conversation_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

# Display chat history
for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f'<div class="user-message"><strong>You:</strong> {message["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="assistant-message"><strong>EcoTravel:</strong> {message["content"]}</div>', unsafe_allow_html=True)

# Chat input
if prompt := st.chat_input("Describe your dream sustainable trip..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Get response from backend
    with st.spinner("Planning your sustainable adventure..."):
        response = send_message(prompt)
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Rerun to display new messages
    st.rerun()

# Footer
st.markdown("---")
st.caption("Powered by Gemini AI, LangGraph, FastAPI, and Streamlit | Plan responsibly, travel sustainably")
