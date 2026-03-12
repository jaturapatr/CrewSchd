"""
CrewSchd - Business Context Module
Handles teams, operating hours, and fixed utilization rules.
"""

def apply_business_context(model, schedule, days, shifts, context_dict, employee_dict):
    print("🏢 Applying Time-Slot Based Business Context...")
    time_slots = range(6)
    shift_to_slots = {
        'Morning': [1, 2], 'Evening': [3, 4], 'Night': [5, 0],
        '12hDay': [2, 3, 4], '12hNight': [5, 0, 1]
    }
    team_requirements = context_dict["strict_day_coverage"]
    operating_hours = context_dict.get("operating_hours", {})
    fixed_weekly_days = context_dict.get("fixed_weekly_days", {})
    
    for team_name, required_headcount in team_requirements.items():
        team_members = [eid for emp_id, details in employee_dict["employees"].items() if details.get("team") == team_name for eid in [emp_id]]
        if not team_members: continue

        active_slots = operating_hours.get(team_name, list(time_slots))

        # --- Hard Constraint: Fixed Weekly Days ---
        if team_name in fixed_weekly_days:
            target_days = fixed_weekly_days[team_name]
            print(f"  📌 TEAM {team_name.upper()}: Both staff MUST work exactly {target_days} days.")
            for eid in team_members:
                days_worked = []
                for d in days:
                    worked_today = model.NewBoolVar(f'{eid}_worked_fixed_{d.isoformat()}')
                    model.AddMaxEquality(worked_today, [schedule[(eid, d, s)] for s in shifts])
                    days_worked.append(worked_today)
                model.Add(sum(days_worked) == target_days)

        for d in days:
            # 1. RESTRICTION: Operating Hours
            if team_name in operating_hours:
                for e in team_members:
                    for s in shifts:
                        if any(slot not in active_slots for slot in shift_to_slots[s]):
                            model.Add(schedule[(e, d, s)] == 0)

            # 2. DYNAMIC FALLBACK: 9h vs 12h
            team_uses_12h = model.NewBoolVar(f'team_{team_name}_uses_12h_{d.isoformat()}')
            for e in team_members:
                model.Add(sum(schedule[(e, d, s)] for s in ['Morning', 'Evening', 'Night']) == 0).OnlyEnforceIf(team_uses_12h)
                model.Add(sum(schedule[(e, d, s)] for s in ['12hDay', '12hNight']) == 0).OnlyEnforceIf(team_uses_12h.Not())

            # 3. COVERAGE
            for slot in time_slots:
                if slot in active_slots:
                    slot_workers = [schedule[(e, d, s)] for e in team_members for s in shifts if slot in shift_to_slots[s]]
                    model.Add(sum(slot_workers) >= required_headcount)
                
    print("✅ Time-Slot Context applied with Team Operating Hours and Fixed Days.")
