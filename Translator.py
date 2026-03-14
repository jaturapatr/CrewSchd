"""
Bee Colony - AI Translator Module (3-Shapes Version)
Translates natural language managerial requests into structured JSON 
for both Weather Overrides and Universal Dynamic Rules.
"""

import os
import json
import streamlit as st
from datetime import date
from google import genai
from google.genai import types

@st.cache_data(ttl=3600, show_spinner=False)
def translate_weather_to_json(user_input: str, api_key: str, context_json: str) -> dict:
    """
    Translates natural language requests into structured 'overrides' JSON.
    """
    try:
        client = genai.Client(api_key=api_key)
        today = date.today()
        context = json.loads(context_json)
        
        system_instruction = f"""
        You are the 'Operations Hub' for CrewSchd. 
        TODAY IS: {today.isoformat()} ({today.strftime('%A')})
        
        CONTEXT:
        - Employees: {context.get('employees', 'None')}
        - Branch: {context.get('branch', 'Unknown')}
        - Team: {context.get('team', 'Unknown')}

        YOUR PROTOCOL:
        1. Calculate relative dates (tomorrow, next Monday) based on TODAY.
        2. Identify employees by their unique ID (e.g., EMP001).
        3. Return ONLY a JSON object with an 'overrides' key.

        OVERRIDE SCHEMA:
        {{
          "overrides": [
            {{ "type": "block_employee_availability", "employee": "EMP001", "date": "YYYY-MM-DD", "reason": "Sick" }}
          ]
        }}
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            config=types.GenerateContentConfig(system_instruction=system_instruction, response_mime_type="application/json"),
            contents=user_input
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(ttl=3600, show_spinner=False)
def translate_rule_to_json(user_input: str, api_key: str, current_rules_json: str) -> dict:
    """
    Translates natural language into a 'dynamic_rule' using the 3-Shapes Architecture.
    """
    try:
        client = genai.Client(api_key=api_key)
        
        system_instruction = f"""
        You are the 'Universal Rule Architect'. Your job is to translate managerial policy requests 
        into the '3-Shapes' algebraic format for OR-Tools.

        SHAPE 1: aggregator (Limits & Minimums)
        - Handles: 'Max 40 hours', 'Min 2 staff', 'Exactly 5 days', 'No weekends'.
        - Keys: target_timeframe (daily/weekly/working_days), scope (individual/collective), operator (<=, >=, ==), value (int), penalty (optional int), target_days (optional array of names e.g. ["Saturday", "Sunday"]), target_block (optional time string e.g. "20:00").

        SHAPE 2: rolling_window (Fatigue & Patterns)
        - Handles: 'No 3 nights in a row', 'Max 2 heavy shifts in 3 days'.
        - Keys: window_size (int), limit (int), penalty (optional int).

        SHAPE 3: implication (If-Then Logic)
        - Handles: 'If working late, cannot work early tomorrow'.
        - Keys: if_condition ({{ "block": "20:00" }}), then_enforce ({{ "blocks": ["00:00"], "must_equal": 0, "offset_days": 1 }}).

        INSTRUCTIONS:
        1. Identify which shape fits the request best.
        2. Return ONLY a JSON object representing the new rule.
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            config=types.GenerateContentConfig(system_instruction=system_instruction, response_mime_type="application/json"),
            contents=f"CURRENT RULES: {current_rules_json}\n\nNEW REQUEST: {user_input}"
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}
