import os
import streamlit as st
from dotenv import load_dotenv

def get_secret(key, default):
    """
    Helper to get a secret from Streamlit Cloud or Environment Variables.
    """
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)

def get_api_key():
    """
    Centralized API Key Retrieval.
    Prioritizes Streamlit Cloud Secrets, then falls back to local .env variables.
    """
    # 1. Try Streamlit Secrets (Cloud Production)
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    
    # 2. Try Environment Variables (Local Development)
    base_dir = os.path.dirname(os.path.dirname(__file__))
    env_path = os.path.join(base_dir, '.env')
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
    
    return os.getenv("GEMINI_API_KEY")

def get_users():
    """
    Centralized User credentials.
    """
    return {
        "admin": get_secret("ADMIN_PASSWORD", "admin123"),
        "manager": get_secret("MANAGER_PASSWORD", "manager123")
    }

def show_login_page():
    """
    Standardized Login UI.
    """
    st.markdown("""
        <style>
        .stApp { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); }
        [data-testid="stForm"] { background: rgba(255, 255, 255, 0.05); border-radius: 15px; border: 1px solid rgba(255, 255, 255, 0.1); padding: 40px; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37); backdrop-filter: blur(4px); max-width: 500px; margin: auto; }
        .login-header { text-align: center; margin-bottom: 30px; }
        .login-header h1 { color: #3498db; font-size: 3rem; margin-bottom: 0; }
        .login-header p { color: #94a3b8; font-size: 1.1rem; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="login-header"><h1>🛠️ CrewSchd</h1><p>Enterprise Operations Command Center</p></div>', unsafe_allow_html=True)
    
    USERS = get_users()
    
    with st.form("login_form", clear_on_submit=False):
        st.write("### 🔐 Secure Access")
        username = st.text_input("Username", placeholder="e.g. manager")
        password = st.text_input("Password", type="password", placeholder="••••••••")
        
        c1, c2, c3 = st.columns([1, 2, 1])
        submit = c2.form_submit_button("UNLOCk OPERATIONS", width="stretch")
        
        if submit:
            if username in USERS and USERS[username] == password:
                st.session_state["authenticated"] = True
                st.session_state["user"] = username
                st.success("Access Granted. Initializing Command Center...")
                import time
                time.sleep(1)
                st.rerun()
            else:
                st.error("Access Denied: Invalid Credentials")
