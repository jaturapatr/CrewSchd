import streamlit as st
import os
import json
import sys
from datetime import date, timedelta
import pandas as pd
import streamlit.components.v1 as components
import plotly.express as px

# --- PAGE CONFIG MUST BE FIRST ---
st.set_page_config(page_title="CrewSchd Control Tower", layout="wide", page_icon="🛠️")

# Add modules directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

# Import existing engine logic
from roster_engine import generate_roster
from run_translation import run_translation
from Exporter import export_perfect_roster

# --- AUTHENTICATION ---
USERS = {
    "admin": "beecolony2026",
    "manager": "logistics123"
}

def login():
    # --- MODERN CSS FOR LOGIN ---
    st.markdown("""
        <style>
        .stApp {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        }
        [data-testid="stForm"] {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 40px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            backdrop-filter: blur(4px);
            max-width: 500px;
            margin: auto;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            color: #3498db;
            font-size: 3rem;
            margin-bottom: 0;
        }
        .login-header p {
            color: #94a3b8;
            font-size: 1.1rem;
        }
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
    # Priority 1: Streamlit Secrets (Cloud)
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass # Secrets not configured (local dev)
    # Priority 2: Environment Variables (.env)
    from dotenv import load_dotenv
    load_dotenv()
    return os.environ.get("GEMINI_API_KEY")

# --- DASHBOARD MAIN ---
def main():
    if "authenticated" not in st.session_state:
        login()
        return

    base_dir = os.path.dirname(__file__)
    jsons_dir = os.path.join(base_dir, 'jsons')
    rosters_dir = os.path.join(base_dir, 'Rosters')
    
    # 🛠️ GLOBAL DATA LOAD (Required by multiple components)
    weather_path = os.path.join(jsons_dir, 'weather.json')
    if os.path.exists(weather_path):
        with open(weather_path, 'r') as f: weather = json.load(f)
    else:
        weather = {"daily_overrides": []}

    # Sidebar Navigation & Weather Manager
    st.sidebar.title(f"🛠️ CrewSchd")
    st.sidebar.caption("Making your crew work!")
    st.sidebar.caption(f"User: {st.session_state['user'].capitalize()}")
    
    if st.sidebar.button("Logout", width="stretch"):
        del st.session_state["authenticated"]
        st.rerun()

    st.sidebar.divider()
    menu = st.sidebar.radio("Navigation", ["🚜 Control Tower", "🌴 Leave Dashboard", "🕰️ Time Machine", "📊 Resource Analytics", "📜 Rulebook"])
    
    # --- FLOATING CHAT CSS ---
    st.markdown("""
        <style>
        /* Target the outer container of the popover */
        div[data-testid="stPopover"] {
            position: fixed;
            bottom: 30px;
            right: 30px;
            z-index: 999999;
            width: 60px !important;
            height: 60px !important;
        }
        /* Target the button inside the popover */
        div[data-testid="stPopover"] > button {
            border-radius: 50% !important;
            width: 60px !important;
            height: 60px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            background-color: #3498db !important;
            color: white !important;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3) !important;
            border: none !important;
            padding: 0 !important;
        }
        /* Style the popover dialog */
        div[data-testid="stPopoverBody"] {
            width: 450px !important;
            height: 80vh !important;
            max-height: 80vh !important;
            border-radius: 15px !important;
            border: 1px solid #3498db !important;
            background-color: #1e293b !important;
            bottom: 80px !important;
            right: 0px !important;
            display: flex !important;
            flex-direction: column !important;
        }
        </style>
    """, unsafe_allow_html=True)

    if menu == "🚜 Control Tower":
        target_date = st.sidebar.date_input("Schedule Start Date", value=date.today())
        st.title("🚜 Control Tower")

        # 🤖 FLOATING ROSTER ASSISTANT (Bottom Right)
        with st.container():
            with st.popover("🤖", help="Open AI Roster Assistant"):
                st.subheader("🤖 Roster Assistant")
                st.caption("Request changes (Leaves/Sick) OR ask questions.")
                
                import glob
                files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
                current_roster = "{}"
                if files:
                    with open(files[-1], 'r') as f: current_roster = f.read()
                with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: emps_ctx = f.read()
                with open(os.path.join(jsons_dir, 'business_context.json'), 'r') as f: biz_ctx = f.read()

                if "chat_history" not in st.session_state:
                    st.session_state.chat_history = []

                for msg in st.session_state.chat_history:
                    with st.chat_message(msg["role"]):
                        st.write(msg["content"])

                user_prompt = st.chat_input("e.g., Fai is sick tomorrow...")
                
                if user_prompt:
                    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
                    from google import genai
                    from google.genai import types
                    from dotenv import load_dotenv
                    load_dotenv(dotenv_path=os.path.join(base_dir, '.env'))
                    client = genai.Client(api_key=get_api_key())
                    today_str = date.today().isoformat()
                    today_name = date.today().strftime('%A')
                    sys_inst = f"""
                    You are the Bee-Colony Operations Hub. 
                    TODAY IS: {today_str} ({today_name})
                    CONTEXT:
                    - Current Roster: {current_roster}
                    - Employee Database: {emps_ctx}
                    - Business Rules: {biz_ctx}
                    YOUR PROTOCOL:
                    1. Accurate relative date calculations.
                    2. Use Name, not ID.
                    3. If feasible, return ONLY a JSON object with key 'overrides'. Label reason as 'Sick' or 'Vacation'.
                    4. Answer accurately.
                    """
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        config=types.GenerateContentConfig(system_instruction=sys_inst),
                        contents=user_prompt
                    )
                    try:
                        clean_text = response.text.replace('```json', '').replace('```', '').strip()
                        res_data = json.loads(clean_text)
                        if "overrides" in res_data:
                            weather["daily_overrides"].extend(res_data["overrides"])
                            with open(weather_path, 'w') as f: json.dump(weather, f, indent=2)
                            st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Added {len(res_data['overrides'])} rules."})
                            st.rerun()
                    except:
                        st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        st.rerun()

        if st.button("🚀 RUN MATH ENGINE", width="stretch", type="primary"):
            log_output = st.empty()
            with st.spinner("🔢 Solving Matrix..."):
                try:
                    status = generate_roster(target_date)
                    if status == "INFEASIBLE":
                        st.error("❌ **MATHEMATICAL PARADOX DETECTED**\n\nThe current constraints (Active Overrides + Labor Laws + Headcount) are physically impossible to solve. Please remove some Active Overrides or lower the coverage requirements and try again.")
                    elif status is None:
                        st.error("❌ **ENGINE FAILURE**\n\nThe engine returned no result. Check logs for details.")
                    else:
                        export_perfect_roster()
                        st.success("✅ Roster Generated and Exported!")
                        st.balloons()
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ **CRITICAL SYSTEM ERROR**\n\n{str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

        st.divider()
        
        # 📅 BEAUTIFUL ROSTER GRID WITH CHANGE TRACKING
        st.subheader("🗓️ Visual Master Schedule")
        import glob
        files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
        
        if len(files) >= 1:
            # 1. Load Latest and Previous for Comparison
            latest_file = files[-1]
            prev_file = files[-2] if len(files) > 1 else None
            
            with open(latest_file, 'r') as f: roster = json.load(f)
            prev_roster = None
            if prev_file:
                with open(prev_file, 'r') as f: prev_roster = json.load(f)
            
            with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: emps = json.load(f)
            
            # 2. Map Emojis
            EMOJI_MAP = {
                "Morning": "☀️ Morning",
                "Evening": "🌆 Evening",
                "Night": "🌑 Night",
                "12hDay": "🔥 12h Day",
                "12hNight": "🌌 12h Night",
                "—": "💤 OFF"
            }

            # 3. Build Data with Change Detection
            data = []
            change_count = 0
            all_dates = sorted(roster["assignments"].keys())
            
            for eid, details in emps["employees"].items():
                row = {"Staff": details['name'], "Team": details["team"]} # Keep Team in dict for filtering but not in final display
                for d in all_dates:
                    new_s = roster["assignments"][d].get(eid, "—")
                    old_s = prev_roster["assignments"].get(d, {}).get(eid, "—") if prev_roster else new_s
                    
                    display_val = EMOJI_MAP.get(new_s, new_s)
                    if new_s != old_s:
                        display_val = f"🔄 {display_val}"
                        change_count += 1
                    
                    row[d] = display_val
                data.append(row)
            
            # 4. Display Logic
            if change_count > 0:
                st.info(f"✨ **Intelligence Report:** Found {change_count} shift changes since the last version (marked with 🔄).")

            df = pd.DataFrame(data)
            # Remove Team from the display dataframe but keep it in the list of dicts for tab filtering
            display_columns = ["Staff"] + all_dates
            
            # Stylized Dataframe
            def style_cells(val):
                if "🔄" in str(val): return "font-weight: bold"
                if "Morning" in str(val): return "color: #f08c00"
                if "Night" in str(val): return "color: #1971c2"
                if "12h" in str(val): return "color: #e8590c; font-weight: bold"
                if "OFF" in str(val): return "color: #adb5bd; font-style: italic"
                return ""

            # Filter by Display Mode
            team_names = sorted(list(set(row["Team"] for row in data)))
            view_type = st.radio("Display Mode", ["🎨 Visual Pulse", "📋 Spreadsheet"], horizontal=True, label_visibility="collapsed")
            
            if view_type == "📋 Spreadsheet":
                team_tabs = st.tabs(["All Teams"] + team_names)
                
                with team_tabs[0]:
                    st.dataframe(
                        df[display_columns].style.map(style_cells),
                        column_config={d: st.column_config.TextColumn(date.fromisoformat(d).strftime('%a %d')) for d in all_dates},
                        hide_index=True, width="stretch", height=600
                    )
                    
                    # HTML Export Button inside All Teams tab
                    report_path = os.path.join(base_dir, 'Perfect_Roster_View.html')
                    if os.path.exists(report_path):
                        with open(report_path, 'r', encoding='utf-8') as f:
                            st.download_button(
                                label="📥 Download HTML Report",
                                data=f.read(),
                                file_name=f"roster_{target_date}.html",
                                mime="text/html",
                                width="stretch"
                            )

                for i, team in enumerate(team_names):
                    with team_tabs[i+1]:
                        st.dataframe(
                            df[df["Team"] == team][display_columns].style.map(style_cells),
                            column_config={d: st.column_config.TextColumn(date.fromisoformat(d).strftime('%a %d')) for d in all_dates},
                            hide_index=True, width="stretch"
                        )
            else:
                # --- 🎨 VISUAL PULSE (ANALYTIC VIEW) ---
                st.write("### 📉 Operational Pulse")
                st.caption("Analyzing headcount flow and shift distribution across the week.")
                
                pulse_data = []
                for d in all_dates:
                    for s in ["Morning", "Evening", "Night", "12hDay", "12hNight"]:
                        count = sum(1 for eid, assigned_s in roster["assignments"][d].items() if assigned_s == s)
                        pulse_data.append({"Date": d, "Shift": s, "Headcount": count})
                
                pulse_df = pd.DataFrame(pulse_data)
                fig_pulse = px.bar(
                    pulse_df, x="Date", y="Headcount", color="Shift",
                    title="Workforce Capacity Heartbeat",
                    color_discrete_map={
                        "Morning": "#f1c40f", "Evening": "#e67e22", "Night": "#34495e",
                        "12hDay": "#e74c3c", "12hNight": "#9b59b6"
                    },
                    template="plotly_dark", height=400
                )
                st.plotly_chart(fig_pulse, width="stretch")

                st.divider()
                c1, c2 = st.columns(2)
                
                with c1:
                    st.write("#### 🛡️ Team Coverage Balance")
                    # Daily average headcount by team
                    team_coverage = []
                    for d in all_dates:
                        for team in team_names:
                            count = sum(1 for eid, assigned_s in roster["assignments"][d].items() if emps["employees"][eid]["team"] == team and assigned_s != "—")
                            team_coverage.append({"Date": d, "Team": team, "Count": count})
                    
                    fig_team = px.line(
                        pd.DataFrame(team_coverage), x="Date", y="Count", color="Team",
                        markers=True, title="Team Presence Stability", template="plotly_dark"
                    )
                    st.plotly_chart(fig_team, width="stretch")

                with c2:
                    st.write("#### 🎓 Experience Mix (Tier Ratio)")
                    # Ratio of Senior vs Junior shifts
                    tier_data = []
                    for d in all_dates:
                        for tier in ["Senior", "Junior"]:
                            count = sum(1 for eid, assigned_s in roster["assignments"][d].items() if emps["employees"][eid]["tier"] == tier and assigned_s != "—")
                            tier_data.append({"Date": d, "Tier": tier, "Count": count})
                    
                    fig_tier = px.area(
                        pd.DataFrame(tier_data), x="Date", y="Count", color="Tier",
                        title="Seniority Concentration", template="plotly_dark",
                        color_discrete_map={"Senior": "#2ecc71", "Junior": "#bdc3c7"}
                    )
                    st.plotly_chart(fig_tier, width="stretch")
        else:
            st.warning("No roster found. Please run the Math Engine.")

    elif menu == "🌴 Leave Dashboard":
        st.title("🌴 Leave Dashboard")
        st.subheader("Manage and Track Staff Leave Quotas & Active Requests")
        
        with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: employees = json.load(f)
        
        # --- 1. OVERVIEW METRICS ---
        weather_vacation = {} 
        weather_sick = {}     
        for rule in weather.get("daily_overrides", []):
            if rule.get("type") == "block_employee_availability":
                e_name = rule.get("employee")
                reason = str(rule.get("reason", "")).lower()
                is_sick = any(word in reason for word in ["sick", "medical", "hospital", "doctor"])
                for eid, edata in employees["employees"].items():
                    if edata["name"] == e_name:
                        if is_sick: weather_sick[eid] = weather_sick.get(eid, 0) + 1
                        else: weather_vacation[eid] = weather_vacation.get(eid, 0) + 1

        total_pending = len(weather.get("daily_overrides", []))
        st.sidebar.metric("Pending Overrides", total_pending)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Active Vacation Days", sum(weather_vacation.values()))
        m2.metric("Active Sick Days", sum(weather_sick.values()))
        m3.metric("Total Workforce", len(employees["employees"]))

        # --- 2. QUOTA TRACKING TABLE ---
        st.divider()
        st.subheader("📊 Quota Accounting")
        quota_data = []
        for eid, e_data in employees["employees"].items():
            v_used = e_data.get("vacation_used", 0) + weather_vacation.get(eid, 0)
            v_rem = e_data.get("vacation_quota", 13) - v_used
            s_used = e_data.get("sick_used", 0) + weather_sick.get(eid, 0)
            s_rem = e_data.get("sick_quota", 30) - s_used
            status = "✅ OK" if (v_rem >= 0 and s_rem >= 0) else "🚨 EXCEEDED"
            
            quota_data.append({
                "Staff": e_data["name"],
                "Vacation Used": v_used,
                "Vacation Rem.": v_rem,
                "Sick Used": s_used,
                "Sick Rem.": s_rem,
                "Status": status
            })
        st.dataframe(pd.DataFrame(quota_data).style.apply(lambda x: ["color: red; font-weight: bold" if v == "🚨 EXCEEDED" else "" for v in x], axis=1), hide_index=True, width="stretch")

        # --- 3. ACTIVE REQUESTS MANAGER ---
        st.divider()
        st.subheader("🗓️ Active Overrides Manager")
        overrides = weather.get("daily_overrides", [])
        if not overrides:
            st.info("No active overrides found.")
        else:
            # Group overrides by date for better visualization
            df_overrides = pd.DataFrame(overrides)
            if not df_overrides.empty:
                # Add a 'Delete' column and display
                for i, rule in enumerate(overrides):
                    col1, col2, col3, col4 = st.columns([2, 2, 3, 1])
                    col1.write(f"**{rule.get('employee')}**")
                    col2.write(rule.get('date'))
                    col3.write(f"*{rule.get('reason')}*")
                    if col4.button("🗑️", key=f"dash_del_{i}"):
                        overrides.pop(i)
                        with open(weather_path, 'w') as f: json.dump({"daily_overrides": overrides}, f, indent=2)
                        st.success(f"Removed override for {rule.get('employee')}")
                        st.rerun()
                
                if st.button("🔥 CLEAR ALL OVERRIDES", type="secondary", width="stretch"):
                    with open(weather_path, 'w') as f: json.dump({"daily_overrides": []}, f, indent=2)
                    st.success("All overrides cleared!")
                    st.rerun()

    elif menu == "🕰️ Time Machine":
        st.title("🕰️ Roster Time Machine")
        st.subheader("Analyze, Compare, and Restore previous versions of your operations.")
        
        import glob
        files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime, reverse=True)
        
        if not files:
            st.info("No historical rosters found. Generate a roster to start creating backup points.")
            return

        # 1. VIEW SELECTOR
        view_mode = st.radio("Choose Visualization Mode", ["🖼️ Snapshot Gallery", "📈 Timeline View", "🗓️ Comparison View", "📦 Version List"], horizontal=True)
        st.divider()

        # 2. DATA PREP
        latest_file = files[0] # The current live roster (usually)
        with open(latest_file, 'r') as f: live_roster = json.load(f)
        with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: emps = json.load(f)

        if view_mode == "📈 Timeline View":
            st.write("### 📈 Chronological Flight Path")
            st.caption("Tracking the evolution of Roster Complexity & AI Overrides over time.")
            
            timeline_data = []
            for f_path in reversed(files): # Chronological order
                with open(f_path, 'r') as f: d = json.load(f)
                m = d.get("metadata", {})
                timeline_data.append({
                    "Version": str(m.get("timestamp")),
                    "Generated": m.get("generated_at"),
                    "Overrides": len(m.get("weather_snapshot", [])),
                    "Type": m.get("status", "FEASIBLE")
                })
            
            df_tl = pd.DataFrame(timeline_data)
            
            # Plotly Timeline Chart
            fig_tl = px.line(
                df_tl, x="Generated", y="Overrides", text="Version",
                title="AI Operations Intensity (Number of active Overrides per version)",
                markers=True, template="plotly_dark", height=400,
                color_discrete_sequence=["#3498db"]
            )
            fig_tl.update_traces(textposition="top center")
            st.plotly_chart(fig_tl, width="stretch")
            
            st.info("💡 **Insight:** Peaks in the graph represent periods of high operational complexity (e.g., mass sick leaves or peak events).")
            
            # Vertical Timeline (Visual)
            st.write("#### 🛰️ Version Trajectory")
            for item in timeline_data[::-1]: # Newest first
                with st.container(border=True):
                    c1, c2 = st.columns([1, 5])
                    c1.write(f"**v_{item['Version']}**")
                    status_color = "🔵" if item["Type"] == "OPTIMAL" else "🟢"
                    c2.write(f"{status_color} {item['Generated']} — {item['Overrides']} Overrides active.")

        elif view_mode == "🗓️ Comparison View":
            st.write("### 🔍 Side-by-Side Comparison")
            st.caption("Compare a historical 'Ghost' roster (left) with your current 'Live' roster (right).")
            
            selected_f = st.selectbox("Select Version to Compare", files, format_func=lambda x: f"Version {os.path.basename(x).split('_')[-1].replace('.json', '')} (Generated: {json.load(open(x))['metadata']['generated_at']})")
            
            with open(selected_f, 'r') as f: historical = json.load(f)
            
            # Comparison Metrics
            c1, c2, c3 = st.columns(3)
            h_meta = historical.get("metadata", {})
            l_meta = live_roster.get("metadata", {})
            
            # Find changes count
            diff_count = 0
            all_dates = sorted(historical["assignments"].keys())
            for d in all_dates:
                for eid in emps["employees"]:
                    if historical["assignments"][d].get(eid) != live_roster["assignments"].get(d, {}).get(eid):
                        diff_count += 1

            c1.metric("Selected Points", h_meta.get("timestamp"))
            c2.metric("Total Shifts", len(all_dates) * len(emps["employees"]))
            c3.metric("Shift Deviations", diff_count, delta=f"{diff_count} changes", delta_color="inverse")

            # --- DUAL ROSTER LAYOUT ---
            st.divider()
            left_col, right_col = st.columns(2)
            
            # Map Emojis
            EM_MAP = {"Morning": "☀️", "Evening": "🌆", "Night": "🌑", "12hDay": "🔥", "12hNight": "🌌", "—": "💤"}

            with left_col:
                st.subheader("📜 Historical Ghost")
                h_data = []
                for eid, edata in emps["employees"].items():
                    row = {"Staff": edata["name"]}
                    for d in all_dates:
                        val = historical["assignments"][d].get(eid, "—")
                        row[d] = f"{EM_MAP.get(val, val)} {val}"
                    h_data.append(row)
                st.dataframe(pd.DataFrame(h_data), hide_index=True)

            with right_col:
                st.subheader("🚀 Live Roster")
                l_data = []
                for eid, edata in emps["employees"].items():
                    row = {"Staff": edata["name"]}
                    for d in all_dates:
                        h_val = historical["assignments"][d].get(eid, "—")
                        l_val = live_roster["assignments"].get(d, {}).get(eid, "—")
                        display = f"{EM_MAP.get(l_val, l_val)} {l_val}"
                        if h_val != l_val:
                            display = f"🔄 {display}"
                        row[d] = display
                    l_data.append(row)
                
                def color_diff(val):
                    return 'background-color: rgba(255, 165, 0, 0.2); font-weight: bold' if "🔄" in str(val) else ''
                
                st.dataframe(pd.DataFrame(l_data).style.applymap(color_diff), hide_index=True)
            
            st.divider()
            if st.button("⏪ RESTORE SELECTED VERSION", type="primary", width="stretch"):
                with open(weather_path, 'w') as f:
                    json.dump({"daily_overrides": h_meta.get("weather_snapshot", [])}, f, indent=2)
                st.success("State restored! Re-run the engine to apply.")
                st.rerun()

        elif view_mode == "🖼️ Snapshot Gallery":
            st.write("### 🖼️ Visual Snapshot Gallery")
            cols = st.columns(3)
            for i, f_path in enumerate(files[:12]): # Show last 12
                with open(f_path, 'r') as f: data = json.load(f)
                meta = data.get("metadata", {})
                ts = meta.get("timestamp")
                
                with cols[i % 3]:
                    with st.container(border=True):
                        st.write(f"**📦 Version {ts}**")
                        st.caption(f"📅 {meta.get('generated_at')}")
                        
                        # MINI HEATMAP (Visual representation)
                        # We'll create a small 7x5 grid using colored blocks
                        shifts_active = 0
                        for day in data["assignments"].values():
                            shifts_active += len(day)
                        
                        # Simple visual bar for density
                        density = (shifts_active / (len(emps["employees"]) * 7)) * 100
                        st.progress(min(density/100, 1.0), text=f"Work Density: {int(density)}%")
                        
                        # Icons for overrides
                        overrides = meta.get("weather_snapshot", [])
                        st.write(f"🧠 {len(overrides)} AI Overrides")
                        
                        if st.button("⏪ Restore", key=f"gal_res_{ts}"):
                            with open(weather_path, 'w') as f:
                                json.dump({"daily_overrides": overrides}, f, indent=2)
                            st.rerun()

        elif view_mode == "📦 Version List":
            for f_path in files:
                f_name = os.path.basename(f_path)
                with open(f_path, 'r') as f: data = json.load(f)
                meta = data.get("metadata", {})
                ts = meta.get("timestamp", "Unknown")
                gen_at = meta.get("generated_at", "Unknown")
                weather_snap = meta.get("weather_snapshot", [])
                
                with st.expander(f"📦 Version {ts} (Generated: {gen_at})"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write("**Weather Snapshot at this point:**")
                        if not weather_snap:
                            st.caption("No overrides active.")
                        else:
                            for rule in weather_snap:
                                st.code(f"{rule.get('employee', 'Global')}: {rule.get('reason', 'Surge')}")
                    
                    with col2:
                        if st.button("⏪ Restore this state", key=f"restore_{ts}"):
                            with open(weather_path, 'w') as f:
                                json.dump({"daily_overrides": weather_snap}, f, indent=2)
                            st.success(f"Restored weather to version {ts}. Please re-run the engine.")
                            st.rerun()
                    
                    st.download_button("📥 Download This JSON", data=json.dumps(data, indent=2), file_name=f_name, key=f"dl_{ts}")

    elif menu == "📊 Resource Analytics":
        st.title("📊 Staff Resource Analytics")
        st.subheader("Deep insights into team health and workload distribution.")

        import glob
        rosters_dir = os.path.join(base_dir, 'Rosters')
        files = glob.glob(os.path.join(rosters_dir, 'roster_*.json'))
        if not files:
            st.warning("No roster data available for analysis. Please generate a roster first.")
            return
        
        latest_file = max(files, key=os.path.getmtime)
        with open(latest_file, 'r') as f: roster = json.load(f)
        jsons_dir = os.path.join(base_dir, 'jsons')
        with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: employees = json.load(f)

        # --- ADVANCED ANALYTICS ENGINE ---
        stats = []
        shift_h = {"Morning": 9, "Evening": 9, "Night": 9, "12hDay": 12, "12hNight": 12}
        all_dates = sorted(roster["assignments"].keys())
        
        for eid, e_data in employees["employees"].items():
            total_h = 0
            nights = 0
            twelve_h_shifts = 0
            consecutive_days = 0
            max_consecutive = 0
            
            for d in all_dates:
                s_name = roster["assignments"][d].get(eid)
                if s_name and s_name != "—":
                    total_h += shift_h.get(s_name, 0)
                    if "Night" in s_name: nights += 1
                    if "12h" in s_name: twelve_h_shifts += 1
                    consecutive_days += 1
                    max_consecutive = max(max_consecutive, consecutive_days)
                else:
                    consecutive_days = 0
            
            stats.append({
                "Name": e_data["name"], 
                "Team": e_data["team"], 
                "Weekly Hours": total_h, 
                "Night Shifts": nights,
                "12h Intensity": twelve_h_shifts,
                "Max Streak": max_consecutive
            })
        
        df = pd.DataFrame(stats)
        
        # 1. FAIRNESS CALCULATION (Standard Deviation of Workload)
        workload_variance = df["Weekly Hours"].std()
        fairness_score = max(0, 100 - (workload_variance * 2)) # 100 is perfect equality
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Workforce", len(employees["employees"]))
        m2.metric("Fairness Index", f"{int(fairness_score)}%", help="How evenly work is distributed. Higher is better.")
        m3.metric("Avg Fatigue", f"{round(df['Max Streak'].mean(), 1)} days", help="Average consecutive working days.")
        m4.metric("System Fragility", f"{df['12h Intensity'].max()} max", help="Highest concentration of 12h shifts on one person.")

        st.divider()
        
        # 2. VISUAL DISTRIBUTION
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write("### 🎢 Fatigue Velocity (Work Streaks)")
            st.caption("Max consecutive days worked. Anything over 5 days increases error rates by 30%.")
            fig_fatigue = px.bar(
                df, x="Max Streak", y="Name", orientation='h', color="Max Streak",
                color_continuous_scale='OrRd',
                labels={"Max Streak": "Longest Consecutive Streak (Days)"},
                template="plotly_dark", height=400
            )
            st.plotly_chart(fig_fatigue, width="stretch")

        with c2:
            st.write("### 🧬 Shift Complexity Mix")
            # Show ratio of 12h vs 9h shifts
            intensity_df = df.groupby("Team")[["12h Intensity", "Weekly Hours"]].sum().reset_index()
            fig_intensity = px.pie(
                intensity_df, values='12h Intensity', names='Team',
                hole=.4, title="12h Shift Distribution",
                color_discrete_sequence=px.colors.sequential.RdBu
            )
            st.plotly_chart(fig_intensity, width="stretch")

        st.divider()
        
        # 3. IMPACTFUL WATCHLISTS
        st.write("### 🩺 Clinical Roster Health Checks")
        w1, w2 = st.columns(2)
        
        with w1:
            st.write("#### 🏮 Fatigue Risk (Long Streaks)")
            risk_streak = df[df["Max Streak"] >= 6].sort_values("Max Streak", ascending=False)
            if not risk_streak.empty:
                st.warning(f"Found {len(risk_streak)} staff working 6+ days in a row.")
                st.dataframe(risk_streak[["Name", "Max Streak", "Team"]], hide_index=True)
            else:
                st.success("No dangerous work streaks detected.")

        with w2:
            st.write("#### 💎 Critical Dependency (12h Concentration)")
            risk_dependency = df[df["12h Intensity"] >= 4].sort_values("12h Intensity", ascending=False)
            if not risk_dependency.empty:
                st.error("High Dependency Alert: These staff carry the majority of 12h shifts.")
                st.dataframe(risk_dependency[["Name", "12h Intensity", "Weekly Hours"]], hide_index=True)
            else:
                st.success("12h shifts are well-balanced across the team.")

        st.divider()
        # --- ORIGINAL ANALYTICS (Preserved for compatibility) ---
        c3, c4 = st.columns([2, 1])
        with c3:
            st.write("### 🔥 Total Weekly Workload")
            df["Status"] = df["Weekly Hours"].apply(lambda x: "🚨 High Strain" if x > 60 else "✅ Normal")
            fig_workload = px.bar(
                df, x="Weekly Hours", y="Name", orientation='h', color="Status",
                color_discrete_map={"🚨 High Strain": "#e74c3c", "✅ Normal": "#2ecc71"},
                template="plotly_dark", height=400
            )
            st.plotly_chart(fig_workload, width="stretch")

        with c4:
            st.write("### 📦 Departmental Load")
            fig_pie = px.sunburst(
                df, path=['Team', 'Name'], values='Weekly Hours',
                color='Weekly Hours', color_continuous_scale='RdYlGn_r',
                template="plotly_dark", height=400
            )
            st.plotly_chart(fig_pie, width="stretch")

    elif menu == "📜 Rulebook":
        st.title("📜 Operational Rulebook")
        st.subheader("The mathematical and logical constraints governing your operations.")
        st.caption("Rules are sorted by Penalty Severity (Impact on the Math Engine).")

        # Load Rule Data
        jsons_dir = os.path.join(base_dir, 'jsons')
        with open(os.path.join(jsons_dir, 'thai_laws.json'), 'r') as f: laws = json.load(f)
        with open(os.path.join(jsons_dir, 'company_policies.json'), 'r') as f: policies = json.load(f)
        
        rules_list = []

        # 1. HARD LAWS (Highest Penalty)
        for key, val in laws.items():
            rules_list.append({
                "Category": "🧱 Thai Labor Law",
                "Rule Name": key.replace('_', ' ').title(),
                "Description": f"Hard legal constraint: {val}",
                "Penalty Impact": "CORE (Infinite)",
                "Priority": 1000000000
            })

        # 2. CEO POLICIES (Dynamic Penalties)
        p_targets = policies.get("optimization_targets", {})
        for name, data in p_targets.items():
            penalty = 0
            desc = ""
            if "penalty_per_extra_person" in data: 
                penalty = data["penalty_per_extra_person"]
                desc = f"Ideal headcount: {data.get('ideal_headcount')}. Penalty per extra person."
            elif "penalty_per_occurrence" in data:
                penalty = data["penalty_per_occurrence"]
                desc = f"Limit: {data.get('limit')}. Penalty per violation."
            elif "penalty_per_day_under" in data:
                penalty = data["penalty_per_day_under"]
                desc = f"Target days: {data.get('target_days')}. Penalty per day under target."

            rules_list.append({
                "Category": "📈 CEO Policy",
                "Rule Name": name.replace('_', ' ').title(),
                "Description": desc,
                "Penalty Impact": f"{penalty:,} pts",
                "Priority": penalty
            })

        # Display sorted by Priority
        df_rules = pd.DataFrame(rules_list).sort_values("Priority", ascending=False)
        
        def color_category(val):
            if "Law" in str(val): return 'color: #e74c3c; font-weight: bold'
            return 'color: #3498db'

        st.table(df_rules[["Category", "Rule Name", "Description", "Penalty Impact"]].style.applymap(color_category, subset=["Category"]))

        st.divider()
        st.write("### 🧠 How the Engine Thinks")
        st.info("""
            1. **Hard Rules (1,000,000,000+ impact):** These are 'Hard Constraints'. If the engine cannot satisfy these (e.g., someone working 7 days in a row), it will return **INFEASIBLE**.
            2. **Soft Rules (Penalties):** These are goals. The engine will try to minimize the total penalty score. A rule with a 20,000 penalty is 20x more important to the engine than a rule with a 1,000 penalty.
        """)

if __name__ == "__main__":
    main()
