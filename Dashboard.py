import streamlit as st
import os
import json
import sys
from datetime import date
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- PAGE CONFIG MUST BE FIRST ---
st.set_page_config(page_title="CrewSchd Control Tower", layout="wide", page_icon="🛠️")

# Add modules directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules', 'ui'))

# Import UI Modules
from control_tower import show_control_tower
from leave_dashboard import show_leave_dashboard
from time_machine import show_time_machine
from analytics import show_analytics
from employee_mgmt import show_employee_mgmt
from company_overview import show_company_overview

# --- AUTHENTICATION ---
def get_secret(key, default):
    # Try Streamlit Secrets first (Cloud)
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    # Fallback to Environment Variables (Local)
    return os.getenv(key, default)

USERS = {
    "admin": get_secret("ADMIN_PASSWORD", "admin123"),
    "manager": get_secret("MANAGER_PASSWORD", "manager123")
}

def login():
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

def get_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY")

def main():
    if "authenticated" not in st.session_state:
        login()
        return

    base_dir = os.path.dirname(__file__)
    jsons_root = os.path.join(base_dir, 'jsons')
    
    # 🛠️ GLOBAL DATA LOAD (Company Level)
    biz_ctx_path = os.path.join(jsons_root, 'business_context.json')
    if not os.path.exists(biz_ctx_path):
        with open(biz_ctx_path, 'w') as f: json.dump({"company_name": "CrewSchd", "strict_day_coverage": {}}, f)
    
    with open(biz_ctx_path, 'r') as f: biz_ctx_data = json.load(f)
    
    # --- APP TITLE (Very Top) ---
    app_name = biz_ctx_data.get("company_name", "CrewSchd")
    st.sidebar.title(f"🛠️ {app_name}")
    st.sidebar.divider()

    # --- SCHEDULING CONTEXT (Grouped) ---
    with st.sidebar.container(border=True):
        st.write("📅 **Scheduling Context**")
        target_date = st.date_input("Start Date", value=date.today())
        
        available_branches = sorted([d for d in os.listdir(jsons_root) if os.path.isdir(os.path.join(jsons_root, d))])
        if not available_branches: available_branches = ["Main Office"]
        selected_branch = st.selectbox("📍 Branch", available_branches)
        
        branch_path = os.path.join(jsons_root, selected_branch)
        available_teams = sorted([d for d in os.listdir(branch_path) if os.path.isdir(os.path.join(branch_path, d))])
        if not available_teams: available_teams = ["General"]
        selected_team = st.selectbox("👥 Team", available_teams)

    st.sidebar.divider()

    jsons_dir = os.path.join(jsons_root, selected_branch, selected_team)
    rosters_dir = os.path.join(base_dir, 'Rosters', selected_branch, selected_team)
    
    os.makedirs(jsons_dir, exist_ok=True)
    os.makedirs(rosters_dir, exist_ok=True)

    # 🛠️ LOCAL DATA LOAD (Branch & Team Specific)
    emp_path = os.path.join(jsons_dir, 'employee.json')
    if not os.path.exists(emp_path):
        with open(emp_path, 'w') as f: json.dump({"employees": {}}, f)
    with open(emp_path, 'r') as f: employees = json.load(f)

    pol_path = os.path.join(jsons_dir, 'company_policies.json')
    if not os.path.exists(pol_path):
        with open(pol_path, 'w') as f: json.dump({"optimization_targets": {}}, f)
    with open(pol_path, 'r') as f: policies = json.load(f)

    law_path = os.path.join(base_dir, 'jsons', 'thai_laws.json')
    if os.path.exists(law_path):
        with open(law_path, 'r') as f: laws = json.load(f)
    else:
        laws = {}
    
    weather_path = os.path.join(jsons_dir, 'weather.json')
    if os.path.exists(weather_path):
        with open(weather_path, 'r') as f: weather = json.load(f)
    else:
        weather = {"daily_overrides": []}

    # Sidebar Navigation
    nav_options = ["🚜 Control Tower", "🌴 Leave Dashboard", "🕰️ Time Machine", "📊 Resource Analytics"]
    if st.session_state["user"] == "admin":
        nav_options.append("🏢 Company Overview")
        nav_options.append("👥 Employee Management")
    
    menu = st.sidebar.radio("Navigation", nav_options)

    # Move User/Logout to the very bottom
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Logged in as: {st.session_state['user'].capitalize()}")
    if st.sidebar.button("Logout", width="stretch", type="secondary"):
        del st.session_state["authenticated"]
        st.rerun()
    
    # --- FLOATING CHAT CSS ---
    st.markdown("""
        <style>
        div[data-testid="stPopover"] { position: fixed; bottom: 30px; right: 30px; z-index: 999999; width: 60px !important; height: 60px !important; }
        div[data-testid="stPopover"] > button { border-radius: 50% !important; width: 60px !important; height: 60px !important; display: flex !important; align-items: center !important; justify-content: center !important; background-color: #3498db !important; color: white !important; box-shadow: 0 4px 15px rgba(0,0,0,0.3) !important; border: none !important; padding: 0 !important; }
        div[data-testid="stPopoverBody"] { width: 450px !important; height: 80vh !important; max-height: 80vh !important; border-radius: 15px !important; border: 1px solid #3498db !important; background-color: #1e293b !important; bottom: 80px !important; right: 0px !important; display: flex !important; flex-direction: column !important; }
        </style>
    """, unsafe_allow_html=True)

    # Route to pages
    if menu == "🚜 Control Tower":
        show_control_tower(target_date, rosters_dir, jsons_dir, weather_path, weather, json.dumps(employees), json.dumps(biz_ctx_data), get_api_key, base_dir, selected_branch, selected_team)
    elif menu == "🌴 Leave Dashboard":
        show_leave_dashboard(jsons_dir, weather_path, weather, employees)
    elif menu == "🕰️ Time Machine":
        show_time_machine(rosters_dir, jsons_dir, weather_path, employees)
    elif menu == "📊 Resource Analytics":
        show_analytics(rosters_dir, jsons_dir, employees)
    elif menu == "🏢 Company Overview":
        show_company_overview(jsons_root, base_dir)
    elif menu == "👥 Employee Management":
        show_employee_mgmt(jsons_root, selected_branch, selected_team)

if __name__ == "__main__":
    main()
