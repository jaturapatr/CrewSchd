"""
CrewSchd - Business Policies Module
Handles soft constraints and optimization penalties.
"""

def apply_business_policies(model, schedule, days, shifts, policies_dict, employee_dict):
    print("📈 Applying CEO Policies using employee.json data...")
    employee_ids = list(employee_dict["employees"].keys())
    total_penalty_score = 0

    opt_targets = policies_dict.get("optimization_targets", {})

    # POLICY 2: Maximize Weekend Firepower
    rule_weekend = opt_targets.get("maximize_weekend_firepower", {})
    if rule_weekend:
        penalty_weekend_off = 500
        target_day_names = rule_weekend.get("target_days", ["Saturday", "Sunday"])
        for emp_id in employee_ids:
            took_weekend_off = model.NewBoolVar(f'{emp_id}_weekend_off')
            weekend_shifts = []
            for d in days:
                if d.strftime('%A') in target_day_names:
                    weekend_shifts.extend([schedule[(emp_id, d, s)] for s in shifts])
            if weekend_shifts:
                model.Add(sum(weekend_shifts) == 0).OnlyEnforceIf(took_weekend_off)
                model.Add(sum(weekend_shifts) > 0).OnlyEnforceIf(took_weekend_off.Not())
                total_penalty_score += (took_weekend_off * penalty_weekend_off)

    # POLICY 3: Penalize "Clopen" Shifts
    rule_clopen = opt_targets.get("penalize_clopen_rotation", {})
    if rule_clopen:
        clopen_penalty = 3500
        for emp_id in employee_ids:
            for i in range(len(days) - 1):
                today, tomorrow = days[i], days[i+1]
                is_clopen = model.NewBoolVar(f'{emp_id}_clopen_{today.isoformat()}')
                night_worked = schedule[(emp_id, today, 'Night')] + schedule[(emp_id, today, '12hNight')]
                morning_worked = schedule[(emp_id, tomorrow, 'Morning')] + schedule[(emp_id, tomorrow, '12hDay')]
                model.Add(night_worked + morning_worked == 2).OnlyEnforceIf(is_clopen)
                total_penalty_score += (is_clopen * clopen_penalty)

    # POLICY 4: The "Emergency Only" 12h Surcharge
    # If the engine uses a 12h shift, hit it with a massive 50,000 pt penalty
    for emp_id in employee_ids:
        for d in days:
            total_penalty_score += (schedule[(emp_id, d, "12hDay")] * 50000)
            total_penalty_score += (schedule[(emp_id, d, "12hNight")] * 50000)

    # --- NEW: Fatigue Shield (Soft Fatigue Breaker) ---
    # Penalty for working 3 heavy shifts in a rolling 3-day window
    fatigue_penalty = 50000
    for emp_id in employee_ids:
        for i in range(len(days) - 2):
            d1, d2, d3 = days[i], days[i+1], days[i+2]
            
            is_heavy_d1 = model.NewBoolVar(f'{emp_id}_soft_heavy_{d1.isoformat()}')
            is_heavy_d2 = model.NewBoolVar(f'{emp_id}_soft_heavy_{d2.isoformat()}')
            is_heavy_d3 = model.NewBoolVar(f'{emp_id}_soft_heavy_{d3.isoformat()}')
            
            model.AddMaxEquality(is_heavy_d1, [schedule[(emp_id, d1, "12hDay")], schedule[(emp_id, d1, "12hNight")]])
            model.AddMaxEquality(is_heavy_d2, [schedule[(emp_id, d2, "12hDay")], schedule[(emp_id, d2, "12hNight")]])
            model.AddMaxEquality(is_heavy_d3, [schedule[(emp_id, d3, "12hDay")], schedule[(emp_id, d3, "12hNight")]])
            
            is_fatigued = model.NewBoolVar(f'{emp_id}_fatigue_{d1.isoformat()}')
            model.Add(is_heavy_d1 + is_heavy_d2 + is_heavy_d3 == 3).OnlyEnforceIf(is_fatigued)
            model.Add(is_heavy_d1 + is_heavy_d2 + is_heavy_d3 < 3).OnlyEnforceIf(is_fatigued.Not())
            total_penalty_score += (is_fatigued * fatigue_penalty)

    # POLICY 6: Max Consecutive Same Shifts
    rule_same_shift = opt_targets.get("max_consecutive_same_shifts", {})
    if rule_same_shift:
        limit = rule_same_shift.get("limit", 1)
        penalty = 5000
        for emp_id in employee_ids:
            for i in range(len(days) - limit):
                window = [days[i + j] for j in range(limit + 1)]
                for s in shifts:
                    is_violated = model.NewBoolVar(f'{emp_id}_same_shift_{s}_{window[0].isoformat()}')
                    model.Add(sum(schedule[(emp_id, d, s)] for d in window) > limit).OnlyEnforceIf(is_violated)
                    model.Add(sum(schedule[(emp_id, d, s)] for d in window) <= limit).OnlyEnforceIf(is_violated.Not())
                    total_penalty_score += (is_violated * penalty)

    # --- NEW: Weekend Fairness ---
    weekend_days = ["Saturday", "Sunday"]
    emp_weekend_work = {}
    for emp_id in employee_ids:
        weekend_vars = []
        for d in days:
            if d.strftime('%A') in weekend_days:
                worked_weekend = model.NewBoolVar(f'{emp_id}_worked_weekend_{d.isoformat()}')
                model.AddMaxEquality(worked_weekend, [schedule[(emp_id, d, s)] for s in shifts])
                weekend_vars.append(worked_weekend)
        
        total_weekend = model.NewIntVar(0, 2, f'total_weekend_{emp_id}')
        model.Add(total_weekend == sum(weekend_vars))
        emp_weekend_work[emp_id] = total_weekend

    if len(emp_weekend_work) > 1:
        min_w = model.NewIntVar(0, 2, 'min_weekend')
        max_w = model.NewIntVar(0, 2, 'max_weekend')
        model.AddMinEquality(min_w, list(emp_weekend_work.values()))
        model.AddMaxEquality(max_w, list(emp_weekend_work.values()))
        
        weekend_gap = model.NewIntVar(0, 2, 'weekend_gap')
        model.Add(weekend_gap == max_w - min_w)
        total_penalty_score += (weekend_gap * 5000)

    # POLICY 8: Overall Workload Fairness
    employee_work_totals = {}
    for emp_id in employee_ids:
        days_worked_vars = []
        for d in days:
            worked_today = model.NewBoolVar(f'{emp_id}_worked_total_{d.isoformat()}')
            model.AddMaxEquality(worked_today, [schedule[(emp_id, d, s)] for s in shifts])
            days_worked_vars.append(worked_today)
        
        total_days = model.NewIntVar(0, len(days), f'total_days_{emp_id}')
        model.Add(total_days == sum(days_worked_vars))
        employee_work_totals[emp_id] = total_days

    if len(employee_work_totals) > 1:
        min_work = model.NewIntVar(0, len(days), 'min_work_days')
        max_work = model.NewIntVar(0, len(days), 'max_work_days')
        model.AddMinEquality(min_work, list(employee_work_totals.values()))
        model.AddMaxEquality(max_work, list(employee_work_totals.values()))
        workload_gap = model.NewIntVar(0, len(days), 'workload_gap')
        model.Add(workload_gap == max_work - min_work)
        total_penalty_score += (workload_gap * 1500)

    print("✅ CEO Policies mapped successfully.")
    return total_penalty_score
