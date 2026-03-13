"""
Bee Colony - Weather Translator Module
Translates natural language managerial requests into structured JSON constraints
for the operations research math engine using the Gemini API.
"""

import os
import json
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

def translate_weather_to_json(user_input: str, api_key: str) -> list:
    """
    Takes a natural language request from a manager and uses the Gemini API 
    to translate it into a strict, predictable JSON array of rule overrides.
    
    Args:
        user_input (str): The natural language request (e.g., "Kwang called in sick for Monday").
        api_key (str): Your Google AI Studio API key.
        
    Returns:
        list: A Python list of dictionaries representing the extracted constraints.
    """
    try:
        # 1. Initialize the API
        genai.configure(api_key=api_key)
        
        # 2. Define the System Prompt
        # Acts as a strict Operations Research JSON parser, categorizing requests
        # and providing few-shot examples for exact schema mapping.
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
        
        EXAMPLES:
        User: "Kwang called in sick for Monday"
        Output: [{"constraint_class": "block_employee_availability", "target_employee": "Kwang", "target_date": "Monday", "reason": "Called in sick"}]
        
        User: "We need at least 3 people on the Afternoon shift this Friday because of the festival."
        Output: [{"constraint_class": "force_minimum_headcount", "target_date": "Friday", "target_shift": "Afternoon", "required_value": 3, "reason": "Festival surge"}]
        
        User: "Make sure Alice works the Morning shift tomorrow, and Bob cannot work at all."
        Output: [
            {"constraint_class": "require_specific_shift", "target_employee": "Alice", "target_date": "tomorrow", "target_shift": "Morning", "reason": "Manager request"},
            {"constraint_class": "block_employee_availability", "target_employee": "Bob", "target_date": "tomorrow", "reason": "Manager request"}
        ]
        """

        # 3. Initialize the ultra-fast Gemini 2.5 Flash model
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        
        # 4. Enforce Structured Output
        # Physically force the API to return valid JSON
        config = GenerationConfig(
            response_mime_type="application/json"
        )
        
        # 5. Generate the response
        response = model.generate_content(
            user_input,
            generation_config=config
        )
        
        # 6. Error Handling & Parsing
        # Safely parse the API response string into a Python list
        constraints = json.loads(response.text)
        return constraints
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from Gemini: {e}")
        # In case of decode error, response.text might still be accessible
        try:
            print(f"Raw output: {response.text}")
        except:
            pass
        return []
    except Exception as e:
        print(f"An error occurred during API communication: {e}")
        return []

def translate_policy_to_json(user_input: str, api_key: str, current_policies: dict) -> dict:
    """
    Translates natural language policy requests into the `company_policies.json` structure.
    """
    try:
        genai.configure(api_key=api_key)
        
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
        
        INSTRUCTIONS:
        1. If the user wants to update an existing policy penalty, modify the 'penalty' value.
        2. If the user wants to create a new policy, suggest a new key and structure.
        3. Return the COMPLETE updated `optimization_targets` object.
        4. If the request is unclear, return the current policies with a 'message' field explaining why.
        """

        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        
        config = GenerationConfig(
            response_mime_type="application/json"
        )
        
        response = model.generate_content(
            user_input,
            generation_config=config
        )
        
        return json.loads(response.text)
        
    except Exception as e:
        print(f"Policy translation error: {e}")
        return current_policies.get("optimization_targets", {})

if __name__ == "__main__":
    from dotenv import load_dotenv
    import os

    # Load environment variables from the .env file in the root directory
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path=env_path)

    api_key = os.environ.get("GEMINI_API_KEY")
    
    if api_key:
        test_input = "Kwang called in sick for Monday, and we need 4 people for the Night shift on Tuesday."
        print(f"Testing input: '{test_input}'")
        
        result = translate_weather_to_json(test_input, api_key)
        
        print("\nExtracted JSON:")
        print(json.dumps(result, indent=2))
    else:
        print("Please set your GEMINI_API_KEY in the .env file to test the script directly.")
