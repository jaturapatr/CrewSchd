"""
CrewSchd - Thai Labor Law Module
Enforces hard legal constraints based on Thai LPA.
"""
import json
import os

def apply_thai_labor_laws(model, schedule, employees, days, shifts):
    print("🧱 Loading Thai Labor Laws from JSON...")
    
    try:
        # Use relative path to find the json in the 'jsons' directory
        base_dir = os.path.dirname(os.path.dirname(__file__))
        laws_path = os.path.join(base_dir, 'jsons', 'thai_laws.json')
        with open(laws_path, 'r') as f: 
            data = json.load(f)
            laws = data.get("laws", {})
    except Exception as e:
        print(f"Warning: Could not load thai_laws.json ({e}). Using defaults.")
        laws = {
            "max_shifts_per_day": 1,
            "max_total_hours_per_week": 84,
            "max_working_days_per_week": 6
        }
    
    shift_lengths = {
        'Morning': 9, 'Evening': 9, 'Night': 9,
        '12hDay': 12, '12hNight': 12
    }

    for e in employees:
        # Law 1: Max 1 Shift Per Day
        for d in days:
            model.AddAtMostOne(schedule[(e, d, s)] for s in shifts)

        # Law 2: Max 84 Hours Per Week
        employee_total_hours = []
        for d in days:
            for s in shifts:
                hours_worked = schedule[(e, d, s)] * shift_lengths[s]
                employee_total_hours.append(hours_worked)
        model.Add(sum(employee_total_hours) <= laws.get("max_total_hours_per_week", 84))

        # Law 3: Mandatory 1 Day Off Per Week
        days_worked_this_week = []
        for d in days:
            # Note: d is a date object
            worked_today = model.NewBoolVar(f'{e}_worked_on_{d.isoformat()}')
            model.AddMaxEquality(worked_today, [schedule[(e, d, s)] for s in shifts])
            days_worked_this_week.append(worked_today)
        model.Add(sum(days_worked_this_week) <= laws.get("max_working_days_per_week", 6))

    print("✅ Thai Labor Laws successfully locked into the Math Engine.")
