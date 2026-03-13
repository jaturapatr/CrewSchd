import os
import sys
import json
from datetime import date
from unittest.mock import MagicMock, patch

# Add paths
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(base_dir, 'modules'))

from Translator import translate_weather_to_json, translate_policy_to_json
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
        res = translate_weather_to_json("someone is sick", mock_api_key, context)
        if "overrides" in res:
            print("✅ Weather Translator logic verified.")
        else:
            print(f"❌ Weather Translator logic failed: {res}")

        # Test Policy
        mock_response.text = json.dumps({"skeleton_night_crew": {"penalty": 5000}})
        print("Testing Policy Architect wrapper...")
        res = translate_policy_to_json("increase night penalty", mock_api_key, {}, context)
        if "skeleton_night_crew" in res:
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

if __name__ == "__main__":
    # Ensure we are in the right directory
    os.chdir(base_dir)
    
    test_translators()
    test_roster_engine()
