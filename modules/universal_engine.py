"""
CrewSchd - Universal Math Engine (3-Shapes Architecture)
Consolidated algebraic templates for all operational logic.
"""
import json

def apply_universal_rules(model, schedule, employee_ids, days, blocks, rules_json, diagnostic_mode=False):
    """
    The Universal Translator.
    Returns a list of (CP-SAT variable, human_readable_name) tuples for all active rules.
    """
    try:
        if not diagnostic_mode:
            print(f"📐 UNIVERSAL MATH: Processing {len(rules_json)} rules...")
    except UnicodeEncodeError:
        if not diagnostic_mode:
            print(f"[UNIVERSAL MATH] Processing {len(rules_json)} rules...")
            
    all_rule_vars = []
    
    for rule in rules_json:
        shape = rule.get("math_shape")
        if shape == "aggregator":
            p = apply_aggregator(model, schedule, employee_ids, days, blocks, rule, diagnostic_mode)
            if p: all_rule_vars.extend(p)
        elif shape == "rolling_window":
            p = apply_rolling_window(model, schedule, employee_ids, days, blocks, rule, diagnostic_mode)
            if p: all_rule_vars.extend(p)
        elif shape == "implication":
            p = apply_implication(model, schedule, employee_ids, days, blocks, rule, diagnostic_mode)
            if p: all_rule_vars.extend(p)
            
    return all_rule_vars

def apply_aggregator(model, schedule, employee_ids, days, blocks, rule, diag=False):
    target_group = rule.get("target_group", employee_ids)
    timeframe = rule.get("target_timeframe", "daily")
    op = rule.get("operator", "<=")
    val = rule.get("value", 0)
    scope = rule.get("scope", "individual")
    penalty = rule.get("penalty", None)
    
    # In diagnostic mode, hard constraints become very high penalties
    if diag and penalty is None:
        penalty = 1000000 
    
    target_days_names = rule.get("target_days", None)
    target_block = rule.get("target_block", None)
    rule_name = rule.get("rule_name", "Unnamed Aggregator")
    
    rule_vars = []

    if scope == "individual":
        for eid in target_group:
            vars_to_sum = []
            if timeframe == "weekly":
                for d in days:
                    if target_days_names and d.strftime('%A') not in target_days_names: continue
                    for b in blocks:
                        if target_block and b != target_block: continue
                        vars_to_sum.append(schedule[(eid, d, b)])
                if vars_to_sum:
                    _handle_constraint(model, vars_to_sum, op, val, penalty, rule_vars, f"{rule_name}_{eid}", diag)
            elif timeframe == "daily":
                t_date = rule.get("target_date")
                for d in days:
                    if t_date and d.isoformat() != t_date: continue
                    if target_days_names and d.strftime('%A') not in target_days_names: continue
                    vars_to_sum = [schedule[(eid, d, b)] for b in blocks if not target_block or b == target_block]
                    if vars_to_sum:
                        _handle_constraint(model, vars_to_sum, op, val, penalty, rule_vars, f"{rule_name}_{eid}_{d.isoformat()}", diag)
            elif timeframe == "working_days":
                daily_vars = []
                for d in days:
                    if target_days_names and d.strftime('%A') not in target_days_names: continue
                    is_working = model.NewBoolVar(f'wd_{eid}_{d.isoformat()}_{rule_name}')
                    blocks_to_check = [schedule[(eid, d, b)] for b in blocks if (not target_block or b == target_block)]
                    if blocks_to_check:
                        model.AddMaxEquality(is_working, blocks_to_check)
                        daily_vars.append(is_working)
                if daily_vars:
                    _handle_constraint(model, daily_vars, op, val, penalty, rule_vars, f"{rule_name}_{eid}_wdays", diag)
    
    elif scope == "collective":
        for d in days:
            if target_days_names and d.strftime('%A') not in target_days_names: continue
            blocks_to_iterate = [target_block] if target_block else blocks
            for b in blocks_to_iterate:
                if b not in blocks: continue
                vars_to_sum = [schedule[(eid, d, b)] for eid in target_group]
                _handle_constraint(model, vars_to_sum, op, val, penalty, rule_vars, f"{rule_name}_{d.isoformat()}_{b}", diag)

    return [(v, rule_name) for v in rule_vars]

def apply_rolling_window(model, schedule, employee_ids, days, blocks, rule, diag=False):
    window = rule.get("window_size", 3)
    limit = rule.get("limit", 2)
    target_group = rule.get("target_group", employee_ids)
    penalty = rule.get("penalty", None)
    rule_name = rule.get("rule_name", "Unnamed Window")
    if diag and penalty is None: penalty = 1000000
    
    rule_vars = []
    for eid in target_group:
        for i in range(len(days) - window + 1):
            window_days = days[i : i + window]
            vars_in_window = [schedule[(eid, d, b)] for d in window_days for b in blocks]
            _handle_constraint(model, vars_in_window, "<=", limit, penalty, rule_vars, f"{rule_name}_{eid}_win_{i}", diag)
    return [(v, rule_name) for v in rule_vars]

def apply_implication(model, schedule, employee_ids, days, blocks, rule, diag=False):
    if_cond = rule.get("if_condition", {})
    then_enforce = rule.get("then_enforce", {})
    target_group = rule.get("target_group", employee_ids)
    penalty = rule.get("penalty", None)
    rule_name = rule.get("rule_name", "Unnamed Implication")
    if diag and penalty is None: penalty = 1000000
    
    if_block = if_cond.get("block")
    then_blocks = then_enforce.get("blocks", [then_enforce.get("block")])
    offset = then_enforce.get("offset_days", 0)
    must_equal = then_enforce.get("must_equal", 0)

    rule_vars = []
    for eid in target_group:
        for i in range(len(days) - offset):
            d_today = days[i]
            d_target = days[i + offset]
            for t_block in then_blocks:
                if not t_block: continue
                if penalty is None:
                    model.Add(schedule[(eid, d_target, t_block)] == must_equal).OnlyEnforceIf(schedule[(eid, d_today, if_block)])
                else:
                    is_viol = model.NewBoolVar(f'viol_{rule_name}_{eid}_{d_today.isoformat()}_{t_block}')
                    if must_equal == 0:
                        model.AddMultiplicationEquality(is_viol, [schedule[(eid, d_today, if_block)], schedule[(eid, d_target, t_block)]])
                    else:
                        model.Add(is_viol >= schedule[(eid, d_today, if_block)] - schedule[(eid, d_target, t_block)])
                    rule_vars.append(is_viol * penalty)
    return [(v, rule_name) for v in rule_vars]

def _handle_constraint(model, vars_list, operator, value, penalty, rule_vars, name, diag):
    safe_name = "".join(c for c in name if c.isalnum() or c == "_")
    
    if penalty is None:
        if operator == "<=": model.Add(sum(vars_list) <= value)
        elif operator == ">=": model.Add(sum(vars_list) >= value)
        elif operator == "==": model.Add(sum(vars_list) == value)
    else:
        if operator == "==":
            if penalty < 0:
                is_equal = model.NewBoolVar(f'is_eq_{safe_name}')
                model.Add(sum(vars_list) == value).OnlyEnforceIf(is_equal)
                rule_vars.append(is_equal * penalty)
            else:
                sh = model.NewIntVar(0, 100, f'sh_{safe_name}')
                ex = model.NewIntVar(0, 100, f'ex_{safe_name}')
                model.Add(sum(vars_list) == value - sh + ex)
                rule_vars.append((sh + ex) * penalty)
        else:
            if penalty < 0: return
            slack = model.NewIntVar(0, 100, f'sl_{safe_name}')
            if operator == ">=":
                model.Add(sum(vars_list) >= value - slack)
            elif operator == "<=":
                model.Add(sum(vars_list) <= value + slack)
            rule_vars.append(slack * penalty)
