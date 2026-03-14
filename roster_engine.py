"""
CrewSchd - Math Engine Orchestrator (Universal Tiered Branch)
A purely data-driven constraint solver with unified Location Context logic.
"""

import os
import sys
import json
from datetime import date, timedelta
from ortools.sat.python import cp_model

# Add modules directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.persistence import apply_history_constraints, apply_persistence_locks
from modules.universal_engine import apply_universal_rules

def generate_roster(start_date=None, branch="Main Office", team="Cashier"):
    print(f"🛠️ Initializing UNIVERSAL Engine [{branch} -> {team}]...")
    model = cp_model.CpModel()
    base_dir = os.path.dirname(__file__)
    
    # 1. LOAD DATA
    try:
        # A. Global Tiers (Laws, Corp Compliance)
        with open(os.path.join(base_dir, 'jsons', 'universal_rules.json'), 'r', encoding='utf-8') as f:
            univ_data = json.load(f)
            laws = univ_data.get("laws", [])
            corp_compliance = univ_data.get("corp_compliance", [])

        # B. Branch Tier (Location Context - includes Headcount)
        branch_path = os.path.join(base_dir, 'jsons', branch)
        with open(os.path.join(branch_path, 'business_context.json'), 'r', encoding='utf-8') as f:
            branch_data = json.load(f)
            loc_context = branch_data.get("location_context", [])
        
        # C. Local Team Data
        team_jsons = os.path.join(branch_path, team)
        with open(os.path.join(team_jsons, 'employee.json'), 'r', encoding='utf-8') as f: employee_dict = json.load(f)
        with open(os.path.join(team_jsons, 'weather.json'), 'r', encoding='utf-8') as f: weather_dict = json.load(f)
            
    except Exception as e:
        print(f"❌ ERROR loading data: {e}")
        return

    # 2. SETUP HORIZON
    if start_date is None: start_date = date.today()
    days = [start_date + timedelta(days=i) for i in range(7)]
    blocks = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]
    employee_ids = list(employee_dict.get("employees", {}).keys())
    
    if not employee_ids: return "NO_EMPLOYEES"

    # 3. CREATE BOOLEAN GRID
    schedule = {}
    for eid in employee_ids:
        can_work_nights = employee_dict["employees"][eid].get("can_work_nights", True)
        for d in days:
            for b in blocks:
                var = model.NewBoolVar(f's_{eid}_{d.isoformat()}_{b}')
                schedule[(eid, d, b)] = var
                if not can_work_nights and b in ["00:00", "04:00", "20:00"]:
                    model.Add(var == 0)

    # ---------------------------------------------------------
    # 4. CONSOLIDATE DYNAMIC RULES
    # ---------------------------------------------------------
    master_dynamic_rules = []
    
    # - Global Mandates
    master_dynamic_rules.extend(laws)
    master_dynamic_rules.extend(corp_compliance)
    
    # - Location Context (Already includes filtered headcount for this team)
    # We filter loc_context to only rules meant for THIS team (or global collective rules)
    for rule in loc_context:
        target_team = rule.get("target_team")
        if target_team and target_team != team: continue
        master_dynamic_rules.append(rule)

    # - Team Weather (Prefs + Overrides)
    for eid, edata in employee_dict.get("employees", {}).items():
        pref_rule = edata.get("special_preference_json")
        if pref_rule and isinstance(pref_rule, dict):
            pref_rule["target_group"] = [eid]
            pref_rule["rule_name"] = f"Preference: {edata.get('name')}"
            master_dynamic_rules.append(pref_rule)

    name_to_id = {edata["name"].strip().lower(): eid for eid, edata in employee_dict["employees"].items()}
    for rule in weather_dict.get("daily_overrides", []):
        if rule.get("type") == "block_employee_availability":
            emp_ref = str(rule.get("employee")).strip().lower()
            eid = emp_ref if emp_ref in employee_dict["employees"] else name_to_id.get(emp_ref)
            if eid:
                master_dynamic_rules.append({
                    "rule_name": f"Weather: {rule.get('employee')}",
                    "math_shape": "aggregator", "scope": "individual", "target_group": [eid],
                    "target_timeframe": "daily", "operator": "==", "value": 0,
                    "target_date": rule.get("date")
                })

    # 5. CORE RIGIDITY
    for emp_id in employee_ids:
        for d in days:
            daily_starts = []
            for i in range(len(blocks)):
                curr_b = schedule[(emp_id, d, blocks[i])]
                is_start = model.NewBoolVar(f'{emp_id}_start_{d.isoformat()}_{blocks[i]}')
                if i == 0: model.Add(is_start == curr_b)
                else:
                    prev_b = schedule[(emp_id, d, blocks[i-1])]
                    model.Add(is_start >= curr_b - prev_b)
                    model.Add(is_start <= curr_b)
                    model.Add(is_start <= 1 - prev_b)
                daily_starts.append(is_start)
            model.Add(sum(daily_starts) <= 1)
            model.Add(sum(schedule[(emp_id, d, b)] for b in blocks) <= 3)

    # 6. APPLY UNIVERSAL ENGINE & PERSISTENCE
    all_penalties = apply_universal_rules(model, schedule, employee_ids, days, blocks, master_dynamic_rules)
    
    rosters_dir = os.path.join(base_dir, 'Rosters', branch, team)
    anchor_penalties = apply_persistence_locks(model, schedule, employee_ids, days, blocks, rosters_dir)
    apply_history_constraints(model, schedule, employee_ids, start_date, blocks, rosters_dir)
    
    # 7. MINIMIZE
    model.Minimize(sum(all_penalties + anchor_penalties))
        
    print(f"🚀 Solving Universal Matrix...")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)
    
    # 8. PROCESS RESULTS
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        import time
        timestamp = int(time.time())
        roster_output = {
            "metadata": {
                "branch": branch, "team": team, "generated_at": date.today().isoformat(),
                "timestamp": timestamp, "start_date": start_date.isoformat(),
                "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
                "weather_snapshot": weather_dict.get("daily_overrides", []),
                "type": "block_based"
            },
            "assignments": {}
        }
        for d in days:
            d_str = d.isoformat()
            roster_output["assignments"][d_str] = {}
            for b in blocks:
                for e in employee_ids:
                    if solver.Value(schedule[(e, d, b)]) == 1:
                        if e not in roster_output["assignments"][d_str]: roster_output["assignments"][d_str][e] = []
                        roster_output["assignments"][d_str][e].append(b)
        
        os.makedirs(rosters_dir, exist_ok=True)
        file_name = f'roster_{start_date.isoformat()}_{timestamp}.json'
        save_path = os.path.join(rosters_dir, file_name)
        with open(save_path, 'w') as f: json.dump(roster_output, f, indent=2)
        print(f"✅ Roster SUCCESS: {save_path}")
        return "FEASIBLE"
    else:
        return "INFEASIBLE"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 3:
        generate_roster(date.today(), sys.argv[1], sys.argv[3])
    else:
        generate_roster()
