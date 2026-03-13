"""
CrewSchd - Weather Override Module
Processes AI-generated natural language constraints.
"""
from datetime import date

def apply_daily_weather(model, schedule, weather, employee_dict, days, shifts):
    print("🌩️ Applying Daily Weather Overrides...")
    overrides = weather.get("daily_overrides", [])

    # Robust name matching: Map { lowercase_stripped_name: original_eid }
    name_to_id = {emp_data["name"].strip().lower(): emp_id for emp_id, emp_data in employee_dict["employees"].items()}

    today = date.today()

    for rule in overrides:
        rule_type = rule.get("type")
        target_date_str = rule.get("date")
        if not target_date_str: continue

        target_date = date.fromisoformat(target_date_str)

        # --- THE HISTORY SHIELD ---
        if target_date < today:
            continue

        if target_date not in days: continue

        if rule_type == "block_employee_availability":
            emp_ref = rule.get("employee")
            if not emp_ref: continue
            
            # Resolve ID:
            # 1. Direct ID match
            e_id = None
            if emp_ref in employee_dict["employees"]:
                e_id = emp_ref
            else:
                # 2. Name lookup (case-insensitive)
                e_id = name_to_id.get(str(emp_ref).strip().lower())
            
            if e_id:
                for s in shifts:
                    model.Add(schedule[(e_id, target_date, s)] == 0)
                actual_name = employee_dict["employees"][e_id]["name"]
                print(f"  🚫 Blocked {actual_name} ({e_id}) on {target_date_str}")
            else:
                print(f"⚠️ Skipping block: Employee Reference '{emp_ref}' not found.")
                    
        elif rule_type == "force_minimum_headcount":
            s = rule.get("shift")
            min_count = rule.get("min_count")
            if s in shifts:
                all_emps = list(employee_dict["employees"].keys())
                model.Add(sum(schedule[(e, target_date, s)] for e in all_emps) >= min_count)
