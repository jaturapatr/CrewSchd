"""
CrewSchd - Business Context Module
Handles teams, operating hours, and fixed utilization rules.
"""
import streamlit as st
import json
import os

def apply_business_context(model, schedule, days, shifts, context_dict, employee_dict):
    print("🏢 Applying Time-Slot Based Business Context (Flexible Box)...")
    time_slots = range(6)
    shift_to_slots = {
        'Morning': [1, 2], 'Evening': [3, 4], 'Night': [5, 0],
        '12hDay': [2, 3, 4], '12hNight': [5, 0, 1]
    }
    team_requirements = context_dict["strict_day_coverage"]
    fixed_weekly_days = context_dict.get("fixed_weekly_days", {})
    
    extra_workers_penalties = []

    for team_name, required_headcount in team_requirements.items():
        team_members = [eid for emp_id, details in employee_dict["employees"].items() if details.get("team") == team_name for eid in [emp_id]]
        if not team_members: continue

        # --- THE FLEXIBLE BOX: Dynamic Workload & Leave Smoothing ---
        # Calculate daily demand: In our system, to cover all 6 slots with 'required_headcount',
        # we minimally need (required_headcount * 3) shifts if using 9h, or (required_headcount * 2) if using 12h.
        # We'll use the 12h minimum as the absolute "Iron Floor" for the demand calculation.
        daily_shift_demand = required_headcount * 2 
        
        total_headcount = len(team_members)
        safe_off_limit = total_headcount - daily_shift_demand
        
        # Safety Net
        if safe_off_limit < 0:
            print(f"🚨 CRITICAL UNDERSTAFFING in {team_name}: Need {daily_shift_demand}, have {total_headcount}")
            # We don't st.stop() here as it might be running in a background thread or CLI
            # But we ensure the engine knows it's impossible by setting limit to 0 and letting it return INFEASIBLE
            safe_off_limit = 0

        for d in days:
            # 1. DYNAMIC FALLBACK: 9h vs 12h
            team_uses_12h = model.NewBoolVar(f'team_{team_name}_uses_12h_{d.isoformat()}')
            for e in team_members:
                model.Add(sum(schedule[(e, d, s)] for s in ['Morning', 'Evening', 'Night']) == 0).OnlyEnforceIf(team_uses_12h)
                model.Add(sum(schedule[(e, d, s)] for s in ['12hDay', '12hNight']) == 0).OnlyEnforceIf(team_uses_12h.Not())

            # 2. COVERAGE (Hard)
            for slot in time_slots:
                slot_workers = [schedule[(e, d, s)] for e in team_members for s in shifts if slot in shift_to_slots[s]]
                model.Add(sum(slot_workers) >= required_headcount)

            # 3. THE FLEXIBLE BRICK WALL (Dynamic OFF Limit)
            staff_off_today = []
            for eid in team_members:
                is_working_today = model.NewBoolVar(f'{eid}_is_working_{team_name}_{d.isoformat()}')
                model.AddMaxEquality(is_working_today, [schedule[(eid, d, s)] for s in shifts])
                
                is_off_today = model.NewBoolVar(f'{eid}_is_off_{team_name}_{d.isoformat()}')
                model.Add(is_off_today == 1 - is_working_today)
                staff_off_today.append(is_off_today)
            
            model.Add(sum(staff_off_today) <= safe_off_limit)
            
            # 4. THE FAIRNESS NUDGE (Soft Penalty)
            # Penalize overstaffing beyond the absolute 12h minimum demand to encourage rest
            num_working = model.NewIntVar(0, total_headcount, f'num_working_{team_name}_{d.isoformat()}')
            model.Add(num_working == sum([1 - off_var for off_var in staff_off_today]))
            
            extra_workers = model.NewIntVar(0, total_headcount, f'extra_workers_{team_name}_{d.isoformat()}')
            model.Add(extra_workers >= num_working - daily_shift_demand)
            extra_workers_penalties.append(extra_workers * 100)

    # ---------------------------------------------------------
    # HARD CONSTRAINT: The Minimum Rest Rule (No "Death Shifts")
    # ---------------------------------------------------------
    print("🧱 Building Minimum Rest Constraints across Midnight...")
    employee_ids = list(employee_dict["employees"].keys())
    
    for emp_id in employee_ids:
        for i in range(len(days) - 1):
            today = days[i]
            tomorrow = days[i + 1]
            
            # 1. The Night Shift Blockers
            model.Add(schedule[(emp_id, today, "Night")] + schedule[(emp_id, tomorrow, "Morning")] <= 1)
            model.Add(schedule[(emp_id, today, "Night")] + schedule[(emp_id, tomorrow, "12hDay")] <= 1)
            
            # 2. The 12h Night Blockers
            model.Add(schedule[(emp_id, today, "12hNight")] + schedule[(emp_id, tomorrow, "Morning")] <= 1)
            model.Add(schedule[(emp_id, today, "12hNight")] + schedule[(emp_id, tomorrow, "12hDay")] <= 1)

            # 3. The "Clopen" Blocker
            model.Add(schedule[(emp_id, today, "Evening")] + schedule[(emp_id, tomorrow, "Morning")] <= 1)
            model.Add(schedule[(emp_id, today, "Evening")] + schedule[(emp_id, tomorrow, "12hDay")] <= 1)

    print("✅ Flexible Box and Minimum Rest Rules applied.")
    return extra_workers_penalties
