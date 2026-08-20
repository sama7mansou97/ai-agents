import sqlite3
import json
import math
from .embeddings import generate_embedding

class Database:
    def __init__(self, db_path=None):
        if db_path is None:
            # تحديد المسار المطلق لمجلد homework 1/flask_app/database/resume.db
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            db_path = os.path.join(base_dir, "homework 1", "flask_app", "database", "resume.db")
        
        self.db_path = db_path
        self._add_embedding_columns_if_missing()
        self.backfill_embeddings()
        self._seed_hw2_roles()

        
    def query(self, sql, params=()):
        """تنفيذ الاستعلامات مع ضمان إغلاق الاتصال لتجنب قفل قاعدة البيانات"""
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            cursor.execute(sql, params)
            results = []
            if sql.strip().upper().startswith(('SELECT', 'PRAGMA')):
                results = [dict(row) for row in cursor.fetchall()]
            connection.commit()
            return results
        finally:
            connection.close()

    def _add_embedding_columns_if_missing(self):
        """إضافة عمود المتجهات بالجداول عند عدم وجوده"""
        tables = ['institutions', 'positions', 'experiences', 'skills']
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [col[1] for col in cursor.fetchall()]
                if 'embedding' not in cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN embedding TEXT DEFAULT NULL")
            conn.commit()
        finally:
            conn.close()

    def backfill_embeddings(self):
        """تحديث المتجهات الفارغة للجداول"""
        tables_config = {
            'institutions': {'pk': 'inst_id', 'fields': ['name', 'type', 'department']},
            'positions': {'pk': 'position_id', 'fields': ['title', 'responsibilities']},
            'experiences': {'pk': 'experience_id', 'fields': ['name', 'description']},
            'skills': {'pk': 'skill_id', 'fields': ['name']}
        }

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            for table, config in tables_config.items():
                pk_col = config['pk']
                fields = config['fields']

                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()

                for row in rows:
                    row_dict = dict(row)
                    current_emb = row_dict.get('embedding')

                    if not current_emb or current_emb == 'null':
                        text_to_embed = " ".join([str(row_dict[field]) for field in fields if row_dict.get(field)])
                        if text_to_embed.strip():
                            vec = generate_embedding(text_to_embed)
                            if vec:
                                vec_json = json.dumps(vec)
                                cursor.execute(
                                    f"UPDATE {table} SET embedding = ? WHERE {pk_col} = ?",
                                    (vec_json, row_dict[pk_col])
                                )
            conn.commit()
        finally:
            conn.close()

    def _cosine_similarity(self, vec_a, vec_b):
        """حساب تشابه جيب التمام بين متجهين"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = math.sqrt(sum(a * a for a in vec_a))
        mag_b = math.sqrt(sum(b * b for b in vec_b))
        
        if mag_a == 0 or mag_b == 0:
            return 0.0
            
        return dot_product / (mag_a * mag_b)

    def semantic_search(self, table_name, query_text, top_k=3):
        """البحث الدلالي وحساب التشابه"""
        query_vec = generate_embedding(query_text)
        if not query_vec:
            return []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
        finally:
            conn.close()

        scored_results = []
        for row in rows:
            row_dict = dict(row)
            emb_json = row_dict.get('embedding')
            
            similarity = self._cosine_similarity(query_vec, json.loads(emb_json)) if emb_json else 0.0
            scored_results.append({"data": row_dict, "score": similarity})

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]  # <-- التأكد من إرجاع أعلى النتائج

    
    # أضيفي هذه الدالة داخل كلاس Database في ملف database.py

def _seed_hw2_roles(self):
    """دمج الخبير الجديد وتحديث الـ Orchestrator تلقائياً بدون تكرار"""
    conn = sqlite3.connect(self.db_path)
    try:
        cursor = conn.cursor()
        
        # 1. إدراج الخبير الجديد إذا لم يكن موجوداً
        cursor.execute("""
            INSERT OR IGNORE INTO llm_roles (role, domain, specific_instructions, background_context, few_shot_examples)
            VALUES (
                'Database Semantic Search Expert',
                'Database Retrieval',
                'Analyze the query and decide which table to search semantically. Output ONLY in the format ''table_name|search_phrase'' without extra text or SQL.',
                'Tables available: institutions, positions, experiences, skills.',
                'User: ''Find AI skills'' -> Output: ''skills|AI'''
            )
        """)
        
        # 2. تحديث تعليمات Orchestrator ليتعرف على الخبير الجديد
        cursor.execute("""
            UPDATE llm_roles 
            SET specific_instructions = 'Determine whether to route the request to ''Database Semantic Search Expert'', ''Database Write Expert'', ''Database Read Expert'', or ''Content Expert''. If the user asks about semantic concepts, skills, acronyms, or non-exact matches, route to ''Database Semantic Search Expert''.'
            WHERE role = 'Orchestrator'
        """)
        
        conn.commit()
    except Exception as e:
        print(f"Role Seeding Error: {e}")
    finally:
        conn.close()


def __init__(self, db_path="homework 0/flask_app/database/resume.db"):
    self.db_path = db_path
    self._add_embedding_columns_if_missing()
    self.backfill_embeddings()
    self._seed_hw2_roles()  # <-- أضيفي هذا السطر هنا