"""
CrewSchd - Business Policies Module
Handles soft constraints and optimization penalties for 4h blocks.
"""

def apply_business_policies(model, schedule, days, blocks, policies_dict, employee_dict):
    print("📈 Applying CEO Policies for 4h blocks...")
    employee_ids = list(employee_dict["employees"].keys())
    total_penalty_score = 0

    opt_targets = policies_dict.get("optimization_targets", {})

    # POLICY 1: Prefer 8h (2 blocks) over 4h (1 block)
    # Penalty if working exactly 1 block in a day
    # Penalty if working exactly 3 blocks in a day (OT Surcharge)
    for emp_id in employee_ids:
        for d in days:
            daily_sum = sum(schedule[(emp_id, d, b)] for b in blocks)
            
            # --- 4h Day Penalty (Inefficiency) ---
            is_4h_day = model.NewBoolVar(f'{emp_id}_4h_day_{d.isoformat()}')
            model.Add(daily_sum == 1).OnlyEnforceIf(is_4h_day)
            model.Add(daily_sum != 1).OnlyEnforceIf(is_4h_day.Not())
            total_penalty_score += (is_4h_day * 5000)
            
            # --- 12h Day Penalty (Emergency OT Surcharge) ---
            is_12h_day = model.NewBoolVar(f'{emp_id}_12h_day_{d.isoformat()}')
            model.Add(daily_sum == 3).OnlyEnforceIf(is_12h_day)
            model.Add(daily_sum != 3).OnlyEnforceIf(is_12h_day.Not())
            total_penalty_score += (is_12h_day * 50000)

    # POLICY 2: Maximize Weekend Firepower
    rule_weekend = opt_targets.get("maximize_weekend_firepower", {})
    if rule_weekend:
        penalty_weekend_off = 500
        target_day_names = rule_weekend.get("target_days", ["Saturday", "Sunday"])
        for emp_id in employee_ids:
            took_weekend_off = model.NewBoolVar(f'{emp_id}_weekend_off')
            weekend_blocks = []
            for d in days:
                if d.strftime('%A') in target_day_names:
                    weekend_blocks.extend([schedule[(emp_id, d, b)] for b in blocks])
            if weekend_blocks:
                model.Add(sum(weekend_blocks) == 0).OnlyEnforceIf(took_weekend_off)
                model.Add(sum(weekend_blocks) > 0).OnlyEnforceIf(took_weekend_off.Not())
                total_penalty_score += (took_weekend_off * penalty_weekend_off)

    # POLICY 3: Fatigue Shield (Soft)
    # Penalty for working 2+ blocks for many consecutive days
    for emp_id in employee_ids:
        for i in range(len(days) - 3): # 4-day window
            window = [days[i+j] for j in range(4)]
            is_heavy_streak = model.NewBoolVar(f'{emp_id}_heavy_streak_{window[0].isoformat()}')
            daily_heavy = []
            for d in window:
                h = model.NewBoolVar(f'{emp_id}_h_{d.isoformat()}')
                # Heavy is 2 or 3 blocks
                model.Add(sum(schedule[(emp_id, d, b)] for b in blocks) >= 2).OnlyEnforceIf(h)
                model.Add(sum(schedule[(emp_id, d, b)] for b in blocks) < 2).OnlyEnforceIf(h.Not())
                daily_heavy.append(h)
            model.Add(sum(daily_heavy) == 4).OnlyEnforceIf(is_heavy_streak)
            model.Add(sum(daily_heavy) < 4).OnlyEnforceIf(is_heavy_streak.Not())
            total_penalty_score += (is_heavy_streak * 10000)

    # POLICY 4: Overall Workload Fairness (Block-based)
    employee_block_totals = {}
    for emp_id in employee_ids:
        total_blocks = model.NewIntVar(0, len(days) * 3, f'total_blocks_{emp_id}')
        model.Add(total_blocks == sum(schedule[(emp_id, d, b)] for d in days for b in blocks))
        employee_block_totals[emp_id] = total_blocks

    if len(employee_block_totals) > 1:
        min_b = model.NewIntVar(0, len(days) * 3, 'min_blocks')
        max_b = model.NewIntVar(0, len(days) * 3, 'max_blocks')
        model.AddMinEquality(min_b, list(employee_block_totals.values()))
        model.AddMaxEquality(max_b, list(employee_block_totals.values()))
        block_gap = model.NewIntVar(0, len(days) * 3, 'block_gap')
        model.Add(block_gap == max_b - min_b)
        total_penalty_score += (block_gap * 2000)

    print("✅ CEO Policies mapped successfully for blocks.")
    return total_penalty_score
