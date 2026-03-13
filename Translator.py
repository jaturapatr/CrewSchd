"""
Bee Colony - AI Translator Module
Translates natural language managerial requests into structured JSON 
for Operational Overrides (Weather).
"""

import os
import json
from datetime import date
from google import genai
from google.genai import types

def translate_weather_to_json(user_input: str, api_key: str, context: dict) -> dict:
    """
    Translates natural language requests (e.g., 'Fai is sick tomorrow') 
    into a structured 'overrides' JSON for the roster engine.
    """
    try:
        client = genai.Client(api_key=api_key)
        
        today = date.today()
        today_str = today.isoformat()
        today_name = today.strftime('%A')
        
        system_instruction = f"""
        You are the 'Operations Hub' for CrewSchd. 
        TODAY IS: {today_str} ({today_name})
        
        CONTEXT (JSON):
        - Current Roster: {context.get('current_roster', 'None')}
        - Employees: {context.get('employees', 'None')}
        - Branch: {context.get('branch', 'Unknown')}
        - Team: {context.get('team', 'Unknown')}

        YOUR PROTOCOL:
        1. Calculate relative dates (tomorrow, next Monday) based on TODAY.
        2. Identify employees by Name (from the Employees context).
        3. If the request is a scheduling change, return ONLY a JSON object with an 'overrides' key.
        4. If it's a question, answer concisely.

        OVERRIDE SCHEMA:
        {{
          "overrides": [
            {{
              "type": "block_employee_availability", 
              "employee": "Name", 
              "date": "YYYY-MM-DD", 
              "reason": "Sick/Vacation"
            }}
          ]
        }}
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json"
            ),
            contents=user_input
        )
        
        return json.loads(response.text)
        
    except Exception as e:
        print(f"Weather translation error: {e}")
        return {"error": str(e)}
