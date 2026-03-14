"""
CrewSchd - Math Engine Orchestrator
A modular constraint programming solver for enterprise shift scheduling.
"""

import os
import sys
import json
from datetime import date, timedelta
from ortools.sat.python import cp_model

# Add modules directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

# Import modular components
from modules.laws import apply_thai_labor_laws
from modules.policies import apply_business_policies
from modules.context import apply_business_context
from modules.weather import apply_daily_weather
from modules.persistence import apply_history_constraints, apply_persistence_locks

def generate_roster(start_date=None, branch="Main Office", team="Cashier"):
    print(f"🛠️ Initializing CrewSchd Math Engine for [{branch} -> {team}]...")
    model = cp_model.CpModel()
    base_dir = os.path.dirname(__file__)
    
    # 1. LOAD DATA (Branch & Team Specific)
    try:
        jsons_dir = os.path.join(base_dir, 'jsons', branch, team)
        # Ensure directory exists for new branches/teams
        if not os.path.exists(jsons_dir):
            os.makedirs(jsons_dir)
            # Create default empty files if they don't exist
            with open(os.path.join(jsons_dir, 'employee.json'), 'w') as f: json.dump({"employees": {}}, f)
            with open(os.path.join(jsons_dir, 'company_policies.json'), 'w') as f: json.dump({"optimization_targets": {}}, f)

        # Branch JSONS (Branch Level)
        branch_ctx_path = os.path.join(base_dir, 'jsons', branch, 'business_context.json')
        if not os.path.exists(branch_ctx_path):
            with open(branch_ctx_path, 'w') as f: json.dump({"strict_day_coverage": {}}, f)
        with open(branch_ctx_path, 'r') as f: context_dict = json.load(f)

        # Local JSONS (Team Level)
        with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: employee_dict = json.load(f)
        with open(os.path.join(jsons_dir, 'company_policies.json'), 'r') as f: policies_dict = json.load(f)
        
        weather_path = os.path.join(jsons_dir, 'weather.json')
        if not os.path.exists(weather_path):
            weather_dict = {"daily_overrides": []}
            with open(weather_path, 'w') as f: json.dump(weather_dict, f, indent=2)
        else:
            with open(weather_path, 'r') as f: weather_dict = json.load(f)
            
    except Exception as e:
        print(f"❌ ERROR loading data for {branch}/{team}: {e}")
        return

    # 2. SETUP HORIZON
    if start_date is None:
        start_date = date.today()
    
    days = [start_date + timedelta(days=i) for i in range(7)]
    # 6 blocks representing a 24-hour day (4 hours each)
    blocks = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]
    employee_ids = list(employee_dict.get("employees", {}).keys())
    
    if not employee_ids:
        print(f"⚠️ No employees found for {branch}/{team}")
        return "NO_EMPLOYEES"

    # 3. CREATE BOOLEAN GRID
    schedule = {}
    for e_id in employee_ids:
        emp_data = employee_dict["employees"][e_id]
        can_work_nights = emp_data.get("can_work_nights", True)
        for d in days:
            for b in blocks:
                var = model.NewBoolVar(f's_{e_id}_{d.isoformat()}_{b}')
                schedule[(e_id, d, b)] = var
                
                # Adaptation of can_work_nights for 4h blocks
                if not can_work_nights and b in ["00:00", "04:00", "20:00"]:
                    model.Add(var == 0)

    # ---------------------------------------------------------
    # MICRO-SHIFT: The "One Start Per Day" Gap Detector (Split-Shift Blocker)
    # ---------------------------------------------------------
    print("🧱 Building the Split-Shift Blocker...")
    for emp_id in employee_ids:
        for d in days:
            daily_starts = []
            for i in range(len(blocks)):
                current_block = schedule[(emp_id, d, blocks[i])]
                is_start = model.NewBoolVar(f'{emp_id}_start_{d.isoformat()}_{blocks[i]}')
                
                if i == 0:
                    model.Add(is_start == current_block)
                else:
                    prev_block = schedule[(emp_id, d, blocks[i-1])]
                    # Math trick to detect a 0 -> 1 transition
                    model.Add(is_start >= current_block - prev_block)
                    model.Add(is_start <= current_block)
                    model.Add(is_start <= 1 - prev_block)
                daily_starts.append(is_start)
            
            # THE BRICK WALL: You can only clock in ONCE per day.
            model.Add(sum(daily_starts) <= 1)
            
            # THAI LABOR LAW (Max 12 hours including OT): 
            # You can work a maximum of THREE 4-hour blocks per day.
            model.Add(sum(schedule[(emp_id, d, b)] for b in blocks) <= 3)
                
    # 4. APPLY MODULAR CONSTRAINTS
    # --- Persistence & Stability ---
    rosters_dir = os.path.join(base_dir, 'Rosters', branch, team)
    # Update these functions to use 'blocks' terminology if they depend on shift names
    anchor_penalties = apply_persistence_locks(model, schedule, employee_ids, days, blocks, rosters_dir)
    apply_history_constraints(model, schedule, employee_ids, start_date, blocks, rosters_dir)
    
    # --- Hard Laws ---
    apply_thai_labor_laws(model, schedule, employee_ids, days, blocks)
    
    # --- Business Logic ---
    context_penalties = apply_business_context(model, schedule, days, blocks, context_dict, employee_dict)
    
    # --- Dynamic AI Overrides ---
    apply_daily_weather(model, schedule, weather_dict, employee_dict, days, blocks)
    
    # --- Soft Policies ---
    policy_penalty = apply_business_policies(model, schedule, days, blocks, policies_dict, employee_dict)
    
    # 5. MASTER OBJECTIVE (Minimize Penalties)
    all_penalties = anchor_penalties + context_penalties + [policy_penalty]
    model.Minimize(sum(all_penalties))
        
    print(f"🚀 Solving for {branch}/{team} horizon starting {start_date.isoformat()}...")
    solver = cp_model.CpSolver()
    
    # Deterministic settings for stability
    solver.parameters.random_seed = 42
    solver.parameters.num_search_workers = 1 
    solver.parameters.max_time_in_seconds = 10.0
    
    status = solver.Solve(model)
    
    # 6. PROCESS RESULTS
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        import time
        timestamp = int(time.time())
        print(f"\n✅ Roster for {branch}/{team} Generated Successfully! (v_{timestamp})")
        
        roster_output = {
            "metadata": {
                "branch": branch,
                "team": team,
                "generated_at": date.today().isoformat(),
                "timestamp": timestamp,
                "start_date": start_date.isoformat(),
                "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
                "weather_snapshot": weather_dict.get("daily_overrides", []),
                "type": "block_based" # Flag for UI/Exporter
            },
            "assignments": {}
        }

        for d in days:
            d_str = d.isoformat()
            roster_output["assignments"][d_str] = {}
            for b in blocks:
                for e in employee_ids:
                    if solver.Value(schedule[(e, d, b)]) == 1:
                        if e not in roster_output["assignments"][d_str]:
                            roster_output["assignments"][d_str][e] = []
                        roster_output["assignments"][d_str][e].append(b)
            
        # Save JSON for Persistence & Exporter
        rosters_dir = os.path.join(base_dir, 'Rosters', branch, team)
        if not os.path.exists(rosters_dir):
            os.makedirs(rosters_dir)
        
        # USE TIMESTAMPED VERSIONING
        file_name = f'roster_{start_date.isoformat()}_{timestamp}.json'
        save_path = os.path.join(rosters_dir, file_name)
        with open(save_path, 'w') as f:
            json.dump(roster_output, f, indent=2)
        print(f"💾 Roster version saved to {save_path}")
        return "FEASIBLE"
            
    else:
        print(f"\n❌ ERROR for {branch}/{team}: INFEASIBLE.")
        return "INFEASIBLE"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 3:
        try:
            target_date = date.fromisoformat(sys.argv[1])
            br = sys.argv[2]
            tm = sys.argv[3]
            generate_roster(target_date, br, tm)
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD.")
    elif len(sys.argv) > 2:
        generate_roster(date.today(), sys.argv[1], sys.argv[2])
    else:
        generate_roster()
