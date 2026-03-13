"""
CrewSchd - Master Roster Exporter (Staff-Centric View)
Converts JSON rosters into an easy-to-read staff-vs-day time table with active headcount tracking.
"""

import json
import os
import glob
from datetime import date, timedelta
from dotenv import load_dotenv

# --- CONFIGURATION ---
SHIFT_TIMES = {
    "Morning":  {"in": "05:00", "out": "14:00"},
    "Evening":  {"in": "13:00", "out": "22:00"},
    "Night":    {"in": "21:00", "out": "06:00"},
    "12hDay":   {"in": "08:00", "out": "20:00"},
    "12hNight": {"in": "20:00", "out": "08:00"}
}

import streamlit as st

def get_latest_roster(base_dir, branch="Main Office", team="Cashier"):
    rosters_dir = os.path.join(base_dir, 'Rosters', branch, team)
    if not os.path.exists(rosters_dir): return None
    files = glob.glob(os.path.join(rosters_dir, 'roster_*.json'))
    if not files: return None
    return max(files, key=os.path.getmtime)

def get_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass # Secrets not configured (local dev)
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
    return os.environ.get("GEMINI_API_KEY")

def get_roster_explanation(roster_data, employee_data, weather_data):
    api_key = get_api_key()
    if not api_key: return "Optimized roster following Thai Labor Laws and team isolation logic."

    from google import genai
    client = genai.Client(api_key=api_key)
    
    num_leaves = len(weather_data.get("daily_overrides", []))
    start_date = roster_data["metadata"]["start_date"]
    
    prompt = f"Acting as a Senior Operations Engineer, provide a 2-sentence 'Mathematical Strategy Summary' for this week's roster starting {start_date} handling {num_leaves} absences."
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"AI Summary Error: {e}")
        return "System optimization successfully balanced team coverage against shortages."

def export_perfect_roster(branch="Main Office", team="Cashier"):
    base_dir = os.path.dirname(__file__)
    latest_file = get_latest_roster(base_dir, branch, team)
    if not latest_file: return

    with open(latest_file, 'r') as f: roster = json.load(f)
    jsons_dir = os.path.join(base_dir, 'jsons', branch, team)
    with open(os.path.join(jsons_dir, 'employee.json'), 'r') as f: employees = json.load(f)
    
    weather_path = os.path.join(jsons_dir, 'weather.json')
    if os.path.exists(weather_path):
        with open(weather_path, 'r') as f: weather = json.load(f)
    else:
        weather = {"daily_overrides": []}

    strategy_summary = get_roster_explanation(roster, employees, weather)

    # 1. DATA PREP
    sorted_dates = sorted(roster["assignments"].keys())
    
    # Identify who is on leave this week and find their return date
    leave_map = {} # { emp_name: {"reason": str, "max_date": date} }
    for rule in weather.get("daily_overrides", []):
        rule_type = rule.get("type")
        if rule_type == "block_employee_availability":
            e_name = rule.get("employee")
            d_str = rule.get("date")
            if not d_str or not e_name: continue
            d_obj = date.fromisoformat(d_str)
            
            if e_name not in leave_map:
                leave_map[e_name] = {"reason": rule.get("reason"), "max_date": d_obj}
            else:
                if d_obj > leave_map[e_name]["max_date"]:
                    leave_map[e_name]["max_date"] = d_obj

    # Calculate Active Headcount (Only count staff who are NOT on leave blocks this week)
    team_counts = {}
    # Initialize all teams from employee data to 0
    for e in employees.get("employees", {}).values():
        if e["team"] not in team_counts:
            team_counts[e["team"]] = 0
            
    for eid, e_data in employees.get("employees", {}).items():
        if e_data["name"] not in leave_map:
            team_counts[e_data["team"]] += 1

    # Build Absence List with Expected Return Dates
    absences = []
    for name, data in leave_map.items():
        return_date = data["max_date"] + timedelta(days=1)
        absences.append({
            "name": name, 
            "reason": data["reason"], 
            "return": return_date.strftime('%a %d %b')
        })

    # Sort employees by Team then Name
    all_emp_ids = sorted(employees.get("employees", {}).keys(), key=lambda eid: (employees["employees"][eid]["team"], employees["employees"][eid]["name"]))

    # 2. BUILD HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            :root {{ --primary: #2c3e50; --accent: #3498db; --bg: #f8f9fa; }}
            body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); padding: 30px; margin: 0; }}
            .paper {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); max-width: 1500px; margin: auto; }}
            h1 {{ border-bottom: 2px solid var(--accent); padding-bottom: 15px; margin-bottom: 30px; }}
            
            table.roster {{ width: 100%; border-collapse: collapse; margin-bottom: 40px; border: 1px solid #dee2e6; }}
            .roster th {{ background: var(--primary); color: white; padding: 12px; font-size: 12px; border: 1px solid #34495e; }}
            .roster td {{ border: 1px solid #e1e4e8; padding: 10px; font-size: 13px; text-align: center; }}
            
            /* Team Header Row - Aligned Left */
            .team-row {{ background-color: #34495e !important; color: white !important; font-weight: bold; text-align: left !important; font-size: 14px; letter-spacing: 1px; }}
            
            /* Zebra Striping */
            .staff-row:nth-child(even) {{ background-color: #f8f9fa; }}
            .staff-row:hover {{ background-color: #f0f7ff !important; }}
            
            .emp-name {{ text-align: left !important; font-weight: bold; border-left: 4px solid #ddd; }}
            .team-Cashier .emp-name {{ border-left-color: #3498db; }}
            .team-Service .emp-name {{ border-left-color: #2ecc71; }}
            .team-Admin .emp-name {{ border-left-color: #e67e22; }}
            
            .time-box {{ font-family: 'Courier New', monospace; font-weight: bold; color: #2980b9; }}
            .off {{ color: #bdc3c7; font-weight: normal; font-size: 11px; background-color: #fafafa; }}
            
            .summary-section {{ border-top: 2px dashed #eee; padding-top: 30px; display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }}
            .strategy-box {{ grid-column: span 2; background: #f0f7ff; padding: 20px; border-radius: 8px; font-style: italic; border-left: 5px solid var(--accent); }}
            .card {{ background: #f9fbfd; border: 1px solid #e1e4e8; border-radius: 8px; padding: 20px; }}
            .card h3 {{ margin-top: 0; font-size: 14px; color: #6a737d; text-transform: uppercase; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
            .absent-item {{ background: #fff5f5; border: 1px solid #feb2b2; color: #c53030; padding: 8px 12px; border-radius: 6px; margin-bottom: 10px; font-size: 13px; line-height: 1.4; }}
            .return-date {{ display: block; font-size: 10px; text-transform: uppercase; color: #e53e3e; font-weight: bold; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div class="paper">
            <h1>🛠️ CrewSchd Logistics - Weekly Staff Roster ({branch} -> {team})</h1>

            <table class="roster">
                <thead>
                    <tr>
                        <th style="width: 220px">Staff Member</th>
                        {"".join([f"<th>{date.fromisoformat(d).strftime('%a %d %b')}</th>" for d in sorted_dates])}
                    </tr>
                </thead>
                <tbody>
    """

    current_team_header = None
    for eid in all_emp_ids:
        emp = employees["employees"][eid]
        
        # Insert Team Header Row (even though it's one team, we keep the UI consistent)
        if emp['team'] != current_team_header:
            current_team_header = emp['team']
            html += f"<tr class='team-row'><td colspan='{len(sorted_dates) + 1}' style='text-align: left; padding-left: 20px;'>📦 TEAM: {current_team_header.upper()}</td></tr>"
            
        html += f"<tr class='staff-row team-{emp['team']}'><td class='emp-name'>{emp['name']} <small style='font-weight:normal; opacity:0.6'>({eid})</small></td>"
        
        for d_str in sorted_dates:
            shift_name = roster["assignments"][d_str].get(eid)
            if shift_name:
                t = SHIFT_TIMES[shift_name]
                html += f"<td><div class='time-box'>{t['in']} - {t['out']}</div><div style='font-size:9px; color:#95a5a6'>{shift_name}</div></td>"
            else:
                html += "<td class='off'>— OFF —</td>"
        html += "</tr>"

    html += f"""
                </tbody>
            </table>

            <div class="summary-section">
                <div class="strategy-box">
                    <strong>💡 Operations Strategy Summary:</strong><br>
                    {strategy_summary}
                </div>
                
                <div class="card">
                    <h3>Available Headcount (No Leaves)</h3>
                    <table style="width:100%; font-size: 13px;">
                        {"".join([f"<tr><td>{t}</td><td style='text-align:right'><b>{c} Staff</b></td></tr>" for t, c in sorted(team_counts.items())])}
                    </table>
                </div>

                <div class="card">
                    <h3>Absent Tracking & Recovery</h3>
                    {"".join([f"<div class='absent-item'><b>{a['name']}</b>: {a['reason']}<span class='return-date'>Expected Return: {a['return']}</span></div>" for a in absences]) if absences else "No active absences reported."}
                </div>
            </div>

            <p style="text-align:center; color: #999; font-size: 11px; margin-top:40px;">
                CONFIDENTIAL ROSTER - Thai Labor Protection Act Compliant
            </p>
        </div>
    </body>
    </html>
    """

    output_path = os.path.join(base_dir, f'Perfect_Roster_View_{branch.replace(" ", "_")}_{team.replace(" ", "_")}.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✨ UPDATED STAFF-CENTRIC ROSTER for {branch}/{team}: Created at {output_path}")

if __name__ == "__main__":
    export_perfect_roster()
