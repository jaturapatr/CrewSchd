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

def generate_roster(start_date=None):
    print("🛠️ Initializing CrewSchd Math Engine...")
    model = cp_model.CpModel()
    base_dir = os.path.dirname(__file__)
    
    # 1. LOAD DATA
    try:
        jsons_dir = os.path.join(base_dir, 'jsons')
        with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: employee_dict = json.load(f)
        with open(os.path.join(jsons_dir, 'company_policies.json'), 'r') as f: policies_dict = json.load(f)
        with open(os.path.join(jsons_dir, 'business_context.json'), 'r') as f: context_dict = json.load(f)
        
        weather_path = os.path.join(jsons_dir, 'weather.json')
        if not os.path.exists(weather_path):
            weather_dict = {"daily_overrides": []}
            with open(weather_path, 'w') as f: json.dump(weather_dict, f, indent=2)
        else:
            with open(weather_path, 'r') as f: weather_dict = json.load(f)
            
    except Exception as e:
        print(f"❌ ERROR loading data: {e}")
        return

    # 2. SETUP HORIZON
    if start_date is None:
        start_date = date.today()
    
    days = [start_date + timedelta(days=i) for i in range(7)]
    shifts = ["Morning", "Evening", "Night", "12hDay", "12hNight"]
    employee_ids = list(employee_dict["employees"].keys())
    
    # 3. CREATE BOOLEAN GRID
    schedule = {}
    for e_id in employee_ids:
        emp_data = employee_dict["employees"][e_id]
        can_work_nights = emp_data.get("can_work_nights", True)
        for d in days:
            for s in shifts:
                var = model.NewBoolVar(f's_{e_id}_{d.isoformat()}_{s}')
                schedule[(e_id, d, s)] = var
                
                # HARD CONSTRAINT: can_work_nights flag
                if not can_work_nights and ("Night" in s or "12hNight" in s):
                    model.Add(var == 0)
                
    # 4. APPLY MODULAR CONSTRAINTS
    # --- Persistence & Stability ---
    anchor_penalties = apply_persistence_locks(model, schedule, employee_ids, days, shifts, base_dir)
    apply_history_constraints(model, schedule, employee_ids, start_date, shifts)
    
    # --- Hard Laws ---
    apply_thai_labor_laws(model, schedule, employee_ids, days, shifts)
    
    # --- Business Logic ---
    apply_business_context(model, schedule, days, shifts, context_dict, employee_dict)
    
    # --- Dynamic AI Overrides ---
    apply_daily_weather(model, schedule, weather_dict, employee_dict, days, shifts)
    
    # --- Soft Policies ---
    policy_penalty = apply_business_policies(model, schedule, days, shifts, policies_dict, employee_dict)
    
    # 5. MASTER OBJECTIVE (Minimize Penalties)
    all_penalties = anchor_penalties + [policy_penalty]
    model.Minimize(sum(all_penalties))
        
    print(f"🚀 Solving for horizon starting {start_date.isoformat()}...")
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
        print(f"\n✅ Roster Generated Successfully! (v_{timestamp})")
        
        roster_output = {
            "metadata": {
                "generated_at": date.today().isoformat(),
                "timestamp": timestamp,
                "start_date": start_date.isoformat(),
                "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
                "weather_snapshot": weather_dict.get("daily_overrides", [])
            },
            "assignments": {}
        }

        for d in days:
            d_str = d.isoformat()
            roster_output["assignments"][d_str] = {}
            print(f"--- {d_str} ({d.strftime('%A')}) ---")
            for s in shifts:
                workers = []
                for e in employee_ids:
                    if solver.Value(schedule[(e, d, s)]) == 1:
                        name = employee_dict["employees"][e]["name"]
                        workers.append(f"{name} ({e})")
                        roster_output["assignments"][d_str][e] = s
                print(f"  {s:<10}: {', '.join(workers) if workers else '--'}")
            print()
            
        # Save JSON for Persistence & Exporter
        rosters_dir = os.path.join(base_dir, 'Rosters')
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
        print("\n❌ ERROR: INFEASIBLE. The constraints created a mathematical paradox.")
        return "INFEASIBLE"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            target_date = date.fromisoformat(sys.argv[1])
            generate_roster(target_date)
        except ValueError:
            print("Invalid date format. Use YYYY-MM-DD.")
    else:
        generate_roster()
