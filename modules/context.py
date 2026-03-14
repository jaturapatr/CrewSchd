"""
CrewSchd - Business Context Module
Handles teams, coverage, and rest rules for 4h blocks.
Uses Hard Constraints for coverage to ensure legal/operational integrity.
"""
import streamlit as st
import json
import os

def apply_business_context(model, schedule, days, blocks, context_dict, employee_dict):
    print("🏢 Applying Block-Based Business Context (Hard Constraints)...")
    
    team_requirements = context_dict["strict_day_coverage"]
    fixed_weekly_days = context_dict.get("fixed_weekly_days", {})
    
    context_penalties = []

    for team_name, required_headcount in team_requirements.items():
        team_members = [eid for emp_id, details in employee_dict["employees"].items() if details.get("team") == team_name for eid in [emp_id]]
        if not team_members: continue

        # --- THE FLEXIBLE BOX: Dynamic Workload & Leave Smoothing ---
        daily_block_demand = required_headcount * 6
        total_headcount = len(team_members)
        # Max blocks per person is 3 (12h)
        total_team_capacity_blocks = total_headcount * 3
        
        # Calculate safe OFF limit based on new 12h OT capacity
        safe_off_count = max(0, (total_team_capacity_blocks - daily_block_demand) // 3)

        for d in days:
            # 1. COVERAGE (Hard Brick Wall)
            for b in blocks:
                block_workers = [schedule[(e, d, b)] for e in team_members]
                model.Add(sum(block_workers) >= required_headcount)

            # 2. THE FLEXIBLE BRICK WALL (Now a Soft Penalty to avoid paradox with Thai Law)
            staff_off_today = []
            for eid in team_members:
                is_working_today = model.NewBoolVar(f'{eid}_working_{team_name}_{d.isoformat()}')
                model.AddMaxEquality(is_working_today, [schedule[(eid, d, b)] for b in blocks])
                
                is_off_today = model.NewBoolVar(f'{eid}_off_{team_name}_{d.isoformat()}')
                model.Add(is_off_today == 1 - is_working_today)
                staff_off_today.append(is_off_today)
            
            num_off = model.NewIntVar(0, total_headcount, f'num_off_{team_name}_{d.isoformat()}')
            model.Add(num_off == sum(staff_off_today))
            
            excess_off = model.NewIntVar(0, total_headcount, f'excess_off_{team_name}_{d.isoformat()}')
            model.Add(excess_off >= num_off - safe_off_count)
            context_penalties.append(excess_off * 500000) 
            
            # 3. THE FAIRNESS NUDGE (Soft Penalty)
            num_working = model.NewIntVar(0, total_headcount, f'num_working_cnt_{team_name}_{d.isoformat()}')
            model.Add(num_working == sum([1 - off_var for off_var in staff_off_today]))
            
            extra_workers = model.NewIntVar(0, total_headcount, f'extra_workers_cnt_{team_name}_{d.isoformat()}')
            target_working = max(0, total_headcount - safe_off_count)
            model.Add(extra_workers >= num_working - target_working)
            context_penalties.append(extra_workers * 100)

    # ---------------------------------------------------------
    # HARD CONSTRAINT: The Minimum Rest Rule (11 Hours)
    # ---------------------------------------------------------
    print("🧱 Building Minimum Rest Constraints (11h) across Midnight...")
    employee_ids = list(employee_dict["employees"].keys())
    for emp_id in employee_ids:
        for i in range(len(days) - 1):
            today = days[i]
            tomorrow = days[i + 1]
            model.Add(schedule[(emp_id, today, "20:00")] + schedule[(emp_id, tomorrow, "00:00")] <= 1)
            model.Add(schedule[(emp_id, today, "20:00")] + schedule[(emp_id, tomorrow, "04:00")] <= 1)
            model.Add(schedule[(emp_id, today, "20:00")] + schedule[(emp_id, tomorrow, "08:00")] <= 1)
            model.Add(schedule[(emp_id, today, "16:00")] + schedule[(emp_id, tomorrow, "00:00")] <= 1)
            model.Add(schedule[(emp_id, today, "16:00")] + schedule[(emp_id, tomorrow, "04:00")] <= 1)

    print("✅ Hard Coverage and Minimum Rest Rules applied.")
    return context_penalties
