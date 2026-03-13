import streamlit as st
import os
import json
import pandas as pd
from datetime import date
import shutil
import glob

def show_employee_mgmt(jsons_root, selected_branch, selected_team):
    st.title("⚙️ Enterprise Management")
    base_dir = os.path.dirname(jsons_root)
    
    # 1. COMPANY LEVEL
    st.write("### 🏢 Company Settings")
    biz_ctx_path = os.path.join(jsons_root, 'business_context.json')
    if os.path.exists(biz_ctx_path):
        with open(biz_ctx_path, 'r') as f: biz_ctx_data = json.load(f)
    else:
        biz_ctx_data = {"company_name": "CrewSchd"}

    c_name = st.text_input("Company Name", value=biz_ctx_data.get("company_name", "CrewSchd"))
    if st.button("Update Company Name"):
        biz_ctx_data["company_name"] = c_name
        with open(biz_ctx_path, 'w') as f: json.dump(biz_ctx_data, f, indent=2)
        st.success("Company name updated!")
        st.rerun()

    st.divider()

    # 2. BRANCH LEVEL
    st.write(f"### 📍 Branch Operations: {selected_branch}")
    
    # Branch-specific Business Context
    branch_ctx_path = os.path.join(jsons_root, selected_branch, 'business_context.json')
    if os.path.exists(branch_ctx_path):
        with open(branch_ctx_path, 'r') as f: branch_ctx = json.load(f)
    else:
        branch_ctx = {"strict_day_coverage": {}}

    with st.expander("⚖️ Edit Branch Coverage Rules"):
        st.caption("Define minimum headcount per team for this branch.")
        # Simple JSON editor for coverage
        new_coverage_json = st.text_area("Coverage Config (JSON)", value=json.dumps(branch_ctx.get("strict_day_coverage", {}), indent=2))
        if st.button("Save Branch Rules"):
            try:
                branch_ctx["strict_day_coverage"] = json.loads(new_coverage_json)
                with open(branch_ctx_path, 'w') as f: json.dump(branch_ctx, f, indent=2)
                st.success(f"Rules for {selected_branch} updated!")
                st.rerun()
            except Exception as e:
                st.error(f"Invalid JSON: {e}")

    st.write("#### 🛠️ Global Branch Tools")
    available_branches = sorted([d for d in os.listdir(jsons_root) if os.path.isdir(os.path.join(jsons_root, d))])
    
    col1, col2 = st.columns(2)
    with col1:
        new_b = st.text_input("New Branch Name", placeholder="e.g. Phuket")
        if st.button("➕ Create Branch", width="stretch"):
            if new_b:
                branch_dir = os.path.join(jsons_root, new_b)
                os.makedirs(branch_dir, exist_ok=True)
                # Initialize with default context
                with open(os.path.join(branch_dir, 'business_context.json'), 'w') as f:
                    json.dump({"strict_day_coverage": {}}, f)
                st.success(f"Branch '{new_b}' created!")
                st.rerun()
    with col2:
        branch_to_del = st.selectbox("Delete Branch", options=["-- Select Branch --"] + available_branches)
        if st.button("🗑️ Delete Selected Branch", type="secondary", width="stretch"):
            if branch_to_del != "-- Select Branch --":
                json_branch_path = os.path.join(jsons_root, branch_to_del)
                if os.path.exists(json_branch_path): shutil.rmtree(json_branch_path)
                roster_branch_path = os.path.join(base_dir, 'Rosters', branch_to_del)
                if os.path.exists(roster_branch_path): shutil.rmtree(roster_branch_path)
                html_pattern = os.path.join(base_dir, f'Perfect_Roster_View_{branch_to_del.replace(" ", "_")}_*.html')
                for f in glob.glob(html_pattern):
                    try: os.remove(f)
                    except: pass
                st.warning(f"Branch '{branch_to_del}' and all associated files deleted!")
                st.rerun()

    st.divider()

    # 3. TEAM LEVEL
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
                with open(os.path.join(new_team_dir, 'employee.json'), 'w') as f: json.dump({"employees": {}}, f)
                with open(os.path.join(new_team_dir, 'company_policies.json'), 'w') as f: json.dump({"optimization_targets": {}}, f)
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
                html_report = os.path.join(base_dir, f'Perfect_Roster_View_{selected_branch.replace(" ", "_")}_{team_to_del.replace(" ", "_")}.html')
                if os.path.exists(html_report):
                    try: os.remove(html_report)
                    except: pass
                st.warning(f"Team '{team_to_del}' and all associated files deleted!")
                st.rerun()

    st.divider()

    # 4. EMPLOYEE LEVEL
    st.write(f"### 👤 Staff Directory ({selected_branch} -> {selected_team})")
    jsons_dir = os.path.join(jsons_root, selected_branch, selected_team)
    employee_path = os.path.join(jsons_dir, 'employee.json')
    
    if not os.path.exists(employee_path):
        with open(employee_path, 'w') as f: json.dump({"employees": {}}, f)
    with open(employee_path, 'r') as f: data = json.load(f)
    employees = data.get("employees", {})

    st.caption("Double-click a cell to edit. Click the empty row at the bottom to add. Select a row and press Delete to remove.")
    
    if employees:
        df = pd.DataFrame.from_dict(employees, orient='index')
        df.index.name = "ID"
        df = df.reset_index()
    else:
        df = pd.DataFrame(columns=["ID", "name", "tier", "can_work_nights"])

    edited_df = st.data_editor(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("Emp ID", required=True),
            "name": st.column_config.TextColumn("Full Name", required=True),
            "tier": st.column_config.SelectboxColumn("Tier", options=["Junior", "Senior", "Manager"], required=True, default="Junior"),
            "can_work_nights": st.column_config.CheckboxColumn("Works Nights?", default=True),
            "team": None, "vacation_quota": None, "vacation_used": None, "sick_quota": None, "sick_used": None
        }
    )

    if st.button("💾 SAVE STAFF CHANGES", type="primary", width="stretch"):
        new_emps = {}
        for _, row in edited_df.iterrows():
            if pd.isna(row["ID"]) or not str(row["ID"]).strip(): continue
            eid = str(row["ID"]).strip()
            old_data = employees.get(eid, {})
            new_emps[eid] = {
                "name": str(row.get("name", "")),
                "tier": str(row.get("tier", "Junior")),
                "can_work_nights": bool(row.get("can_work_nights", True)),
                "team": selected_team,
                "vacation_quota": old_data.get("vacation_quota", 13),
                "vacation_used": old_data.get("vacation_used", 0),
                "sick_quota": old_data.get("sick_quota", 30),
                "sick_used": old_data.get("sick_used", 0)
            }
        data["employees"] = new_emps
        data["last_updated"] = date.today().isoformat()
        with open(employee_path, 'w') as f: json.dump(data, f, indent=2)
        st.success("✅ Team roster updated successfully!")
        st.rerun()
