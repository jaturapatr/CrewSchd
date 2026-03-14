"""
CrewSchd - Persistence & History Module
Handles the 'Law of Nature': past locks and future anchors.
Supports both legacy shift names and new 4h block lists.
"""
import json
import os
import glob
from datetime import date, timedelta

# Mapping for backward compatibility
SHIFT_TO_BLOCKS = {
    "Morning": ["08:00", "12:00"],
    "Evening": ["16:00", "20:00"],
    "Night": ["20:00", "00:00"],
    "12hDay": ["08:00", "12:00", "16:00"], # Approx
    "12hNight": ["20:00", "00:00", "04:00"], # Approx
    "—": [],
    "OFF": []
}

def normalize_to_blocks(val):
    """Converts legacy shift strings or block lists into a set of blocks."""
    if isinstance(val, list):
        return set(val)
    if isinstance(val, str):
        # Handle case where val might be "☀️ Morning" or just "Morning"
        clean_val = val.split(" ")[-1] if " " in val else val
        return set(SHIFT_TO_BLOCKS.get(clean_val, []))
    return set()

def apply_history_constraints(model, schedule, employee_ids, start_date, blocks, rosters_dir):
    """
    Loads yesterday's roster to handle turnaround constraints.
    """
    yesterday = start_date - timedelta(days=1)
    
    history_files = glob.glob(os.path.join(rosters_dir, f'roster_{yesterday.isoformat()}_*.json'))
    if history_files:
        history_file = max(history_files, key=os.path.getmtime)
        print(f"📜 Loading history from {os.path.basename(history_file)}...")
        with open(history_file, 'r') as f:
            history_data = json.load(f)
            
        for e_id in employee_ids:
            raw_val = history_data.get("assignments", {}).get(yesterday.isoformat(), {}).get(e_id, [])
            last_blocks = normalize_to_blocks(raw_val)
            
            # 11 hours rest after 20:00-00:00 means they can't work 00:00, 04:00 or 08:00 today.
            if "20:00" in last_blocks:
                today = start_date
                model.Add(schedule[(e_id, today, "00:00")] == 0)
                model.Add(schedule[(e_id, today, "04:00")] == 0)
                model.Add(schedule[(e_id, today, "08:00")] == 0)
                print(f"  - Restricted {e_id} from early blocks today due to last night's work.")
    else:
        print(f"🌅 No history found in {rosters_dir}. Starting with a clean slate.")

def apply_persistence_locks(model, schedule, employee_ids, days, blocks, rosters_dir):
    """
    STABILITY ENGINE: Prevents changes to the past and discourages changes to the future.
    Now handles both old and new data formats.
    """
    today = date.today()
    
    past_assignments = {}   # { "date": { "emp": set(blocks) } }
    future_anchors = {}     # { "date": { "emp": set(blocks) } }
    
    if not os.path.exists(rosters_dir):
        os.makedirs(rosters_dir)
        
    roster_files = glob.glob(os.path.join(rosters_dir, 'roster_*.json'))
    for f_path in roster_files:
        try:
            with open(f_path, 'r') as f:
                data = json.load(f)
                assignments = data.get("assignments", {})
                for d_str, emps in assignments.items():
                    d_obj = date.fromisoformat(d_str)
                    
                    # Normalize all employees for this day
                    norm_emps = {eid: normalize_to_blocks(val) for eid, val in emps.items()}
                    
                    if d_obj < today:
                        if d_str not in past_assignments: past_assignments[d_str] = norm_emps
                    else:
                        if d_str not in future_anchors: future_anchors[d_str] = norm_emps
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            continue

    # 1. Apply Hard Locks (The Past)
    if past_assignments:
        print(f"🔒 THE LAW OF NATURE: Hard-locking {len(past_assignments)} days of history...")
        for d_str, day_history in past_assignments.items():
            d_obj = date.fromisoformat(d_str)
            if d_obj in days:
                for e_id in employee_ids:
                    past_blocks_set = day_history.get(e_id, set())
                    for b in blocks:
                        model.Add(schedule[(e_id, d_obj, b)] == (1 if b in past_blocks_set else 0))

    # 2. Apply Soft Anchors (The Future Stability)
    consistency_penalties = []
    if future_anchors:
        print(f"⚓ STABILITY ANCHOR: Protecting future block assignments in {rosters_dir}...")
        for d_str, day_future in future_anchors.items():
            d_obj = date.fromisoformat(d_str)
            if d_obj in days:
                for e_id in employee_ids:
                    old_blocks_set = day_future.get(e_id, set())
                    for b in blocks:
                        is_changed = model.NewBoolVar(f'changed_{e_id}_{d_str}_{b}')
                        old_val = 1 if b in old_blocks_set else 0
                        model.Add(schedule[(e_id, d_obj, b)] != old_val).OnlyEnforceIf(is_changed)
                        model.Add(schedule[(e_id, d_obj, b)] == old_val).OnlyEnforceIf(is_changed.Not())
                        consistency_penalties.append(is_changed * 10000)

    return consistency_penalties
