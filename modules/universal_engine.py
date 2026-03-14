"""
CrewSchd - Universal Math Engine (3-Shapes Architecture)
Consolidated algebraic templates for all operational logic.
"""
import json

def apply_universal_rules(model, schedule, employee_ids, days, blocks, rules_json):
    """
    The Universal Translator.
    """
    # Safely print without unicode for terminal compatibility
    try:
        print(f"📐 UNIVERSAL MATH: Processing {len(rules_json)} rules...")
    except UnicodeEncodeError:
        print(f"[UNIVERSAL MATH] Processing {len(rules_json)} rules...")
    total_penalties = []
    
    for rule in rules_json:
        shape = rule.get("math_shape")
        if shape == "aggregator":
            p = apply_aggregator(model, schedule, employee_ids, days, blocks, rule)
            if p: total_penalties.extend(p)
        elif shape == "rolling_window":
            p = apply_rolling_window(model, schedule, employee_ids, days, blocks, rule)
            if p: total_penalties.extend(p)
        elif shape == "implication":
            p = apply_implication(model, schedule, employee_ids, days, blocks, rule)
            if p: total_penalties.extend(p)
            
    return total_penalties

def apply_aggregator(model, schedule, employee_ids, days, blocks, rule):
    """Shape 1: Aggregator. Handles sums, limits, and headcount."""
    target_group = rule.get("target_group", employee_ids)
    timeframe = rule.get("target_timeframe", "daily")
    op = rule.get("operator", "<=")
    val = rule.get("value", 0)
    scope = rule.get("scope", "individual")
    penalty = rule.get("penalty", None) # If None, it's a Hard Constraint
    
    target_days_names = rule.get("target_days", None) # e.g., ["Saturday", "Sunday"]
    target_block = rule.get("target_block", None) # e.g., "20:00"
    
    penalties = []

    if scope == "individual":
        for eid in target_group:
            if timeframe == "weekly":
                vars_to_sum = []
                for d in days:
                    if target_days_names and d.strftime('%A') not in target_days_names: continue
                    for b in blocks:
                        if target_block and b != target_block: continue
                        vars_to_sum.append(schedule[(eid, d, b)])
                if vars_to_sum:
                    _handle_constraint(model, vars_to_sum, op, val, penalty, penalties, f"{eid}_weekly")
            elif timeframe == "daily":
                t_date = rule.get("target_date")
                for d in days:
                    if t_date and d.isoformat() != t_date: continue
                    if target_days_names and d.strftime('%A') not in target_days_names: continue
                    
                    vars_to_sum = []
                    for b in blocks:
                        if target_block and b != target_block: continue
                        vars_to_sum.append(schedule[(eid, d, b)])
                    if vars_to_sum:
                        _handle_constraint(model, vars_to_sum, op, val, penalty, penalties, f"{eid}_{d.isoformat()}")
            elif timeframe == "working_days":
                # Special logic for counting days worked vs blocks
                daily_vars = []
                for d in days:
                    if target_days_names and d.strftime('%A') not in target_days_names: continue
                    is_working = model.NewBoolVar(f'{eid}_working_{d.isoformat()}_{rule.get("rule_name")}')
                    blocks_to_check = [schedule[(eid, d, b)] for b in blocks if (not target_block or b == target_block)]
                    if blocks_to_check:
                        model.AddMaxEquality(is_working, blocks_to_check)
                        daily_vars.append(is_working)
                if daily_vars:
                    _handle_constraint(model, daily_vars, op, val, penalty, penalties, f"{eid}_wdays")
    
    elif scope == "collective":
        # Headcount logic
        for d in days:
            if target_days_names and d.strftime('%A') not in target_days_names: continue
            
            blocks_to_iterate = [target_block] if target_block else blocks
            for b in blocks_to_iterate:
                if b not in blocks: continue # Safety check
                vars_to_sum = [schedule[(eid, d, b)] for eid in target_group]
                _handle_constraint(model, vars_to_sum, op, val, penalty, penalties, f"coll_{d.isoformat()}_{b}")

    return penalties

def apply_rolling_window(model, schedule, employee_ids, days, blocks, rule):
    """Shape 2: Rolling Window. Handles fatigue and streaks."""
    window = rule.get("window_size", 3)
    limit = rule.get("limit", 2)
    target_group = rule.get("target_group", employee_ids)
    penalty = rule.get("penalty", None)
    
    penalties = []
    for eid in target_group:
        for i in range(len(days) - window + 1):
            window_days = days[i : i + window]
            vars_in_window = [schedule[(eid, d, b)] for d in window_days for b in blocks]
            _handle_constraint(model, vars_in_window, "<=", limit, penalty, penalties, f"{eid}_win_{i}")
    return penalties

def apply_implication(model, schedule, employee_ids, days, blocks, rule):
    """Shape 3: Implication. Handles rest rules and dependencies."""
    if_cond = rule.get("if_condition", {})
    then_enforce = rule.get("then_enforce", {})
    target_group = rule.get("target_group", employee_ids)
    penalty = rule.get("penalty", None)
    
    if_block = if_cond.get("block")
    then_blocks = then_enforce.get("blocks", [then_enforce.get("block")])
    offset = then_enforce.get("offset_days", 0)
    must_equal = then_enforce.get("must_equal", 0)

    penalties = []
    for eid in target_group:
        for i in range(len(days) - offset):
            d_today = days[i]
            d_target = days[i + offset]
            
            for t_block in then_blocks:
                if not t_block: continue
                if penalty is None:
                    model.Add(schedule[(eid, d_target, t_block)] == must_equal).OnlyEnforceIf(schedule[(eid, d_today, if_block)])
                else:
                    # Soft implication: If A worked, and B worked (where B should be 0), apply penalty
                    is_violated = model.NewBoolVar(f'{eid}_imp_viol_{d_today.isoformat()}_{t_block}')
                    # Violation = A worked (1) AND B worked (1)
                    model.AddMultiplicationEquality(is_violated, [schedule[(eid, d_today, if_block)], schedule[(eid, d_target, t_block)]])
                    penalties.append(is_violated * penalty)
    return penalties

def _handle_constraint(model, vars_list, operator, value, penalty, penalty_list, name):
    if penalty is None:
        if operator == "<=": model.Add(sum(vars_list) <= value)
        elif operator == ">=": model.Add(sum(vars_list) >= value)
        elif operator == "==": model.Add(sum(vars_list) == value)
    else:
        if operator == "==":
            if penalty < 0:
                # FIX 2 (Reward Case): Soft Equality Reward (e.g., "Reward exactly 2 blocks")
                is_equal = model.NewBoolVar(f'is_eq_{name}')
                model.Add(sum(vars_list) == value).OnlyEnforceIf(is_equal)
                # The solver will try to set is_equal to 1 to collect the negative penalty (reward).
                penalty_list.append(is_equal * penalty)
            else:
                # Soft Equality Penalty (e.g., "Must be exactly 2 blocks, else penalty")
                shortage = model.NewIntVar(0, 100, f'shortage_{name}')
                excess = model.NewIntVar(0, 100, f'excess_{name}')
                model.Add(sum(vars_list) == value - shortage + excess)
                penalty_list.append((shortage + excess) * penalty)
        else:
            # FIX 1: Infinite Slack Paradox
            if penalty < 0:
                print(f"⚠️ WARNING: Ignored negative penalty ({penalty}) on inequality rule '{name}'. This prevents infinite profit loops.")
                return

            # Create a slack variable for the penalty
            shortage_or_excess = model.NewIntVar(0, 100, f'slack_{name}')
            if operator == ">=":
                model.Add(sum(vars_list) >= value - shortage_or_excess)
            elif operator == "<=":
                model.Add(sum(vars_list) <= value + shortage_or_excess)
            penalty_list.append(shortage_or_excess * penalty)
