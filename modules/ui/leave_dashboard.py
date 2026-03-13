import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

def show_leave_dashboard(jsons_dir, weather_path, weather, employees):
    st.title("🌴 Leave Dashboard")
    st.subheader("Manage and Track Staff Leave Quotas & Active Requests")
    
    # --- 1. OVERVIEW METRICS ---
    weather_vacation = {} 
    weather_sick = {}     
    overrides = weather.get("daily_overrides", [])
    
    for rule in overrides:
        if rule.get("type") == "block_employee_availability":
            e_name = rule.get("employee")
            reason = str(rule.get("reason", "")).lower()
            is_sick = any(word in reason for word in ["sick", "medical", "hospital", "doctor"])
            for eid, edata in employees["employees"].items():
                if edata["name"] == e_name:
                    if is_sick: weather_sick[eid] = weather_sick.get(eid, 0) + 1
                    else: weather_vacation[eid] = weather_vacation.get(eid, 0) + 1

    total_pending = len(overrides)
    st.sidebar.metric("Pending Overrides", total_pending)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Vacation Days", sum(weather_vacation.values()))
    m2.metric("Active Sick Days", sum(weather_sick.values()))
    m3.metric("Total Workforce", len(employees["employees"]))

    # --- 2. VISUAL CALENDAR OVERVIEW ---
    st.divider()
    st.subheader("🗓️ Visual Coverage Calendar")
    
    if not overrides:
        st.info("No active overrides found.")
    else:
        # Prepare data for calendar heatmap
        cal_data = []
        if overrides:
            for rule in overrides:
                cal_data.append({
                    "Date": rule.get("date"),
                    "Staff": rule.get("employee"),
                    "Type": "Sick" if any(w in str(rule.get("reason")).lower() for w in ["sick", "medical", "doctor"]) else "Vacation",
                    "Reason": rule.get("reason")
                })
        
        df_cal = pd.DataFrame(cal_data)
        
        if not df_cal.empty:
            all_dates = sorted(df_cal["Date"].unique())
            
            # Tabular Leave Grid
            st.write("#### 📅 Leave Grid")
            all_dates_range = []
            if all_dates:
                start_dt = date.fromisoformat(min(all_dates))
                end_dt = date.fromisoformat(max(all_dates))
                curr = start_dt
                while curr <= end_dt:
                    all_dates_range.append(curr.isoformat())
                    curr += timedelta(days=1)
            
            grid_data = []
            for staff in sorted([e["name"] for e in employees["employees"].values()]):
                row = {"Staff": staff}
                has_leave = False
                for d in all_dates_range:
                    match = df_cal[(df_cal["Staff"] == staff) & (df_cal["Date"] == d)]
                    if not match.empty:
                        leave_type = match.iloc[0]["Type"]
                        row[d] = "🤒 Sick" if leave_type == "Sick" else "🌴 Leave"
                        has_leave = True
                    else:
                        row[d] = "✅ Available"
                if has_leave:
                    grid_data.append(row)
            
            if grid_data:
                df_grid = pd.DataFrame(grid_data)
                def color_leave(val):
                    if "Sick" in str(val): return 'background-color: rgba(231, 76, 60, 0.3); color: #e74c3c; font-weight: bold'
                    if "Leave" in str(val): return 'background-color: rgba(52, 152, 219, 0.3); color: #3498db; font-weight: bold'
                    return 'color: #2ecc71; opacity: 0.5'
                
                st.dataframe(df_grid.style.applymap(color_leave, subset=[c for c in df_grid.columns if c != "Staff"]), 
                             hide_index=True, width="stretch")
            else:
                st.info("No absences in the current view range.")

    # --- 3. QUOTA TRACKING TABLE ---
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
