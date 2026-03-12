import os
import json
from dotenv import load_dotenv
from datetime import date, timedelta

def run_translation():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path=env_path)
    api_key = os.environ.get('GEMINI_API_KEY')

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)

    # Get today's date for reference
    today = date.today()
    today_name = today.strftime('%A')
    
    system_instruction = f"""
    You are the 'Weather Translator' for the Bee Colony scheduling system.
    Today's reference date is {today.isoformat()} ({today_name}).

    Your job is to parse natural language requests and translate them into a strict JSON array of constraint objects.

    STRICT RULES:
    1. IDENTIFY EMPLOYEES: Extract the name of any employee mentioned.
    2. MAP DATES: Convert relative days (like "tomorrow", "next Wednesday", "this Friday") into absolute ISO date strings (YYYY-MM-DD) based on today's reference date.
    3. CATEGORIZE:
       - Use "block_employee_availability" for sick leave, maternity, or any time off.
       - Use "force_minimum_headcount" for surge demand.
       - Use "require_specific_shift" if someone MUST work a certain time.

    JSON SCHEMA:
    Return a JSON array of objects with these keys:
    - type (string, required): "block_employee_availability", "force_minimum_headcount", or "require_specific_shift"
    - employee (string, required if name mentioned)
    - date (string, required): The absolute ISO date (YYYY-MM-DD)
    - reason (string, required)
    """

    prompt = "Sine is out for 2 weeks because of an accident, and Dona just called in sick today and will be out for the whole week."
    
    print(f"Translating prompt relative to today ({today.isoformat()})...")
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type='application/json'
        ),
        contents=prompt
    )

    constraints = json.loads(response.text)
    
    final_output = {'daily_overrides': constraints}

    with open(os.path.join(os.path.dirname(__file__), 'jsons', 'weather.json'), 'w') as f:
        json.dump(final_output, f, indent=2)

    print('Translation saved to jsons/weather.json')
    print(json.dumps(final_output, indent=2))

if __name__ == "__main__":
    run_translation()
