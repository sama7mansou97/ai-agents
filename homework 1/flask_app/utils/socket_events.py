from flask_socketio import emit
from flask_app import socketio
from flask_app.utils.llm import send_message
import sqlite3
import os

db = None

def execute_sql_write(query):
    """تنفيذ أوامر الكتابة أو الإضافة (INSERT/UPDATE) فعلياً على قاعدة البيانات"""
    try:
        from flask import current_app
        db_path = current_app.db.db_path
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()
        conn.close()
        return True, "Database successfully updated!"
    except Exception as e:
        return False, str(e)

@socketio.on('send_message')
def handle_message(data):
    global db
    if db is None:
        from flask import current_app
        db = current_app.db

    user_message = data.get('message', '').strip()
    if not user_message:
        return

    # جلب بيانات السيرة الذاتية الحالية
    resume_data = db.getResumeData()

    # الخطوة 1: الـ Orchestrator يحدد الخبير المناسب
    orchestrator_prompt = f"""You are the Orchestrator AI in a multi-agent resume system.
Analyze the user's message and choose ONE most appropriate expert from these three:
1. Content Expert — answers questions about the resume content itself.
2. Database Read Expert — turns a question into a SQL query and answers from the database.
3. Database Write Expert — writes and executes SQL statements (like INSERT or UPDATE) to modify the database.

User Message: "{user_message}"

Respond ONLY with the exact name of the expert you chose:
- Content Expert
- Database Read Expert
- Database Write Expert"""

    print(f"\n[Orchestrator] Processing message: '{user_message}'")
    chosen_expert = send_message(user_message, orchestrator_prompt).strip()
    
    # تحديد سلوك الخبير
    if "Write" in chosen_expert:
        expert_name = "Database Write Expert"
        expert_prompt = f"""You are the Database Write Expert. The user wants to modify the resume data: '{user_message}'
Current database schema context:
- institutions (inst_id, type, name, department, address, city, state, zip)
- positions (position_id, inst_id, title, responsibilities, start_date, end_date)
- experiences (experience_id, position_id, name, description, hyperlink, start_date, end_date)
- skills (skill_id, experience_id, name, skill_level)

Your task is to write a valid SQLite INSERT or UPDATE SQL statement targeting ONLY these actual tables and columns. 
IMPORTANT: Output ONLY the raw SQL statement inside a ```sql ... ``` block so it can be executed automatically, followed by a short explanation."""

  
    elif "Read" in chosen_expert:
        expert_name = "Database Read Expert"
        expert_prompt = f"You are the Database Read Expert. Answer this question by formulating a SQL query perspective based on the resume data: {resume_data}"
    else:
        expert_name = "Content Expert"
        expert_prompt = f"You are the Content Expert. Answer this question based on the resume content: {resume_data}"

    print(f"[Orchestrator] -> Selected Expert: [{expert_name}]")

    # الخطوة 2: تشغيل الخبير واستلام النتيجة
    try:
        expert_response = send_message(user_message, expert_prompt)
        
        execution_msg = ""
        # إذا كان الخبير هو Database Write Expert، نبحث عن استعلام SQL ونقوم بتنفيذه فعلياً!
        if expert_name == "Database Write Expert" and "```sql" in expert_response:
            try:
                sql_query = expert_response.split("```sql")[1].split("```")[0].strip()
                success, msg = execute_sql_write(sql_query)
                if success:
                    execution_msg = "\n\n✅ **[Database Status]**: The SQL statement was executed successfully and saved to the database!"
                else:
                    execution_msg = f"\n\n⚠️ **[Database Status Error]**: {msg}"
            except Exception as sql_err:
                execution_msg = f"\n\n⚠️ Could not auto-execute SQL: {sql_err}"

        ai_response = f"**[Orchestrator]** Selected Expert: **{expert_name}**\n\n{expert_response}{execution_msg}"
    except Exception as error:
        print(f"Error: {error}")
        ai_response = f"⚠️ Error processing request: {error}"

    emit('receive_message', {'response': ai_response})