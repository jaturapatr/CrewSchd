"""
CrewSchd - Thai Labor Law Module
Enforces hard legal constraints based on Thai LPA.
"""
import json
import os

def apply_thai_labor_laws(model, schedule, employees, days, blocks):
    print("🧱 Loading Thai Labor Laws from JSON...")
    
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        laws_path = os.path.join(base_dir, 'jsons', 'thai_laws.json')
        with open(laws_path, 'r') as f: 
            data = json.load(f)
            laws = data.get("laws", {})
    except Exception as e:
        print(f"Warning: Could not load thai_laws.json ({e}). Using defaults.")
        laws = {
            "max_total_hours_per_week": 84,
            "max_working_days_per_week": 6
        }
    
    # Each block is 4 hours
    block_length = 4

    for e in employees:
        # Law 1: Max 84 Hours Per Week
        employee_total_hours = []
        for d in days:
            for b in blocks:
                hours_worked = schedule[(e, d, b)] * block_length
                employee_total_hours.append(hours_worked)
        model.Add(sum(employee_total_hours) <= laws.get("max_total_hours_per_week", 84))

        # Law 2: Mandatory 1 Day Off Per Week
        days_worked_this_week = []
        for d in days:
            worked_today = model.NewBoolVar(f'{e}_worked_on_{d.isoformat()}')
            model.AddMaxEquality(worked_today, [schedule[(e, d, b)] for b in blocks])
            days_worked_this_week.append(worked_today)
        model.Add(sum(days_worked_this_week) <= laws.get("max_working_days_per_week", 6))

    print("✅ Thai Labor Laws successfully locked into the Math Engine.")
