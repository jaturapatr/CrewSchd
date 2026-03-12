import streamlit as st
import os
import json
import sys
from datetime import date, timedelta
import pandas as pd
import streamlit.components.v1 as components

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
    st.title("🛠️ CrewSchd - Secure Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        if submit:
            if username in USERS and USERS[username] == password:
                st.session_state["authenticated"] = True
                st.session_state["user"] = username
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")

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
    menu = st.sidebar.radio("Navigation", ["🚜 Control Tower", "🕰️ Time Machine", "📊 Resource Analytics"])
    
    # 🛠️ INTERACTIVE WEATHER MANAGER (Sidebar)
    st.sidebar.divider()
    st.sidebar.subheader("🗓️ Active Overrides")
    
    overrides = weather.get("daily_overrides", [])
    if not overrides:
        st.sidebar.info("No active overrides.")
    else:
        for i, rule in enumerate(overrides):
            with st.sidebar.expander(f"{rule.get('employee', 'Global')} - {rule.get('date', 'Demand')}"):
                st.write(f"**Type:** {rule.get('type')}")
                st.write(f"**Reason:** {rule.get('reason', 'N/A')}")
                if st.button("🗑️ Remove", key=f"del_{i}"):
                    overrides.pop(i)
                    with open(weather_path, 'w') as f: json.dump({"daily_overrides": overrides}, f, indent=2)
                    st.rerun()

    if menu == "🚜 Control Tower":
        target_date = st.sidebar.date_input("Schedule Start Date", value=date.today())
        st.title("🚜 Control Tower")
        
        # 🤖 UNIFIED INTELLIGENCE BOT
        with st.container(border=True):
            st.subheader("🤖 Roster Assistant")
            st.caption("Request changes (Leaves/Sick) OR ask questions about the current roster.")
            
            # Load context for the bot
            import glob
            files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
            current_roster = "{}"
            if files:
                with open(files[-1], 'r') as f: current_roster = f.read()
            with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: emps_ctx = f.read()
            with open(os.path.join(jsons_dir, 'business_context.json'), 'r') as f: biz_ctx = f.read()

            user_prompt = st.chat_input("e.g., Who is working Sunday? OR Fai is on leave Monday...")
            
            if user_prompt:
                with st.spinner("Processing..."):
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
                    
                    YOUR PROTOCOL (THINK LIKE A HUMAN MANAGER):
                    1. DATE INTELLIGENCE:
                       - Carefully calculate relative dates. If today is Thursday 12th, "next Wednesday" is the 18th. 
                       - Do NOT just add 7 days. Use the calendar.
                    
                    2. EMPLOYEE IDENTIFICATION:
                       - Use the employee NAME (e.g., "Mam", "Fai") in the JSON 'employee' field, NOT the ID (e.g., "EMP002").
                    
                    3. If the user REQUESTS A CHANGE:
                       - FIRST: Analyze if the request is FEASIBLE based on the CONTEXT.
                       - IF IMPOSSIBLE: Explain WHY. DO NOT return JSON.
                       - IF FEASIBLE: Return ONLY a JSON object with key 'overrides' AND a brief confirmation.
                       - SCHEMA: type: "block_employee_availability", employee: "Name", date: "YYYY-MM-DD", reason: "desc"
                    
                    4. If the user ASKS A QUESTION:
                       - Answer accurately based on the CONTEXT.
                    """
                    
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        config=types.GenerateContentConfig(system_instruction=sys_inst),
                        contents=user_prompt
                    )
                    
                    # Detection Logic: JSON vs TEXT
                    try:
                        clean_text = response.text.replace('```json', '').replace('```', '').strip()
                        res_data = json.loads(clean_text)
                        if "overrides" in res_data:
                            weather["daily_overrides"].extend(res_data["overrides"])
                            with open(weather_path, 'w') as f: json.dump(weather, f, indent=2)
                            st.success(f"✅ Operations Updated: Added {len(res_data['overrides'])} rules.")
                            st.rerun()
                    except:
                        # It's a text response
                        st.markdown(f"**🤖 Bee-Bot:** {response.text}")

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

            # Filter by Team Tabs
            team_names = sorted(list(set(row["Team"] for row in data)))
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
            st.warning("No roster found. Please run the Math Engine.")

    elif menu == "🕰️ Time Machine":
        st.title("🕰️ Roster Time Machine")
        st.subheader("Roll back to a previous 'respawn point' and restore its weather state.")
        
        import glob
        files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime, reverse=True)
        
        if not files:
            st.info("No historical rosters found.")
        else:
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
                            # 1. Revert weather.json to this snapshot
                            with open(weather_path, 'w') as f:
                                json.dump({"daily_overrides": weather_snap}, f, indent=2)
                            st.success(f"Restored weather to version {ts}. Please re-run the engine to update the current roster.")
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

        stats = []
        shift_h = {"Morning": 9, "Evening": 9, "Night": 9, "12hDay": 12, "12hNight": 12}
        for eid, e_data in employees["employees"].items():
            total_h = 0
            nights = 0
            for day_data in roster["assignments"].values():
                s_name = day_data.get(eid)
                if s_name:
                    total_h += shift_h.get(s_name, 0)
                    if "Night" in s_name: nights += 1
            stats.append({"Name": e_data["name"], "Team": e_data["team"], "Weekly Hours": total_h, "Night Shifts": nights})
        
        df = pd.DataFrame(stats)
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Workforce", len(employees["employees"]))
        m2.metric("Avg Weekly Hours", round(df["Weekly Hours"].mean(), 1))
        m3.metric("Peak Load (Max H)", f"{df['Weekly Hours'].max()} hrs")

        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1:
            st.write("### 🔥 Weekly Workload by Employee")
            df["Status"] = df["Weekly Hours"].apply(lambda x: "⚠️ High Strain" if x > 60 else "✅ Normal")
            st.bar_chart(df, x="Name", y="Weekly Hours", color="Status")
        with c2:
            st.write("### 📦 Departmental Load")
            team_load = df.groupby("Team")["Weekly Hours"].sum()
            st.area_chart(team_load)

        st.divider()
        st.write("### 🚨 Burnout Watchlist")
        risk_list = df[df["Weekly Hours"] >= 60].sort_values("Weekly Hours", ascending=False)
        if not risk_list.empty:
            st.table(risk_list[["Name", "Team", "Weekly Hours", "Night Shifts"]])
            st.error("Management Alert: The employees above are working near-maximum capacity.")
        else:
            st.success("Zero burnout detected! All employees are working sustainable hours.")

if __name__ == "__main__":
    main()
