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
from time_machine import show_time_machine
from staff_war_room import show_staff_war_room
from employee_mgmt import show_employee_mgmt
from security import get_api_key, show_login_page
from context_mgmt import show_context_mgmt
from marketplace import show_marketplace

def main():
    if "authenticated" not in st.session_state:
        show_login_page()
        return

    base_dir = os.path.dirname(__file__)
    jsons_root = os.path.join(base_dir, 'jsons')
    
    # 🛠️ GLOBAL DATA LOAD (Company Level)
    biz_ctx_path = os.path.join(jsons_root, 'business_context.json')
    if not os.path.exists(biz_ctx_path):
        with open(biz_ctx_path, 'w', encoding='utf-8') as f: json.dump({"company_name": "CrewSchd", "strict_day_coverage": {}}, f)
    
    with open(biz_ctx_path, 'r', encoding='utf-8') as f: biz_ctx_data = json.load(f)
    
    # --- APP TITLE (Very Top) ---
    app_name = biz_ctx_data.get("company_name", "CrewSchd")
    st.sidebar.title(f"🛠️ {app_name}")
    st.sidebar.divider()

    # --- SCHEDULING CONTEXT (Simplified Sidebar) ---
    with st.sidebar.container(border=True):
        st.write("📅 **Current Context**")
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
    branch_ctx_path = os.path.join(jsons_root, selected_branch, 'business_context.json')
    if not os.path.exists(branch_ctx_path):
        with open(branch_ctx_path, 'w', encoding='utf-8') as f: json.dump({"strict_day_coverage": {}}, f)
    with open(branch_ctx_path, 'r', encoding='utf-8') as f: branch_ctx_data = json.load(f)

    emp_path = os.path.join(jsons_dir, 'employee.json')
    if not os.path.exists(emp_path):
        with open(emp_path, 'w', encoding='utf-8') as f: json.dump({"employees": {}}, f)
    with open(emp_path, 'r', encoding='utf-8') as f: employees = json.load(f)

    # Sidebar Navigation
    nav_options = ["🚜 Control Tower", "🤝 Shift Marketplace", "🕰️ Time Machine"]
    if st.session_state["user"] == "admin":
        nav_options.append("🛡️ Staff War Room")
        nav_options.append("📐 Context Management")
        nav_options.append("👥 Employee Management")
    
    menu = st.sidebar.radio("Navigation", nav_options)

    # Move User/Logout to the very bottom
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
        show_control_tower(target_date, rosters_dir, jsons_dir, json.dumps(employees), json.dumps(branch_ctx_data), get_api_key(), base_dir, selected_branch, selected_team, jsons_root)
    elif menu == "🤝 Shift Marketplace":
        show_marketplace(rosters_dir, jsons_dir, employees)
    elif menu == "🕰️ Time Machine":
        weather_path = os.path.join(jsons_dir, 'weather.json')
        show_time_machine(rosters_dir, jsons_dir, weather_path, employees)
    elif menu == "🛡️ Staff War Room":
        show_staff_war_room(jsons_root, base_dir)
    elif menu == "📐 Context Management":
        show_context_mgmt(jsons_root, selected_branch, get_api_key())
    elif menu == "👥 Employee Management":
        show_employee_mgmt(jsons_root, selected_branch, selected_team)

if __name__ == "__main__":
    main()
