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
        penalty_weekend_off = 500 # Tier 6: Comfort
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
        clopen_penalty = 3500 # Tier 4: Human
        for emp_id in employee_ids:
            for i in range(len(days) - 1):
                today, tomorrow = days[i], days[i+1]
                is_clopen = model.NewBoolVar(f'{emp_id}_clopen_{today.isoformat()}')
                night_worked = schedule[(emp_id, today, 'Night')] + schedule[(emp_id, today, '12hNight')]
                morning_worked = schedule[(emp_id, tomorrow, 'Morning')] + schedule[(emp_id, tomorrow, '12hDay')]
                model.Add(night_worked + morning_worked == 2).OnlyEnforceIf(is_clopen)
                total_penalty_score += (is_clopen * clopen_penalty)

    # POLICY 4: 12h Shift Surcharge (Operating Cost)
    # Tier 2: Profit - Heavily penalize 12h shifts to prefer 9h shifts
    twelve_hour_penalty = 40000 
    for emp_id in employee_ids:
        for d in days:
            is_12h = model.NewBoolVar(f'{emp_id}_12h_check_{d.isoformat()}')
            model.AddMaxEquality(is_12h, [schedule[(emp_id, d, '12hDay')], schedule[(emp_id, d, '12hNight')]])
            total_penalty_score += (is_12h * twelve_hour_penalty)

    # POLICY 6: Max Consecutive Same Shifts (Any type)
    rule_same_shift = opt_targets.get("max_consecutive_same_shifts", {})
    if rule_same_shift:
        limit = rule_same_shift.get("limit", 1)
        penalty = 5000 # Tier 4: Human
        for emp_id in employee_ids:
            for i in range(len(days) - limit):
                window = [days[i + j] for j in range(limit + 1)]
                for s in shifts:
                    is_violated = model.NewBoolVar(f'{emp_id}_same_shift_{s}_{window[0].isoformat()}')
                    model.Add(sum(schedule[(emp_id, d, s)] for d in window) > limit).OnlyEnforceIf(is_violated)
                    model.Add(sum(schedule[(emp_id, d, s)] for d in window) <= limit).OnlyEnforceIf(is_violated.Not())
                    total_penalty_score += (is_violated * penalty)

    # POLICY 7: Labor Efficiency (Minimize 'OFF' days)
    # Give a small penalty for every day someone is NOT working
    employee_work_totals = {}
    for emp_id in employee_ids:
        off_penalty = 100 # Tier 6: Comfort
        
        days_worked_vars = []
        for d in days:
            worked_today = model.NewBoolVar(f'{emp_id}_worked_{d.isoformat()}')
            model.AddMaxEquality(worked_today, [schedule[(emp_id, d, s)] for s in shifts])
            days_worked_vars.append(worked_today)
            total_penalty_score += (worked_today.Not() * off_penalty)
        
        # Track total days worked for this employee to use in Fairness logic
        total_days = model.NewIntVar(0, len(days), f'total_days_{emp_id}')
        model.Add(total_days == sum(days_worked_vars))
        employee_work_totals[emp_id] = total_days

    # POLICY 8: Workload Fairness (Minimize the gap)
    if len(employee_work_totals) > 1:
        min_work = model.NewIntVar(0, len(days), 'min_work_days')
        max_work = model.NewIntVar(0, len(days), 'max_work_days')
        model.AddMinEquality(min_work, list(employee_work_totals.values()))
        model.AddMaxEquality(max_work, list(employee_work_totals.values()))
        
        workload_gap = model.NewIntVar(0, len(days), 'workload_gap')
        model.Add(workload_gap == max_work - min_work)
        
        # Penalty for every day of difference between the most and least worked staff
        # Tier 5: Balance
        total_penalty_score += (workload_gap * 1500)

    # POLICY 9: Daily Minimum Utilization (No more than 2 OFF for Service)
    service_members = [eid for eid, details in employee_dict["employees"].items() if details.get("team") == "Service"]
    if service_members:
        # Tier 1: Survival - Top Priority
        min_service_working = len(service_members) - 2
        for d in days:
            working_vars = []
            for eid in service_members:
                is_working = model.NewBoolVar(f'is_working_service_{eid}_{d.isoformat()}')
                model.AddMaxEquality(is_working, [schedule[(eid, d, s)] for s in shifts])
                working_vars.append(is_working)
            
            num_working = model.NewIntVar(0, len(service_members), f'num_service_working_{d.isoformat()}')
            model.Add(num_working == sum(working_vars))
            
            # Penalty if working staff < 7
            under_utilization = model.NewIntVar(0, len(service_members), f'under_util_service_{d.isoformat()}')
            model.Add(under_utilization >= min_service_working - num_working)
            total_penalty_score += (under_utilization * 100000) # Heavy penalty to force compliance

    print("✅ CEO Policies mapped successfully.")
    return total_penalty_score
