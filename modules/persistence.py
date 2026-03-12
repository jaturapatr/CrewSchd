"""
CrewSchd - Persistence & History Module
Handles the 'Law of Nature': past locks and future anchors.
"""
import json
import os
import glob
from datetime import date, timedelta

def apply_history_constraints(model, schedule, employee_ids, start_date, shifts):
    """
    Loads yesterday's roster to handle turnaround constraints.
    """
    yesterday = start_date - timedelta(days=1)
    base_dir = os.path.dirname(os.path.dirname(__file__))
    rosters_dir = os.path.join(base_dir, 'Rosters')
    
    # Find the LATEST version of yesterday's roster
    history_files = glob.glob(os.path.join(rosters_dir, f'roster_{yesterday.isoformat()}_*.json'))
    if history_files:
        history_file = max(history_files, key=os.path.getmtime)
        print(f"📜 Loading history from {os.path.basename(history_file)}...")
        with open(history_file, 'r') as f:
            history_data = json.load(f)
            
        for e_id in employee_ids:
            last_shift = history_data.get("assignments", {}).get(yesterday.isoformat(), {}).get(e_id)
            
            if last_shift in ['Night', '12hNight']:
                today = start_date
                model.Add(schedule[(e_id, today, 'Morning')] == 0)
                model.Add(schedule[(e_id, today, '12hDay')] == 0)
                print(f"  - Restricted {e_id} from early shifts today due to last night's work.")
    else:
        print("🌅 No history found. Starting with a clean slate.")

def apply_persistence_locks(model, schedule, employee_ids, days, shifts, base_dir):
    """
    STABILITY ENGINE:
    1. HARD LOCKS (Past): Dates before today cannot be changed.
    2. SOFT ANCHORS (Future): Dates today or later are "preferred" to stay the same.
    """
    today = date.today()
    
    past_assignments = {}   # { "date": { "emp": "shift" } }
    future_anchors = {}     # { "date": { "emp": "shift" } }
    
    rosters_dir = os.path.join(base_dir, 'Rosters')
    roster_files = glob.glob(os.path.join(rosters_dir, 'roster_*.json'))
    for f_path in roster_files:
        try:
            with open(f_path, 'r') as f:
                data = json.load(f)
                assignments = data.get("assignments", {})
                for d_str, emps in assignments.items():
                    d_obj = date.fromisoformat(d_str)
                    if d_obj < today:
                        if d_str not in past_assignments: past_assignments[d_str] = emps
                    else:
                        if d_str not in future_anchors: future_anchors[d_str] = emps
        except:
            continue

    # 1. Apply Hard Locks (The Past)
    if past_assignments:
        print(f"🔒 THE LAW OF NATURE: Hard-locking {len(past_assignments)} days of history...")
        for d_str, day_history in past_assignments.items():
            d_obj = date.fromisoformat(d_str)
            if d_obj in days:
                for e_id in employee_ids:
                    past_shift = day_history.get(e_id)
                    for s in shifts:
                        model.Add(schedule[(e_id, d_obj, s)] == (1 if s == past_shift else 0))

    # 2. Apply Soft Anchors (The Future Stability)
    consistency_penalties = []
    if future_anchors:
        print(f"⚓ STABILITY ANCHOR: Found {len(future_anchors)} days of future assignments to protect...")
        for d_str, day_future in future_anchors.items():
            d_obj = date.fromisoformat(d_str)
            if d_obj in days:
                for e_id in employee_ids:
                    old_shift = day_future.get(e_id)
                    if old_shift:
                        is_changed = model.NewBoolVar(f'changed_{e_id}_{d_str}')
                        model.Add(schedule[(e_id, d_obj, old_shift)] == 0).OnlyEnforceIf(is_changed)
                        model.Add(schedule[(e_id, d_obj, old_shift)] == 1).OnlyEnforceIf(is_changed.Not())
                        consistency_penalties.append(is_changed * 10000)

    return consistency_penalties
