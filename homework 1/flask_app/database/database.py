import os
import csv
import sqlite3

TABLE_ORDER = [
    'institutions',
    'positions',
    'experiences',
    'skills',
    'llm_roles'
]

class Database:
    def __init__(self, db_path, hw0_dir=None):
        self.db_path = db_path
        self.hw0_dir = hw0_dir

    def getResumeData(self):
        """جلب البيانات وتنسيق القواميس المتداخلة بما يتوافق 100% مع resume.html"""
        inst_rows = self.query("SELECT * FROM institutions")
        pos_rows = self.query("SELECT * FROM positions")
        exp_rows = self.query("SELECT * FROM experiences")
        skills_rows = self.query("SELECT * FROM skills")

        # 1. بناء قاموس المؤسسات {inst_id: inst_dict}
        resume = {}
        for inst in inst_rows:
            inst_dict = dict(inst)
            inst_id = inst_dict.get('inst_id')
            if inst_id is not None:
                inst_dict['positions'] = {}
                resume[inst_id] = inst_dict

        # 2. بناء قاموس الوظائف داخل كل مؤسسة {pos_id: pos_dict}
        for pos in pos_rows:
            pos_dict = dict(pos)
            pos_id = pos_dict.get('position_id')
            inst_id = pos_dict.get('inst_id')
            pos_dict['experiences'] = {}
            
            if inst_id in resume and pos_id is not None:
                resume[inst_id]['positions'][pos_id] = pos_dict

        # 3. بناء قاموس الخبرات داخل كل وظيفة {exp_id: exp_dict}
        for exp in exp_rows:
            exp_dict = dict(exp)
            exp_id = exp_dict.get('experience_id')
            pos_id = exp_dict.get('position_id')
            exp_dict['skills'] = {}

            for inst in resume.values():
                if pos_id in inst['positions'] and exp_id is not None:
                    inst['positions'][pos_id]['experiences'][exp_id] = exp_dict

        # 4. ربط المهارات بالخبرات {skill_id: skill_dict}
        for skill in skills_rows:
            skill_dict = dict(skill)
            skill_id = skill_dict.get('skill_id')
            exp_id = skill_dict.get('experience_id')

            if exp_id is not None and skill_id is not None:
                for inst in resume.values():
                    for pos in inst['positions'].values():
                        if exp_id in pos['experiences']:
                            pos['experiences'][exp_id]['skills'][skill_id] = skill_dict

        # نُرجع قاموس resume مباشرة ليتوافق مع resume.items() في القالب
        return resume

    def createTables(self, purge=False):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        if purge and os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()

        sql_dirs = []
        if self.hw0_dir:
            sql_dirs.append(os.path.join(self.hw0_dir, 'database', 'create_tables'))
        
        hw1_sql_dir = os.path.join(os.path.dirname(__file__), 'create_tables')
        if os.path.exists(hw1_sql_dir):
            sql_dirs.append(hw1_sql_dir)

        for s_dir in sql_dirs:
            if os.path.exists(s_dir):
                for sql_file in sorted(os.listdir(s_dir)):
                    if sql_file.endswith('.sql'):
                        with open(os.path.join(s_dir, sql_file), 'r', encoding='utf-8') as f:
                            cursor.executescript(f.read())

        if self.hw0_dir:
            csv_dir = os.path.join(self.hw0_dir, 'database', 'initial_data')
            if os.path.exists(csv_dir):
                for table in TABLE_ORDER:
                    csv_path = os.path.join(csv_dir, f"{table}.csv")
                    if os.path.exists(csv_path):
                        with open(csv_path, 'r', encoding='utf-8') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                cols = list(row.keys())
                                placeholders = ', '.join(['?'] * len(cols))
                                sql = f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
                                cursor.execute(sql, list(row.values()))

        connection.commit()
        connection.close()

    def query(self, sql, params=()):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()
        cursor.execute(sql, params)
        
        if sql.strip().upper().startswith("SELECT"):
            result = [dict(row) for row in cursor.fetchall()]
        else:
            connection.commit()
            result = cursor.rowcount
            
        connection.close()
        return result

    def getLLMRoles(self):
        try:
            rows = self.query("SELECT * FROM llm_roles")
            return {row['role']: row for row in rows}
        except Exception:
            return {}

    def insertRows(self, table, columns, values):
        value_sql, bound_params = [], []
        for value in values:
            if isinstance(value, str) and value.strip().startswith("(SELECT"):
                value_sql.append(value)
            else:
                value_sql.append("?")
                bound_params.append(value)
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(value_sql)})"
        self.query(sql, tuple(bound_params))