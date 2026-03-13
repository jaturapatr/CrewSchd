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
                
                # Context for the AI (Serialized to string for st.cache_data compatibility)
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
        
        EMOJI_MAP = {
            "Morning": "☀️ Morning", "Evening": "🌆 Evening", "Night": "🌑 Night",
            "12hDay": "🔥 12h Day", "12hNight": "🌌 12h Night", "—": "💤 OFF"
        }

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
        
        if change_count > 0:
            st.info(f"✨ **Intelligence Report:** Found {change_count} shift changes since the last version (marked with 🔄).")

        df = pd.DataFrame(data)
        display_columns = ["Staff"] + all_dates
        
        def style_cells(val):
            if "🔄" in str(val): return "font-weight: bold"
            if "Morning" in str(val): return "color: #f08c00"
            if "Night" in str(val): return "color: #1971c2"
            if "12h" in str(val): return "color: #e8590c; font-weight: bold"
            if "OFF" in str(val): return "color: #adb5bd; font-style: italic"
            return ""

        team_names = sorted(list(set(row["Team"] for row in data)))
        view_type = st.radio("Display Mode", ["🎨 Visual Pulse", "📋 Spreadsheet"], horizontal=True, label_visibility="collapsed")
        
        if view_type == "📋 Spreadsheet":
            team_tabs = st.tabs(["All Teams"] + team_names)
            with team_tabs[0]:
                st.dataframe(
                    df[display_columns].style.map(style_cells),
                    column_config={d: st.column_config.TextColumn(date.fromisoformat(d).strftime('%a [%d/%m/%y]')) for d in all_dates},
                    hide_index=True, width="stretch", height=600
                )
                report_path = os.path.join(base_dir, f'Perfect_Roster_View_{branch.replace(" ", "_")}_{team.replace(" ", "_")}.html')
                if os.path.exists(report_path):
                    with open(report_path, 'r', encoding='utf-8') as f:
                        st.download_button(
                            label="📥 Download HTML Report",
                            data=f.read(),
                            file_name=f"roster_{target_date}.html",
                            mime="text/html",
                            width="stretch"
                        )

            for i, team_name in enumerate(team_names):
                with team_tabs[i+1]:
                    st.dataframe(
                        df[df["Team"] == team_name][display_columns].style.map(style_cells),
                        column_config={d: st.column_config.TextColumn(date.fromisoformat(d).strftime('%a [%d/%m/%y]')) for d in all_dates},
                        hide_index=True, width="stretch"
                    )
        else:
            # --- 🎨 VISUAL PULSE ---
            st.write("### 📉 Operational Pulse")
            shift_h = {"Morning": 9, "Evening": 9, "Night": 9, "12hDay": 12, "12hNight": 12}
            total_staff = len(emps["employees"])
            total_capacity_hours = total_staff * 48
            
            actual_scheduled_hours = 0
            low_hour_staff = []
            effort_data = []

            for eid, details in emps["employees"].items():
                staff_hours = 0
                for d in all_dates:
                    s_name = roster["assignments"][d].get(eid)
                    if s_name and s_name != "—":
                        h = shift_h.get(s_name, 0)
                        staff_hours += h
                        actual_scheduled_hours += h
                effort_data.append({"Staff": details["name"], "Hours": staff_hours})
                if staff_hours < 16:
                    low_hour_staff.append(f"{details['name']} ({staff_hours}h)")

            utilization_rate = (actual_scheduled_hours / total_capacity_hours) * 100 if total_capacity_hours > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Workforce Utilization", f"{int(utilization_rate)}%", delta=f"{int(utilization_rate - 85)}% from target", delta_color="inverse" if utilization_rate < 80 else "normal")
            m2.metric("Scheduled Labor", f"{actual_scheduled_hours}h")
            m3.metric("Excess Capacity", f"{total_capacity_hours - actual_scheduled_hours}h")

            if low_hour_staff:
                st.error(f"🚨 **CFO Alert: Redundant Headcount Detected**\n\nFully utilized: **{', '.join(low_hour_staff)}**.")
            
            pulse_data = []
            for d in all_dates:
                for s in ["Morning", "Evening", "Night", "12hDay", "12hNight"]:
                    count = sum(1 for eid, assigned_s in roster["assignments"][d].items() if assigned_s == s)
                    pulse_data.append({"Date": d, "Shift": s, "Headcount": count})
            
            fig_pulse = px.bar(
                pd.DataFrame(pulse_data), x="Date", y="Headcount", color="Shift",
                title="Workforce Capacity Heartbeat",
                color_discrete_map={
                    "Morning": "#f1c40f", "Evening": "#e67e22", "Night": "#34495e",
                    "12hDay": "#e74c3c", "12hNight": "#9b59b6"
                },
                template="plotly_dark", height=400
            )
            st.plotly_chart(fig_pulse, width="stretch")

            st.write("#### ⚖️ Worker Effort (Weekly Hours)")
            df_effort = pd.DataFrame(effort_data).sort_values("Hours", ascending=False)
            fig_effort = px.bar(
                df_effort, x="Staff", y="Hours", text="Hours",
                title="Total Weekly Workload", template="plotly_dark", height=400,
                color="Hours", color_continuous_scale="RdYlGn_r"
            )
            st.plotly_chart(fig_effort, width="stretch")

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.write("#### 🛡️ Team Coverage Balance")
                team_coverage = []
                for d in all_dates:
                    for team_name in team_names:
                        count = sum(1 for eid, assigned_s in roster["assignments"][d].items() if emps["employees"][eid]["team"] == team_name and assigned_s != "—")
                        team_coverage.append({"Date": d, "Team": team_name, "Count": count})
                st.plotly_chart(px.line(pd.DataFrame(team_coverage), x="Date", y="Count", color="Team", markers=True, title="Team Presence Stability", template="plotly_dark"), width="stretch")
            with c2:
                st.write("#### 🎓 Experience Mix")
                tier_data = []
                for d in all_dates:
                    for tier in ["Senior", "Junior"]:
                        count = sum(1 for eid, assigned_s in roster["assignments"][d].items() if emps["employees"][eid]["tier"] == tier and assigned_s != "—")
                        tier_data.append({"Date": d, "Tier": tier, "Count": count})
                st.plotly_chart(px.area(pd.DataFrame(tier_data), x="Date", y="Count", color="Tier", title="Seniority Concentration", template="plotly_dark", color_discrete_map={"Senior": "#2ecc71", "Junior": "#bdc3c7"}), width="stretch")
    else:
        st.warning("No roster found. Please run the Math Engine.")
