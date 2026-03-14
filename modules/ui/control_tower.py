import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px
import glob
from datetime import date
from roster_engine import generate_roster
from Exporter import export_perfect_roster
from Translator import translate_weather_to_json

def get_infeasible_diagnosis(api_key, branch, team, emps_ctx, b_ctx, overrides_ctx):
    """Uses LLM to explain why the roster is infeasible."""
    from google import genai
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    You are the 'Roster Forensic Analyst'. The scheduling engine just returned INFEASIBLE for:
    BRANCH: {branch}
    TEAM: {team}
    
    CONTEXT:
    - Employees: {emps_ctx}
    - Branch Coverage Rules: {b_ctx}
    - Active Leave/Sick Overrides: {overrides_ctx}
    - Rules Enforced: Thai Labor Law (max 6 days, max 84h), 11h Rest Rule, Max 12h per day.
    
    TASK:
    Analyze the math. Explain exactly why this is impossible (e.g., 'You have 3 staff but need 4 to cover 24/7' or 'Too many sick leaves on Tuesday'). 
    Suggest 3 specific options for the admin to fix it. Be concise and professional.
    """
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except:
        return "The engine is over-constrained. Check if your headcount can mathematically cover your required blocks while following labor laws (max 6 days/week)."

def show_control_tower(target_date, rosters_dir, jsons_dir, weather_path, weather, emps_ctx, biz_ctx, api_key, base_dir, branch="Main Office", team="Cashier"):
    st.title(f"🚜 Control Tower: {branch} -> {team}")

    # 🤖 FLOATING ROSTER ASSISTANT (Bottom Right)
    with st.container():
        with st.popover("🤖", help="Open AI Roster Assistant"):
            st.subheader("🤖 Roster Assistant")
            st.caption("Request changes (Leaves/Sick) OR ask questions.")
            
            files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
            current_roster = "{}"
            if files:
                with open(files[-1], 'r') as f: current_roster = f.read()

            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []

            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])

            user_prompt = st.chat_input("e.g., Fai is sick tomorrow...")
            
            if user_prompt:
                st.session_state.chat_history.append({"role": "user", "content": user_prompt})
                ai_context_json = json.dumps({
                    "current_roster": current_roster,
                    "employees": emps_ctx,
                    "branch": branch,
                    "team": team
                })
                with st.spinner("Hub is thinking..."):
                    res_data = translate_weather_to_json(user_prompt, api_key, ai_context_json)
                    if "overrides" in res_data:
                        weather["daily_overrides"].extend(res_data["overrides"])
                        with open(weather_path, 'w') as f: json.dump(weather, f, indent=2)
                        st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Added {len(res_data['overrides'])} rules."})
                        st.rerun()
                    elif "error" in res_data:
                        st.session_state.chat_history.append({"role": "assistant", "content": f"❌ Error: {res_data['error']}"})
                        st.rerun()
                    else:
                        st.session_state.chat_history.append({"role": "assistant", "content": str(res_data)})
                        st.rerun()

    if st.button("🚀 RUN MATH ENGINE", width="stretch", type="primary"):
        with st.spinner(f"🔢 Solving Matrix for {branch}/{team}..."):
            try:
                status = generate_roster(target_date, branch=branch, team=team)
                if status == "INFEASIBLE":
                    st.error("❌ **MATHEMATICAL PARADOX DETECTED**")
                    with st.expander("🔍 AI Diagnostic: Why is this impossible?", expanded=True):
                        diagnosis = get_infeasible_diagnosis(api_key, branch, team, emps_ctx, biz_ctx, json.dumps(weather))
                        st.write(diagnosis)
                elif status is None:
                    st.error("❌ **ENGINE FAILURE**")
                else:
                    export_perfect_roster(branch=branch, team=team)
                    st.success(f"✅ Roster Generated and Exported for {branch} -> {team}!")
                    st.balloons()
                    st.rerun()
            except Exception as e:
                st.error(f"❌ **CRITICAL SYSTEM ERROR**\n\n{str(e)}")
                import traceback
                st.code(traceback.format_exc())

    st.divider()
    
    # 📅 BEAUTIFUL ROSTER GRID
    st.subheader("🗓️ Visual Master Schedule")
    files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
    
    if len(files) >= 1:
        latest_file = files[-1]
        prev_file = files[-2] if len(files) > 1 else None
        with open(latest_file, 'r') as f: roster = json.load(f)
        prev_roster = None
        if prev_file:
            with open(prev_file, 'r') as f: prev_roster = json.load(f)
        with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: emps = json.load(f)
        
        BLOCK_MAP = {"00:00": "🌑 00-04", "04:00": "🌅 04-08", "08:00": "☀️ 08-12", "12:00": "🌤️ 12-16", "16:00": "🌇 16-20", "20:00": "🌌 20-00"}
        data = []
        change_count = 0
        all_dates = sorted(roster["assignments"].keys())
        for eid, details in emps["employees"].items():
            row = {"Staff": details['name'], "Team": details["team"]}
            for d in all_dates:
                new_blocks = roster["assignments"][d].get(eid, [])
                old_blocks = prev_roster["assignments"].get(d, {}).get(eid, []) if prev_roster else new_blocks
                if not new_blocks: display_val = "💤 OFF"
                else:
                    sorted_new = sorted(new_blocks)
                    display_val = " + ".join([BLOCK_MAP.get(b, b) for b in sorted_new])
                if set(new_blocks) != set(old_blocks):
                    display_val = f"🔄 {display_val}"
                    change_count += 1
                row[d] = display_val
            data.append(row)
        
        if change_count > 0: st.info(f"✨ **Intelligence Report:** Found {change_count} block changes since last version.")
        df = pd.DataFrame(data)
        display_columns = ["Staff"] + all_dates
        
        def style_cells(val):
            if "🔄" in str(val): return "font-weight: bold"
            if "OFF" in str(val): return "color: #adb5bd; font-style: italic"
            return "color: #3498db"

        view_type = st.radio("Display Mode", ["🎨 Visual Pulse", "📋 Spreadsheet"], horizontal=True, label_visibility="collapsed")
        
        if view_type == "📋 Spreadsheet":
            team_names = sorted(list(set(row["Team"] for row in data)))
            team_tabs = st.tabs(["All Teams"] + team_names)
            with team_tabs[0]:
                st.dataframe(df[display_columns].style.map(style_cells), column_config={d: st.column_config.TextColumn(date.fromisoformat(d).strftime('%a [%d/%m/%y]')) for d in all_dates}, hide_index=True, width="stretch", height=600)
                report_path = os.path.join(base_dir, f'Perfect_Roster_View_{branch.replace(" ", "_")}_{team.replace(" ", "_")}.html')
                if os.path.exists(report_path):
                    with open(report_path, 'r', encoding='utf-8') as f: st.download_button("📥 Download HTML Report", f.read(), f"roster_{target_date}.html", "text/html", width="stretch")
            for i, team_name in enumerate(team_names):
                with team_tabs[i+1]:
                    st.dataframe(df[df["Team"] == team_name][display_columns].style.map(style_cells), column_config={d: st.column_config.TextColumn(date.fromisoformat(d).strftime('%a [%d/%m/%y]')) for d in all_dates}, hide_index=True, width="stretch")
        else:
            st.write("### 📉 Operational Pulse")
            total_staff = len(emps["employees"])
            total_capacity_hours = total_staff * 48
            actual_scheduled_hours = 0
            effort_data = []
            for eid, details in emps["employees"].items():
                staff_hours = 0
                for d in all_dates:
                    assigned = roster["assignments"][d].get(eid, [])
                    h = len(assigned) * 4
                    staff_hours += h
                    actual_scheduled_hours += h
                effort_data.append({"Staff": details["name"], "Hours": staff_hours})
            utilization_rate = (actual_scheduled_hours / total_capacity_hours) * 100 if total_capacity_hours > 0 else 0
            m1, m2, m3 = st.columns(3)
            m1.metric("Workforce Utilization", f"{int(utilization_rate)}%")
            m2.metric("Scheduled Labor", f"{actual_scheduled_hours}h")
            m3.metric("Excess Capacity", f"{total_capacity_hours - actual_scheduled_hours}h")
            
            pulse_data = []
            all_blocks = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]
            for d in all_dates:
                for b in all_blocks:
                    count = sum(1 for eid, assigned_list in roster["assignments"][d].items() if b in assigned_list)
                    pulse_data.append({"Date": d, "Block": b, "Headcount": count})
            st.plotly_chart(px.bar(pd.DataFrame(pulse_data), x="Date", y="Headcount", color="Block", title="Workforce Heartbeat (4h Blocks)", template="plotly_dark", height=400), width="stretch")
            st.plotly_chart(px.bar(pd.DataFrame(effort_data).sort_values("Hours", ascending=False), x="Staff", y="Hours", text="Hours", title="Total Weekly Workload", template="plotly_dark", height=400, color="Hours", color_continuous_scale="RdYlGn_r"), width="stretch")
    else:
        st.warning("No roster found. Please run the Math Engine.")
