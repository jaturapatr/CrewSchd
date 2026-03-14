import streamlit as st
import os
import json
import pandas as pd
from Translator import translate_rule_to_json

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
        if_cond = rule.get("if_condition", {}).get("block", "Late")
        return f"Rest Mandate: If working {if_cond}, early start tomorrow forbidden."
    return "Custom logic."

def show_context_mgmt(jsons_root, selected_branch, api_key):
    st.title("📐 Universal Context Architect")
    st.subheader(f"Tiered Intelligence: {selected_branch}")

    # --- 1. DATA LOADING ---
    branch_ctx_path = os.path.join(jsons_root, selected_branch, 'business_context.json')
    with open(branch_ctx_path, 'r', encoding='utf-8') as f: branch_ctx = json.load(f)
    if "location_context" not in branch_ctx: branch_ctx["location_context"] = []
    if "active_strategies" not in branch_ctx: branch_ctx["active_strategies"] = {} 

    univ_path = os.path.join(jsons_root, 'universal_rules.json')
    with open(univ_path, 'r', encoding='utf-8') as f: univ_data = json.load(f)

    # --- TIERED TABS ---
    t1, t2, t3 = st.tabs(["🏛️ Company Mandates (Global)", "📍 Branch Strategies (Local)", "🖼️ Strategy Gallery"])

    # TAB 1: GLOBAL MANDATES (Laws, Corp Compliance)
    with t1:
        st.write("### 🏛️ Corporate HQ Rules")
        st.caption("These rules apply to every branch and are maintained by the CEO.")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🧱 Laws (Hard)")
            for r in univ_data.get("laws", []):
                with st.container(border=True):
                    st.write(f"**{r.get('rule_name')}**")
                    st.caption(get_human_description(r))
        with c2:
            st.markdown("#### 🛡️ Corp Compliance")
            for r in univ_data.get("corp_compliance", []):
                with st.container(border=True):
                    st.write(f"**{r.get('rule_name')}**")
                    st.caption(get_human_description(r))
                    penalty = r.get("penalty")
                    if penalty: st.caption(f"Priority: Soft (Weight: {penalty:,})")
                    else: st.error("Priority: CRITICAL")

    # TAB 2: BRANCH STRATEGIES (Location Context)
    with t2:
        st.write("### 📍 Branch-Specific Rules")
        st.caption(f"Custom rules and Headcount limits for {selected_branch}.")
        
        # AI Rule Designer
        with st.container(border=True):
            st.write("#### 🤖 AI Rule Designer")
            rule_prompt = st.chat_input("Describe a custom rule for this branch...", key="chat_arch")
            if rule_prompt:
                with st.spinner("Architecting..."):
                    new_rule = translate_rule_to_json(rule_prompt, api_key, json.dumps(branch_ctx["location_context"]))
                    if "error" not in new_rule:
                        branch_ctx["location_context"].append(new_rule)
                        with open(branch_ctx_path, 'w', encoding='utf-8') as f: json.dump(branch_ctx, f, indent=2)
                        st.rerun()

        st.divider()
        if not branch_ctx["location_context"]:
            st.info("No custom rules or headcount set for this branch.")
        else:
            for i, rule in enumerate(branch_ctx["location_context"]):
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"**{rule.get('rule_name')}**")
                        st.write(f"👉 {get_human_description(rule)}")
                        
                        # Use priority_label if present, else determine by penalty
                        p_label = rule.get("priority_label")
                        if p_label:
                            st.error(f"Priority: {p_label}")
                        elif rule.get("penalty"): 
                            st.caption(f"Priority: Soft (Weight: {rule.get('penalty'):,})")
                        else: 
                            st.error("Priority: CRITICAL")
                            
                        with st.expander("🛠️ View Blueprint"): st.json(rule)
                    with col2:
                        if st.button("🗑️", key=f"del_loc_rule_{i}"):
                            branch_ctx["location_context"].pop(i)
                            with open(branch_ctx_path, 'w', encoding='utf-8') as f: json.dump(branch_ctx, f, indent=2)
                            st.rerun()

    # TAB 3: STRATEGY GALLERY
    with t3:
        st.write("### 🖼️ Operational Templates")
        templates_path = os.path.join(jsons_root, 'rule_templates.json')
        if os.path.exists(templates_path):
            with open(templates_path, 'r', encoding='utf-8') as f: templates_data = json.load(f).get("templates", [])
            branch_path = os.path.join(jsons_root, selected_branch)
            available_teams = sorted([d for d in os.listdir(branch_path) if os.path.isdir(os.path.join(branch_path, d))])
            
            for temp in templates_data:
                tid = temp["id"]
                with st.container(border=True):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.write(f"**{temp['template_name']}**")
                        st.caption(temp['description'])
                    with c2:
                        target_team = st.selectbox(f"Team", options=available_teams, key=f"tsel_{tid}")
                        team_strategies = branch_ctx["active_strategies"].get(target_team, {})
                        is_active = tid in team_strategies
                        status = st.toggle("Activate", value=is_active, key=f"tg_{tid}_{target_team}")
                        
                        if status:
                            current_params = team_strategies.get(tid, {})
                            new_params = {}
                            for param in temp.get("editable_params", []):
                                p_val = st.number_input(param["label"], param["min"], param["max"], value=int(current_params.get(param["key"], param["default"])), key=f"pr_{tid}_{target_team}_{param['key']}")
                                new_params[param["key"]] = p_val
                            
                            if status != is_active or new_params != current_params:
                                if st.button("SAVE STATE", key=f"sv_{tid}_{target_team}"):
                                    if target_team not in branch_ctx["active_strategies"]: branch_ctx["active_strategies"][target_team] = {}
                                    branch_ctx["active_strategies"][target_team][tid] = new_params
                                    # REBUILD RULES
                                    manual_rules = [r for r in branch_ctx["location_context"] if "Mode:" not in r.get("rule_name", "")]
                                    branch_ctx["location_context"] = manual_rules
                                    for t, tids in branch_ctx["active_strategies"].items():
                                        for atid, ps in tids.items():
                                            tmpl = next((x for x in templates_data if x["id"] == atid), None)
                                            if tmpl:
                                                for rb in tmpl["rules_template"]:
                                                    nr = rb.copy()
                                                    nr["rule_name"] = f"Mode: {tmpl['template_name']} ({t})"
                                                    nr.update(ps)
                                                    branch_ctx["location_context"].append(nr)
                                    with open(branch_ctx_path, 'w', encoding='utf-8') as f: json.dump(branch_ctx, f, indent=2)
                                    st.rerun()
                        elif is_active:
                            if st.button("DEACTIVATE", key=f"de_{tid}_{target_team}"):
                                branch_ctx["active_strategies"][target_team].pop(tid, None)
                                # REBUILD
                                manual_rules = [r for r in branch_ctx["location_context"] if "Mode:" not in r.get("rule_name", "")]
                                branch_ctx["location_context"] = manual_rules
                                with open(branch_ctx_path, 'w', encoding='utf-8') as f: json.dump(branch_ctx, f, indent=2)
                                st.rerun()
