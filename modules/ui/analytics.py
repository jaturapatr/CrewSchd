import streamlit as st
import os
import json
import glob
import pandas as pd
import plotly.express as px

def show_analytics(rosters_dir, jsons_dir, employees):
    st.title("📊 Staff Resource Analytics")
    st.subheader("Deep insights into team health and workload distribution (4h Blocks).")

    files = glob.glob(os.path.join(rosters_dir, 'roster_*.json'))
    if not files:
        st.warning("No roster data available for analysis. Please generate a roster first.")
        return
    
    latest_file = max(files, key=os.path.getmtime)
    with open(latest_file, 'r') as f: roster = json.load(f)

    # --- ADVANCED ANALYTICS ENGINE ---
    stats = []
    all_dates = sorted(roster["assignments"].keys())
    
    for eid, e_data in employees["employees"].items():
        total_h = 0
        night_blocks = 0
        full_days = 0 # 8h days
        consecutive_days = 0
        max_consecutive = 0
        
        for d in all_dates:
            assigned_blocks = roster["assignments"][d].get(eid, [])
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
        
        stats.append({
            "Name": e_data["name"], 
            "Team": e_data["team"], 
            "Weekly Hours": total_h, 
            "Night Blocks": night_blocks,
            "8h Days": full_days,
            "Max Streak": max_consecutive
        })
    
    df = pd.DataFrame(stats)
    
    # 1. FAIRNESS CALCULATION
    workload_variance = df["Weekly Hours"].std()
    fairness_score = max(0, 100 - (workload_variance * 2)) if not pd.isna(workload_variance) else 100
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Workforce", len(employees["employees"]))
    m2.metric("Fairness Index", f"{int(fairness_score)}%", help="How evenly work is distributed.")
    m3.metric("Avg Fatigue", f"{round(df['Max Streak'].mean(), 1)} days", help="Avg consecutive days worked.")
    m4.metric("System Load", f"{df['8h Days'].sum()} total", help="Total number of 8h shifts assigned.")

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
        st.write("### 🧬 Full-Day Distribution (8h)")
        intensity_df = df.groupby("Team")[["8h Days", "Weekly Hours"]].sum().reset_index()
        fig_intensity = px.pie(
            intensity_df, values='8h Days', names='Team',
            hole=.4, title="8h Shift Distribution",
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
        st.write("#### 💎 Workload Concentration")
        risk_dependency = df[df["Weekly Hours"] >= 40].sort_values("Weekly Hours", ascending=False)
        if not risk_dependency.empty:
            st.error("High Workload Alert: Staff nearing or exceeding 40h.")
            st.dataframe(risk_dependency[["Name", "Weekly Hours", "Team"]], hide_index=True)
        else:
            st.success("Workloads are well-balanced.")

    st.divider()
    c3, c4 = st.columns([2, 1])
    with c3:
        st.write("### 🔥 Total Weekly Workload")
        df["Status"] = df["Weekly Hours"].apply(lambda x: "🚨 High Strain" if x > 48 else "✅ Normal")
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
