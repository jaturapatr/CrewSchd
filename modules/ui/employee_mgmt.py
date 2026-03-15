import streamlit as st
import os
import json
import pandas as pd
from datetime import date
import shutil
import glob
from Translator import translate_rule_to_json

# Standard rules to be applied to every new branch
STANDARD_RULES = [
    {
      "rule_name": "Strategy: Workload Balancing",
      "math_shape": "aggregator",
      "scope": "individual",
      "target_timeframe": "weekly",
      "operator": "<=",
      "value": 12,
      "penalty": 2000
    },
    {
      "rule_name": "Strategy: Fatigue Prevention",
      "math_shape": "rolling_window",
      "window_size": 3,
      "limit": 6,
      "penalty": 10000
    }
]

def show_employee_mgmt(jsons_root, selected_branch, selected_team):
    st.title("⚙️ Enterprise Management")
    base_dir = os.path.dirname(jsons_root)
    
    # 1. COMPANY LEVEL
    st.write("### 🏢 Company Settings")
    biz_ctx_path = os.path.join(jsons_root, 'business_context.json')
    if os.path.exists(biz_ctx_path):
        with open(biz_ctx_path, 'r', encoding='utf-8') as f: biz_ctx_data = json.load(f)
    else:
        biz_ctx_data = {"company_name": "CrewSchd"}

    c_name = st.text_input("Company Name", value=biz_ctx_data.get("company_name", "CrewSchd"))
    if st.button("Update Company Name"):
        biz_ctx_data["company_name"] = c_name
        with open(biz_ctx_path, 'w', encoding='utf-8') as f: json.dump(biz_ctx_data, f, indent=2)
        st.success("Company name updated!")
        st.rerun()

    st.divider()

    # 2. TEAM LEVEL
    st.write(f"### 🏘️ Team Operations (in {selected_branch})")
    branch_path = os.path.join(jsons_root, selected_branch)
    available_teams = sorted([d for d in os.listdir(branch_path) if os.path.isdir(os.path.join(branch_path, d))])

    col3, col4 = st.columns(2)
    with col3:
        new_t = st.text_input("New Team Name", placeholder="e.g. Security")
        if st.button("➕ Create Team", width="stretch"):
            if new_t:
                new_team_dir = os.path.join(branch_path, new_t)
                os.makedirs(new_team_dir, exist_ok=True)
                with open(os.path.join(new_team_dir, 'employee.json'), 'w', encoding='utf-8') as f: json.dump({"employees": {}}, f)
                with open(os.path.join(new_team_dir, 'company_policies.json'), 'w', encoding='utf-8') as f: json.dump({"optimization_targets": {}}, f)
                st.success(f"Team '{new_t}' created!")
                st.rerun()
    with col4:
        team_to_del = st.selectbox("Delete Team", options=["-- Select Team --"] + available_teams)
        if st.button("🗑️ Delete Selected Team", type="secondary", width="stretch"):
            if team_to_del != "-- Select Team --":
                json_team_path = os.path.join(branch_path, team_to_del)
                if os.path.exists(json_team_path): shutil.rmtree(json_team_path)
                roster_team_path = os.path.join(base_dir, 'Rosters', selected_branch, team_to_del)
                if os.path.exists(roster_team_path): shutil.rmtree(roster_team_path)
                st.warning(f"Team '{team_to_del}' deleted!")
                st.rerun()

    st.divider()

    # 3. BRANCH LEVEL TOOLS
    st.write("### 📍 Global Branch Tools")
    available_branches = sorted([d for d in os.listdir(jsons_root) if os.path.isdir(os.path.join(jsons_root, d))])
    
    c1, c2 = st.columns(2)
    with c1:
        new_b = st.text_input("New Branch Name", placeholder="e.g. Phuket")
        if st.button("➕ Create New Branch", width="stretch"):
            if new_b:
                new_branch_dir = os.path.join(jsons_root, new_b)
                os.makedirs(new_branch_dir, exist_ok=True)
                default_context = {
                    "company_name": biz_ctx_data.get("company_name", "CrewSchd"),
                    "location_context": []
                }
                with open(os.path.join(new_branch_dir, 'business_context.json'), 'w', encoding='utf-8') as f:
                    json.dump(default_context, f, indent=2)
                st.success(f"Branch '{new_b}' created!")
                st.rerun()
    with c2:
        branch_to_del = st.selectbox("Delete Branch", options=["-- Select Branch --"] + available_branches)
        if st.button("🗑️ Delete Selected Branch", type="secondary", width="stretch"):
            if branch_to_del != "-- Select Branch --":
                shutil.rmtree(os.path.join(jsons_root, branch_to_del))
                roster_branch_path = os.path.join(base_dir, 'Rosters', branch_to_del)
                if os.path.exists(roster_branch_path): shutil.rmtree(roster_branch_path)
                st.warning(f"Branch '{branch_to_del}' deleted!")
                st.rerun()

    st.divider()

    # 4. EMPLOYEE LEVEL
    st.write(f"### 👤 Staff Directory ({selected_branch} -> {selected_team})")
    jsons_dir = os.path.join(jsons_root, selected_branch, selected_team)
    employee_path = os.path.join(jsons_dir, 'employee.json')
    
    if not os.path.exists(employee_path):
        with open(employee_path, 'w', encoding='utf-8') as f: json.dump({"employees": {}}, f)
    with open(employee_path, 'r', encoding='utf-8') as f: data = json.load(f)
    employees = data.get("employees", {})

    st.caption("Admin: Manage staff quotas and preferences.")
    
    rows = []
    for eid, edata in employees.items():
        rows.append({
            "ID": eid,
            "Name": edata.get("name"),
            "Tier": edata.get("tier", "Junior"),
            "Nights?": edata.get("can_work_nights", True),
            "Vacation Quota": edata.get("vacation_quota", 13),
            "Sick Quota": edata.get("sick_quota", 30),
            "Preference": edata.get("special_preference_text", "")
        })
    
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["ID", "Name", "Tier", "Nights?", "Vacation Quota", "Sick Quota", "Preference"])

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("Emp ID", required=True),
            "Name": st.column_config.TextColumn("Full Name", required=True),
            "Tier": st.column_config.SelectboxColumn("Tier", options=["Junior", "Senior", "Manager"], default="Junior"),
            "Nights?": st.column_config.CheckboxColumn("Nights", default=True),
            "Vacation Quota": st.column_config.NumberColumn("Vacation Quota", min_value=0, default=13),
            "Sick Quota": st.column_config.NumberColumn("Sick Quota", min_value=0, default=30),
            "Preference": st.column_config.TextColumn("Special preference (e.g. 'Max 20h/week')", width="large")
        }
    )

    if st.button("💾 SAVE STAFF & PREFERENCES", type="primary", width="stretch"):
        new_emps = {}
        from security import get_api_key
        
        with st.spinner("Processing AI preferences..."):
            for _, row in edited_df.iterrows():
                if pd.isna(row["ID"]) or not str(row["ID"]).strip(): continue
                eid = str(row["ID"]).strip()
                pref_text = str(row.get("Preference", "")).strip()
                
                old_edata = employees.get(eid, {})
                current_pref_json = old_edata.get("special_preference_json", None)
                if pref_text and pref_text != old_edata.get("special_preference_text"):
                    res = translate_rule_to_json(f"Rule for {eid}: {pref_text}", get_api_key(), "[]")
                    if "error" not in res: current_pref_json = res
                    else: st.error(f"Could not understand preference for {eid}: {res['error']}")
                elif not pref_text: current_pref_json = None

                new_emps[eid] = {
                    "name": str(row["Name"]),
                    "tier": str(row["Tier"]),
                    "can_work_nights": bool(row["Nights?"]),
                    "team": selected_team,
                    "special_preference_text": pref_text,
                    "special_preference_json": current_pref_json,
                    "vacation_quota": int(row.get("Vacation Quota", 13)),
                    "vacation_used": old_edata.get("vacation_used", 0),
                    "sick_quota": int(row.get("Sick Quota", 30)),
                    "sick_used": old_edata.get("sick_used", 0)
                }
            
            data["employees"] = new_emps
            data["last_updated"] = date.today().isoformat()
            with open(employee_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
            st.success("✅ Staff updated!")
            st.rerun()

    # --- 5. QUOTA TRACKING TABLE ---
    st.divider()
    st.write("### 📊 Leave Quota Tracking")
    
    weather_path = os.path.join(jsons_dir, 'weather.json')
    weather_vacation = {} 
    weather_sick = {}
    
    if os.path.exists(weather_path):
        with open(weather_path, 'r', encoding='utf-8') as f:
            weather = json.load(f)
            overrides = weather.get("daily_overrides", [])
            norm_emps = {edata["name"].strip().lower(): eid for eid, edata in employees.items()}
            id_map = {eid.strip().lower(): eid for eid in employees.keys()}
            for rule in overrides:
                emp_ref = rule.get("employee")
                if not emp_ref: continue
                ref_lower = str(emp_ref).strip().lower()
                e_id = id_map.get(ref_lower) or norm_emps.get(ref_lower)
                if e_id:
                    reason = str(rule.get("reason", "")).lower()
                    is_sick = any(word in reason for word in ["sick", "medical", "hospital", "doctor"])
                    if is_sick: weather_sick[e_id] = weather_sick.get(e_id, 0) + 1
                    else: weather_vacation[e_id] = weather_vacation.get(e_id, 0) + 1

    quota_data = []
    for eid, e_data in employees.items():
        v_used = e_data.get("vacation_used", 0) + weather_vacation.get(eid, 0)
        v_rem = e_data.get("vacation_quota", 13) - v_used
        s_used = e_data.get("sick_used", 0) + weather_sick.get(eid, 0)
        s_rem = e_data.get("sick_quota", 30) - s_used
        status = "✅ OK" if (v_rem >= 0 and s_rem >= 0) else "🚨 EXCEEDED"
        quota_data.append({"Staff": e_data["name"], "Vacation Used": v_used, "Vacation Rem.": v_rem, "Sick Used": s_used, "Sick Rem.": s_rem, "Status": status})
    
    if quota_data:
        st.dataframe(pd.DataFrame(quota_data).style.apply(lambda x: ["color: red; font-weight: bold" if v == "🚨 EXCEEDED" else "" for v in x], axis=1), hide_index=True, width="stretch")
