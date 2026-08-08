import os
import re
import requests
import sqlite3
from jinja2 import Template

DEFAULT_MODEL = "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MASTER_TEMPLATE = Template("""\
You are a {{ role }}, an expert in {{ domain }}.

{{ specific_instructions }}
{% if background_context %}
Context:
{{ background_context }}
{% endif %}
{% if few_shot_examples %}
Examples:
{{ few_shot_examples }}
{% endif %}
Request: {{ request }}
""", trim_blocks=True, lstrip_blocks=True)


def fill_template(role, domain, specific_instructions, background_context="", few_shot_examples="", request=""):
    return MASTER_TEMPLATE.render(
        role=role,
        domain=domain,
        specific_instructions=specific_instructions,
        background_context=background_context,
        few_shot_examples=few_shot_examples,
        request=request
    )


def send_message(user_message, system_prompt="You are a helpful assistant."):
    api_key = os.getenv('OPENROUTER_API_KEY')

    if not api_key or api_key == 'paste-your-key-here':
        return "⚠️ No API key found. Add your OpenRouter key to the .env file and restart the app."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8080"
    }

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message}
    ]

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json={"model": DEFAULT_MODEL, "messages": messages},
            timeout=25
        )
        result = response.json()

        if 'error' in result:
            return f"⚠️ OpenRouter error: {result['error'].get('message', 'Unknown error')}"

        if 'choices' not in result:
            return f"⚠️ Unexpected response: {result}"

        return result['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ Connection error: {str(e)}"


def clean_code_block(code_str):
    match = re.search(r'```(?:python|sql)?\s*(.*?)\s*```', code_str, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return code_str.strip()


def handle_ai_chat_request(db, role=None, message=""):
    if role is None:
        return send_message(message)

    roles_data = db.getLLMRoles() if hasattr(db, 'getLLMRoles') else {}
    config = {}
    
    if isinstance(roles_data, dict):
        config = roles_data.get(role, {})
    elif isinstance(roles_data, list):
        config = next((r for r in roles_data if r.get('role') == role), {})

    if not config:
        config = {'role': role, 'domain': 'Resume Assistance', 'specific_instructions': ''}

    background_context = config.get('background_context') or ""

    if role == "Content Expert":
        if hasattr(db, 'getResumeText'):
            background_context += "\n" + db.getResumeText()

    elif role == "Database Read Expert":
        background_context += (
            "\n\nDATABASE SCHEMA & INSTRUCTIONS FOR DATABASE READ EXPERT:\n"
            "1. Tables Available:\n"
            "   - `positions` (position_id, title, ...)\n"
            "   - `experiences` (experience_id, position_id, name, description, hyperlink, start_date, end_date)\n"
            "   - `skills` (skill_id, experience_id, name, skill_level)\n"
            "2. Always query from existing tables (`experiences`, `positions`, `skills`). Never reference `employment` or `work_experience`.\n"
            "3. Output ONLY a valid SQLite SELECT query.\n"
            "4. Do NOT include explanations, markdown formatting, or code blocks (like ```sql).\n"
            "5. Output raw SQL text ONLY."
        )

    elif role == "Database Write Expert":
        db_file = getattr(db, 'db_path', 'flask_app/database/resume.db')
        if not os.path.isabs(db_file):
            db_file = os.path.abspath(db_file)
        
        background_context += (
            f"\n\nDATABASE RULES & SCHEMA:\n"
            f"1. Database Absolute Path: r'{db_file}'\n"
            f"2. Table `experiences` (experience_id PK, position_id NOT NULL, name NOT NULL, description NOT NULL, hyperlink, start_date, end_date)\n"
            f"3. Table `skills` (skill_id PK, experience_id, name NOT NULL, skill_level NOT NULL)\n"
            f"4. Rule: ALWAYS fetch a valid `position_id` before inserting into `experiences`!\n"
            f"5. Return ONLY Python code inside ```python ... ``` block. Assign final outcome message string to `outcome`."
        )

    system_prompt = fill_template(
        role=config.get('role', role),
        domain=config.get('domain', ''),
        specific_instructions=config.get('specific_instructions', ''),
        background_context=background_context,
        few_shot_examples=config.get('few_shot_examples') or "",
        request=message
    )

    if role == "Orchestrator":
        plan_text = send_message(system_prompt)
        print(f"\n================ [Orchestrator Plan] ================\n{plan_text}\n=====================================================")

        msg_lower = message.lower()
        if "database write expert" in plan_text.lower() or any(k in msg_lower for k in ['add', 'insert', 'update', 'delete']):
            return handle_ai_chat_request(db, role="Database Write Expert", message=message)
        elif "database read expert" in plan_text.lower() or any(k in msg_lower for k in ['how long', 'does he know', 'what skills', 'how many']):
            return handle_ai_chat_request(db, role="Database Read Expert", message=message)
        else:
            return handle_ai_chat_request(db, role="Content Expert", message=message)

    raw_response = send_message(system_prompt)

    if role == "Database Read Expert":
        sql_query = clean_code_block(raw_response).strip()
        print(f"\n================ [Database Read Expert SQL] ================\n{sql_query}\n============================================================")
        try:
            if hasattr(db, 'execute_read_query'):
                res = db.execute_read_query(sql_query)
                return f"**[Database Read Expert]**\n\nQuery Result:\n{res}"
            elif hasattr(db, 'query'):
                res = db.query(sql_query)
                return f"**[Database Read Expert]**\n\nQuery Result:\n{res}"
        except Exception as e:
            print(f"Read Exception: {e}")
            return f"**[Database Read Expert]**\n\n{raw_response}"

    elif role == "Database Write Expert":
        print(f"\n[EXPERT TRIGGERED]: Database Write Expert\nRaw Code:\n{raw_response}\n")
        cleaned_code = clean_code_block(raw_response)
        try:
            local_scope = {"db": db, "sqlite3": sqlite3, "outcome": ""}
            exec(cleaned_code, {}, local_scope)
            outcome = local_scope.get("outcome", "Database updated successfully.")
            return f"**[Database Write Expert]**\n\n{outcome}"
        except Exception as e:
            return f"**[Database Write Expert]**\n\nExecution error: {e}"

    elif role == "Content Expert":
        return f"**[Content Expert]**\n\n{raw_response}"

    return raw_response
