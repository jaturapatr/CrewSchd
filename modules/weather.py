"""
CrewSchd - Weather Override Module
Processes AI-generated natural language constraints for 4h blocks.
"""
from datetime import date

def apply_daily_weather(model, schedule, weather, employee_dict, days, blocks):
    print("🌩️ Applying Daily Weather Overrides for blocks...")
    overrides = weather.get("daily_overrides", [])
    
    # Robust name matching: Map { lowercase_stripped_name: original_eid }
    name_to_id = {emp_data["name"].strip().lower(): emp_id for emp_id, emp_data in employee_dict["employees"].items()}
    
    today = date.today()
    
    for rule in overrides:
        rule_type = rule.get("type")
        target_date_str = rule.get("date")
        if not target_date_str: continue
        
        try:
            target_date = date.fromisoformat(target_date_str)
        except ValueError:
            continue
        
        if target_date < today:
            continue

        if target_date not in days: continue

        if rule_type == "block_employee_availability":
            emp_ref = rule.get("employee")
            if not emp_ref: continue
            
            ref_lower = str(emp_ref).strip().lower()
            e_id = None
            if emp_ref in employee_dict["employees"]:
                e_id = emp_ref
            else:
                e_id = name_to_id.get(ref_lower)
            
            if e_id:
                # Block ALL 4h blocks for that day
                for b in blocks:
                    model.Add(schedule[(e_id, target_date, b)] == 0)
                actual_name = employee_dict["employees"][e_id]["name"]
                print(f"  🚫 Blocked {actual_name} ({e_id}) on {target_date_str}")
            else:
                print(f"⚠️ Skipping block: Employee Reference '{emp_ref}' not found.")
