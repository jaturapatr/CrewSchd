"""
Bee Colony - Weather Translator Module
Translates natural language managerial requests into structured JSON constraints
for the operations research math engine using the Gemini API.
"""

import os
import json
from google import genai
from google.genai import types

def translate_weather_to_json(user_input: str, api_key: str) -> list:
    """
    Takes a natural language request from a manager and uses the Gemini API 
    to translate it into a strict, predictable JSON array of rule overrides.
    """
    try:
        client = genai.Client(api_key=api_key)
        
        system_instruction = """
        You are the 'Weather Translator' for the Bee Colony scheduling system.
        Your job is to parse natural language requests from managers and translate them into a strict JSON array of constraint objects.
        
        ALLOWED constraint_class VALUES:
        - "block_employee_availability": Use when someone cannot work (sick, leave, vacation).
        - "force_minimum_headcount": Use when a specific shift needs extra people.
        - "require_specific_shift": Use when an employee MUST work a specific shift.
        
        JSON SCHEMA:
        You must return a JSON array containing objects with the following keys. Omit keys if they do not apply.
        - constraint_class (string, required)
        - target_employee (string, optional)
        - target_date (string, optional: e.g., "Monday", "2023-10-24")
        - target_shift (string, optional: e.g., "Morning", "Afternoon", "Night")
        - required_value (integer, optional: e.g., for minimum headcount)
        - reason (string, required: a brief explanation)
        """

        response = client.models.generate_content(
            model='gemini-2.0-flash', # Standardizing on Flash 2.0
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json"
            ),
            contents=user_input
        )
        
        return json.loads(response.text)
        
    except Exception as e:
        print(f"Weather translation error: {e}")
        return []

def translate_policy_to_json(user_input: str, api_key: str, current_policies: dict) -> dict:
    """
    Translates natural language policy requests into the `company_policies.json` structure.
    """
    try:
        client = genai.Client(api_key=api_key)
        
        system_instruction = f"""
        You are the 'Policy Architect' for the CrewSchd system.
        Your job is to parse natural language requests from admins and update the `company_policies.json` structure.
        
        CURRENT POLICIES:
        {json.dumps(current_policies, indent=2)}
        
        ALLOWED POLICY TYPES (optimization_targets keys):
        - skeleton_night_crew: Target specific shift and headcount.
        - maximize_weekend_firepower: Target specific days (e.g. Saturday, Sunday).
        - penalize_clopen_rotation: Penalize specific shift sequences.
        - prioritize_cheap_labor: Penalize specific employee tiers working over a limit.
        - max_consecutive_same_shifts: Limit consecutive shifts of the same type.
        - force_team_utilization: Ensure a team works a certain number of days.
        
        JSON SCHEMA for optimization_targets:
        Each target should have a descriptive key (snake_case) and include:
        - For headcount targets: target_shift, ideal_headcount, penalty_per_extra_person
        - For day targets: target_days (list), penalty_for_full_weekend_off (or similar)
        - For sequence targets: shift_1, shift_2_next_day, penalty_per_occurrence
        - For labor targets: tier_to_penalize, standard_days_allowed, penalty_per_extra_day
        - For limit targets: limit, penalty_per_occurrence
        - For team targets: team, target_days, penalty_per_day_under
        """

        response = client.models.generate_content(
            model='gemini-2.0-flash',
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json"
            ),
            contents=user_input
        )
        
        return json.loads(response.text)
        
    except Exception as e:
        print(f"Policy translation error: {e}")
        return current_policies.get("optimization_targets", {})

if __name__ == "__main__":
    from dotenv import load_dotenv
    # Load environment variables
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path=env_path)

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        test_input = "Kwang called in sick for Monday."
        print(f"Testing input: '{test_input}'")
        result = translate_weather_to_json(test_input, api_key)
        print("\nExtracted JSON:")
        print(json.dumps(result, indent=2))
