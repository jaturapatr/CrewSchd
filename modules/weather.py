"""
CrewSchd - Weather Override Module
Processes AI-generated natural language constraints.
"""
from datetime import date

def apply_daily_weather(model, schedule, weather, employee_dict, days, shifts):
    print("🌩️ Applying Daily Weather Overrides...")
    overrides = weather.get("daily_overrides", [])
    name_to_id = {emp_data["name"]: emp_id for emp_id, emp_data in employee_dict["employees"].items()}
    
    today = date.today()
    
    for rule in overrides:
        rule_type = rule.get("type")
        target_date_str = rule.get("date")
        if not target_date_str: continue
        
        target_date = date.fromisoformat(target_date_str)
        
        # --- THE HISTORY SHIELD ---
        if target_date < today:
            print(f"  ⏩ Skipping past weather rule for {target_date_str} (History is locked)")
            continue

        if target_date not in days: continue

        if rule_type == "block_employee_availability":
            e_name = rule.get("employee")
            e_id = name_to_id.get(e_name) or name_to_id.get(e_name.capitalize()) if e_name else None
            if e_id:
                for s in shifts:
                    model.Add(schedule[(e_id, target_date, s)] == 0)
            else:
                print(f"⚠️ Skipping weather rule: No employee target found for '{rule.get('reason')}'")
                    
        elif rule_type == "force_minimum_headcount":
            s = rule.get("shift")
            min_count = rule.get("min_count")
            if s in shifts:
                all_emps = list(employee_dict["employees"].keys())
                model.Add(sum(schedule[(e, target_date, s)] for e in all_emps) >= min_count)
