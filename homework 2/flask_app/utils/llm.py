import os
import requests
from flask import session
from dotenv import load_dotenv
from .database import Database

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../../.env'))

MODEL_NAME = "openai/gpt-4o-mini"

class LLMHelper:
    def __init__(self, db=None):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.db = db if db else Database()

    def send_to_openrouter(self, system_prompt: str, user_message: str) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=20)
            res_json = response.json()
            if 'choices' in res_json and len(res_json['choices']) > 0:
                return res_json['choices'][0]['message']['content']
        except Exception as e:
            return f"Request failed: {str(e)}"
        return "Error getting response."
    def execute_semantic_search(self, expert_output: str, original_query: str) -> str:
        """تحليل مخرجات الخبير صيغة (table|search_text) واستدعاء db.semanticSearch()"""
        try:
            parts = expert_output.strip().split('|')
            if len(parts) == 2:
                table_name = parts[0].strip()
                search_phrase = parts[1].strip()
                
                print(f"🔍 [Semantic Search Expert] Searching table: '{table_name}' for query: '{search_phrase}'")
                
                results = self.db.semanticSearch(table_name, search_phrase, top_k=3)
                
                if results:
                    context_str = "\n".join([f"- {res['data']}" for res in results])
                else:
                    context_str = "No semantic matches found."

                system_prompt = (
                    "You are an AI Resume Assistant. "
                    "Answer the user's question accurately using ONLY the provided database context."
                )
                full_user_message = f"Database Context:\n{context_str}\n\nUser Question: {original_query}"
                return self.send_to_openrouter(system_prompt, full_user_message)
        except Exception as e:
            print(f"Error parsing semantic expert output: {e}")

        # في حال حدوث أي خلل في التنسيق، نلجأ للبحث المباشر كخيار احتياطي
        results = self.db.semanticSearch("skills", original_query, top_k=3)
        context_str = "\n".join([f"- {res['data']}" for res in results])
        return self.send_to_openrouter("You are an AI Resume Assistant.", f"Database Context:\n{context_str}\n\nUser Question: {original_query}")
    

    def answer_with_semantic_search(self, user_query: str, table_name: str = "skills") -> str:
        """جلب نتائج البحث الدلالي واستخدامها كـ Context لـ OpenRouter"""
        search_results = self.db.semantic_search(table_name, user_query, top_k=3)
        
        if not search_results or search_results[0].get('score', 0) == 0:
            raw_data = self.db.query(f"SELECT * FROM {table_name}")
            context_str = "\n".join([f"- {row}" for row in raw_data])
        else:
            context_str = "\n".join([f"- {res['data']}" for res in search_results])

        system_prompt = (
            "You are an AI Resume Assistant. "
            "Answer the user's question accurately using ONLY the provided database context."
        )
        full_user_message = f"Database Context:\n{context_str}\n\nUser Question: {user_query}"
        return self.send_to_openrouter(system_prompt, full_user_message)


def handle_ai_chat_request(db, role: str, message: str) -> str:
    llm = LLMHelper(db)

    # 1. إذا كان الموجه هو خبير البحث الدلالي
    if role == "Database Semantic Search Expert":
        # جلب تعليمات الدور من القاعدة
        roles_data = db.query("SELECT * FROM llm_roles WHERE role = 'Database Semantic Search Expert'")
        system_instructions = roles_data[0]['specific_instructions'] if roles_data else "Analyze the query and output ONLY in format 'table_name|search_phrase'."
        
        # أخذ الإجابة المباشرة المكونة من table|search_phrase
        expert_output = llm.send_to_openrouter(system_instructions, message)
        print(f"🎯 [Orchestrator -> Database Semantic Search Expert Output]: {expert_output}")
        
        # تنفيذ البحث الدلالي بـ execute_semantic_search
        return llm.execute_semantic_search(expert_output, message)

    # 2. إذا كان الموجه هو Orchestrator، يقرر من هو الخبير المناسب أولاً
    if role == "Orchestrator":
        orchestrator_instructions = (
            "Determine which expert to route the user's request to.\n"
            "Options:\n"
            "- 'Database Semantic Search Expert': for semantic search, acronyms (like MSU), conceptual skills (like AI), or fuzzy matching.\n"
            "- 'Database Read Expert': for exact SQL matching.\n"
            "- 'Database Write Expert': for data creation/update/deletion.\n"
            "- 'Content Expert': for general questions.\n"
            "Output ONLY the exact role name."
        )
        selected_role = llm.send_to_openrouter(orchestrator_instructions, message).strip()
        print(f"🔀 [Orchestrator Decision]: Routing to -> {selected_role}")

        if "Semantic" in selected_role:
            return handle_ai_chat_request(db, "Database Semantic Search Expert", message)

    # 3. باقي الحالات والخبراء الآخرين
    try:
        all_inst = db.query("SELECT * FROM institutions")
        all_skills = db.query("SELECT * FROM skills")
        context_str = f"Education:\n{all_inst}\n\nSkills:\n{all_skills}"
    except Exception:
        context_str = "No database records found."

    system_prompt = (
        f"You are acting as: {role}.\n"
        f"Use this resume context to answer accurately:\n{context_str}"
    )
    return llm.send_to_openrouter(system_prompt, message)


# ======================================================================
# HUMAN VALIDATION & RISK WORKFLOW
# ======================================================================

DANGEROUS_KEYWORDS = ['delete', 'remove', 'clear', 'drop', 'destroy']

def assess_message_risk(message: str) -> bool:
    """فحص الرسالة للتحقق من أفعال الحذف والتعديل الخطيرة"""
    lowered = message.lower()
    return any(keyword in lowered for keyword in DANGEROUS_KEYWORDS)

def request_human_validation(message: str) -> str:
    """طلب تأكيد المستخدم وتخزين الأمر في الـ session"""
    session['pending_validation'] = message
    return (
        f'This looks like it could delete or modify data: "{message}". '
        f'Are you sure you want to proceed? (yes/no)'
    )

def handle_validation_response(db, response: str) -> str:
    """معالجة استجابة المستخدم لعمليات الحذف بالتمرير المباشر للخبير"""
    original_message = session.get('pending_validation', '')
    normalized = response.strip().lower()

    if normalized in ('yes', 'y'):
        session.pop('pending_validation', None)
        llm = LLMHelper(db)
        
        all_skills = db.query("SELECT * FROM skills")
        system_prompt = (
            "You are acting as: Database Write Expert.\n"
            f"Current Skills Table Context:\n{all_skills}\n"
            "The user confirmed the deletion/update action. Respond to confirm the execution."
        )
        return llm.send_to_openrouter(system_prompt, original_message)

    if normalized in ('no', 'n'):
        session.pop('pending_validation', None)
        return "Okay, I won't do that. The request was cancelled."

    return f'Please answer "yes" or "no" -- do you want me to proceed with: "{original_message}"?'