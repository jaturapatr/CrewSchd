import streamlit as st
import os
import json
import pandas as pd
import plotly.express as px
import glob
from datetime import date
from roster_engine import generate_roster, run_auto_healer, validate_roster
from Exporter import export_perfect_roster
from Translator import translate_weather_to_json

def get_human_description(rule):
    shape = rule.get("math_shape")
    val = rule.get("value")
    if shape == "aggregator":
        timeframe = rule.get("target_timeframe", "daily")
        scope = rule.get("scope", "individual")
        if scope == "individual":
            if timeframe == "weekly": return f"Max {val} blocks ({(val or 0)*4}h)/week."
            if timeframe == "working_days": return f"Max {val} work days/week."
            return f"Max {val} blocks/day."
        else: # collective
            team = rule.get("target_team", "the team")
            return f"Operational Floor: {team} must have at least {val} staff per 4h block."
    elif shape == "rolling_window":
        return f"Pattern Guard: Max {rule.get('limit')} blocks in {rule.get('window_size')} days."
    elif shape == "implication":
        return f"Rest Mandate: If working {rule.get('if_condition', {}).get('block')}, early start tomorrow forbidden."
    return "Custom logic."

def show_control_tower(target_date, rosters_dir, jsons_dir, emps_ctx, branch_ctx_json, api_key, base_dir, branch="Main Office", team="Cashier", jsons_root=None):
    st.title(f"🚜 Control Tower: {branch} -> {team}")

    # --- 1. QUICK HEADCOUNT ADJUSTMENT (Admin Only) ---
    if st.session_state.get("user") == "admin":
        branch_ctx_path = os.path.join(jsons_root, branch, 'business_context.json')
        with open(branch_ctx_path, 'r', encoding='utf-8') as f: b_ctx = json.load(f)
        loc_context = b_ctx.get("location_context", [])
        
        rule_idx = -1
        current_val = 1
        for i, r in enumerate(loc_context):
            if r.get("rule_name", "").startswith(f"Min Staff per Block: {team}"):
                rule_idx = i
                current_val = r.get("value", 1)
                break
        
        new_val = st.slider(f"⚖️ Min Staff / Block ({team})", 1, 10, value=int(current_val), key=f"ct_hc_{team}")
        if new_val != current_val:
            if rule_idx >= 0: loc_context[rule_idx]["value"] = new_val
            else:
                loc_context.append({
                    "rule_name": f"Min Staff per Block: {team}", "math_shape": "aggregator",
                    "scope": "collective", "target_team": team, "target_timeframe": "daily",
                    "operator": ">=", "value": new_val, "priority_label": "Headcount"
                })
            b_ctx["location_context"] = loc_context
            with open(branch_ctx_path, 'w', encoding='utf-8') as f: json.dump(b_ctx, f, indent=2)
            st.rerun()

    # --- 2. AI ASSISTANT ---
    weather_path = os.path.join(jsons_dir, 'weather.json')
    if os.path.exists(weather_path):
        with open(weather_path, 'r', encoding='utf-8') as f: weather = json.load(f)
    else:
        weather = {"daily_overrides": []}

    with st.container():
        with st.popover("🤖", help="Open AI Roster Assistant"):
            st.subheader("🤖 Roster Assistant")
            files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
            current_roster = "{}"
            if files:
                with open(files[-1], 'r', encoding='utf-8') as f: current_roster = f.read()
            if "chat_history" not in st.session_state: st.session_state.chat_history = []
            for msg in st.session_state.chat_history:
                with st.chat_message(msg["role"]): st.write(msg["content"])
            user_prompt = st.chat_input("e.g., Fai is sick tomorrow...")
            if user_prompt:
                st.session_state.chat_history.append({"role": "user", "content": user_prompt})
                ai_context_json = json.dumps({"current_roster": current_roster, "employees": emps_ctx, "branch": branch, "team": team})
                with st.spinner("Hub is thinking..."):
                    res_data = translate_weather_to_json(user_prompt, api_key, ai_context_json)
                    if "overrides" in res_data:
                        weather["daily_overrides"].extend(res_data["overrides"])
                        with open(weather_path, 'w', encoding='utf-8') as f: json.dump(weather, f, indent=2)
                        st.session_state.chat_history.append({"role": "assistant", "content": f"✅ Added {len(res_data['overrides'])} rules."})
                        st.rerun()
                    else:
                        st.session_state.chat_history.append({"role": "assistant", "content": str(res_data)})
                        st.rerun()

    # --- 3. RUN ENGINE ---
    if st.button("🚀 RUN MATH ENGINE", width="stretch", type="primary"):
        with st.spinner(f"🔢 Solving Matrix for {branch}/{team}..."):
            try:
                status = generate_roster(target_date, branch=branch, team=team)
                if status == "INFEASIBLE": st.error("❌ **MATHEMATICAL PARADOX DETECTED**")
                else:
                    export_perfect_roster(branch=branch, team=team)
                    st.success(f"✅ Roster Generated!")
                    st.balloons()
                    st.rerun()
            except Exception as e:
                st.error(f"❌ CRITICAL ERROR: {str(e)}")

    st.divider()
    
    # --- 4. ROSTER GRID ---
    st.subheader("🗓️ Visual Master Schedule")
    files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
    if len(files) >= 1:
        with open(files[-1], 'r', encoding='utf-8') as f: roster = json.load(f)
        prev_roster = None
        if len(files) > 1:
            with open(files[-2], 'r', encoding='utf-8') as f: prev_roster = json.load(f)
        with open(os.path.join(jsons_dir, 'employee.json'), 'r', encoding='utf-8') as f: emps = json.load(f)
        
        overrides = roster.get("metadata", {}).get("weather_snapshot", [])
        leave_lookup = {}
        for r in overrides:
            if r.get("type") == "block_employee_availability":
                leave_lookup[(str(r.get("employee")).strip().lower(), r.get("date"))] = r.get("reason", "Leave")

        BLOCK_MAP = {"00:00": "🌑 00-04", "04:00": "🌅 04-08", "08:00": "☀️ 08-12", "12:00": "🌤️ 12-16", "16:00": "🌇 16-20", "20:00": "🌌 20-00"}
        data = []
        all_dates = sorted(roster["assignments"].keys())
        
        for eid, details in emps["employees"].items():
            row = {"Staff": details['name'], "Team": details["team"], "_eid": eid}
            ename_lower, eid_lower = details['name'].strip().lower(), eid.strip().lower()
            for d in all_dates:
                new_b = roster["assignments"][d].get(eid, [])
                old_b = prev_roster["assignments"].get(d, {}).get(eid, []) if prev_roster else new_b
                if not new_b:
                    reason = leave_lookup.get((eid_lower, d)) or leave_lookup.get((ename_lower, d))
                    display_val = "🤒 SICK" if reason and "sick" in str(reason).lower() else "🌴 LEAVE" if reason else "💤 DAY-OFF"
                else:
                    display_val = " + ".join([BLOCK_MAP.get(b, b) for b in sorted(new_b)])
                if set(new_b) != set(old_b): display_val = f"🔄 {display_val}"
                row[d] = display_val
            data.append(row)
        
        df_full = pd.DataFrame(data)
        display_columns = ["Staff"] + all_dates
        
        def style_cells(val):
            if "SICK" in str(val) or "LEAVE" in str(val): return "color: #e74c3c; font-weight: bold; font-style: italic"
            if "DAY-OFF" in str(val): return "color: #e67e22; font-weight: bold; font-style: italic"
            return "color: #3498db"

        team_names = sorted(list(set(row["Team"] for row in data)))
        team_tabs = st.tabs(team_names)
        
        clicked_eid = None
        clicked_date = None

        for i, team_name in enumerate(team_names):
            with team_tabs[i]:
                team_df = df_full[df_full["Team"] == team_name].reset_index(drop=True)
                event = st.dataframe(
                    team_df[display_columns].style.map(style_cells), 
                    column_config={d: st.column_config.TextColumn(date.fromisoformat(d).strftime('%a [%d/%m/%y]')) for d in all_dates}, 
                    hide_index=True, width="stretch", on_select="rerun",
                    selection_mode=["single-row", "single-column"],
                    key=f"grid_{team_name}"
                )
                
                if event and "selection" in event:
                    rows = event["selection"].get("rows", [])
                    cols = event["selection"].get("columns", [])
                    if rows and cols:
                        clicked_eid = team_df.iloc[rows[0]]["_eid"]
                        col_name = cols[0]
                        if col_name in all_dates: clicked_date = col_name
                
                report_path = os.path.join(base_dir, f'Perfect_Roster_View_{branch.replace(" ", "_")}_{team_name.replace(" ", "_")}.html')
                if os.path.exists(report_path):
                    with open(report_path, 'r', encoding='utf-8') as f:
                        st.download_button(f"📥 Download {team_name} Report", f.read(), f"roster_{team_name}.html", "text/html", key=f"dl_{team_name}", width="stretch")

        # --- 4.5 AI ROSTER INSPECTOR ---
        if clicked_eid and clicked_date:
            st.divider()
            with st.container(border=True):
                c_insp1, c_insp2 = st.columns([1, 2])
                with c_insp1:
                    st.write(f"### 🔍 AI Inspector")
                    st.markdown(f"**Target:** {emps['employees'][clicked_eid]['name']}<br/>**Date:** {clicked_date}", unsafe_allow_html=True)
                    current_blocks = roster["assignments"].get(clicked_date, {}).get(clicked_eid, [])
                    if not current_blocks: st.info("Staff is not working on this date.")
                    else: st.success(f"Assigned Blocks: {', '.join(current_blocks)}")
                
                with c_insp2:
                    st.write("#### 🛡️ Rejection Audit Trail")
                    if st.button("Run Counter-Factual Analysis", type="primary"):
                        with st.spinner("Engine is evaluating organizational constraints..."):
                            audit_results = []
                            for other_eid, other_edata in emps["employees"].items():
                                if other_eid == clicked_eid: continue
                                sim_roster = json.loads(json.dumps(roster))
                                sim_roster["assignments"][clicked_date].pop(clicked_eid, None)
                                if other_eid not in sim_roster["assignments"][clicked_date]: sim_roster["assignments"][clicked_date][other_eid] = []
                                sim_roster["assignments"][clicked_date][other_eid].extend(current_blocks)
                                is_legal, violations = validate_roster(branch, team, sim_roster)
                                audit_results.append({"name": other_edata["name"], "legal": is_legal, "reasons": violations})
                            st.session_state["insp_results"] = audit_results
                            st.rerun()
                    
                    if "insp_results" in st.session_state:
                        for res in st.session_state["insp_results"]:
                            if not res["legal"]: st.error(f"❌ **{res['name']}**: Rejected ({', '.join(res['reasons'])})")
                            else: st.success(f"✅ **{res['name']}**: Legally Available (Higher penalty score)")

        # --- 4.6 DISRUPTION MANAGEMENT: AUTO-HEALER ---
        st.divider()
        st.write("### 🚑 Disruption Management (Auto-Healer)")
        st.caption("Click any shift in the grid above to instantly find a legal replacement.")
        
        # Pre-populate Auto-Healer from click
        default_date_idx = all_dates.index(clicked_date) if (clicked_date and clicked_date in all_dates) else 0
        ah_date = st.selectbox("Call-out Date", options=all_dates, index=default_date_idx, key=f"ah_date_sel_{team}")
        
        working_staff_ids = [eid for eid, blks in roster["assignments"].get(ah_date, {}).items() if blks and eid in emps["employees"]]
        working_names = [emps["employees"][eid]["name"] for eid in working_staff_ids]
        
        if not working_names: 
            st.info("No staff assigned on this date.")
        else:
            # Safely calculate default staff index
            default_staff_idx = 0
            if clicked_eid and clicked_eid in working_staff_ids:
                default_staff_idx = working_names.index(emps["employees"][clicked_eid]["name"])
            
            ah_staff_name = st.selectbox("Staff Member", options=working_names, index=default_staff_idx, key=f"ah_staff_sel_{team}")
            ah_eid = next(eid for eid, ed in emps["employees"].items() if ed["name"] == ah_staff_name)
            
            if st.button("🔍 Find Replacements", type="primary", key=f"ah_btn_{team}"):
                # Clear previous state before new search
                if "ah_candidates" in st.session_state: del st.session_state["ah_candidates"]
                
                candidates = run_auto_healer(ah_date, ah_eid, branch, team, roster)
                if not candidates: 
                    st.error("❌ No legal replacements found. Organizational constraints (Laws/Rest) block all other staff.")
                else:
                    st.session_state["ah_candidates"] = candidates
                    st.session_state["ah_context"] = {"date": ah_date, "sick_eid": ah_eid, "sick_name": ah_staff_name}
                    st.rerun()
                
        if "ah_candidates" in st.session_state:
            for idx, cand in enumerate(st.session_state["ah_candidates"][:3]):
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**Option {idx+1}: {cand['name']}**")
                        st.caption(f"Impact Score: {int(cand['score']):,} pts")
                    with col2:
                        if st.button("Apply & Heal", key=f"ah_{idx}"):
                            wp = os.path.join(jsons_dir, 'weather.json')
                            with open(wp, 'r', encoding='utf-8') as f: w_data = json.load(f)
                            w_data.setdefault("daily_overrides", []).append({"type": "block_employee_availability", "employee": st.session_state["ah_context"]["sick_eid"], "date": st.session_state["ah_context"]["date"], "reason": "Emergency Auto-Heal"})
                            with open(wp, 'w', encoding='utf-8') as f: json.dump(w_data, f, indent=2)
                            new_r = json.loads(json.dumps(roster))
                            t_d, t_s = st.session_state["ah_context"]["date"], st.session_state["ah_context"]["sick_eid"]
                            blks = new_r["assignments"][t_d].pop(t_s, [])
                            new_r["assignments"][t_d].setdefault(cand["eid"], []).extend(blks)
                            new_r["assignments"][t_d][cand["eid"]] = sorted(list(set(new_r["assignments"][t_d][cand["eid"]])))
                            import time
                            ts = int(time.time())
                            new_r["metadata"]["timestamp"] = ts
                            save_p = os.path.join(rosters_dir, f'roster_{new_r["metadata"]["start_date"]}_{ts}.json')
                            with open(save_p, 'w', encoding='utf-8') as f: json.dump(new_r, f, indent=2)
                            del st.session_state["ah_candidates"]
                            st.rerun()

    else:
        st.warning("No roster found.")
        with open(os.path.join(jsons_dir, 'employee.json'), 'r', encoding='utf-8') as f: emps = json.load(f)

    # --- 5. LEAVE DASHBOARD ---
    st.divider()
    st.subheader("🌴 Leave Management & Tracking")
    weather_vacation, weather_sick = {}, {}
    overrides = weather.get("daily_overrides", [])
    norm_emps = {edata["name"].strip().lower(): eid for eid, edata in emps["employees"].items()}
    id_map = {eid.strip().lower(): eid for eid in emps["employees"].keys()}
    for rule in overrides:
        emp_ref = rule.get("employee")
        if not emp_ref: continue
        ref_lower = str(emp_ref).strip().lower()
        e_id = id_map.get(ref_lower) or norm_emps.get(ref_lower)
        if e_id:
            reason = str(rule.get("reason", "")).lower()
            if any(word in reason for word in ["sick", "medical", "hospital", "doctor"]): weather_sick[e_id] = weather_sick.get(e_id, 0) + 1
            else: weather_vacation[e_id] = weather_vacation.get(e_id, 0) + 1
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pending Overrides", len(overrides))
    m2.metric("Active Vacation", sum(weather_vacation.values()))
    m3.metric("Active Sick", sum(weather_sick.values()))
    m4.metric("Team Size", len(emps["employees"]))
    if overrides:
        cal_lookup = {}
        for rule in overrides:
            emp_ref, d_str = rule.get("employee"), rule.get("date")
            if not emp_ref or not d_str: continue
            e_id = id_map.get(str(emp_ref).strip().lower()) or norm_emps.get(str(emp_ref).strip().lower())
            if e_id: cal_lookup[(e_id, d_str)] = "🤒 Sick" if any(w in str(rule.get("reason")).lower() for w in ["sick", "medical", "doctor"]) else "🌴 Leave"
        all_dates_range, start_dt = [], date.today()
        for i in range(15): all_dates_range.append((start_dt + date.timedelta(days=i)).isoformat())
        grid_data = []
        for eid, edata in emps["employees"].items():
            row, has_entry = {"Staff": edata["name"], "_eid": eid}, False
            for d in all_dates_range:
                val = cal_lookup.get((eid, d), "✅ Available")
                row[d] = val
                if val != "✅ Available": has_entry = True
            if has_entry: grid_data.append(row)
        if grid_data:
            df_grid = pd.DataFrame(grid_data)
            if st.session_state.get("user") == "admin":
                edited_grid = st.data_editor(df_grid, width="stretch", hide_index=True, column_config={"_eid": None, "Staff": st.column_config.TextColumn("Staff", disabled=True), **{d: st.column_config.SelectboxColumn(date.fromisoformat(d).strftime('%a [%d/%m]'), options=["✅ Available", "🤒 Sick", "🌴 Leave"]) for d in all_dates_range}}, key="leave_grid_editor")
                if st.button("💾 SAVE GRID CHANGES", type="primary", width="stretch"):
                    rem_overrides = [r for r in overrides if r.get("date") not in set(all_dates_range)]
                    deletions = []
                    for _, row in edited_grid.iterrows():
                        eid = row["_eid"]
                        for d in all_dates_range:
                            val = row[d]
                            if val != "✅ Available": rem_overrides.append({"type": "block_employee_availability", "employee": eid, "date": d, "reason": "Sick" if val == "🤒 Sick" else "Vacation"})
                            else:
                                was_l = next((r for r in overrides if r.get("date") == d and (r.get("employee") == eid or r.get("employee") == emps["employees"][eid]["name"])), None)
                                if was_l: deletions.append(was_l)
                    with open(weather_path, 'w', encoding='utf-8') as f: json.dump({"daily_overrides": rem_overrides}, f, indent=2)
                    if deletions:
                        lp = os.path.join(jsons_root, 'leave_del_log.json')
                        try:
                            with open(lp, 'r', encoding='utf-8') as f: logs = json.load(f)
                        except: logs = []
                        for d_entry in deletions: logs.append({"deleted_at": date.datetime.now().isoformat(), "admin": st.session_state.get("user"), "leave_detail": d_entry})
                        with open(lp, 'w', encoding='utf-8') as f: json.dump(logs, f, indent=2)
                    st.rerun()
            else:
                def color_leave(val):
                    if "Sick" in str(val): return 'background-color: rgba(231, 76, 60, 0.3); color: #e74c3c; font-weight: bold'
                    if "Leave" in str(val): return 'background-color: rgba(52, 152, 219, 0.3); color: #3498db; font-weight: bold'
                    return 'color: #2ecc71; opacity: 0.5'
                col_m = {d: date.fromisoformat(d).strftime('%a [%d/%m]') for d in all_dates_range}
                df_disp = df_grid.drop(columns=["_eid"]).rename(columns=col_m)
                st.dataframe(df_disp.style.map(color_leave, subset=[c for c in df_disp.columns if c != "Staff"]), hide_index=True, width="stretch")
        else: st.info("No absences in the current view range.")
