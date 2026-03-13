import streamlit as st
import os
import json
import glob
import pandas as pd
import plotly.express as px
from datetime import date

def show_company_overview(jsons_root, base_dir):
    st.title("🏢 Company Command Center")
    st.subheader("Global workforce health and roster status across all branches.")

    all_data = []
    available_branches = sorted([d for d in os.listdir(jsons_root) if os.path.isdir(os.path.join(jsons_root, d))])
    
    for branch in available_branches:
        branch_path = os.path.join(jsons_root, branch)
        teams = sorted([d for d in os.listdir(branch_path) if os.path.isdir(os.path.join(branch_path, d))])
        
        for team in teams:
            team_jsons = os.path.join(branch_path, team)
            emp_file = os.path.join(team_jsons, 'employee.json')
            rosters_dir = os.path.join(base_dir, 'Rosters', branch, team)
            
            # Load Employee Count
            emp_count = 0
            if os.path.exists(emp_file):
                with open(emp_file, 'r') as f:
                    ed = json.load(f)
                    emp_count = len(ed.get("employees", {}))
            
            # Check Latest Roster
            latest_roster_date = "None"
            roster_files = glob.glob(os.path.join(rosters_dir, 'roster_*.json'))
            if roster_files:
                latest_f = max(roster_files, key=os.path.getmtime)
                try:
                    with open(latest_f, 'r') as f:
                        rd = json.load(f)
                        latest_roster_date = rd.get("metadata", {}).get("start_date", "Unknown")
                except: pass

            # Load active overrides (health)
            overrides_count = 0
            weather_file = os.path.join(team_jsons, 'weather.json')
            if os.path.exists(weather_file):
                with open(weather_file, 'r') as f:
                    wd = json.load(f)
                    overrides_count = len(wd.get("daily_overrides", []))

            all_data.append({
                "Branch": branch,
                "Team": team,
                "Staff Count": emp_count,
                "Active Overrides": overrides_count,
                "Latest Roster": latest_roster_date
            })

    if not all_data:
        st.info("No data available across branches.")
        return

    df = pd.DataFrame(all_data)

    # Global Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Workforce", df["Staff Count"].sum())
    m2.metric("Total Active Overrides", df["Active Overrides"].sum())
    m3.metric("Operating Teams", len(df))

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.write("### 📊 Staff Distribution")
        fig_dist = px.bar(df, x="Branch", y="Staff Count", color="Team", title="Workforce by Branch & Team", template="plotly_dark")
        st.plotly_chart(fig_dist, use_container_width=True)

    with c2:
        st.write("### 🤒 Operational Stress (Overrides)")
        fig_health = px.pie(df, values='Active Overrides', names='Branch', title="Absence Concentration", hole=0.4, template="plotly_dark")
        st.plotly_chart(fig_health, use_container_width=True)

    st.divider()
    st.write("### 📋 Roster Pulse Check")
    
    def color_roster(val):
        if val == "None": return 'color: #e74c3c; font-weight: bold'
        return 'color: #2ecc71'

    st.dataframe(df.style.applymap(color_roster, subset=["Latest Roster"]), hide_index=True, use_container_width=True)
