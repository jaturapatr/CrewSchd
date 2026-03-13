import streamlit as st
import os
import json
import glob
import pandas as pd
import plotly.express as px

def show_analytics(rosters_dir, jsons_dir, employees):
    st.title("📊 Staff Resource Analytics")
    st.subheader("Deep insights into team health and workload distribution.")

    files = glob.glob(os.path.join(rosters_dir, 'roster_*.json'))
    if not files:
        st.warning("No roster data available for analysis. Please generate a roster first.")
        return
    
    latest_file = max(files, key=os.path.getmtime)
    with open(latest_file, 'r') as f: roster = json.load(f)

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
    
    # 1. FAIRNESS CALCULATION
    workload_variance = df["Weekly Hours"].std()
    fairness_score = max(0, 100 - (workload_variance * 2))
    
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
        fig_fatigue = px.bar(
            df, x="Max Streak", y="Name", orientation='h', color="Max Streak",
            color_continuous_scale='OrRd',
            labels={"Max Streak": "Longest Consecutive Streak (Days)"},
            template="plotly_dark", height=400
        )
        st.plotly_chart(fig_fatigue, width="stretch")

    with c2:
        st.write("### 🧬 Shift Complexity Mix")
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
