import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px
import glob
from datetime import date
from roster_engine import generate_roster
from Exporter import export_perfect_roster

def show_control_tower(target_date, rosters_dir, jsons_dir, weather_path, weather, emps_ctx, biz_ctx, get_api_key, base_dir, branch="Main Office", team="Cashier"):
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
                except (json.JSONDecodeError, AttributeError, KeyError):
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                    st.rerun()

    if st.button("🚀 RUN MATH ENGINE", width="stretch", type="primary"):
        with st.spinner(f"🔢 Solving Matrix for {branch}/{team}..."):
            try:
                status = generate_roster(target_date, branch=branch, team=team)
                if status == "INFEASIBLE":
                    st.error("❌ **MATHEMATICAL PARADOX DETECTED**\n\nThe current constraints (Active Overrides + Labor Laws + Headcount) are physically impossible to solve. Please remove some Active Overrides or lower the coverage requirements and try again.")
                elif status is None:
                    st.error("❌ **ENGINE FAILURE**\n\nThe engine returned no result. Check logs for details.")
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
    
    # 📅 BEAUTIFUL ROSTER GRID WITH CHANGE TRACKING
    st.subheader("🗓️ Visual Master Schedule")
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
            row = {"Staff": details['name'], "Team": details["team"]}
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
