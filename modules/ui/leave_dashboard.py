import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px
from datetime import date, timedelta, datetime

def show_leave_dashboard(jsons_dir, weather_path, weather, employees):
    st.title("🌴 Leave Dashboard")
    st.subheader("Manage and Track Staff Leave Quotas & Active Requests")
    
    # --- 1. OVERVIEW METRICS ---
    weather_vacation = {} 
    weather_sick = {}     
    overrides = weather.get("daily_overrides", [])
    
    # Normalize employee database for matching
    # Map { lowercase_name: original_eid }
    # Map { lowercase_eid: original_eid }
    norm_emps = {edata["name"].strip().lower(): eid for eid, edata in employees["employees"].items()}
    id_map = {eid.strip().lower(): eid for eid in employees["employees"].keys()}

    for rule in overrides:
        emp_ref = rule.get("employee")
        if not emp_ref: continue
        
        ref_lower = str(emp_ref).strip().lower()
        # Resolve ID: Try direct ID match first, then Name match
        e_id = id_map.get(ref_lower) or norm_emps.get(ref_lower)
            
        if e_id:
            reason = str(rule.get("reason", "")).lower()
            is_sick = any(word in reason for word in ["sick", "medical", "hospital", "doctor"])
            
            if is_sick: weather_sick[e_id] = weather_sick.get(e_id, 0) + 1
            else: weather_vacation[e_id] = weather_vacation.get(e_id, 0) + 1

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
        # Prepare lookup data for the grid
        # We need to map every override to an EID so the grid can find it
        cal_lookup = {} # { (eid, date): type }
        for rule in overrides:
            emp_ref = rule.get("employee")
            d_str = rule.get("date")
            if not emp_ref or not d_str: continue
            
            ref_lower = str(emp_ref).strip().lower()
            e_id = id_map.get(ref_lower) or norm_emps.get(ref_lower)
            
            if e_id:
                is_sick = any(w in str(rule.get("reason")).lower() for w in ["sick", "medical", "doctor"])
                cal_lookup[(e_id, d_str)] = "🤒 Sick" if is_sick else "🌴 Leave"
        
        # Tabular Leave Grid
        st.write("#### 📅 Leave Grid")
        all_dates_range = []
        start_dt = date.today()
        end_dt = start_dt + timedelta(days=14)
        
        curr = start_dt
        while curr <= end_dt:
            all_dates_range.append(curr.isoformat())
            curr += timedelta(days=1)
        
        grid_data = []
        # Build grid based on actual EIDs from database
        for eid, edata in employees["employees"].items():
            row = {"Staff": edata["name"], "_eid": eid} # Hidden eid for save logic
            has_entry = False
            for d in all_dates_range:
                val = cal_lookup.get((eid, d), "✅ Available")
                row[d] = val
                if val != "✅ Available": has_entry = True
            
            if has_entry:
                grid_data.append(row)
        
        if grid_data:
            df_grid = pd.DataFrame(grid_data)
            
            is_admin = st.session_state.get("user") == "admin"
            
            if is_admin:
                st.caption("Admin: Change a cell to '✅ Available' to delete that leave entry.")
                edited_grid = st.data_editor(
                    df_grid,
                    width="stretch",
                    hide_index=True,
                    column_config={
                        "_eid": None, # Hide internal ID
                        "Staff": st.column_config.TextColumn("Staff", disabled=True),
                        **{d: st.column_config.SelectboxColumn(
                            date.fromisoformat(d).strftime('%a [%d/%m/%y]'),
                            options=["✅ Available", "🤒 Sick", "🌴 Leave"]
                        ) for d in all_dates_range}
                    },
                    key="leave_grid_editor"
                )
                
                if st.button("💾 SAVE GRID CHANGES", type="primary", width="stretch"):
                    deletions = []
                    # Logic: We keep overrides that are still in the edited_grid OR weren't in the 14-day window
                    # Start with old overrides
                    remaining_overrides = []
                    
                    # 1. Keep overrides outside the current 14-day window
                    window_dates = set(all_dates_range)
                    for rule in overrides:
                        if rule.get("date") not in window_dates:
                            remaining_overrides.append(rule)
                    
                    # 2. Add back overrides that were kept/changed in the grid
                    for _, row in edited_grid.iterrows():
                        eid = row["_eid"]
                        for d in all_dates_range:
                            val = row[d]
                            if val != "✅ Available":
                                # Find if it existed to preserve details, or create new
                                existing = next((r for r in overrides if r.get("date") == d and (r.get("employee") == eid or r.get("employee") == employees["employees"][eid]["name"])), None)
                                
                                if existing:
                                    # Update type if changed
                                    existing["reason"] = "Sick" if val == "🤒 Sick" else "Vacation"
                                    remaining_overrides.append(existing)
                                else:
                                    # This case shouldn't happen with current UI but for safety:
                                    remaining_overrides.append({
                                        "type": "block_employee_availability",
                                        "employee": eid,
                                        "date": d,
                                        "reason": "Manual Entry"
                                    })
                            else:
                                # Check if it WAS a leave, then log as deletion
                                was_leave = next((r for r in overrides if r.get("date") == d and (r.get("employee") == eid or r.get("employee") == employees["employees"][eid]["name"])), None)
                                if was_leave:
                                    deletions.append(was_leave)

                    # Update files
                    with open(weather_path, 'w') as f:
                        json.dump({"daily_overrides": remaining_overrides}, f, indent=2)
                    
                    if deletions:
                        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        log_path = os.path.join(base_dir, 'jsons', 'leave_del_log.json')
                        logs = []
                        if os.path.exists(log_path):
                            with open(log_path, 'r') as f:
                                try: logs = json.load(f)
                                except: logs = []
                        for d_entry in deletions:
                            logs.append({
                                "deleted_at": datetime.now().isoformat(),
                                "admin": st.session_state.get("user"),
                                "leave_detail": d_entry
                            })
                        os.makedirs(os.path.dirname(log_path), exist_ok=True)
                        with open(log_path, 'w') as f: json.dump(logs, f, indent=2)
                        
                    st.success("✅ Changes saved!")
                    st.rerun()
            else:
                # Read-only for managers
                def color_leave(val):
                    if "Sick" in str(val): return 'background-color: rgba(231, 76, 60, 0.3); color: #e74c3c; font-weight: bold'
                    if "Leave" in str(val): return 'background-color: rgba(52, 152, 219, 0.3); color: #3498db; font-weight: bold'
                    return 'color: #2ecc71; opacity: 0.5'
                
                col_map = {d: date.fromisoformat(d).strftime('%a [%d/%m/%y]') for d in all_dates_range}
                df_display = df_grid.drop(columns=["_eid"]).rename(columns=col_map)
                
                st.dataframe(df_display.style.map(color_leave, subset=[c for c in df_display.columns if c != "Staff"]), 
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
