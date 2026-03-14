import streamlit as st
import os
import json
import glob
import pandas as pd
import plotly.express as px
from datetime import date

def show_staff_war_room(jsons_root, base_dir):
    st.title("🛡️ Staff War Room")
    st.markdown("<p style='color: #888; font-style: italic; margin-top: -15px;'>Real-time multi-dimensional workforce intelligence.</p>", unsafe_allow_html=True)

    # --- 1. DATA AGGREGATION ---
    master_staff = []
    available_branches = sorted([d for d in os.listdir(jsons_root) if os.path.isdir(os.path.join(jsons_root, d))])
    
    with st.spinner("Aggregating global intelligence..."):
        for branch in available_branches:
            branch_path = os.path.join(jsons_root, branch)
            teams = sorted([d for d in os.listdir(branch_path) if os.path.isdir(os.path.join(branch_path, d))])
            
            for team in teams:
                team_jsons = os.path.join(branch_path, team)
                emp_file = os.path.join(team_jsons, 'employee.json')
                weather_file = os.path.join(team_jsons, 'weather.json')
                rosters_dir = os.path.join(base_dir, 'Rosters', branch, team)
                
                if not os.path.exists(emp_file): continue
                with open(emp_file, 'r', encoding='utf-8') as f:
                    ed = json.load(f).get("employees", {})
                
                active_overrides = {}
                if os.path.exists(weather_file):
                    with open(weather_file, 'r', encoding='utf-8') as f:
                        wd = json.load(f).get("daily_overrides", [])
                        for rule in wd:
                            e_ref = str(rule.get("employee", "")).strip().lower()
                            active_overrides[e_ref] = active_overrides.get(e_ref, 0) + 1
                
                latest_roster = None
                files = glob.glob(os.path.join(rosters_dir, 'roster_*.json'))
                if files:
                    latest_f = max(files, key=os.path.getmtime)
                    try:
                        with open(latest_f, 'r', encoding='utf-8') as f:
                            latest_roster = json.load(f)
                    except: pass
                
                all_dates = []
                if latest_roster:
                    all_dates = sorted(latest_roster.get("assignments", {}).keys())

                for eid, e_data in ed.items():
                    ename = e_data.get("name", "Unknown")
                    ename_lower = ename.strip().lower()
                    eid_lower = eid.strip().lower()
                    
                    override_cnt = active_overrides.get(eid_lower, 0) + active_overrides.get(ename_lower, 0)
                    
                    total_h = 0
                    night_blocks = 0
                    full_days = 0
                    consecutive_days = 0
                    max_consecutive = 0
                    
                    if latest_roster:
                        for d in all_dates:
                            assigned_blocks = latest_roster["assignments"][d].get(eid, [])
                            if assigned_blocks:
                                h = len(assigned_blocks) * 4
                                total_h += h
                                if any(b in ["00:00", "04:00", "20:00"] for b in assigned_blocks):
                                    night_blocks += 1
                                if h >= 8:
                                    full_days += 1
                                consecutive_days += 1
                                max_consecutive = max(max_consecutive, consecutive_days)
                            else:
                                consecutive_days = 0
                                
                    master_staff.append({
                        "Branch": branch,
                        "Team": team,
                        "EID": eid,
                        "Name": ename,
                        "Tier": e_data.get("tier", "Junior"),
                        "Overrides": override_cnt,
                        "Weekly Hours": total_h,
                        "Night Blocks": night_blocks,
                        "8h Days": full_days,
                        "Max Streak": max_consecutive,
                        "Has Roster": 1 if latest_roster else 0
                    })

    if not master_staff:
        st.warning("No staff data found across the organization.")
        return

    df = pd.DataFrame(master_staff)

    # --- 2. GLOBAL ALERT TICKER ---
    # Create a quick ticker for immediate actionable intelligence
    high_strain = len(df[df["Weekly Hours"] > 48])
    high_fatigue = len(df[df["Max Streak"] >= 6])
    total_leaves = df["Overrides"].sum()
    
    st.markdown(f"""
    <div style='background-color: #1e293b; padding: 10px 20px; border-radius: 8px; border-left: 5px solid #e74c3c; margin-bottom: 20px; display: flex; justify-content: space-between;'>
        <span><b>🚨 LIVE INTEL:</b></span>
        <span style='color: {"#e74c3c" if high_strain > 0 else "#2ecc71"}'>🔥 {high_strain} Staff in High Strain (>48h)</span>
        <span style='color: {"#f39c12" if high_fatigue > 0 else "#2ecc71"}'>⚠️ {high_fatigue} Staff Highly Fatigued (6+ Days)</span>
        <span style='color: #3498db'>🌴 {total_leaves} Active Leave Requests</span>
    </div>
    """, unsafe_allow_html=True)

    # --- AI EXECUTIVE BRIEFING ---
    with st.expander("🧠 Generate AI Executive Briefing", expanded=False):
        if st.button("Generate Insight Report", width="stretch", type="primary"):
            from google import genai
            from google.genai import types
            from security import get_api_key
            
            api_key = get_api_key()
            if not api_key:
                st.error("API Key not found.")
            else:
                with st.spinner("Analyzing workforce data..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        
                        # Prepare data for AI
                        data_summary = {
                            "total_staff": len(df),
                            "branches": list(df["Branch"].unique()),
                            "teams": list(df["Team"].unique()),
                            "high_strain_staff": df[df["Weekly Hours"] > 48][["Name", "Branch", "Team", "Weekly Hours"]].to_dict('records'),
                            "fatigued_staff": df[df["Max Streak"] >= 6][["Name", "Branch", "Team", "Max Streak"]].to_dict('records'),
                            "total_leaves": int(total_leaves),
                            "branch_workload_avg": df[df["Has Roster"]==1].groupby("Branch")["Weekly Hours"].mean().to_dict()
                        }
                        
                        system_prompt = """
                        You are an expert HR Operations Analyst. Review the provided JSON data representing the current workforce status.
                        Write a concise, bulleted Executive Summary highlighting:
                        1. Overall Health (Is the organization stressed?)
                        2. Key Risks (Identify specific branches or teams with high strain or fatigue).
                        3. Actionable Recommendations (What should management do right now?).
                        Keep it professional, direct, and under 250 words.
                        """
                        
                        response = client.models.generate_content(
                            model='gemini-2.5-flash',
                            config=types.GenerateContentConfig(system_instruction=system_prompt),
                            contents=json.dumps(data_summary, default=str)
                        )
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"AI Analysis Failed: {str(e)}")

    # --- 3. FLUID NAVIGATION LENS ---
    st.write("### 🔭 Select Intelligence Lens")
    view_lens = st.radio(
        "Lens Selection",
        ["🌍 Global HQ", "📍 Branch Hub", "👥 Team Metrics", "👤 Staff Profiler"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.divider()

    # --- 4. DYNAMIC VIEWS ---
    
    # LENS 1: GLOBAL HQ
    if view_lens == "🌍 Global HQ":
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Workforce", len(df))
        m2.metric("Operating Branches", df["Branch"].nunique())
        m3.metric("Operating Teams", df["Team"].nunique())
        m4.metric("Avg Org Weekly Hours", f"{round(df[df['Has Roster']==1]['Weekly Hours'].mean(), 1)}h" if not df[df['Has Roster']==1].empty else "N/A")
        
        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🌍 Workforce Distribution**")
            fig_dist = px.treemap(
                df, path=[px.Constant("Global HQ"), 'Branch', 'Team'], 
                color='Branch', color_discrete_sequence=px.colors.qualitative.Pastel,
                template="plotly_dark", height=400
            )
            fig_dist.update_traces(root_color="black")
            st.plotly_chart(fig_dist, width="stretch", config={'displayModeBar': False})
            
        with c2:
            st.markdown("**🤒 Organizational Stress Concentration**")
            stress_df = df.groupby("Branch")["Overrides"].sum().reset_index()
            fig_health = px.pie(
                stress_df, values='Overrides', names='Branch', hole=0.5, 
                color_discrete_sequence=px.colors.sequential.RdBu,
                template="plotly_dark", height=400
            )
            fig_health.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_health, width="stretch", config={'displayModeBar': False})

    # LENS 2: BRANCH HUB
    elif view_lens == "📍 Branch Hub":
        loc_sel = st.selectbox("🎯 Target Branch", df["Branch"].unique())
        loc_df = df[df["Branch"] == loc_sel]
        
        lm1, lm2, lm3 = st.columns(3)
        lm1.metric(f"Total Staff", len(loc_df))
        lm2.metric("Total Active Overrides", loc_df["Overrides"].sum())
        
        active_rosters = loc_df[loc_df["Has Roster"] == 1]
        lm3.metric("Avg Weekly Hours", f"{round(active_rosters['Weekly Hours'].mean(), 1)}h" if not active_rosters.empty else "N/A")
            
        if not active_rosters.empty:
            st.write("")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**🔥 Workload Distribution ({loc_sel})**")
                fig_loc_workload = px.box(
                    active_rosters, x="Team", y="Weekly Hours", color="Team",
                    points="all", template="plotly_dark", height=400
                )
                st.plotly_chart(fig_loc_workload, width="stretch", config={'displayModeBar': False})
            with c2:
                st.markdown(f"**🎢 Branch Fatigue Radar**")
                fatigue_df = active_rosters.groupby("Team")["Max Streak"].mean().reset_index()
                fig_radar = px.line_polar(
                    fatigue_df, r='Max Streak', theta='Team', line_close=True,
                    template="plotly_dark", height=400
                )
                fig_radar.update_traces(fill='toself')
                st.plotly_chart(fig_radar, width="stretch", config={'displayModeBar': False})
        else:
            st.info(f"Generate rosters for {loc_sel} teams to unlock deep workload analytics.")

    # LENS 3: TEAM METRICS
    elif view_lens == "👥 Team Metrics":
        c1, c2 = st.columns(2)
        with c1: team_branch_sel = st.selectbox("📍 Target Branch", df["Branch"].unique(), key="tb_sel")
        with c2: team_sel = st.selectbox("👥 Target Team", df[df["Branch"] == team_branch_sel]["Team"].unique(), key="t_sel")
            
        team_df = df[(df["Branch"] == team_branch_sel) & (df["Team"] == team_sel)]
        active_team_df = team_df[team_df["Has Roster"] == 1]
        
        if active_team_df.empty:
            st.info(f"Generate a roster for {team_branch_sel} -> {team_sel} to unlock analytics.")
        else:
            workload_variance = active_team_df["Weekly Hours"].std()
            fairness_score = max(0, 100 - (workload_variance * 2)) if not pd.isna(workload_variance) else 100
            
            tm1, tm2, tm3, tm4 = st.columns(4)
            tm1.metric("Equity Score", f"{int(fairness_score)}/100", help="100 means everyone works exact same hours")
            tm2.metric("System Load", f"{active_team_df['8h Days'].sum()} 8h-Days")
            tm3.metric("Avg Fatigue", f"{round(active_team_df['Max Streak'].mean(), 1)} days")
            tm4.metric("Night Intensity", f"{active_team_df['Night Blocks'].sum()} Blocks")
            
            st.write("")
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("**💎 Workload Concentration**")
                active_team_df["Status"] = active_team_df["Weekly Hours"].apply(lambda x: "🚨 High Strain" if x > 48 else "✅ Normal")
                fig_workload = px.bar(
                    active_team_df.sort_values('Weekly Hours'), x="Weekly Hours", y="Name", orientation='h', color="Status",
                    color_discrete_map={"🚨 High Strain": "#e74c3c", "✅ Normal": "#2ecc71"},
                    template="plotly_dark", height=400
                )
                st.plotly_chart(fig_workload, width="stretch", config={'displayModeBar': False})
                
            with c4:
                st.markdown("**🎢 Fatigue Velocity**")
                fig_fatigue = px.bar(
                    active_team_df.sort_values('Max Streak'), x="Max Streak", y="Name", orientation='h', color="Max Streak",
                    color_continuous_scale='OrRd', template="plotly_dark", height=400
                )
                st.plotly_chart(fig_fatigue, width="stretch", config={'displayModeBar': False})

    # LENS 4: INDIVIDUAL PROFILER
    elif view_lens == "👤 Staff Profiler":
        c1, c2, c3 = st.columns(3)
        with c1: i_branch = st.selectbox("📍 Target Branch", df["Branch"].unique(), key="i_b")
        with c2: i_team = st.selectbox("👥 Target Team", df[df["Branch"] == i_branch]["Team"].unique(), key="i_t")
        with c3: i_name = st.selectbox("👤 Target Staff", df[(df["Branch"] == i_branch) & (df["Team"] == i_team)]["Name"].unique(), key="i_n")
        
        staff_record = df[(df["Branch"] == i_branch) & (df["Team"] == i_team) & (df["Name"] == i_name)].iloc[0]
        
        st.write("")
        st.markdown(f"## {staff_record['Name']}")
        st.caption(f"**ID:** {staff_record['EID']} | **Tier:** {staff_record['Tier']} | **Dept:** {staff_record['Branch']} -> {staff_record['Team']}")
        
        col_metrics, col_radar = st.columns([1, 1])
        
        with col_metrics:
            st.write("### Tactical Metrics")
            st.metric("Weekly Assigned Hours", f"{staff_record['Weekly Hours']}h", 
                      delta="High Strain" if staff_record['Weekly Hours'] > 48 else "Normal", 
                      delta_color="inverse" if staff_record['Weekly Hours'] > 48 else "normal")
            st.metric("Consecutive Working Days", f"{staff_record['Max Streak']} Days",
                      delta="Fatigue Alert" if staff_record['Max Streak'] >= 6 else "Healthy",
                      delta_color="inverse" if staff_record['Max Streak'] >= 6 else "normal")
            st.metric("Night Blocks Assigned", staff_record['Night Blocks'])
            st.metric("Active Leave Requests", staff_record['Overrides'])
            
        with col_radar:
            if staff_record["Has Roster"] == 1:
                st.write("### Health Signature")
                # Normalize values for a 0-10 radar chart
                norm_hours = min((staff_record['Weekly Hours'] / 48) * 10, 10)
                norm_fatigue = min((staff_record['Max Streak'] / 6) * 10, 10)
                norm_nights = min((staff_record['Night Blocks'] / 5) * 10, 10)
                norm_leave = min((staff_record['Overrides'] / 2) * 10, 10)
                
                radar_df = pd.DataFrame(dict(
                    r=[norm_hours, norm_fatigue, norm_nights, norm_leave],
                    theta=['Workload Strain', 'Fatigue Risk', 'Night Shift Intensity', 'Leave Utilization']
                ))
                
                fig = px.line_polar(radar_df, r='r', theta='theta', line_close=True, range_r=[0, 10], template="plotly_dark", height=400)
                fig.update_traces(fill='toself', line_color='#3498db', fillcolor='rgba(52, 152, 219, 0.4)')
                st.plotly_chart(fig, width="stretch", config={'displayModeBar': False})
            else:
                st.info("Radar signature requires an active roster.")
