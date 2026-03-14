import os
import sys
import json
from datetime import date
from unittest.mock import MagicMock, patch

# Add paths
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, 'modules'))

from Translator import translate_weather_to_json, translate_rule_to_json
from roster_engine import generate_roster

def test_translators():
    print("--- 🤖 Testing AI Translators (Logic Only) ---")
    mock_api_key = "AIza_test_key"
    context = {
        "current_roster": "{}",
        "employees": "{}",
        "branch": "Main Office",
        "team": "Cashier"
    }
    
    # We mock the Gemini client to avoid actual API calls but test our wrapping logic
    with patch('google.genai.Client') as mock_client:
        mock_response = MagicMock()
        mock_response.text = json.dumps({"overrides": [{"type": "block", "employee": "Test", "date": "2026-03-14", "reason": "Sick"}]})
        mock_client.return_value.models.generate_content.return_value = mock_response
        
        # Test Weather
        print("Testing Weather Translator wrapper...")
        res = translate_weather_to_json("someone is sick", mock_api_key, json.dumps(context))
        if "overrides" in res:
            print("✅ Weather Translator logic verified.")
        else:
            print(f"❌ Weather Translator logic failed: {res}")

        # Test Policy
        mock_response.text = json.dumps({"rule_name": "Test Rule", "math_shape": "aggregator"})
        print("Testing Policy Architect wrapper...")
        res = translate_rule_to_json("make a test rule", mock_api_key, "[]")
        if "rule_name" in res:
            print("✅ Policy Architect logic verified.")
        else:
            print(f"❌ Policy Architect logic failed: {res}")

def test_roster_engine():
    print("\n--- ⚙️ Testing Roster Engine (Dry Run) ---")
    # We'll try to generate a roster for the existing Cashier team
    # This verifies file loading, global business context, and Thai law integration
    try:
        print("Executing generate_roster for Main Office -> Cashier...")
        status = generate_roster(start_date=date.today(), branch="Main Office", team="Cashier")
        if status in ["FEASIBLE", "OPTIMAL"]:
            print(f"✅ Roster Engine SUCCESS: Status is {status}")
        elif status == "INFEASIBLE":
            print("⚠️ Roster Engine returned INFEASIBLE (This is a valid engine result, not a code crash)")
        else:
            print(f"❌ Roster Engine failed with unexpected status: {status}")
    except Exception as e:
        print(f"💥 Roster Engine CRASHED: {e}")
        import traceback
        traceback.print_exc()

def test_auto_healer():
    print("\n--- 🚑 Testing Auto-Healer (Disruption Management) ---")
    try:
        from roster_engine import run_auto_healer
        import glob
        
        # Load the latest roster to use as a base
        rosters_dir = os.path.join(base_dir, 'Rosters', 'Main Office', 'Service')
        files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
        if not files:
            print("⚠️ Skipping Auto-Heal test: No roster files found for Service.")
            
            # Generate a roster first so we have something to heal
            print("Generating a base roster for Service...")
            from roster_engine import generate_roster
            generate_roster(start_date=date.today(), branch="Main Office", team="Service")
            files = sorted(glob.glob(os.path.join(rosters_dir, 'roster_*.json')), key=os.path.getmtime)
            if not files:
                return
            
        with open(files[-1], 'r', encoding='utf-8') as f: 
            base_roster = json.load(f)
            
        # Find a day and an employee who is working
        target_date = "2026-03-16"
        sick_eid = "EMP004"
        
        if target_date not in base_roster.get("assignments", {}) or sick_eid not in base_roster["assignments"][target_date]:
            print("⚠️ Skipping Auto-Heal test: Target date or employee not in roster.")
            return
            
        print(f"Testing Auto-Heal for Date: {target_date}, Sick EID: {sick_eid}")
        candidates = run_auto_healer(target_date, sick_eid, "Main Office", "Service", base_roster)
        
        if candidates:
            print(f"✅ Auto-Healer logic verified. Found {len(candidates)} legal candidates.")
            for c in candidates:
                print(f"  - {c['name']} (Score: {c['score']})")
        else:
            print("⚠️ Auto-Healer found 0 legal candidates. This is mathematically possible but check logic.")
            
    except Exception as e:
        print(f"💥 Auto-Healer CRASHED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ensure we are in the right directory
    os.chdir(base_dir)
    
    test_translators()
    test_roster_engine()
    test_auto_healer()
